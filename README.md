# Unified Dashboard — AutoLearnCS + AutoJob Broadcast

One Flask app, two powerful tools:
- **AutoLearnCS** (`/`) — DSA slide generator + Instagram publisher
- **AutoJob Bot** (`/jobs`) — Real-time job scraper → AI processor → Telegram broadcaster

---

## 📁 Folder Structure

```
unified_project/
│
├── app.py                          ← Unified Flask entry point (run this)
├── requirements.txt
├── .env.example                    ← Copy to .env and fill credentials
│
├── job_module/                     ← AutoJob backend
│   ├── __init__.py
│   ├── config.py                   ← All job bot settings
│   ├── scraper.py                  ← Multi-source scraper (Naukri, LinkedIn, Indeed, etc.)
│   ├── ai_processor.py             ← GPT-3.5 job structuring
│   ├── deduplicator.py             ← Cross-run deduplication
│   ├── formatter.py                ← Telegram message formatter
│   ├── telegram_sender.py          ← Telegram Bot API sender
│   ├── logger.py                   ← Shared logger
│   ├── main_job.py                 ← Pipeline orchestrator
│   ├── scheduler.py                ← APScheduler wrapper
│   └── seen_jobs.json              ← Auto-generated dedup history
│
├── modules/                        ← AutoLearnCS backend (your existing modules)
│   ├── __init__.py
│   ├── generator.py                ← Slide content generator (OpenAI)
│   ├── slide_dispatcher.py         ← Routes topics to correct generator
│   ├── slide_builder.py            ← Renders slides to PNG images
│   ├── insta_poster.py             ← Instagram posting (instagrapi)
│   ├── pinterest_agent.py          ← Pinterest image fetcher
│   ├── topic_tracker.py            ← Topic scheduling state
│   └── scheduler.py                ← AutoLearnCS post scheduler
│
├── utils/                          ← Shared utilities
│   ├── __init__.py
│   ├── logger.py                   ← App-wide logger
│   └── helpers.py                  ← sanitize_filename, ensure_dir, etc.
│
├── templates/
│   ├── index.html                  ← AutoLearnCS dashboard
│   └── jobs.html                   ← AutoJob dashboard
│
└── static/
    └── posts/                      ← Generated slide images (auto-created)
```

---

## 🚀 Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Copy your existing modules
Place your existing AutoLearnCS files into `modules/` and `utils/`:
```
modules/generator.py
modules/slide_dispatcher.py
modules/slide_builder.py
modules/insta_poster.py
modules/pinterest_agent.py
modules/topic_tracker.py
modules/scheduler.py
utils/logger.py
utils/helpers.py
```

### 4. Run
```bash
python app.py
```

- AutoLearnCS: http://localhost:5000/
- AutoJob Bot:  http://localhost:5000/jobs

---

## 🌐 Job Sources Supported

| Source | Location Filter | Experience Filter | Notes |
|--------|----------------|-------------------|-------|
| **Naukri.com** | ✅ India cities | ✅ Years range | Best for India jobs |
| **LinkedIn India** | ✅ Any city | ✅ Extracted from JD | Global reach |
| **Indeed India** | ✅ India + global | ✅ Level-based | Large volume |
| **RemoteOK** | Remote only | ❌ | Remote-focused |
| **WeWorkRemotely** | Remote only | ❌ | Remote-focused |

### Example search queries
- Query: `Python Developer`, Location: `Bangalore`, Experience: `2-5`
- Query: `React Frontend`, Location: `Remote`, Experience: `1-3`
- Query: `Data Scientist`, Location: `Mumbai`, Experience: `3+`

---

## 🔑 Required API Keys

| Key | Used For | Where to Get |
|-----|----------|--------------|
| `OPENAI_API_KEY` | AI job structuring | platform.openai.com |
| `TELEGRAM_BOT_TOKEN` | Sending job alerts | @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Your channel/group | Channel username or ID |
| `IG_USERNAME` / `IG_PASSWORD` | Instagram posting | Your IG credentials |
