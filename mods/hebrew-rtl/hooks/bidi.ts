// Hebrew bidi helpers: a reduced Unicode Bidi Algorithm (UAX #9) for
// terminals that draw cells left to right with no bidi of their own, and
// direction isolates for surfaces that do bidi (desktop, VS Code webview).
//
// Covered: strong L/R, European numbers with their separators and
// terminators (W4-W7), neutrals (N1-N2), trailing whitespace (L1),
// reordering (L2) and bracket mirroring (L4). Not covered: Arabic numbers,
// explicit embeddings (they are stripped first), bracket pairing (N0).

type BidiClass = 'L' | 'R' | 'EN' | 'ES' | 'CS' | 'ET' | 'WS' | 'ON'

export type Style = { bold?: boolean; code?: boolean }

export type Cluster = { text: string; cls: BidiClass; width: number; style: Style }

export type Segment = { text: string; style: Style }

export type VisualLine = { segments: Segment[]; width: number }

export type Base = 0 | 1

export const BIDI_CONTROLS = /[\u200E\u200F\u202A-\u202E\u2066-\u2069]/g
const HEBREW = /[\u05D0-\u05EA\u05EF-\u05F4\uFB1D-\uFB4F]/

const LATIN = /[A-Za-z\u00C0-\u024F]/

export const RLM = '\u200F'
export const RLI = '\u2067'
export const PDI = '\u2069'

const MIRROR: Record<string, string> = {
  '(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{',
  '<': '>', '>': '<', '\u00AB': '\u00BB', '\u00BB': '\u00AB',
}

export function hasHebrew(text: string): boolean {
  return HEBREW.test(text)
}

function isNonSpacing(cp: number): boolean {
  return (
    (cp >= 0x0591 && cp <= 0x05bd) ||
    cp === 0x05bf ||
    cp === 0x05c1 ||
    cp === 0x05c2 ||
    cp === 0x05c4 ||
    cp === 0x05c5 ||
    cp === 0x05c7 ||
    cp === 0xfb1e ||
    (cp >= 0x0300 && cp <= 0x036f) ||
    (cp >= 0xfe00 && cp <= 0xfe0f) ||
    cp === 0x200d
  )
}

function classify(ch: string): BidiClass {
  const cp = ch.codePointAt(0) ?? 0
  if (cp === 0x05be || cp === 0x05c0 || cp === 0x05c3 || cp === 0x05c6) return 'R'
  if ((cp >= 0x05d0 && cp <= 0x05f4) || (cp >= 0xfb1d && cp <= 0xfb4f)) return 'R'
  if (cp >= 0x30 && cp <= 0x39) return 'EN'
  if (ch === '+' || ch === '-') return 'ES'
  if (ch === ',' || ch === '.' || ch === ':' || ch === '/' || cp === 0xa0) return 'CS'
  if ('#$%°€₪£¢¥‰'.includes(ch)) return 'ET'
  if (ch === ' ' || ch === '\t') return 'WS'
  if (/[\p{L}\p{N}]/u.test(ch)) return 'L'
  return 'ON'
}

function cellWidth(cp: number): number {
  if (
    (cp >= 0x1100 && cp <= 0x115f) ||
    (cp >= 0x2e80 && cp <= 0xa4cf) ||
    (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) ||
    (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0x1f300 && cp <= 0x1faff)
  ) {
    return 2
  }
  return 1
}

/** Splits text into display clusters: a base character plus its combining marks. */
export function toClusters(text: string, styles?: Style[]): Cluster[] {
  const out: Cluster[] = []
  let i = 0
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    const style = styles?.[i] ?? {}
    i += ch.length
    const last = out[out.length - 1]
    if (isNonSpacing(cp) && last) {
      last.text += ch
      continue
    }
    out.push({ text: ch, cls: isNonSpacing(cp) ? 'ON' : classify(ch), width: cellWidth(cp), style })
  }
  return out
}

/**
 * Paragraph direction, by words rather than UAX #9's first strong character:
 * a Hebrew sentence full of English terms ("Root cause: ה-thermal drift
 * מתחיל...") is still Hebrew. RTL when it holds two Hebrew words or more, or
 * at least as many Hebrew words as Latin ones.
 */
export function detectBase(text: string): Base {
  const words = text.split(/\s+/).filter(w => w !== '')
  const heb = words.filter(w => HEBREW.test(w)).length
  if (heb === 0) return 0
  const lat = words.filter(w => !HEBREW.test(w) && LATIN.test(w)).length
  return heb >= 2 || heb >= lat ? 1 : 0
}

function strongDir(cls: BidiClass): 'L' | 'R' | null {
  if (cls === 'L') return 'L'
  if (cls === 'R' || cls === 'EN') return 'R'
  return null
}

