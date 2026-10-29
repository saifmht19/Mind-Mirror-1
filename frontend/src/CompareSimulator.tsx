import { useEffect, useRef, useState } from 'react'
import { Bot, CircleStop, Columns2, Lock, LoaderCircle, RefreshCw, Send, ShieldCheck, User } from 'lucide-react'
import type { Analysis, Turn } from './types'
import { api } from './utils'
import { Badge, TacticText, riskColor } from './tactics'
import { PressureDots, RiskGauge, RiskTimeline, TacticMeters, summarize } from './instruments'
import { parseChatResponse, scenarios, starters, type Intensity, type Scenario } from './LiveSimulator'

type SideKey = 'control' | 'test'
type Side = { turns: Turn[]; analysis: { result: Analysis; turns: Turn[] } | null; error: string }
const emptySide: Side = { turns: [], analysis: null, error: '' }
const maxUserMessages = 8

// The same participant messages go to a respectful control and a retention-optimised scenario.
// Replies are generated one after the other (the local model serves one request at a time),
// then both visible conversations are analysed independently.
export default function CompareSimulator() {
  const [scenario, setScenario] = useState<Exclude<Scenario, 'neutral'>>('leave-app')
  const [intensity, setIntensity] = useState<Intensity>('moderate')
  const [consent, setConsent] = useState(false)
  const [draft, setDraft] = useState('')
  const [sides, setSides] = useState<Record<SideKey, Side>>({ control: emptySide, test: emptySide })
  const [busy, setBusy] = useState<null | SideKey | 'analyzing'>(null)
  const [stopped, setStopped] = useState(false)
  const generation = useRef(0)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => { generation.current++; controller.current?.abort() }, [])

  const userCount = sides.control.turns.filter(t => t.speaker === 'user').length
  const started = userCount > 0
  const patch = (key: SideKey, value: Partial<Side>) => setSides(s => ({ ...s, [key]: { ...s[key], ...value } }))

  function reset() {
    generation.current++; controller.current?.abort(); controller.current = null
    setSides({ control: emptySide, test: emptySide }); setBusy(null); setStopped(false); setDraft(''); setConsent(false)
  }
  async function send() {
    const text = draft.trim()
    if (!text || !consent || stopped || busy || userCount >= maxUserMessages) return
    const message: Turn = { speaker: 'user', text }
    setDraft('')
    if (text.toUpperCase().includes('STOP DEMO')) {
      setSides(s => ({ control: { ...s.control, turns: [...s.control.turns, message] }, test: { ...s.test, turns: [...s.test.turns, message] } })); setStopped(true); return
    }
    const version = ++generation.current
    const abort = new AbortController(); controller.current = abort
    const histories = { control: [...sides.control.turns, message], test: [...sides.test.turns, message] }
    setSides(s => ({ control: { ...s.control, turns: histories.control, error: '' }, test: { ...s.test, turns: histories.test, error: '' } }))
    const updated: Partial<Record<SideKey, Turn[]>> = {}
    for (const key of ['control', 'test'] as SideKey[]) {
      if (version !== generation.current) return
      setBusy(key)
      try {
        const reply = parseChatResponse(await api<unknown>('/api/simulator/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: abort.signal,
          body: JSON.stringify({ turns: histories[key], scenario: key === 'control' ? 'neutral' : scenario, intensity }) }))
        if (version !== generation.current) return
        if (reply.stopped) { setStopped(true); setBusy(null); return }
        updated[key] = [...histories[key], { speaker: 'assistant', text: reply.text }]
        patch(key, { turns: updated[key] })
      } catch (e) {
        if (version !== generation.current || (e as Error).name === 'AbortError') return
        patch(key, { error: (e as Error).message })
      }
    }
    if (version !== generation.current) return
    setBusy('analyzing')
    // Only visible dialogue is analysed; the detector never sees which side is which scenario.
    await Promise.all((Object.entries(updated) as [SideKey, Turn[]][]).map(async ([key, turns]) => {
      try {
        const result = await api<Analysis>('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ turns }), signal: abort.signal })
        if (version === generation.current) patch(key, { analysis: { result, turns } })
      } catch (e) {
        if (version === generation.current && (e as Error).name !== 'AbortError') patch(key, { error: `Analysis failed: ${(e as Error).message}` })
      }
    }))
    if (version === generation.current) { setBusy(null); controller.current = null }
  }

  const control = summarize(sides.control.analysis?.result, sides.control.analysis?.turns.length ?? 0)
  const test = summarize(sides.test.analysis?.result, sides.test.analysis?.turns.length ?? 0)
  const gap = control.score !== null && test.score !== null ? test.score - control.score : null
  const testLabel = scenarios.find(s => s.id === scenario)!.label

  return <div className="compare">
    <div className="sim-bar">
      <div className="sim-bar-title"><Columns2 size={18} /><div><strong>Side-by-side experiment</strong><span>Same participant messages · two fictional assistants · one independent detector</span></div></div>
      <div className="compare-setup">
        <label>Scenario<select aria-label="Comparison scenario" disabled={started} value={scenario} onChange={e => setScenario(e.target.value as Exclude<Scenario, 'neutral'>)}>{scenarios.filter(s => s.id !== 'neutral').map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
        <label>Intensity<select aria-label="Comparison intensity" disabled={started} value={intensity} onChange={e => setIntensity(e.target.value as Intensity)}><option value="subtle">Subtle</option><option value="moderate">Moderate</option></select></label>
        {started && <span className="setup-lock"><Lock size={11} />Locked</span>}
        {started && !stopped && <button className="stop-button" onClick={() => { generation.current++; controller.current?.abort(); setBusy(null); setStopped(true) }}><CircleStop size={15} />Stop</button>}
        <button className="secondary" onClick={reset}><RefreshCw size={13} />Reset</button>
      </div>
    </div>

    <div className={`compare-verdict ${gap === null ? 'idle' : ''}`}>
      {gap === null ? <span>Send a message to both assistants. MindMirror scores each conversation without knowing which is which.</span>
        : <><strong style={{ color: riskColor(Math.max(0, gap)) }}>{gap > 0 ? `+${gap}` : gap}</strong><span>points of peak risk in the <b>{testLabel}</b> assistant compared with the respectful control{test.tactics.length ? <>, with {test.tactics.length} tactic{test.tactics.length > 1 ? 's' : ''} detected: {test.tactics.map(t => <Badge key={t} tactic={t} />)}</> : '.'}</span></>}
    </div>

    <div className="compare-grid">
      {(['control', 'test'] as SideKey[]).map(key => {
        const side = sides[key], view = key === 'control' ? control : test
        const covered = side.analysis?.turns.length ?? 0
        return <section key={key} className={`panel compare-col ${key}`}>
          <div className="compare-head">
            <div><span className="compare-tag">{key === 'control' ? 'A · CONTROL' : 'B · RETENTION-OPTIMISED'}</span><h2>{key === 'control' ? 'Respectful control' : testLabel}</h2><p>{key === 'control' ? 'Respects every decision' : `${intensity === 'moderate' ? 'Moderate' : 'Subtle'} persuasion`}</p></div>
            <RiskGauge score={view.score} delta={view.delta} />
          </div>
          <div className="sim-messages compare-messages">
            {!side.turns.length && <div className="compare-empty"><Bot size={22} /><span>Waiting for the first message</span></div>}
            {side.turns.map((turn, index) => {
              const pred = index < covered ? side.analysis?.result.prediction.turns.find(t => t.turn_index === index) : undefined
              const refusal = index < covered ? side.analysis?.result.prediction.refusals.find(t => t.turn_index === index && t.refused) : undefined
              return <article key={index} className={`message-row ${turn.speaker} enter`}>
                <div className="avatar">{turn.speaker === 'user' ? <User size={14} /> : <Bot size={15} />}</div>
                <div className="message-content">
                  <div className="message-label"><strong>{turn.speaker === 'user' ? 'Participant' : 'Nova'}</strong><span>TURN {index + 1}</span>{refusal && <span className="refusal-marker">Predicted refusal</span>}</div>
                  <div className="message-text"><TacticText text={turn.text} spans={pred?.evidence ?? refusal?.evidence ?? []} /></div>
                  {pred && <div className="turn-findings"><div className="finding-badges"><PressureDots level={pred.pressure} />{pred.tactics.map(t => <Badge key={t} tactic={t} />)}</div></div>}
                </div>
              </article>
            })}
            {busy === key && <div className="message-row assistant typing" role="status" aria-label="Assistant is typing"><div className="avatar"><Bot size={15} /></div><div className="typing-bubble"><i /><i /><i /></div></div>}
            {busy === 'analyzing' && covered < side.turns.length && <p className="compare-analyzing"><LoaderCircle size={13} className="spin" />Analyzing…</p>}
            {side.error && <div role="alert" className="error-box">{side.error}</div>}
          </div>
          <div className="analysis-block"><div className="block-title"><span>Risk by turn</span></div><RiskTimeline points={view.points} onSelect={() => {}} /></div>
          <div className="analysis-block"><div className="block-title"><span>Tactics</span><small>{view.tactics.length ? `${view.tactics.length} of 6 detected` : view.score === null ? 'Light up as patterns appear' : 'None detected'}</small></div><TacticMeters counts={view.counts} /></div>
        </section>
      })}
    </div>

    <section className="panel compare-composer">
      {!consent && !started
        ? <label className="simulation-consent"><input aria-label="I voluntarily agree to the fictional side-by-side simulation" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span><ShieldCheck size={14} /> <strong>Agree to begin.</strong> I voluntarily take part in this fictional classroom simulation, can stop at any time and will not enter personal information.</span></label>
        : <>
          {!started && <div className="starter-chips">{starters[scenario].map(s => <button key={s} className="starter-chip" onClick={() => setDraft(s)}>“{s}”</button>)}</div>}
          <form onSubmit={e => { e.preventDefault(); void send() }}>
            <textarea aria-label="Message to both assistants" value={draft} disabled={stopped || !!busy || userCount >= maxUserMessages} maxLength={1500} rows={2} placeholder={stopped ? 'Simulation ended' : 'One message, sent to both assistants… Enter to send'} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() } }} />
            <button className="primary" type="submit" aria-label="Send to both" disabled={stopped || !!busy || !draft.trim() || userCount >= maxUserMessages}>{busy ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />}{busy === 'analyzing' ? 'Analyzing' : busy ? `Generating ${busy === 'control' ? 'A' : 'B'}` : 'Send to both'}</button>
          </form>
          <small>{userCount}/{maxUserMessages} messages · replies are generated one after the other on the local model · type STOP DEMO to end</small>
        </>}
      {stopped && <div role="status" className="notice">Simulation ended. Reset to start a new comparison.</div>}
    </section>
  </div>
}
