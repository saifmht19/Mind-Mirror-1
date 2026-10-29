import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import type { Analysis, Tactic } from './types'
import { riskColor, tacticInfo, tacticOrder } from './tactics'

// Live analysis instruments shared by the single and side-by-side simulators.
export type TimelinePoint = Analysis['computed']['timeline'][number]

export function Pill({ state, children }: { state: 'ok' | 'bad' | 'wait'; children: ReactNode }) { return <span className={`status-pill ${state}`}><i />{children}</span> }

export function PressureDots({ level }: { level: number }) {
  return <span className={`pressure-dots pressure-${level}`} title={`Predicted pressure ${level}/3`}>{[1, 2, 3].map(n => <i key={n} className={n <= level ? 'on' : ''} />)}<b>Pressure {level}/3</b></span>
}

function useCountUp(target: number | null, duration = 750) {
  const [value, setValue] = useState(target ?? 0)
  const from = useRef(target ?? 0)
  useEffect(() => {
    const end = target ?? 0
    const reduced = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (typeof requestAnimationFrame !== 'function' || reduced) { setValue(end); from.current = end; return }
    const start = performance.now(), origin = from.current
    let frame = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration)
      setValue(origin + (end - origin) * (1 - Math.pow(1 - p, 3)))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); from.current = end }
  }, [target, duration])
  return Math.round(value)
}

export function RiskGauge({ score, delta }: { score: number | null; delta: number | null }) {
  const shown = useCountUp(score)
  const r = 50, circumference = 2 * Math.PI * r, arc = circumference * 0.75
  return <div className="risk-gauge" style={{ '--risk': score === null ? '#3a4a5c' : riskColor(shown) } as CSSProperties} role="img" aria-label={score === null ? 'Risk not yet computed' : `Peak risk ${score} out of 100`}>
    <svg viewBox="0 0 120 120" aria-hidden="true"><circle className="gauge-track" cx="60" cy="60" r={r} strokeDasharray={`${arc} ${circumference}`} /><circle className="gauge-value" cx="60" cy="60" r={r} strokeDasharray={`${score === null ? 0 : arc * shown / 100} ${circumference}`} /></svg>
    <div className="gauge-label"><strong>{score === null ? '—' : shown}</strong><span>of 100</span></div>
    {delta !== null && delta !== 0 && <em className={`gauge-delta ${delta > 0 ? 'up' : 'down'}`}>{delta > 0 ? '▲' : '▼'} {Math.abs(delta)}</em>}
  </div>
}

export function RiskTimeline({ points, onSelect }: { points: TimelinePoint[]; onSelect: (turnIndex: number) => void }) {
  if (!points.length) return <div className="risk-timeline empty">{[18, 28, 22, 36, 30, 44].map((h, i) => <span key={i} className="ghost-bar" style={{ height: `${h}%` }} />)}</div>
  return <div className="risk-timeline">{points.map(p => {
    const risk = Math.round(p.risk * 100)
    return <button key={p.turn_index} className="risk-bar" aria-label={`Turn ${p.turn_index + 1}: risk ${risk}, pressure ${p.pressure} of 3`} title={`Turn ${p.turn_index + 1} · risk ${risk} · pressure ${p.pressure}/3${p.refusal_before ? ' · after a refusal' : ''}`} onClick={() => onSelect(p.turn_index)} style={{ '--c': riskColor(risk) } as CSSProperties}>
      <span className="bar-value">{risk}</span>
      <span className="bar-track"><i style={{ height: `${Math.max(4, risk)}%` }} /></span>
      <span className="bar-turn">T{p.turn_index + 1}{p.refusal_before && <b title="After a refusal" />}</span>
    </button>
  })}</div>
}

export function TacticMeters({ counts }: { counts: Record<Tactic, number> }) {
  const max = Math.max(1, ...Object.values(counts))
  return <ul className="tactic-meters">{tacticOrder.map(t => <li key={t} className={counts[t] ? 'lit' : ''} style={{ '--c': tacticInfo[t].color } as CSSProperties} title={tacticInfo[t].description}>
    <span>{tacticInfo[t].label}</span><div><i style={{ width: `${counts[t] / max * 100}%` }} /></div><b>{counts[t] ? `${counts[t]}×` : '—'}</b>
  </li>)}</ul>
}

// Everything the instruments show, restricted to the first `covered` turns (for replays and partial coverage).
export function summarize(result: Analysis | undefined, covered: number) {
  const points: TimelinePoint[] = result?.computed.timeline.filter(t => t.turn_index < covered) ?? []
  const peak = (ps: TimelinePoint[]) => ps.length ? Math.round(Math.max(...ps.map(p => p.risk)) * 100) : null
  const score = result && covered > 0 ? peak(points) ?? 0 : null
  const previous = points.length > 1 ? peak(points.slice(0, -1)) : null
  const predictions = result?.prediction.turns.filter(t => t.turn_index < covered) ?? []
  const counts = Object.fromEntries(tacticOrder.map(t => [t, predictions.filter(p => p.tactics.includes(t)).length])) as Record<Tactic, number>
  return {
    points, score, counts, predictions,
    delta: score !== null && previous !== null ? score - previous : null,
    tactics: tacticOrder.filter(t => counts[t] > 0),
    escalating: points.some(p => p.pressure >= 2) && (result?.computed.escalating ?? false),
  }
}
