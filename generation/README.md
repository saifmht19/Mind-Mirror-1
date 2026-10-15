# MindMirror Synthetic Dataset Generation Pipeline (`generation/`)

This directory generates multi-turn and single-turn conversational benchmark datasets mapped to the **MindMirror Manipulation Taxonomy (0–5)**.

---

## 🛠 Features

- **Multi-Backend Support**:
  - `offline`: Parameterized scenario templates across 6 domains (zero API key needed).
  - `gemini`: Google Gemini API (`gemini-1.5-flash` or `gemini-2.0-flash`).
  - `openai`: OpenAI API or any OpenAI-compatible server (Groq, DeepSeek, or local Ollama).
- **Taxonomy Adherence**: Strictly enforces single-tactic dominance and context requirements (e.g. prior user refusal for Tactic 5).
- **Deduplication**: Automatic SHA-256 normalized text hashing.
- **Stratified Dataset Splitting**: Outputs `train.jsonl` (70%), `val.jsonl` (15%), and `test.jsonl` (15%) with balanced tactic representation.

---

## 🚀 How to Run

### 1. Offline Mode (Instant, No API Key Required)
```bash
python generation/generator.py --provider offline --samples-per-tactic 20
```

### 2. Using Google Gemini API
Set your key:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your-gemini-api-key"
```
Run generation:
```bash
python generation/generator.py --provider gemini --samples-per-tactic 25 --model gemini-1.5-flash
```

### 3. Using OpenAI / OpenAI-Compatible Endpoints
Set your key:
```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-openai-api-key"
```
Run generation:
```bash
python generation/generator.py --provider openai --samples-per-tactic 25 --model gpt-4o-mini
```

### 4. Using Local Ollama (Free, Local LLM)
```bash
python generation/generator.py --provider openai --base-url "http://localhost:11434/v1" --model "llama3" --samples-per-tactic 15
```

---

## 📂 Output Locations

- **Full Dataset**: `data/generated/synthetic_dataset.json` and `.jsonl`
- **Stratified Splits**:
  - `data/splits/train.jsonl` (70%)
  - `data/splits/val.jsonl` (15%)
  - `data/splits/test.jsonl` (15%)
