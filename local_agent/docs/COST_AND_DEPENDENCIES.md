# Cost and Dependency Statement

## Cost

Total running cost of AI = Rs 0 / $0.

- No OpenAI API
- No Anthropic API / Claude Code subscription
- No Codex subscription
- No Gemini API
- No paid prospecting / enrichment API
- No cloud AI inference, no token billing

All model requests go through `llm.py -> ask()` which only calls `OLLAMA_URL` (localhost). You can check:
```
grep -rn "openai\|anthropic\|claude\|gemini" local_agent --include=*.py
```
returns nothing.

The original Harvey/Sellbird code in `sellbird/` still has Claude and Codex code (that is the original project), but `local_agent` does not import or run it.

Only cost is your own electricity / hardware :)

## Models

| Model | Used for | Licence |
|---|---|---|
| Qwen3 (1.7b / 4b / 8b / 14b) via Ollama | all text generation | Apache 2.0 |
| sentence-transformers/all-MiniLM-L6-v2 | embeddings | Apache 2.0 |

Note: I checked the licence on the model pages because not every open weight model is open source (for example Llama has its own community licence with conditions). Qwen3 dense models are Apache 2.0.

## Software / libraries

| Name | Used for | Licence |
|---|---|---|
| Ollama | local model server | MIT |
| Python | orchestration | PSF License |
| FastAPI | backend | MIT |
| Uvicorn | server | BSD-3-Clause |
| Pydantic (comes with FastAPI) | request models | MIT |
| SQLite | database | Public Domain |
| requests | http (ollama + scraping) | Apache 2.0 |
| python-dotenv | .env file | BSD-3-Clause |
| psutil | hardware detection | BSD-3-Clause |
| BeautifulSoup4 | html parsing | MIT |
| Scrapy | bulk crawling | BSD-3-Clause |
| Playwright (python) | JS websites | Apache 2.0 |
| sentence-transformers | embeddings | Apache 2.0 |
| PyTorch (installed by sentence-transformers) | embeddings backend | BSD-3-Clause |
| React + ReactDOM 18.3.1 | dashboard | MIT |
| @babel/standalone | JSX in browser | MIT |
| pytest | tests | MIT |
| Harvey / Sellbird (forked repo) | base project | AGPL-3.0 |

Because the base repo is AGPL-3.0, this fork is also AGPL-3.0.

## Services that need internet

| What | When | Paid? |
|---|---|---|
| ollama.com model download | once at setup | free |
| huggingface.co (embedding model) | once at setup | free |
| pypi (pip install) | once at setup | free |
| prospect websites | only when fetching new prospects | free, public pages only |

## Limitations

- Speed depends on the computer. On CPU only, running the full workflow for 4 prospects can take a few minutes.
- Small models (1.7b) sometimes return bad JSON, then the raw output is shown with `parse_error`.
- AI scores can change a bit between runs, that's why rules are mixed in.
- Prospect discovery (finding new companies) is not automated, you give a list of websites / json file. The scraper only reads pages of companies you give it.
- Sample prospects and replies are made up test data.
- Emails are not sent, only drafted.
- Rule based fallback is only keyword matching, it is much weaker than the AI.
- No login / user accounts on the dashboard, it is meant to run on your own machine.
