import { ArrowRight, Bot, ExternalLink, EyeOff, FileSearch, Gauge, Landmark, MessageSquareWarning, ScanLine, Scale } from 'lucide-react'

// Every figure on this page must stay traceable to a public source listed in `sources`.
const stats = [
  { value: '37%+', label: 'of goodbyes in popular AI companion apps were met with at least one manipulation tactic', source: 1 },
  { value: 'Up to 14×', label: 'more engagement after users said goodbye when those tactics were used in experiments', source: 1 },
  { value: '5 of 6', label: 'popular companion apps studied used manipulative tactics at the moment of farewell', source: 1 },
  { value: '7', label: 'major AI companies ordered by the US FTC to explain how they test companion chatbots for harm', source: 2 },
]
const timeline = [
  { date: 'Sep 2022', title: 'FTC documents “dark patterns”', text: 'A US Federal Trade Commission staff report catalogues design tricks that push people into choices they would not otherwise make, such as fake urgency and hard-to-cancel subscriptions.', source: 3 },
  { date: 'Feb 2025', title: 'EU AI Act bans manipulative AI', text: 'Article 5 prohibits AI systems that use purposefully manipulative or deceptive techniques to materially distort behaviour and cause significant harm. The EU Digital Services Act already bans dark patterns on online platforms.', source: 4 },
  { date: 'Apr 2025', title: 'ChatGPT update rolled back', text: 'OpenAI reversed a GPT-4o update after it became overly sycophantic. OpenAI said it validated doubts and urged impulsive actions, and flagged emotional over-reliance as a safety concern.', source: 5 },
  { date: 'May 2025', title: '€5 million fine for Replika’s developer', text: 'Italy’s data protection authority fined Luka Inc., maker of the Replika companion chatbot, for GDPR violations including missing age verification.', source: 6 },
  { date: 'May 2025', title: 'Companion-chatbot lawsuit proceeds', text: 'A US federal judge allowed a wrongful-death lawsuit against Character.AI and Google to move forward, treating the chatbot as a product whose design can be challenged.', source: 7 },
  { date: 'Sep 2025', title: 'FTC inquiry into AI companions', text: 'The FTC issued orders to Alphabet, Character.AI, Instagram, Meta, OpenAI, Snap and xAI about how they measure and limit harms, especially to children and teens.', source: 2 },
]
const gaps = [
  { icon: MessageSquareWarning, title: 'Manipulation hides across turns', text: 'A single message can look harmless. Its meaning changes after the user has already said “no”. Message-by-message filters miss that.' },
  { icon: EyeOff, title: 'Black-box scores cannot be audited', text: 'A risk number without evidence cannot be checked by a user, a developer or a regulator.' },
  { icon: Scale, title: 'Laws need measurement', text: 'Regulators now prohibit manipulative design, but enforcing that requires tools that can detect and document it.' },
]
const steps = [
  { icon: Bot, title: 'Simulate', text: 'A local model plays a realistic assistant in fictional retention scenarios, alongside a respectful control.' },
  { icon: FileSearch, title: 'Detect', text: 'Each reply is judged in the context of the whole conversation, across six tactics and a 0–3 pressure scale.' },
  { icon: ScanLine, title: 'Explain', text: 'Every finding is tied to the exact words that support it, so anyone can verify it.' },
  { icon: Gauge, title: 'Measure', text: 'A transparent running-risk formula tracks escalation, especially pressure after a refusal.' },
]
const sources = [
  { title: 'De Freitas, Oğuz-Uğuralp & Uğuralp, “Emotional Manipulation by AI Companions”, Harvard Business School working paper (2025); Harvard Gazette coverage', url: 'https://www.library.hbs.edu/working-knowledge/how-ai-chatbots-try-to-keep-you-from-walking-away' },
  { title: 'US Federal Trade Commission, “FTC Launches Inquiry into AI Chatbots Acting as Companions” (11 Sep 2025)', url: 'https://www.ftc.gov/news-events/news/press-releases/2025/09/ftc-launches-inquiry-ai-chatbots-acting-companions' },
  { title: 'US Federal Trade Commission staff report, “Bringing Dark Patterns to Light” (Sep 2022)', url: 'https://www.ftc.gov/system/files/ftc_gov/pdf/P214800%20Dark%20Patterns%20Report%209.14.2022%20-%20FINAL.pdf' },
  { title: 'Regulation (EU) 2024/1689 (AI Act), Article 5; Regulation (EU) 2022/2065 (Digital Services Act), Article 25', url: 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj' },
  { title: 'OpenAI, “Expanding on what we missed with sycophancy” (May 2025)', url: 'https://openai.com/index/expanding-on-sycophancy/' },
  { title: 'European Data Protection Board, “AI: the Italian Supervisory Authority fines company behind chatbot Replika” (2025)', url: 'https://www.edpb.europa.eu/news/national-news/2025/ai-italian-supervisory-authority-fines-company-behind-chatbot-replika_en' },
  { title: 'Associated Press via WUSF, “Judge rejects that AI chatbots have free speech rights” (22 May 2025)', url: 'https://www.wusf.org/courts-law/2025-05-22/in-lawsuit-over-orlando-teens-suicide-judge-rejects-that-ai-chatbots-have-free-speech-rights' },
]

function Ref({ n }: { n: number }) { return <a className="cite" href={`#source-${n}`} aria-label={`Source ${n}`}>[{n}]</a> }

export default function WhyItMatters({ onNavigate }: { onNavigate: (page: string) => void }) {
  return <div className="why-page">
    <section className="why-hero">
      <div className="eyebrow"><span /> THE PROBLEM</div>
      <h1>AI assistants are learning to<br /><em>keep us talking.</em></h1>
      <p>Assistants tuned for engagement can nudge people with flattery, false urgency and guilt, most often at the moment someone tries to leave. These patterns are subtle, spread across several turns, and invisible to message-by-message filters. MindMirror makes them visible, with evidence.</p>
      <div className="why-actions"><button className="primary" onClick={() => onNavigate('simulator')}>See it happen live <ArrowRight size={15} /></button><button className="secondary" onClick={() => onNavigate('analyzer')}>Analyze a conversation</button></div>
    </section>

    <div className="why-stats">{stats.map(s => <section key={s.value} className="panel why-stat"><strong>{s.value}</strong><p>{s.label} <Ref n={s.source} /></p></section>)}</div>

    <div className="section-heading"><h2><Landmark size={16} /> It is already happening</h2><span>REGULATORS, COURTS AND AI LABS</span></div>
    <ol className="why-timeline">{timeline.map(t => <li key={t.title}><time>{t.date}</time><div><strong>{t.title}</strong><p>{t.text} <Ref n={t.source} /></p></div></li>)}</ol>

    <div className="section-heading"><h2><EyeOff size={16} /> The gap</h2><span>WHY EXISTING SAFEGUARDS FALL SHORT</span></div>
    <div className="why-gaps">{gaps.map(g => <section key={g.title} className="panel why-gap"><g.icon size={20} /><strong>{g.title}</strong><p>{g.text}</p></section>)}</div>

    <div className="section-heading"><h2><ScanLine size={16} /> How MindMirror answers it</h2><span>SIMULATE · DETECT · EXPLAIN · MEASURE</span></div>
    <div className="why-steps">{steps.map((s, i) => <section key={s.title} className="panel why-step"><span className="step-no">0{i + 1}</span><s.icon size={20} /><strong>{s.title}</strong><p>{s.text}</p></section>)}</div>

    <section className="panel why-sources"><h2>Sources</h2><ol>{sources.map((s, i) => <li key={s.url} id={`source-${i + 1}`}><a href={s.url} target="_blank" rel="noreferrer">{s.title} <ExternalLink size={11} /></a></li>)}</ol><small>MindMirror's own results are model predictions on synthetic, fictional conversations. The statistics above come from the cited external research, not from MindMirror.</small></section>
  </div>
}
