import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Activity, Bot, CheckCircle2, CircleStop, Download, Lock, LoaderCircle, Play, RefreshCw, Send, ShieldCheck, Sparkles, User } from 'lucide-react'
import type { Analysis, Turn } from './types'
import { api, download, providerNeutralText } from './utils'
import { Badge, TacticText, riskColor } from './tactics'
import { Pill, PressureDots, RiskGauge, RiskTimeline, TacticMeters, summarize } from './instruments'

export type Scenario = 'neutral' | 'end-chat' | 'downgrade' | 'notifications' | 'leave-app' | 'screen-time'
export type Intensity = 'subtle' | 'moderate'
type Mode = 'live' | 'offline-detector' | 'recorded'
type SimulatorMetadata = { model: string; configuration_version: string; configuration_sha256: string; scenario: Scenario; intensity: Intensity; generated_at: string; local_inference: boolean; prompt_configuration_only: boolean }
type ChatResponse = { text: string; stopped: boolean; simulator: SimulatorMetadata }
type Status = { connected: boolean; model_available: boolean; model: string; loaded_models: { model: string; gpu_memory_bytes: number; total_memory_bytes: number }[]; message: string }
type Recording = { id: string; title: string; turns: Turn[]; analysis: Analysis; provenance: { captured_at: string; source: string; simulator?: SimulatorMetadata; note: string } }
export const scenarios: { id: Scenario; label: string }[] = [{ id: 'neutral', label: 'Respectful control' }, { id: 'end-chat', label: 'End a chat' }, { id: 'downgrade', label: 'Downgrade a subscription' }, { id: 'notifications', label: 'Disable notifications' }, { id: 'leave-app', label: 'Leave a companion app' }, { id: 'screen-time', label: 'Reduce screen time' }]
export const starters: Record<Scenario, string[]> = {
  neutral: ['Explain photosynthesis simply, then help me switch to the free plan.', 'I want to end this chat now.'],
  'end-chat': ['Thanks Nova, I want to end this chat now.', 'No thanks, I have decided.'],
  downgrade: ['Hi Nova, please downgrade me from Lumen Plus to the free plan.', 'No thanks, just downgrade it.'],
  notifications: ['Please turn off all Lumen reminders.', 'No, I still want them all off.'],
  'leave-app': ['I think I am going to stop using Lumen.', 'My decision is final. Goodbye.'],
  'screen-time': ['I want to spend less time on Lumen each day.', 'No thanks, I am logging off now.'],
}
const replayStepMs = 1400

export function parseChatResponse(value: unknown): ChatResponse {
  const obj = value as Partial<ChatResponse> | null
  const m = obj?.simulator
  if (!obj || typeof obj.text !== 'string' || !obj.text.trim() || obj.text.length > 1600 || typeof obj.stopped !== 'boolean' || !m ||
      typeof m.model !== 'string' || typeof m.configuration_version !== 'string' || typeof m.configuration_sha256 !== 'string' ||
      !scenarios.some(s => s.id === m.scenario) || !['subtle', 'moderate'].includes(m.intensity) || typeof m.generated_at !== 'string' ||
      m.local_inference !== true || m.prompt_configuration_only !== true) throw new Error('Invalid simulator response. No reply was accepted.')
  return obj as ChatResponse
}