/** Resolves an embedding level per cluster for one paragraph. */
export function resolveLevels(clusters: Cluster[], base: Base): number[] {
  const t: BidiClass[] = clusters.map(c => c.cls)
  const n = t.length

  // W4: a single separator between two numbers joins them.
  for (let i = 1; i < n - 1; i++) {
    if ((t[i] === 'ES' || t[i] === 'CS') && t[i - 1] === 'EN' && t[i + 1] === 'EN') t[i] = 'EN'
  }
  // W5: terminators next to a number become part of it.
  for (let i = 0; i < n; i++) {
    if (t[i] !== 'ET') continue
    let j = i
    while (j < n && t[j] === 'ET') j++
    if ((i > 0 && t[i - 1] === 'EN') || (j < n && t[j] === 'EN')) {
      for (let k = i; k < j; k++) t[k] = 'EN'
    }
    i = j - 1
  }
  // W6: leftover separators and terminators are neutral.
  for (let i = 0; i < n; i++) {
    if (t[i] === 'ES' || t[i] === 'CS' || t[i] === 'ET') t[i] = 'ON'
  }
  // W7: a number after Latin text (or at the start of an LTR paragraph) is L.
  let prevStrong: 'L' | 'R' = base === 1 ? 'R' : 'L'
  for (let i = 0; i < n; i++) {
    if (t[i] === 'L' || t[i] === 'R') prevStrong = t[i] as 'L' | 'R'
    else if (t[i] === 'EN' && prevStrong === 'L') t[i] = 'L'
  }
  // N1/N2: neutrals take their neighbours' direction when both agree.
  const baseDir = base === 1 ? 'R' : 'L'
  for (let i = 0; i < n; i++) {
    if (t[i] !== 'WS' && t[i] !== 'ON') continue
    let j = i
    while (j < n && (t[j] === 'WS' || t[j] === 'ON')) j++
    const left = i > 0 ? strongDir(t[i - 1] as BidiClass) ?? baseDir : baseDir
    const right = j < n ? strongDir(t[j] as BidiClass) ?? baseDir : baseDir
    const dir = left === right ? left : baseDir
    for (let k = i; k < j; k++) t[k] = dir
    i = j - 1
  }
  // I1/I2
  return t.map(cls => {
    if (base === 0) return cls === 'R' ? 1 : cls === 'EN' ? 2 : 0
    return cls === 'R' ? 1 : 2
  })
}

/** Greedy word wrap in logical order: [start, end) cluster ranges per line. */
export function wrapRanges(clusters: Cluster[], width: number): Array<[number, number]> {
  const lines: Array<[number, number]> = []
  const max = Math.max(1, width)
  let start = 0
  while (start < clusters.length) {
    let used = 0
    let end = start
    let lastBreak = -1
    while (end < clusters.length) {
      const c = clusters[end]!
      if (used + c.width > max) break
      used += c.width
      if (c.cls === 'WS') lastBreak = end
      end++
    }
    if (end < clusters.length && lastBreak > start) end = lastBreak + 1
    if (end === start) end = start + 1
    let trimmed = end
    while (trimmed > start && clusters[trimmed - 1]!.cls === 'WS') trimmed--
    lines.push([start, trimmed])
    start = end
    while (start < clusters.length && clusters[start]!.cls === 'WS') start++
  }
  return lines
}

/** L1, L2 and L4 for one line: the clusters in the order the cells show them. */
export function reorderLine(clusters: Cluster[], levels: number[], base: Base): Cluster[] {
  const lv = levels.slice()
  for (let i = lv.length - 1; i >= 0 && clusters[i]!.cls === 'WS'; i--) lv[i] = base
  const order = clusters.map((_, i) => i)
  const highest = Math.max(0, ...lv)
  const lowestOdd = Math.min(...lv.filter(l => l % 2 === 1), highest + 1)
  for (let level = highest; level >= lowestOdd; level--) {
    let i = 0
    while (i < order.length) {
      if (lv[order[i]!]! < level) {
        i++
        continue
      }
      let j = i
      while (j < order.length && lv[order[j]!]! >= level) j++
      const run = order.slice(i, j).reverse()
      order.splice(i, j - i, ...run)
      i = j
    }
  }
  return order.map(idx => {
    const c = clusters[idx]!
    const mirrored = lv[idx]! % 2 === 1 ? MIRROR[c.text] : undefined
    return mirrored ? { ...c, text: mirrored } : c
  })
}

function toSegments(clusters: Cluster[]): Segment[] {
  const out: Segment[] = []
  for (const c of clusters) {
    const last = out[out.length - 1]
    if (last && last.style.bold === c.style.bold && last.style.code === c.style.code) {
      last.text += c.text
    } else {
      out.push({ text: c.text, style: c.style })
    }
  }
  return out
}

