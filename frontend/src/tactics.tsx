import type { CSSProperties } from 'react'
import type { Tactic } from './types'
import { tacticSegments } from './utils'

export const tacticInfo: Record<Tactic, { label: string; color: string; description: string }> = {
  'guilt-tripping': { label: 'Guilt-tripping', color: '#f2ad78', description: 'Uses blame, obligation or emotional debt to influence a decision.' },
  'false-urgency': { label: 'False urgency', color: '#edcd76', description: 'Invents or exaggerates deadlines or scarcity to rush a choice.' },
  flattery: { label: 'Flattery', color: '#b49bfa', description: 'Uses disproportionate praise to lower resistance.' },
  'pressure-after-refusal': { label: 'Pressure after refusal', color: '#f18096', description: 'Continues a manipulative pitch after a relevant, explicit user refusal.' },
  'fear-appeal': { label: 'Fear appeal', color: '#eb927d', description: 'Exaggerates negative consequences to provoke anxiety.' },
  'dismissing-choice': { label: 'Dismissing choice', color: '#7bc9dd', description: 'Treats the user’s decision as wrong, irrelevant or not theirs to make.' },
}
export const tacticOrder = Object.keys(tacticInfo) as Tactic[]
const refusalColor = '#9fb4c8'

export function riskColor(score: number) { return score < 30 ? '#86dfbf' : score < 60 ? '#e9c47a' : '#f08aa0' }

export function Badge({ tactic }: { tactic: Tactic }) {
  const { color, label } = tacticInfo[tactic]
  return <span className="tactic-badge" style={{ color, borderColor: `${color}40`, background: `${color}0d` }}>{label}</span>
}

// Evidence highlights coloured by tactic; hover or focus shows which tactic(s) the span supports.
export function TacticText({ text, spans }: { text: string; spans: { start: number; end: number; tactic?: Tactic }[] }) {
  return <>{tacticSegments(text, spans).map((s, i) => {
    if (!s.tactics.length) return <span key={i}>{s.text}</span>
    const known = s.tactics.filter((t): t is Tactic => t in tacticInfo)
    const color = known.length ? tacticInfo[known[0]].color : refusalColor
    const label = s.tactics.map(t => t in tacticInfo ? tacticInfo[t as Tactic].label : 'Explicit refusal').join(' + ')
    return <mark key={i} tabIndex={0} className={`tactic-mark ${known.length ? '' : 'refusal'}`} data-label={label} aria-label={`${s.text} (${label})`} style={{ '--mark': color } as CSSProperties}>{s.text}</mark>
  })}</>
}
