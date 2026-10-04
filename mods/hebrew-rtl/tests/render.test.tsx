import { expect, test } from 'claude-code/testing'

import { PDI, RLI, RLM } from '../hooks/bidi'

const REPLY = [
  'סיכום הבדיקה:',
  '',
  '- **Root cause:** ה-thermal drift מתחיל בערך שעה אחרי ה-power-up',
  '',
  '```ts',
  'const x = "שלום"',
  '```',
  '',
  'English only paragraph.',
].join('\n')

const props = { text: REPLY, isFirstOfReply: true }
const viewport = { columns: 84, rows: 40 }

test('terminal: Hebrew rows reordered and right-aligned, code and English left to Markdown', async $ => {
  const ui = await $.ui.mount({ plugin: 'hebrew-rtl', surface: 'terminal', component: 'AssistantMessage', props, viewport })
  expect(await ui.find({ type: 'Text', text: ':הקידבה םוכיס' })).toBeDefined()
  // read right to left: "• Root cause: ה-thermal drift מתחיל בערך שעה אחרי ה-power-up"
  expect(await ui.find({ type: 'Text', text: 'power-up-ה ירחא העש ךרעב ליחתמ thermal drift-ה :Root cause •' })).toBeDefined()
  expect(await ui.find({ type: 'Markdown', text: 'const x = "שלום"' })).toBeDefined()
  expect(await ui.find({ type: 'Markdown', text: 'English only paragraph.' })).toBeDefined()
  expect(JSON.stringify(await ui.drawn())).toContain('flex-end')
  await ui.unmount()
})

test('terminal: long Hebrew lines are cut to the width, never re-wrapped by the engine', async $ => {
  const long = Array.from({ length: 30 }, () => 'מילה').join(' ')
  const ui = await $.ui.mount({ plugin: 'hebrew-rtl', surface: 'terminal', component: 'AssistantMessage', props: { text: long, isFirstOfReply: true }, viewport: { columns: 44, rows: 40 } })
  const rows = await ui.findAll({ type: 'Text' })
  expect(rows.length).toBeGreaterThan(3)
  for (const row of rows) expect([...(row.text ?? '')].length).toBeLessThanOrEqual(40)
  await ui.unmount()
})

for (const surface of ['desktop', 'vscode'] as const) {
  test(`${surface}: the engine draws the reply with RTL isolates added`, async ($, on) => {
    let seen = ''
    on('ui.render', { component: 'AssistantMessage' }, ($, e) => {
      seen = e.props.text
      // the element the engine draws a reply with: its validation must accept the marks
      const { Markdown } = $.ui.resolve(e)
      return <Markdown text={e.props.text} />
    })
    const ui = await $.ui.mount({ plugin: 'hebrew-rtl', surface, component: 'AssistantMessage', props, viewport })
    expect(JSON.stringify(await ui.drawn())).toContain(RLI)
    expect(seen).toContain(`- ${RLM}${RLI}**Root cause:** ה-thermal drift מתחיל בערך שעה אחרי ה-power-up${PDI}`)
    expect(seen).toContain('English only paragraph.\n'.trimEnd())
    expect(seen).toContain('const x = "שלום"')
    await ui.unmount()
  })

  test(`${surface}: the person's own prompt is isolated too`, async ($, on) => {
    let seen = ''
    on('ui.render', { component: 'UserMessage' }, ($, e) => {
      seen = e.props.text
      const { Text } = $.ui.resolve(e)
      return <Text>{e.props.text}</Text>
    })
    const ui = await $.ui.mount({
      plugin: 'hebrew-rtl',
      surface,
      component: 'UserMessage',
      props: { text: 'לדוגמה מ VSCODE', origin: { kind: 'composer' }, isExpanded: false },
      viewport,
    })
    expect(JSON.stringify(await ui.drawn())).toContain(RLI)
    expect(seen).toBe(`${RLM}${RLI}לדוגמה מ VSCODE${PDI}`)
    await ui.unmount()
  })
}
