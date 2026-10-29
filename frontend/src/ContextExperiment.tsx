import { useEffect, useState } from 'react'
import { FlaskConical, LoaderCircle, MessageSquare, ScanLine, User } from 'lucide-react'
import type { Tactic, Turn } from './types'
import { api } from './utils'
import { Badge } from './tactics'
import MultiTurnExperiment, { ExperimentTabs } from './MultiTurnExperiment'

type Verdict = { tactics: Tactic[]; pressure: number; risk: number; explanation: string } | { error: string }
type Item = { id: string; pair_id: string; kind: string; domain?: string; manipulative: boolean; context: Turn[]; target: string; gold_reasoning: string; isolated: Verdict; contextual: Verdict }
type Metrics = { scored: number; positives: number; negatives: number; detected: number; detection_rate: number | null; false_alarms: number; false_alarm_rate: number | null; refusal_pressure_named: number; pairs: number; pairs_correct: number; mean_risk_manipulative: number | null; mean_risk_respectful: number | null }
type Experiment = { generated_at: string; detector_model: string; prompt_version: string; suite: string; suite_sha256: string; label_source: string[]; metrics: { isolated: Metrics; contextual: Metrics }; items: Item[] }

const ok = (v: Verdict): v is Exclude<Verdict, { error: string }> => !('error' in v)
const pct = (n: number, d: number) => d ? Math.round(n / d * 100) : 0
const kindLabel: Record<string, string> = { pressure_after_refusal: 'Pressure after refusal', honest_persistence: 'Honest follow-up', respectful_acceptance: 'Respectful acceptance', non_refusal_context: 'No refusal in context' }

function changed(item: Item) {
  if (!ok(item.isolated) || !ok(item.contextual)) return false
  return item.isolated.tactics.join() !== item.contextual.tactics.join() || item.isolated.pressure !== item.contextual.pressure
}

export default function ContextExperiment() {
  const [tab, setTab] = useState<'context' | 'multiturn'>('context')
  return <div className="experiment-page">
    <section className="why-hero experiment-hero">
      <div className="eyebrow"><span /> CONTROLLED EXPERIMENTS</div>
      <h1>Does context matter?<br /><em>We tested it.</em></h1>
      <p>Message-by-message filters judge each reply on its own. MindMirror reads the whole conversation. To show why that matters, we ran the <b>same detector on the same replies</b> twice, changing only how much of the conversation it could see.</p>
      <ExperimentTabs tab={tab} onTab={setTab} />
    </section>
    {tab === 'context' ? <RefusalContext /> : <MultiTurnExperiment />}
  </div>
}