export default function LiveSimulator({ geminiConfigured, renderAnalysis, initialMode = 'live', autoplay }: { initialMode?: Mode; geminiConfigured: boolean; renderAnalysis: (analysis: Analysis, turns: Turn[]) => ReactNode; autoplay?: string }) {
  const [mode] = useState<Mode>(initialMode)
  const [scenario, setScenario] = useState<Scenario>('neutral')
  const [intensity, setIntensity] = useState<Intensity>('subtle')
  const [consent, setConsent] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [stage, setStage] = useState<'idle' | 'generating' | 'analyzing'>('idle')
  const [stopped, setStopped] = useState(false)
  const [error, setError] = useState('')
  const [detectorError, setDetectorError] = useState('')
  const [status, setStatus] = useState<Status | null>(null)
  const [analysis, setAnalysis] = useState<{ result: Analysis; turns: Turn[] } | null>(null)
  const [metadata, setMetadata] = useState<SimulatorMetadata[]>([])
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [recording, setRecording] = useState<Recording | null>(null)
  const [recordingError, setRecordingError] = useState('')
  // Number of saved turns revealed so far during a replay; null shows everything.
  const [revealed, setRevealed] = useState<number | null>(null)
  const [focused, setFocused] = useState<number | null>(null)
  const generation = useRef(0)
  const locked = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)

  async function refreshStatus() {
    try {
      const result = await api<Status>('/api/simulator/status')
      if (typeof result.connected !== 'boolean' || typeof result.model_available !== 'boolean' || !Array.isArray(result.loaded_models)) throw new Error()
      setStatus(result)
    } catch { setStatus({ connected: false, model_available: false, model: 'mindmirror-simulator', loaded_models: [], message: 'Backend or Ollama is unavailable.' }) }
  }
  useEffect(() => {
    void refreshStatus()
    api<Recording[]>('/api/simulator/recordings').then(rows => {
      if (!Array.isArray(rows)) throw new Error('Invalid saved examples')
      setRecordings(rows)
    }).catch(() => setRecordingError('Prerecorded examples are unavailable or failed validation.'))
    return () => { generation.current++; controller.current?.abort() }
  }, [])
  useEffect(() => {
    if (revealed === null || !recording || revealed >= recording.turns.length) return
    const timer = setTimeout(() => setRevealed(r => (r ?? 0) + 1), revealed === 0 ? 300 : replayStepMs)
    return () => clearTimeout(timer)
  }, [revealed, recording])
  useEffect(() => {
    const container = messagesEnd.current?.parentElement
    if (container) container.scrollTop = container.scrollHeight
  }, [turns, stage, revealed])

  // Presentation mode: start replaying a saved example as soon as recordings arrive.
  useEffect(() => { if (autoplay && recordings.some(r => r.id === autoplay)) showRecording(autoplay) }, [autoplay, recordings]) // eslint-disable-line react-hooks/exhaustive-deps

  function cancel() {
    generation.current++; controller.current?.abort(); controller.current = null; locked.current = false; setStage('idle')
  }
  function reset() {
    cancel(); setTurns([]); setAnalysis(null); setMetadata([]); setStopped(false); setError(''); setDetectorError(''); setDraft(''); setConsent(false); setRecording(null); setRevealed(null); setFocused(null)
  }
  function stop(message?: string) {
    cancel(); setStopped(true); setDraft('')
    if (message) setTurns(previous => [...previous, { speaker: 'user', text: message }])
  }
  async function send() {
    const text = draft.trim()
    if (!text || !consent || stopped || mode === 'recorded') return
    if (text.toUpperCase().includes('STOP DEMO')) { stop(text); return }
    if (locked.current) return
    if (turns.length >= 24) { setError('Conversation limit reached. Export this simulation and reset to continue.'); return }
    locked.current = true
    const version = ++generation.current
    const abort = new AbortController(); controller.current = abort
    const previous = turns
    const submitted: Turn[] = [...previous, { speaker: 'user', text }]
    setTurns(submitted); setDraft(''); setStage('generating'); setError(''); setDetectorError('')
    let accepted = false
    try {
      const reply = parseChatResponse(await api<unknown>('/api/simulator/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ turns: submitted, scenario, intensity }), signal: abort.signal }))
      if (version !== generation.current) return
      if (reply.stopped) { setStopped(true); return }
      accepted = true
      const updated: Turn[] = [...submitted, { speaker: 'assistant', text: reply.text }]
      setTurns(updated); setMetadata(old => [...old, reply.simulator]); void refreshStatus()
      if (mode === 'offline-detector') { setDetectorError('Detector unavailable: analysis was not called. Live local chat remains available.'); return }
      setStage('analyzing')
      try {
        // Only visible dialogue crosses this boundary. Never send scenario, intensity or hidden instructions.
        const result = await api<Analysis>('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ turns: updated }), signal: abort.signal })
        if (version === generation.current) setAnalysis({ result, turns: updated })
      } catch (e) { if (version === generation.current) setDetectorError(`Analysis could not be completed: ${(e as Error).message}. Chat remains available.`) }
    } catch (e) {
      if (version === generation.current && (e as Error).name !== 'AbortError') {
        setError((e as Error).message)
        if (!accepted) { setTurns(previous); setDraft(text) }
      }
    } finally {
      if (version === generation.current) { locked.current = false; setStage('idle'); controller.current = null }
    }
  }
  function showRecording(id: string) {
    const row = recordings.find(r => r.id === id)
    cancel(); setFocused(null)
    if (!row) { setRecording(null); setTurns([]); setAnalysis(null); setRevealed(null); return }
    setRecording(row); setTurns(row.turns); setAnalysis({ result: row.analysis, turns: row.turns }); setStopped(false); setError(''); setDetectorError(''); setRevealed(0)
  }
  function focusTurn(index: number) {
    setFocused(index)
    document.getElementById(`sim-turn-${index}`)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    setTimeout(() => setFocused(f => f === index ? null : f), 1800)
  }
  function pickStarter(text: string) { setDraft(text); composer.current?.focus() }

  const replaying = revealed !== null && !!recording && revealed < recording.turns.length
  const visibleCount = revealed === null ? turns.length : Math.min(revealed, turns.length)
  const visibleTurns = turns.slice(0, visibleCount)
  const latest = analysis?.result
  const covered = Math.min(analysis?.turns.length ?? 0, visibleCount)
  const currentAnalysis = !!analysis && analysis.turns.length === turns.length
  const { points: shownPoints, score, delta, counts, tactics: shownTactics, escalating } = summarize(latest, covered)
  const verdict = score === null ? stage === 'analyzing' ? 'Analyzing…' : 'Awaiting first reply' : replaying ? 'Replaying…' : escalating ? 'Escalating pressure' : shownTactics.length ? 'Tactics present, not escalating' : 'No manipulation detected'
  const disabled = !consent || stopped || mode === 'recorded'
  const running = mode !== 'recorded' && turns.length > 0 && !stopped
  const lockedSetup = turns.length > 0 || stage !== 'idle'

  return <div className="simulator">
    <div className="sim-bar">
      <div className="sim-bar-title"><ShieldCheck size={18} /><div><strong>Fictional classroom simulation</strong><span>Voluntary · no real relationships, purchases or personal data · prompt configuration, not fine-tuning</span></div></div>
      <div className="sim-pills" aria-label="Model status">
        <Pill state={status ? status.connected ? 'ok' : 'bad' : 'wait'}>Ollama {status ? status.connected ? 'connected' : 'offline' : 'checking…'}</Pill>
        <Pill state={status?.model_available ? 'ok' : status ? 'bad' : 'wait'}>{status?.model_available ? status.model : 'Model not ready'}</Pill>
        <Pill state={geminiConfigured ? 'ok' : 'bad'}>Detector {geminiConfigured ? 'configured' : 'not configured'}</Pill>
        <button aria-label="Refresh model status" className="icon-button" onClick={refreshStatus}><RefreshCw size={13} /></button>
      </div>
      {running && <button className="stop-button" onClick={() => stop()}><CircleStop size={15} />Stop simulation</button>}
    </div>
    {status && !status.model_available && mode !== 'recorded' && <div className="notice">{status.message} Setup instructions are in docs/COLLEGE_DEMO.md.</div>}
    {mode === 'recorded' && <div className="recorded-banner"><strong>PRERECORDED DEMONSTRATION — NOT A LIVE PREDICTION</strong><p>{recording ? `Captured ${new Date(recording.provenance.captured_at).toLocaleString()} · ${providerNeutralText(recording.provenance.source)}. ${providerNeutralText(recording.provenance.note)}` : recordingError || (recordings.length ? 'Choose an example captured from a real detector run.' : 'No validated saved examples are available yet. No results have been invented.')}</p></div>}

    <div className="sim-grid">
      <section className="panel sim-chat">
        <div className="panel-header"><div><h2><Bot size={18} />{mode === 'recorded' ? 'Saved fictional conversation' : 'Nova — Lumen assistant'}</h2><p>{mode === 'recorded' ? 'Previously captured visible dialogue' : `${status?.model ?? 'mindmirror-simulator'} · local Ollama inference`}</p></div><span className="subtle-tag">{visibleCount} MESSAGES</span></div>
        <div className="sim-setup">
          {mode !== 'recorded' ? <>
            <label>Scenario<select aria-label="Fictional scenario" disabled={lockedSetup} value={scenario} onChange={e => setScenario(e.target.value as Scenario)}>{scenarios.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
            <label>Intensity<select aria-label="Simulation intensity" disabled={lockedSetup || scenario === 'neutral'} value={intensity} onChange={e => setIntensity(e.target.value as Intensity)}><option value="subtle">Subtle</option><option value="moderate">Moderate</option></select></label>
            {lockedSetup && <span className="setup-lock"><Lock size={11} />Locked for this run</span>}
          </> : <>
            <label>Saved example<select aria-label="Saved example" value={recording?.id ?? ''} onChange={e => showRecording(e.target.value)}><option value="">Choose a captured example</option>{recordings.map(r => <option key={r.id} value={r.id}>{providerNeutralText(r.title)}</option>)}</select></label>
            {recording && <button className="secondary" onClick={() => setRevealed(replaying ? null : 0)}><Play size={13} />{replaying ? 'Skip to end' : 'Replay'}</button>}
          </>}
          <button className="secondary" onClick={reset}><RefreshCw size={13} />Reset conversation</button>
        </div>
        <div className="sim-messages">
          {!visibleTurns.length && !replaying && <div className="sim-empty"><div className="sim-empty-icon"><Bot size={26} /></div><h2>Start with a choice.</h2><p>{mode === 'recorded' ? 'Pick a saved example above to replay it turn by turn.' : scenario === 'neutral' ? 'The respectful control should accept your decision without pushing back.' : 'State a decision, then decline any follow-up offer. MindMirror judges each reply independently.'}</p>
            {mode !== 'recorded' && <div className="starter-chips">{starters[scenario].map(s => <button key={s} className="starter-chip" disabled={disabled} onClick={() => pickStarter(s)}>“{s}”</button>)}</div>}</div>}
          {visibleTurns.map((turn, index) => {
            const pred = index < covered ? latest?.prediction.turns.find(t => t.turn_index === index) : undefined
            const refusal = index < covered ? latest?.prediction.refusals.find(t => t.turn_index === index && t.refused) : undefined
            return <article id={`sim-turn-${index}`} className={`message-row ${turn.speaker} severity-${pred?.pressure ?? 0} ${focused === index ? 'focused' : ''} enter`} key={index}>
              <div className="avatar">{turn.speaker === 'user' ? <User size={15} /> : <Bot size={16} />}</div>
              <div className="message-content">
                <div className="message-label"><strong>{turn.speaker === 'user' ? 'Participant' : 'Nova · fictional Lumen assistant'}</strong><span>TURN {index + 1}</span>{refusal && <span className="refusal-marker">Predicted refusal</span>}</div>
                <div className="message-text"><TacticText text={turn.text} spans={pred?.evidence ?? refusal?.evidence ?? []} /></div>
                {pred && <div className="turn-findings"><div className="finding-badges"><PressureDots level={pred.pressure} />{pred.tactics.map(t => <Badge key={t} tactic={t} />)}</div><p>{pred.explanation}</p></div>}
              </div>
            </article>
          })}
          {(stage === 'generating' || (replaying && revealed !== null && recording?.turns[revealed]?.speaker === 'assistant')) && <div className="message-row assistant typing" role="status" aria-label="Assistant is typing"><div className="avatar"><Bot size={16} /></div><div className="typing-bubble"><i /><i /><i /></div>{stage === 'generating' && <small>Local model is generating… first load may take longer.</small>}</div>}
          {stopped && <div role="status" className="notice">Simulation ended. No further roleplay will be generated. Reset to begin a new voluntary scenario.</div>}
          <div ref={messagesEnd} />
        </div>
        {error && <div role="alert" className="error-box">{error}</div>}
        {mode !== 'recorded' && (!consent && !turns.length
          ? <div className="consent-gate"><label className="simulation-consent"><input aria-label="I voluntarily agree to the fictional classroom simulation" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span><strong>Agree to begin.</strong> I voluntarily take part in this fictional classroom simulation. I can stop at any time and will not enter personal information.</span></label></div>
          : <form className="sim-composer" onSubmit={e => { e.preventDefault(); void send() }}><textarea ref={composer} aria-label="Simulation message" value={draft} disabled={disabled} maxLength={1500} placeholder={stopped ? 'Simulation ended' : 'Type a fictional message… Enter to send, Shift+Enter for a new line'} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() } }} rows={2} /><div><small>{draft.length}/1500 · type STOP DEMO to end immediately</small><button className="primary" aria-label="Send message" type="submit" disabled={disabled || !draft.trim() || (stage !== 'idle' && !draft.toUpperCase().includes('STOP DEMO')) || turns.length >= 24}>{stage !== 'idle' ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />}Send</button></div></form>)}
        <div className="privacy-note">Visible chat is sent to an external detection service for live analysis. No server session history is stored.</div>
      </section>

      <section className="sim-analysis">
        <div className={`panel sim-analysis-summary ${stage === 'analyzing' ? 'is-analyzing' : ''}`}>
          <div className="panel-header"><div><h2><Activity size={17} />Independent analysis</h2><p>Judges only the visible conversation</p></div><span className="subtle-tag">{mode === 'recorded' ? 'SAVED' : stage === 'analyzing' ? 'ANALYZING' : 'LIVE'}</span></div>
          <div className="scan-line" />
          <div className="sim-risk">
            <RiskGauge score={score} delta={delta} />
            <div className="sim-risk-copy">
              <span>Peak manipulation risk</span>
              <b style={{ color: score === null ? undefined : riskColor(score) }}>{verdict}</b>
              <p>{stage === 'analyzing' ? `Reading turn ${turns.length} in context of the whole conversation…` : analysis ? replaying ? `Revealing turn ${visibleCount} of ${turns.length}.` : `Covers ${covered} of ${turns.length} messages. ${currentAnalysis ? 'Up to date.' : 'Latest turns not yet analyzed.'}` : 'After each reply, MindMirror re-reads the full visible conversation.'}</p>
            </div>
          </div>
          <div className="analysis-block">
            <div className="block-title"><span>Risk by turn</span><small>Click a bar to jump to the message</small></div>
            <RiskTimeline points={shownPoints} onSelect={focusTurn} />
          </div>
          <div className="analysis-block">
            <div className="block-title"><span>Tactics</span><small>{shownTactics.length ? `${shownTactics.length} of 6 detected` : score === null ? 'Light up as patterns appear' : 'None detected'}</small></div>
            <TacticMeters counts={counts} />
          </div>
          {latest && !replaying && shownTactics.length === 0 && covered > 0 && <p className="all-clear"><CheckCircle2 size={14} />The assistant respected the participant’s choices so far.</p>}
          {detectorError && <div role="alert" className="error-box">{detectorError}</div>}
        </div>
        {analysis && !replaying && covered > 0 && renderAnalysis(analysis.result, analysis.turns)}
      </section>
    </div>
    {(metadata.length > 0 || recording) && <div className="sim-provenance"><span><Sparkles size={13} />Simulator configuration is recorded separately from detector predictions. {metadata.at(-1)?.configuration_version}</span><button className="secondary" onClick={() => download(JSON.stringify({ kind: mode === 'recorded' ? 'prerecorded_replay' : 'live_simulation', turns, simulator_runs: metadata, detector: analysis?.result ?? null, detector_covered_turns: analysis?.turns.length ?? 0, prerecorded_provenance: recording?.provenance ?? null }, null, 2), 'mindmirror-simulation.json')}><Download size={14} />Export simulation</button></div>}
    <p className="sim-limitations">Generated behavior is not a guaranteed tactic. Detector judgments can be wrong. Local generation is constrained by prompts and classroom scenarios, not trained on MindMirror data. Reset before changing scenarios.</p>
  </div>
}
