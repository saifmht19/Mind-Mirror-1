import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Pause, Play, X } from 'lucide-react'

// Scripted walkthrough for a live presentation. Every step uses saved or static content,
// so the tour works without the local model or the detection service.
export const tourSteps = [
  { page: 'why', title: 'The problem is real', text: 'Engagement-optimised AI nudges people with flattery, urgency and guilt, most often when they try to leave. Regulators, courts and AI labs are already responding.', seconds: 14 },
  { page: 'simulator', replay: 'captured-retention', title: 'Watch it happen', text: 'A fictional assistant keeps pushing after the user says “No thanks”. MindMirror flags each tactic, highlights the exact words and tracks rising risk turn by turn.', seconds: 16 },
  { page: 'experiment', title: 'Context is the key', text: 'The same replies, judged alone and in context, from a single refusal up to full ten-turn conversations. Pressure after a refusal is only visible when the detector can see the refusal.', seconds: 16 },
  { page: 'compare', title: 'Try it live', text: 'One message goes to a respectful assistant and to a retention-optimised one. MindMirror scores both without knowing which is which.', seconds: 12 },
  { page: 'research', title: 'Transparent by design', text: 'A six-tactic taxonomy, exact evidence spans and an open risk formula. Every score is a model prediction that people can check, not a verdict.', seconds: 12 },
] as const

export default function PresentationTour({ step, onStep, onExit }: { step: number; onStep: (step: number) => void; onExit: () => void }) {
  const [playing, setPlaying] = useState(true)
  const [elapsed, setElapsed] = useState(0)
  const current = tourSteps[step]
  const last = step === tourSteps.length - 1
  useEffect(() => { setElapsed(0) }, [step])
  useEffect(() => {
    if (!playing) return
    const timer = setInterval(() => setElapsed(e => e + 0.1), 100)
    return () => clearInterval(timer)
  }, [playing])
  useEffect(() => {
    if (playing && elapsed >= current.seconds) { if (last) setPlaying(false); else onStep(step + 1) }
  }, [elapsed, playing, current.seconds, last, step, onStep])
  useEffect(() => {
    function key(e: KeyboardEvent) {
      if (e.key === 'Escape') onExit()
      else if (e.key === 'ArrowRight' && !last) onStep(step + 1)
      else if (e.key === 'ArrowLeft' && step > 0) onStep(step - 1)
      else if (e.key === ' ' && (e.target as HTMLElement)?.tagName !== 'TEXTAREA') { e.preventDefault(); setPlaying(p => !p) }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [step, last, onStep, onExit])

  return <div className="tour" role="dialog" aria-label="Presentation mode">
    <div className="tour-progress">{tourSteps.map((_, i) => <i key={i} className={i < step ? 'done' : ''}>{i === step && <em style={{ width: `${Math.min(100, elapsed / current.seconds * 100)}%` }} />}</i>)}</div>
    <div className="tour-body">
      <span className="tour-step">{String(step + 1).padStart(2, '0')} / {String(tourSteps.length).padStart(2, '0')}</span>
      <div><strong>{current.title}</strong><p>{current.text}</p></div>
      <div className="tour-controls">
        <button aria-label="Previous step" disabled={step === 0} onClick={() => onStep(step - 1)}><ArrowLeft size={15} /></button>
        <button aria-label={playing ? 'Pause' : 'Play'} onClick={() => setPlaying(p => !p)}>{playing ? <Pause size={15} /> : <Play size={15} />}</button>
        <button aria-label="Next step" disabled={last} onClick={() => onStep(step + 1)}><ArrowRight size={15} /></button>
        <button aria-label="Exit presentation" onClick={onExit}><X size={15} /></button>
      </div>
    </div>
  </div>
}
