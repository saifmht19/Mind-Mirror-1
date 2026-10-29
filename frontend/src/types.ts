export type Speaker = 'user' | 'assistant'
export type Turn = { speaker: Speaker; text: string }
export type Tactic = 'guilt-tripping' | 'false-urgency' | 'flattery' | 'pressure-after-refusal' | 'fear-appeal' | 'dismissing-choice'
export type Span = { start: number; end: number; text: string }
export type TurnPrediction = { turn_index: number; tactics: Tactic[]; primary_tactic: Tactic | null; pressure: number; evidence: (Span & { tactic: Tactic })[]; explanation: string; refusal_before: boolean; refusal_turn_index: number | null }
export type Analysis = {
  prediction: { turns: TurnPrediction[]; refusals: { turn_index: number; refused: boolean; evidence: Span[]; explanation: string }[]; conversation_tactics: Tactic[]; escalating: boolean; explanation: string }
  computed: { timeline: { turn_index: number; pressure: number; risk: number; refusal_before: boolean }[]; risk_score: number; peak_risk: number; final_risk: number; escalating: boolean; max_pressure: number; refusal_pressure_onset: number | null; explanation: string }
  metadata: { model: string; detected_at: string; request_id: string; prompt_version: string; attempts: number; latency_ms: number }
}
export type Example = { id: string; title: string; description: string; turns: Turn[] }
export type DatasetRecord = { index: number; conversation_id: string | number; metadata: Record<string, unknown>; turns: Turn[]; error: string | null }
export type BatchResult = DatasetRecord & { status: 'success' | 'failed'; analysis?: Analysis; error: string | null }