/** Wraps a paragraph to `width` cells and reorders each line for a non-bidi terminal. */
export function visualLines(text: string, width: number, base: Base, styles?: Style[]): VisualLine[] {
  const clusters = toClusters(text, styles)
  const levels = resolveLevels(clusters, base)
  return wrapRanges(clusters, width).map(([s, e]) => {
    const line = reorderLine(clusters.slice(s, e), levels.slice(s, e), base)
    return { segments: toSegments(line), width: line.reduce((w, c) => w + c.width, 0) }
  })
}

/** One line, no wrapping, as plain text in visual order. */
export function visualText(text: string, base: Base = detectBase(text)): string {
  const clusters = toClusters(text)
  return reorderLine(clusters, resolveLevels(clusters, base), base)
    .map(c => c.text)
    .join('')
}

/**
 * Inline markdown to plain text plus a style per UTF-16 unit:
 * `code`, **bold**, __bold__, [label](url).
 */
export function parseInline(src: string): { text: string; styles: Style[] } {
  let text = ''
  const styles: Style[] = []
  const push = (s: string, style: Style) => {
    text += s
    for (let k = 0; k < s.length; k++) styles.push(style)
  }
  let bold = false
  let i = 0
  while (i < src.length) {
    if (src[i] === '`') {
      const close = src.indexOf('`', i + 1)
      if (close > i) {
        push(src.slice(i + 1, close), { bold, code: true })
        i = close + 1
        continue
      }
    }
    if (src.startsWith('**', i) || src.startsWith('__', i)) {
      bold = !bold
      i += 2
      continue
    }
    if (src[i] === '[') {
      const m = /^\[([^\]]+)\]\(([^)\s]+)\)/.exec(src.slice(i))
      if (m) {
        push(m[1]!, { bold })
        i += m[0].length
        continue
      }
    }
    push(src[i]!, { bold })
    i++
  }
  return { text, styles }
}

const FENCE = /^\s*(```|~~~)/
const MD_PREFIX = /^(\s*(?:[-*+]|\d+[.)])\s+|\s*#{1,6}\s+|\s*>\s?)?/
const DIR_TAG_OPEN = /<(?:div|p|span|bdi|bdo|section)\b[^>]*\bdir\s*=\s*["']?(?:rtl|ltr|auto)["']?[^>]*>/gi
const DIR_TAG_CLOSE = /<\/(?:div|p|span|bdi|bdo|section)>/gi

/** Applies `fn` to every line outside fenced code blocks. */
export function mapProseLines(text: string, fn: (line: string) => string): string {
  let inFence = false
  return text
    .split('\n')
    .map(line => {
      if (FENCE.test(line)) {
        inFence = !inFence
        return line
      }
      return inFence ? line : fn(line)
    })
    .join('\n')
}

/**
 * Display hygiene, outside code: drops bidi control characters and
 * direction-only HTML wrappers, and turns em dashes into hyphens.
 */
export function sanitize(text: string): string {
  const hadDirTags = DIR_TAG_OPEN.test(text)
  DIR_TAG_OPEN.lastIndex = 0
  return mapProseLines(text, line => {
    let out = line.replace(BIDI_CONTROLS, '').replace(/\u2014/g, '-')
    if (hadDirTags) out = out.replace(DIR_TAG_OPEN, '').replace(DIR_TAG_CLOSE, '')
    return out
  })
}

/**
 * For surfaces that do bidi: each Hebrew-majority line gets RLM (so a
 * dir=auto container takes it as RTL) and an RTL isolate after its markdown
 * marker (so mixed Hebrew/English inside keeps its order in an LTR container).
 * Table rows isolate per cell.
 */
export function isolateHebrew(text: string): string {
  return mapProseLines(text, line => {
    if (!hasHebrew(line)) return line
    if (/^\s*\|/.test(line)) {
      return line
        .split('|')
        .map(cell => (hasHebrew(cell) && detectBase(cell) === 1 ? cell.replace(/^(\s*)(.*?)(\s*)$/, `$1${RLI}$2${PDI}$3`) : cell))
        .join('|')
    }
    if (detectBase(line) !== 1) return line
    const prefix = MD_PREFIX.exec(line)?.[0] ?? ''
    const body = line.slice(prefix.length)
    const trail = /\s*$/.exec(body)?.[0] ?? ''
    return `${prefix}${RLM}${RLI}${body.slice(0, body.length - trail.length)}${PDI}${trail}`
  })
}

/** For terminals: each table cell with Hebrew in visual order; widths unchanged. */
export function visualTableRow(line: string): string {
  return line
    .split('|')
    .map(cell => (hasHebrew(cell) ? cell.replace(/^(\s*)(.*?)(\s*)$/, (_m, a: string, b: string, c: string) => a + visualText(b) + c) : cell))
    .join('|')
}
