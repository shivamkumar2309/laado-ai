# LAADO — Personal AI Assistant

A Jarvis-inspired desktop AI assistant with voice interaction, persistent memory, and real-time streaming responses.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-green)
![Groq](https://img.shields.io/badge/LLM-Groq%20%2F%20Llama%203.1-orange)

---

## Features

- **Voice-first interaction** — wake word, auto-listen, auto-dormant on silence
- **Single AI call decision engine** — one structured call decides intent, actions, and replies (no hardcoded keyword chains)
- **Persistent memory** — SQLite-backed, categorized facts (identity, preference, goal, mood), with automatic conversation summarization so context never gets lost
- **Real-time streaming** — AI responses appear word-by-word and are spoken sentence-by-sentence as they generate, not after the full reply completes
- **Dynamic web actions** — opens any website or YouTube search the user names, with no fixed site list
- **Jarvis-style UI** — animated sonar visualization, live activity log, built with PySide6

---

## Architecture

```
app.py            → entry point
start_screen.py    → animated splash / start screen
app_ui.py           → main UI (sonar widget, status panels, voice loop)
brain.py             → AI decision engine (Groq API, streaming, intent routing)
memory.py             → SQLite persistent memory (facts, profile, summaries)
listen.py              → microphone capture + speech-to-text + noise calibration
speak.py                 → text-to-speech (Edge TTS) with streaming sentence playback
```

### How a conversation turn works

```
listen()  →  brain.think()  →  speak() / UI stream
              │
              ├─ Fast JSON call: decides intent (chat/exit/open_site/youtube/recall/...)
              └─ If intent == "chat": second streaming call
                    → text shown live in UI
                    → sentences spoken as soon as they're complete
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/<your-username>/laado-ai.git
cd laado-ai
pip install -r requirements.txt
```

### 2. Get a free Groq API key

Sign up at [console.groq.com](https://console.groq.com) and create an API key (free tier, fast inference).

### 3. Configure your environment

```bash
cp .env.example .env
```

Edit `.env` and paste your key:

```
GROQ_API_KEY=your_actual_key_here
```

### 4. Set your microphone device

In `listen.py`, set `MIC_ID` to match your microphone's device index. List available devices with:

```python
import sounddevice as sd
print(sd.query_devices())
```

### 5. Run

```bash
python app.py
```

---

## Usage

- Click **INITIALIZE** to start
- Speak naturally — LAADO listens, thinks, and replies
- Say **"wake up"** to resume after LAADO goes dormant from silence
- Say **"open kahoot"**, **"play lo-fi music on youtube"**, etc. — sites and searches are resolved dynamically, not from a fixed list
- Say **"exit"**, **"quit"**, or **"band kar do"** to close the app
- Tell LAADO your name or preferences naturally — it remembers across sessions

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | PySide6 (Qt) |
| LLM | Groq API — Llama 3.1 8B Instant |
| Speech-to-Text | Google Speech Recognition |
| Text-to-Speech | Microsoft Edge TTS |
| Memory | SQLite |

---

## Roadmap

- [ ] Local Whisper STT (offline fallback)
- [ ] Voice interrupt support (barge-in while LAADO is speaking)
- [ ] Settings UI (mic selection, voice, personality tuning)
- [ ] Packaged installer (PyInstaller)

---

## License

MIT