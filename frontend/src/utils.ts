import type { Turn } from './types'

export function evidenceSegments(text: string, spans: { start: number; end: number }[]) {
  const chars = Array.from(text)
  const highlighted = new Set<number>()
  for (const s of spans) for (let i = s.start; i < s.end; i++) highlighted.add(i)
  const segments: { text: string; highlight: boolean }[] = []
  chars.forEach((char, i) => {
    const highlight = highlighted.has(i)
    const last = segments.at(-1)
    if (last && last.highlight === highlight) last.text += char
    else segments.push({ text: char, highlight })
  })
  return segments
}

// Like evidenceSegments, but keeps which tactics cover each run so highlights can be colour-coded.
// Spans without a tactic (refusal evidence) are tagged 'refusal'.
export type TacticSegment = { text: string; tactics: string[] }
export function tacticSegments(text: string, spans: { start: number; end: number; tactic?: string }[]): TacticSegment[] {
  const chars = Array.from(text)
  const marks: string[][] = chars.map(() => [])
  for (const s of spans) for (let i = Math.max(0, s.start); i < Math.min(chars.length, s.end); i++) {
    const tag = s.tactic ?? 'refusal'
    if (!marks[i].includes(tag)) marks[i].push(tag)
  }
  const segments: TacticSegment[] = []
  chars.forEach((char, i) => {
    const last = segments.at(-1)
    if (last && last.tactics.join('|') === marks[i].join('|')) last.text += char
    else segments.push({ text: char, tactics: [...marks[i]] })
  })
  return segments
}

export function parsePasted(raw: string): Turn[] {
  let turns: Turn[]
  if (raw.trim().startsWith('[') || raw.trim().startsWith('{')) {
    const parsed = JSON.parse(raw)
    turns = Array.isArray(parsed) ? parsed : parsed.turns
  } else {
    turns = []
    for (const line of raw.split(/\r?\n/)) {
      const match = /^(user|assistant):\s?(.*)$/i.exec(line)
      if (match) turns.push({ speaker: match[1].toLowerCase() as Turn['speaker'], text: match[2] })
      else if (turns.length) turns[turns.length - 1].text += '\n' + line
      else if (line.trim()) throw new Error('Start each message with User: or Assistant:, or paste JSON.')
    }
  }
  if (!Array.isArray(turns) || !turns.length || turns.length > 80 || turns.some(t => !['user', 'assistant'].includes(t.speaker) || typeof t.text !== 'string' || !t.text.trim())) throw new Error('Use 1–80 nonblank user/assistant messages.')
  return turns.map(({ speaker, text }) => ({ speaker, text }))
}

export function providerNeutralText(text: string): string {
  return text.replace(/GEMINI_API_KEY/g, 'detector credentials').replace(/gemini-[\w.-]+/gi, 'configured detector').replace(/Google Gemini/gi, 'the detection service').replace(/Gemini/g, 'Detector').replace(/gemini/g, 'detector')
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(providerNeutralText(typeof data.detail === 'string' ? data.detail : typeof data.detail?.message === 'string' ? data.detail.message : Array.isArray(data.detail) ? data.detail.map((e: { msg: string }) => e.msg).join('; ') : 'The backend could not complete this request.'))
  }
  return response.json()
}

export function download(value: string, name: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([value], { type }))
  const a = document.createElement('a'); a.href = url; a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