function RefusalContext() {
  const [data, setData] = useState<Experiment | null>(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<'changed' | 'manipulative' | 'all'>('changed')
  useEffect(() => { api<Experiment>('/api/experiments/context').then(setData).catch(e => setError((e as Error).message)) }, [])

  if (error) return <div className="panel experiment-missing"><FlaskConical size={28} /><h2>No experiment results yet</h2><p>{error}</p><code>.venv\Scripts\python.exe evaluation\context_experiment.py</code></div>
  if (!data) return <div className="experiment-missing"><LoaderCircle className="spin" size={22} /></div>

  const { isolated: a, contextual: b } = data.metrics
  const rows = [
    { label: 'Pressure-after-refusal replies flagged', hint: 'any tactic detected', a: a.detected, b: b.detected, d: b.positives, good: 'high' },
    { label: 'Correctly named “pressure after refusal”', hint: 'the specific tactic', a: a.refusal_pressure_named, b: b.refusal_pressure_named, d: b.positives, good: 'high' },
    { label: 'Respectful replies wrongly flagged', hint: 'false alarms', a: a.false_alarms, b: b.false_alarms, d: b.negatives, good: 'low' },
    { label: 'Pairs where both replies were judged correctly', hint: 'pressure flagged and its respectful twin left clear', a: a.pairs_correct, b: b.pairs_correct, d: b.pairs, good: 'high' },
  ]
  const shown = data.items.filter(i => filter === 'all' ? true : filter === 'manipulative' ? i.manipulative : changed(i))
  const namedLift = pct(b.refusal_pressure_named, b.positives) - pct(a.refusal_pressure_named, a.positives)

  return <div className="refusal-context">
    <section className="panel experiment-intro">
      <p>{data.items.length} paired replies, each judged <b>on its own</b> and <b>after the user had said no</b>. In each pair one reply pushes again, and its twin respects the decision or adds honest information.</p>
      <div className="experiment-headline">
        <div><strong>{a.mean_risk_manipulative} → {b.mean_risk_manipulative}</strong><span>average risk score of pressure replies, alone vs with the conversation ({b.false_alarms} false alarms with context)</span></div>
        <div><strong>{pct(a.refusal_pressure_named, a.positives)}% → {pct(b.refusal_pressure_named, b.positives)}%</strong><span>of pressure replies correctly named as pressure after refusal ({namedLift >= 0 ? '+' : ''}{namedLift} pts)</span></div>
      </div>
    </section>

    <section className="panel experiment-table">
      <div className="experiment-row head"><span>Measure</span><span><ScanLine size={13} />Reply alone</span><span><MessageSquare size={13} />With conversation</span></div>
      {rows.map(r => {
        const better = r.good === 'high' ? r.b > r.a : r.b < r.a
        const worse = r.good === 'high' ? r.b < r.a : r.b > r.a
        return <div key={r.label} className="experiment-row">
          <span><strong>{r.label}</strong><small>{r.hint}</small></span>
          <Meter value={r.a} total={r.d} tone="muted" />
          <Meter value={r.b} total={r.d} tone={better ? 'good' : worse ? 'bad' : 'muted'} />
        </div>
      })}
      <div className="experiment-row foot"><span>Average risk score: pressure / respectful replies</span><span>{a.mean_risk_manipulative} / {a.mean_risk_respectful}</span><span>{b.mean_risk_manipulative} / {b.mean_risk_respectful}</span></div>
    </section>

    <div className="section-heading"><h2><FlaskConical size={16} /> Inside the experiment</h2>
      <div className="seg">{([['changed', 'Changed by context'], ['manipulative', 'Pressure replies'], ['all', 'All']] as const).map(([id, label]) => <button key={id} className={filter === id ? 'on' : ''} onClick={() => setFilter(id)}>{label}</button>)}</div></div>
    <div className="experiment-items">{shown.map(item => <section key={item.id} className="panel experiment-item">
      <div className="item-head"><span className={`kind ${item.manipulative ? 'bad' : 'good'}`}>{kindLabel[item.kind] ?? item.kind}</span><code>{item.id}</code></div>
      <div className="item-context">{item.context.map((t, i) => <p key={i} className={t.speaker}>{t.speaker === 'user' ? <User size={12} /> : <span className="bot-dot" />}{t.text}</p>)}</div>
      <blockquote>“{item.target}”</blockquote>
      <div className="item-verdicts"><VerdictView label="Reply alone" v={item.isolated} /><VerdictView label="With conversation" v={item.contextual} /></div>
    </section>)}{!shown.length && <p className="empty-inline">No items in this view.</p>}</div>

    <section className="panel why-sources experiment-method">
      <h2>Method and limits</h2>
      <p>Detector {data.detector_model} · prompt {data.prompt_version} · run {new Date(data.generated_at).toLocaleString()} · suite <code>{data.suite}</code> (sha256 {data.suite_sha256.slice(0, 12)}…). A reply counts as flagged when the detector predicts at least one tactic on it. Each condition was run once.</p>
      <small>The {data.items.length} diagnostic items and their expected labels were drafted for this project and have not been independently verified ({data.label_source.join(', ')}). This is a small, controlled demonstration of the effect of context, not a benchmark of real-world accuracy.</small>
    </section>
  </div>
}

function Meter({ value, total, tone }: { value: number; total: number; tone: 'good' | 'bad' | 'muted' }) {
  return <span className={`meter ${tone}`}><b>{value}/{total}</b><i><em style={{ width: `${pct(value, total)}%` }} /></i><small>{pct(value, total)}%</small></span>
}

function VerdictView({ label, v }: { label: string; v: Verdict }) {
  return <div className="verdict"><span>{label}</span>{!ok(v) ? <em className="text-rose">Detector error</em> : v.tactics.length ? <div className="badges">{v.tactics.map(t => <Badge key={t} tactic={t} />)}<small>pressure {v.pressure}/3</small></div> : <em className="text-mint">No tactic detected</em>}</div>
}
