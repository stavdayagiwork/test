import type { Register } from 'claude-code'

import {
  detectBase,
  hasHebrew,
  isolateHebrew,
  parseInline,
  sanitize,
  visualLines,
  visualTableRow,
} from './bidi'
import type { Segment, Style, VisualLine } from './bidi'

const RULES = `Hebrew output rules (the person reads Hebrew in terminals and apps with weak right-to-left support):
- Plain text and markdown only: no HTML, no dir attributes, no Unicode direction marks (LRM, RLM, embeddings, isolates).
- Start each Hebrew line, heading and list item with a Hebrew word, not an English word, a number or a symbol.
- Put English identifiers, paths, commands and code in backticks, and keep them few and short inside Hebrew sentences.
- Do not end a Hebrew sentence with an English word, a number or a closing parenthesis; rephrase so it ends in Hebrew.
- Do not wrap English in parentheses inside a Hebrew sentence; use a separate clause instead.
- Use "-" (hyphen), never an em dash.`

// Cells the transcript's bullet and margins take from the viewport.
const GUTTER = 4

type Item =
  | { type: 'raw'; lines: string[] }
  | { type: 'blank' }
  | { type: 'para'; text: string; marker: string; indent: number; heading: boolean; everyLine: boolean }

type ParaDraft = { lines: string[]; marker: string; indent: number; heading: boolean; everyLine: boolean; source: string }

