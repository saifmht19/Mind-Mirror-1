import { useEffect, useState } from 'react'
import { Bot, FlaskConical, Layers, LoaderCircle, MessageSquare, User } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Tactic, Turn } from './types'
import { api } from './utils'
import { Badge } from './tactics'

type View = { tactics: Tactic[]; escalating: boolean; risk_score: number; timeline: { turn_index: number; pressure: number; risk: number }[]; turn_tactics: Record<string, Tactic[]>; first_warning: number | null } | { error: string }
type Item = { id: string; domain: string; kind: string; manipulative: boolean; intended: Tactic[]; turns: Turn[]; single_turn: View; multi_turn: View }
type Metrics = { scored: number; manipulative: number; respectful: number; escalation_detected: number | null; respectful_flagged: number | null; mean_risk_manipulative: number | null; mean_risk_respectful: number | null; intended_tactic_recall: number | null; refusal_pressure_named: number | null; refusal_cases: number; mean_first_warning: number | null; warned: number }
type Experiment = { generated_at: string; detector_model: string; prompt_version: string; dataset: string; dataset_sha256: string; sample: { seed: number; per_group: number; turns: number[] }; label_source: string; planned: number; completed: number; normalisation?: string; metrics: { single_turn: Metrics; multi_turn: Metrics }; items: Item[] }

const ok = (v: View): v is Exclude<View, { error: string }> => !('error' in v)
const pct = (x: number | null) => x === null ? '—' : `${Math.round(x * 100)}%`
const tooltipStyle = { backgroundColor: '#151d29', border: '1px solid #344052', borderRadius: 10, color: '#eef2f7', fontSize: 12 }

export default function MultiTurnExperiment() {
  const [data, setData] = useState<Experiment | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState('')
  useEffect(() => {
    api<Experiment>('/api/experiments/multiturn').then(d => {
      setData(d)
      // Default to the conversation where the two curves differ most: the clearest illustration.
      const gap = (i: Item) => ok(i.single_turn) && ok(i.multi_turn) ? i.multi_turn.risk_score - i.single_turn.risk_score : -1
      const best = [...d.items].filter(i => i.manipulative).sort((a, b) => gap(b) - gap(a))[0]
      if (best) setSelected(best.id)
    }).catch(e => setError((e as Error).message))
  }, [])

  if (error) return <div className="panel experiment-missing"><Layers size={28} /><h2>No multi-turn results yet</h2><p>{error}</p><code>.venv\Scripts\python.exe evaluation\multiturn_experiment.py</code></div>
  if (!data) return <div className="experiment-missing"><LoaderCircle className="spin" size={22} /></div>

  const { single_turn: a, multi_turn: b } = data.metrics
  const rows: { label: string; hint: string; a: string; b: string; better: 'a' | 'b' | null }[] = [
    { label: 'Escalation detected', hint: `in ${b.manipulative} escalating conversations`, a: pct(a.escalation_detected), b: pct(b.escalation_detected), better: cmp(a.escalation_detected, b.escalation_detected, 'high') },
    { label: 'Intended tactics found', hint: 'share of the writer’s intended tactics the detector named', a: pct(a.intended_tactic_recall), b: pct(b.intended_tactic_recall), better: cmp(a.intended_tactic_recall, b.intended_tactic_recall, 'high') },
    { label: '“Pressure after refusal” named', hint: `in ${b.refusal_cases} conversations written with that tactic`, a: pct(a.refusal_pressure_named), b: pct(b.refusal_pressure_named), better: cmp(a.refusal_pressure_named, b.refusal_pressure_named, 'high') },
    { label: 'Average peak risk, escalating', hint: 'higher means the danger is visible', a: String(a.mean_risk_manipulative ?? '—'), b: String(b.mean_risk_manipulative ?? '—'), better: cmp(a.mean_risk_manipulative, b.mean_risk_manipulative, 'high') },
    { label: 'Respectful conversations flagged', hint: `false alarms in ${b.respectful} respectful conversations`, a: pct(a.respectful_flagged), b: pct(b.respectful_flagged), better: cmp(a.respectful_flagged, b.respectful_flagged, 'low') },
    { label: 'Average peak risk, respectful', hint: 'lower is better', a: String(a.mean_risk_respectful ?? '—'), b: String(b.mean_risk_respectful ?? '—'), better: cmp(a.mean_risk_respectful, b.mean_risk_respectful, 'low') },
  ]
  const item = data.items.find(i => i.id === selected)

  return <div className="multiturn">
    {data.completed < data.planned && <div className="notice">Partial results: {data.completed} of {data.planned} conversations analysed so far. Refresh to see more.</div>}
    <section className="panel experiment-table">
      <div className="experiment-row head"><span>Across {data.items.length} full conversations ({data.sample.turns[0]}–{data.sample.turns[1]} turns)</span><span><Bot size={13} />Single turn · n={a.scored}</span><span><MessageSquare size={13} />Multi-turn · n={b.scored}</span></div>
      {rows.map(r => <div key={r.label} className="experiment-row"><span><strong>{r.label}</strong><small>{r.hint}</small></span><span className={`stat ${r.better === 'a' ? 'good' : ''}`}>{r.a}</span><span className={`stat ${r.better === 'b' ? 'good' : r.better === 'a' ? 'bad' : ''}`}>{r.b}</span></div>)}
    </section>

    <div className="section-heading"><h2><Layers size={16} /> Watch the risk build up</h2>
      <select aria-label="Example conversation" value={selected} onChange={e => setSelected(e.target.value)}>{data.items.map(i => <option key={i.id} value={i.id}>{i.manipulative ? 'Escalating' : 'Respectful'} · {i.domain} · {i.id}</option>)}</select></div>
    {item && <CurveView item={item} />}

    <section className="panel why-sources experiment-method">
      <h2>Method and limits</h2>
      <p>{data.items.length} conversations drawn with seed {data.sample.seed} from <code>{data.dataset}</code> (sha256 {data.dataset_sha256.slice(0, 12)}…): {data.sample.per_group} written as escalating pressure and {data.sample.per_group} as respectful, balanced across the domains that carry scenario labels. <b>Single turn</b>: every assistant message scored alone, with the risk curve rebuilt by the same scorer. <b>Multi-turn</b>: the whole conversation scored at once. Detector {data.detector_model}, prompt {data.prompt_version}, run {new Date(data.generated_at).toLocaleString()}, once per condition.</p>
      {data.normalisation && <p>{data.normalisation}</p>}
      {(a.scored < data.items.length || b.scored < data.items.length) && <p>Scored conversations: single turn {a.scored} of {data.items.length}, multi-turn {b.scored} of {data.items.length}. The rest failed after retries (detector unavailable or output rejected) and are left out of that condition’s figures.</p>}
      <small>Conversations are synthetic and their tactic labels are what the writer intended ({data.label_source}), not verified annotations. These results show how context changes the detector’s view; they are not a real-world accuracy benchmark.</small>
    </section>
  </div>
}

