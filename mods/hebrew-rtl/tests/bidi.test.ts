import { describe, expect, test } from 'claude-code/testing'

import { detectBase, isolateHebrew, PDI, RLI, RLM, sanitize, visualLines, visualText } from '../hooks/bidi'

const join = (text: string, width: number) =>
  visualLines(text, width, detectBase(text)).map(l => l.segments.map(s => s.text).join(''))

describe('direction', () => {
  test('a Hebrew sentence full of English terms is RTL', async () => {
    expect(detectBase('Root cause: ה-thermal drift מתחיל בערך שעה אחרי ה-power-up')).toBe(1)
    expect(detectBase('לדוגמה מ VSCODE')).toBe(1)
  })
  test('English with one Hebrew word stays LTR, pure English is LTR', async () => {
    expect(detectBase('Run the build, then send it to the team, תודה')).toBe(0)
    expect(detectBase('plain English line')).toBe(0)
  })
})

describe('visual order for terminals', () => {
  test('Hebrew letters reversed, Latin and numbers kept, period at the left', async () => {
    expect(visualText('שלום עולם world 123.')).toBe('.world 123 םלוע םולש')
  })
  test('numbers with separators stay one LTR run', async () => {
    expect(visualText('גרסה 2.1 עכשיו')).toBe('וישכע 2.1 הסרג')
  })
  test('brackets are mirrored inside RTL text', async () => {
    expect(visualText('שלום (בדיקה)')).toBe('(הקידב) םולש')
  })
  test('the VS Code example reads right to left', async () => {
    expect(visualText('לדוגמה מ VSCODE')).toBe('VSCODE מ המגודל')
  })
  test('pure English is untouched', async () => {
    expect(visualText('hello (world) 1.5')).toBe('hello (world) 1.5')
  })
  test('wrap happens before reorder: the first row holds the start of the sentence', async () => {
    const rows = join('אחת שתיים שלוש ארבע', 10)
    expect(rows).toEqual(['םייתש תחא', 'עברא שולש'])
  })
  test('niqqud stays on its letter', async () => {
    // shin + shin dot + qamats is one cell: it moves as a unit and keeps its marks after the letter
    expect(visualText('\u05E9\u05C1\u05B8\u05DC\u05D5\u05B9\u05DD')).toBe('\u05DD\u05D5\u05B9\u05DC\u05E9\u05C1\u05B8')
  })
})

describe('rich surfaces', () => {
  test('a Hebrew bullet is isolated after its marker, markdown intact', async () => {
    expect(isolateHebrew('- **Root cause:** ה-thermal drift מתחיל')).toBe(`- ${RLM}${RLI}**Root cause:** ה-thermal drift מתחיל${PDI}`)
  })
  test('code fences and English lines are untouched', async () => {
    const src = 'plain line\n```\nconst x = "שלום עולם"\n```'
    expect(isolateHebrew(src)).toBe(src)
  })
  test('sanitize drops direction marks, dir wrappers and em dashes outside code', async () => {
    expect(sanitize('<div dir="rtl">‏שלום — עולם</div>')).toBe('שלום - עולם')
    expect(sanitize('```\na — b\n```')).toBe('```\na — b\n```')
  })
})
