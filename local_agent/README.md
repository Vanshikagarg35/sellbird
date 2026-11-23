# Local Sales Agent (Harvey fork)

This is my submission for the local AI sales agent assignment. I forked Harvey (now called Sellbird) and added a new folder `local_agent/` which runs fully on local AI using Ollama + Qwen3. No OpenAI / Claude / Gemini or any paid API is used.

The original Harvey code uses Claude Code CLI or Codex for the AI part, so I did not use that part. The `local_agent` folder does not import anything from the `sellbird/` package, it is a separate app. I used Harvey's ideas (signals, ICP, writer, reply handler). Dashboard is made in React.

## What it does

- Add multiple products (example: TaskNest has 2 products - BookEasy and StockSaathi)
- Business profile generation from a local company info file
- ICP generation for each product separately
- Prospect research from already downloaded website text
- Buying signal classification
- Problem statement for each prospect
- Prospect scoring (AI score + simple rules)
- Personalised cold email
- Reply classification (sample replies given in `data/sample_replies.json`)
- Hardware detection and model recommendation
- If Ollama is down -> error shown, task goes to queue, rule based output where possible

## Setup

Needs Python 3.10 or above

1. Install Ollama from https://ollama.com/download

2. Pull the model (pick one according to your RAM, the app also tells you which one in the status box)
```
ollama pull qwen3:4b
```
For low RAM (< 12GB) use `qwen3:1.7b`, for 32GB RAM or GPU use `qwen3:8b`.

3. Install python packages
```
cd local_agent
python -m venv venv
venv\Scripts\activate      (windows)
source venv/bin/activate   (linux/mac)
pip install -r requirements.txt
playwright install chromium   (only needed for JS websites)
```

4. Download the embedding model once (needs internet one time)
```
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

5. Copy `.env.example` to `.env` (no keys needed). After step 4 is done set `HF_HUB_OFFLINE=1` so embeddings don't try to go online

6. Load sample data
```
python seed.py
```

7. Run
```
uvicorn app:app --port 8000
```
Open http://localhost:8000

## Demo flow

1. Check the status box - ollama running, model, hardware
2. Select product (BookEasy)
3. Generate business profile -> Generate ICP
4. Load prospects
5. For each prospect click Research -> Signals -> Problem -> Score -> Email (or click "Run full workflow for all")
6. Reply classification - load sample replies, click use, classify
7. Show logs at bottom (logs/llm_calls.log)
8. Switch product to StockSaathi and do same, ICP will be different

## Offline test

After setup, turn off wifi and run:
```
ollama serve        (if not already running)
python offline_test.py
```
This script blocks every connection which is not localhost, so if something tries to go to internet the test fails. All 8 workflows should PASS. You can also use the dashboard with wifi off.

## Getting new prospects (needs internet)

Web research is separate from the AI part (`research/` folder).
- `python import_data.py fetch` - fetches website text for prospects that have no text yet (requests + BeautifulSoup)
- Scrapy spider for many sites: `scrapy runspider research/company_spider.py -a urls_file=urls.txt -o data/prospects/crawled.json`
- Playwright is used if a site needs javascript

After fetching, everything is saved in SQLite so AI part works offline.

## Tests
```
pytest tests
```

## Folder structure
```
local_agent/
  app.py            fastapi routes
  workflows.py      all 8 AI workflows
  llm.py            ollama calls + logging (only local)
  rules.py          non-AI fallback logic
  embed.py          sentence transformers
  hardware.py       RAM/CPU/GPU detection
  database.py       sqlite
  import_data.py    load prospects
  seed.py           sample products
  offline_test.py   offline acceptance test
  research/         web scraping (internet needed)
  static/           dashboard (React, files in static/lib so no internet needed)
  data/             sample company info, prospects, replies
  docs/             technical documentation
```

More details in `docs/TECHNICAL_DOCUMENTATION.md` and `docs/COST_AND_DEPENDENCIES.md`.