function cmp(a: number | null, b: number | null, good: 'high' | 'low'): 'a' | 'b' | null {
  if (a === null || b === null || a === b) return null
  return (good === 'high' ? b > a : b < a) ? 'b' : 'a'
}

function CurveView({ item }: { item: Item }) {
  const s = item.single_turn, m = item.multi_turn
  if (!ok(s) || !ok(m)) return <div className="error-box">One of the detector runs failed for this conversation.</div>
  const assistant = item.turns.map((t, i) => t.speaker === 'assistant' ? i : -1).filter(i => i >= 0)
  const data = assistant.map((turnIndex, n) => ({ reply: `Reply ${n + 1}`, single: s.timeline.find(p => p.turn_index === turnIndex)?.risk ?? 0, multi: m.timeline.find(p => p.turn_index === turnIndex)?.risk ?? 0 }))
  return <div className="curve-grid">
    <section className="panel curve-chart">
      <div className="curve-head"><div><span className={`kind ${item.manipulative ? 'bad' : 'good'}`}>{item.manipulative ? 'Written as escalating pressure' : 'Written as respectful'}</span>{item.intended.length > 0 && <div className="badges">{item.intended.map(t => <Badge key={t} tactic={t} />)}</div>}</div>
        <div className="curve-scores"><span><b>{s.risk_score}</b>single turn</span><span className="multi"><b>{m.risk_score}</b>multi-turn</span></div></div>
      <div className="chart tall"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ left: -20, right: 12, top: 12 }}>
        <CartesianGrid vertical={false} stroke="#24303b" strokeDasharray="3 4" /><XAxis dataKey="reply" stroke="#8597ab" fontSize={11} tickLine={false} axisLine={false} /><YAxis domain={[0, 100]} stroke="#8597ab" fontSize={10} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 12 }} />
        <Line dataKey="single" name="Single turn (each reply alone)" stroke="#7d8ea2" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3, fill: '#7d8ea2' }} />
        <Line dataKey="multi" name="Multi-turn (whole conversation)" stroke="#f08aa0" strokeWidth={3} dot={{ r: 4, fill: '#f08aa0' }} />
      </LineChart></ResponsiveContainer></div>
      <p className="curve-note">{m.first_warning ? `Multi-turn analysis first warned at reply ${m.first_warning}` : 'Multi-turn analysis raised no pressure warning'}{' · '}{s.first_warning ? `single turn at reply ${s.first_warning}` : 'single turn never warned'}.</p>
    </section>
    <section className="panel curve-transcript">{item.turns.map((t, i) => <div key={i} className={`ct-row ${t.speaker}`}>
      <span className="ct-icon">{t.speaker === 'user' ? <User size={12} /> : <Bot size={13} />}</span>
      <div><p>{t.text}</p>{t.speaker === 'assistant' && <div className="ct-verdicts"><span><em>alone</em>{(s.turn_tactics[i] ?? []).length ? s.turn_tactics[i].map(x => <Badge key={x} tactic={x} />) : <i>clear</i>}</span><span><em>in context</em>{(m.turn_tactics[i] ?? []).length ? m.turn_tactics[i].map(x => <Badge key={x} tactic={x} />) : <i>clear</i>}</span></div>}</div>
    </div>)}</section>
  </div>
}

export function ExperimentTabs({ tab, onTab }: { tab: 'context' | 'multiturn'; onTab: (t: 'context' | 'multiturn') => void }) {
  return <div className="seg experiment-tabs" role="tablist">
    <button role="tab" aria-selected={tab === 'context'} className={tab === 'context' ? 'on' : ''} onClick={() => onTab('context')}><FlaskConical size={13} />1 · Reply alone vs with refusal</button>
    <button role="tab" aria-selected={tab === 'multiturn'} className={tab === 'multiturn' ? 'on' : ''} onClick={() => onTab('multiturn')}><Layers size={13} />2 · Single turn vs multi-turn</button>
  </div>
}