const HEADING = /^\s*#{1,6}\s+(.*)$/
const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/
const QUOTE = /^\s*>\s?(.*)$/
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/
const FENCE = /^\s*(```|~~~)/
const TABLE = /^\s*\|/

/** Splits a reply into markdown the engine draws and Hebrew paragraphs the mod draws. */
export function toItems(text: string): Item[] {
  const items: Item[] = []
  let raw: string[] = []
  let para: ParaDraft | null = null

  const flushRaw = () => {
    if (raw.length > 0) items.push({ type: 'raw', lines: raw })
    raw = []
  }
  const flushPara = () => {
    if (!para) return
    const joined = para.lines.join(' ')
    if (hasHebrew(joined)) {
      flushRaw()
      items.push({ type: 'para', text: joined, marker: para.marker, indent: para.indent, heading: para.heading, everyLine: para.everyLine })
    } else {
      const source = para.source
      raw.push(...para.lines.map((l, i) => (i === 0 ? source : l)))
    }
    para = null
  }

  let inFence = false
  for (const line of text.split('\n')) {
    if (inFence || FENCE.test(line)) {
      flushPara()
      if (FENCE.test(line)) inFence = !inFence
      raw.push(line)
      continue
    }
    if (line.trim() === '') {
      flushPara()
      flushRaw()
      items.push({ type: 'blank' })
      continue
    }
    if (TABLE.test(line)) {
      flushPara()
      raw.push(visualTableRow(line))
      continue
    }
    if (RULE.test(line)) {
      flushPara()
      raw.push(line)
      continue
    }
    const heading = HEADING.exec(line)
    const list = LIST.exec(line)
    const quote = QUOTE.exec(line)
    if (heading) {
      flushPara()
      para = { lines: [heading[1]!], marker: '', indent: 0, heading: true, everyLine: false, source: line }
      flushPara()
    } else if (list) {
      flushPara()
      const marker = /\d/.test(list[2]!) ? list[2]! : '\u2022'
      para = { lines: [list[3]!], marker, indent: list[1]!.length, heading: false, everyLine: false, source: line }
    } else if (quote) {
      flushPara()
      para = { lines: [quote[1]!], marker: '\u2502', indent: 0, heading: false, everyLine: true, source: line }
    } else if (para && !para.heading) {
      para.lines.push(line.trim())
    } else {
      flushPara()
      para = { lines: [line.trim()], marker: '', indent: 0, heading: false, everyLine: false, source: line }
    }
  }
  flushPara()
  flushRaw()
  return items
}

/** A paragraph as rows of segments in visual order, right-aligned when RTL. */
export function layoutPara(item: Extract<Item, { type: 'para' }>, width: number): { rtl: boolean; rows: Segment[][] } {
  const { text, styles } = parseInline(item.text)
  const base = detectBase(text)
  const markerW = item.marker ? item.marker.length + 1 : 0
  const lineStyles: Style[] = item.heading ? styles.map(s => ({ ...s, bold: true })) : styles
  const lines: VisualLine[] = visualLines(text, width - item.indent - markerW, base, lineStyles)
  const rows = lines.map((line, i) => {
    const showMarker = item.marker !== '' && (i === 0 || item.everyLine)
    const gap = showMarker ? ' ' : ''
    const pad = ' '.repeat(showMarker ? 0 : markerW)
    const indent = ' '.repeat(item.indent)
    const marker: Segment = { text: showMarker ? item.marker : '', style: {} }
    return base === 1
      ? [...line.segments, { text: gap + pad, style: {} }, marker, { text: indent, style: {} }]
      : [{ text: indent, style: {} }, marker, { text: gap + pad, style: {} }, ...line.segments]
  })
  return { rtl: base === 1, rows: rows.map(r => r.filter(s => s.text !== '')) }
}

export const register: Register = (on, options) => {
  const terminalOn = options.terminalMode !== 'off'
  const richOn = options.richMode !== 'off'

  on('prompt.compose', async ($, e, next) => {
    const result = await next(e)
    if (options.promptRules === false) return result
    return { sections: [...result.sections, { id: 'hebrew-rtl:rules', text: RULES, scope: 'session' as const }] }
  })

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    const clean = sanitize(e.props.text)
    if (!hasHebrew(clean)) {
      return clean === e.props.text ? next(e) : next({ ...e, props: { ...e.props, text: clean } })
    }
    if (e.surface !== 'terminal') {
      return next({ ...e, props: { ...e.props, text: richOn ? isolateHebrew(clean) : clean } })
    }
    if (!terminalOn) return next({ ...e, props: { ...e.props, text: clean } })

    const { Box, Text, Markdown } = $.ui.resolve(e)
    const width = Math.max(20, (e.viewport?.columns ?? 80) - GUTTER)
    const children = toItems(clean).map(item => {
      if (item.type === 'blank') return <Text> </Text>
      if (item.type === 'raw') return <Markdown text={item.lines.join('\n')} />
      const { rtl, rows } = layoutPara(item, width)
      return (
        <Box flexDirection="column">
          {rows.map(row => (
            <Box justifyContent={rtl ? 'flex-end' : 'flex-start'}>
              <Text wrap="truncate-end">
                {row.map(s =>
                  s.style.code ? (
                    <Text color="cyan" bold={s.style.bold}>{s.text}</Text>
                  ) : s.style.bold ? (
                    <Text bold>{s.text}</Text>
                  ) : (
                    s.text
                  ),
                )}
              </Text>
            </Box>
          ))}
        </Box>
      )
    })
    return <Box flexDirection="column">{children}</Box>
  })

  on('ui.render', { component: 'UserMessage' }, async ($, e, next) => {
    const text = e.props.text
    if (!hasHebrew(text)) return next(e)
    if (e.surface !== 'terminal') {
      return richOn ? next({ ...e, props: { ...e.props, text: isolateHebrew(text.replace(/[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g, '')) } }) : next(e)
    }
    if (!terminalOn) return next(e)

    // The prompt row keeps the engine's own frame; its body is pre-wrapped
    // to the width so the engine has nothing left to wrap.
    const width = Math.max(20, (e.viewport?.columns ?? 80) - GUTTER - 2)
    const out = text.split('\n').flatMap(line => {
      if (!hasHebrew(line)) return [line]
      const base = detectBase(line)
      return visualLines(line, width, base).map(v => {
        const body = v.segments.map(s => s.text).join('')
        return base === 1 ? ' '.repeat(Math.max(0, width - v.width)) + body : body
      })
    })
    return next({ ...e, props: { ...e.props, text: out.join('\n') } })
  })
}
