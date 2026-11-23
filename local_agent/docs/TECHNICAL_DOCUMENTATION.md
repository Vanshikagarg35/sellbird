# Technical Documentation

## 1. Architecture

```
  Browser (React dashboard - static/index.html + app.jsx)
          |
          v
  FastAPI (app.py)  ----->  SQLite (data/sales_agent.db)
          |
          v
  workflows.py  ---- rules.py (non AI fallback)
          |      \
          |       embed.py (sentence-transformers, local)
          v
  llm.py  ----->  Ollama on localhost:11434  ----> qwen3 model (on your computer)


  research/ (separate, needs internet)
  scraper.py / company_spider.py / playwright_fetch.py  ---> saves page text into SQLite
```

There are 2 separate parts:

**Local AI part** - `llm.py`, `workflows.py`, `embed.py`. All model calls go through one function `llm.ask()` which only sends request to `OLLAMA_URL` (default http://localhost:11434). There is no other AI client in the code.

**Web research part** - `research/` folder. This only downloads public website text (home/about/careers pages) and checks robots.txt. It does not call any AI. The text is stored in the `prospects.page_text` column, after that the AI part reads it from db so it works offline.

## 2. Workflows

| Workflow | Function | Output |
|---|---|---|
| Business profile | `business_profile()` | summary, value prop, features, target market, tone (from local company info txt file) |
| ICP | `generate_icp()` | industries, size, roles, pain points, buying signals - separate for every product |
| Research | `research_prospect()` | what they do, current process, facts for personalisation. Uses embeddings to pick most relevant parts of website text first because small models have small context |
| Buying signals | `classify_signals()` | list of signals with evidence. If the evidence is not actually present in the text the signal is removed (small models sometimes make up things) |
| Problem statement | `problem_statement()` | 2-3 sentences |
| Scoring | `score_prospect()` | 0-100. final = 60% AI score + 40% rule score. Score >= 60 is marked qualified |
| Email | `write_email()` | subject + body, under 120 words |
| Reply classification | `classify_reply()` | interested / not_interested / objection / out_of_office / referral / unsubscribe / unclear + suggested action |

Most prompts ask for JSON and we use ollama's `format: "json"` option. For scoring, problem statement and email a JSON schema is passed in `format` (ollama structured outputs) because the 4b model was sometimes returning the ICP json back instead of a score, and in plain text mode it was writing its whole thinking in the problem statement.

Qwen3 has a thinking mode. `"think": false` alone was not enough on my setup (it was writing "Okay, the user wants..." and taking 2-3 min), so `/no_think` is also added at the end of every prompt. Any `<think>` tags are removed from output. If ollama stops a reply with "token repeat limit" the call is tried once more with lower temperature.

## 3. Multi product

Products are stored in `products` table. Business profile, ICP and prospects are all linked with `product_id`, so every product has its own ICP and its own prospect list. Example data has 2 products from same company (BookEasy - booking software, StockSaathi - inventory software) and one company (Sharma Hardware) is a prospect for both products, but gets different score.

## 4. Local model setup and model selection

`hardware.py` detects RAM (psutil), CPU cores, and GPU (nvidia-smi for NVIDIA, Apple Silicon detected from platform). Then:

| Condition | Model | Profile | Download size (approx) |
|---|---|---|---|
| NVIDIA GPU with 10GB+ VRAM | qwen3:14b | high-performance | ~9 GB |
| GPU with 6GB+ VRAM or 32GB+ RAM | qwen3:8b | high-performance | ~5 GB |
| 12GB+ RAM (normal laptop) | qwen3:4b | standard | ~2.5 GB |
| less than 12GB RAM | qwen3:1.7b | low-memory | ~1.4 GB |

GPU is not required. On CPU only, 4b takes around 10-40 sec per request depending on the laptop.
You can override with `MODEL_NAME` in `.env` or change it from the dashboard dropdown (only models that are already pulled are shown).

Embeddings: `all-MiniLM-L6-v2` (about 90MB) via sentence-transformers. Downloaded once to the huggingface cache. If it is not available, the code uses simple word overlap instead (and prints a message).

## 5. Hardware requirements

Minimum (standard config): 8GB RAM (with qwen3:1.7b), 5GB free disk, any 64 bit CPU.
Recommended: 16GB RAM for qwen3:4b.
High performance: 32GB RAM or NVIDIA GPU 6GB+ for qwen3:8b / 14b.

## 6. Offline behaviour

After installing packages, pulling the model and downloading the embedding model, internet is not needed for:
business profile, ICP, research from saved data, signals, problem statement, scoring, emails, reply classification.

Internet is needed only for: installing, pulling models, and fetching new prospect websites (`research/`).

`offline_test.py` patches python's socket so any non-localhost connection raises an error, then runs all 8 workflows. So if any hidden call to internet happens the test will fail.

## 7. Failure handling

- If Ollama is not running / model not pulled: `llm.ask()` raises `OllamaDown`. There is no fallback to any cloud API.
- The dashboard status box shows a red message (for example "Ollama is not running... Start it with: ollama serve" or "Model qwen3:4b is not downloaded. Run: ollama pull qwen3:4b").
- The failed task is saved in `task_queue` table with status pending. Button "Process queued tasks" runs them again when ollama is back.
- Rule based (non LLM) output is given where it is possible: buying signals (keyword match), scoring (points for industry/size/role/signals), reply classification (keywords). These are marked with `source: rule_based` so it is clear it is not AI output.
- Business profile, ICP, problem statement and email need the LLM so they just show error + get queued.

## 8. Logs

Every model call is written in `logs/llm_calls.log`:
```
[2026-11-20 14:02:11] OK task=icp model=qwen3:4b url=http://localhost:11434 time=21.4s prompt_tokens=412 output_tokens=233 cost=$0
[2026-11-20 14:05:40] FAILED task=email model=qwen3:4b reason=ollama not reachable at http://localhost:11434
```
The logs can also be seen in the dashboard (bottom section). The token counts are from ollama response, only for info.

## 9. Main decisions

- Made a separate `local_agent` folder instead of changing Harvey's `sellbird` package, because the original code is very big and is built around Claude CLI / Codex subprocess. Changing all of it in the given time was risky, so a smaller separate app was simpler and easier to prove that no cloud AI is used.
- Used plain sqlite3 instead of an ORM, the data is small.
- Dashboard is React. React, ReactDOM and Babel files are kept in `static/lib/` (not CDN) so the page also opens without internet, and no npm build step is needed.
- Rule score mixed with AI score because small model scores were not very consistent between runs.
- Evidence check for buying signals to reduce made up signals.

## 10. Mocked / simulated parts

- Prospect data in `data/prospects/sample_prospects.json` is made up sample data (fake companies on `.test` domains), it is used as "previously downloaded data". The scraper works on real websites but the demo uses this file.
- Sample replies are also written by me for testing, they are not real emails.
- Emails are only generated and saved, they are not sent (sending was not part of this assignment).
