# News Sentiment API

A FastAPI backend that fetches live news articles, scores their sentiment (positive / negative / neutral), and stores the results for querying and analytics.

## What it does

1. **Fetch** — pulls live articles for a search query from [NewsAPI](https://newsapi.org)
2. **Analyze** — runs each article's text through a sentiment scorer (VADER) to get a label and score
3. **Store** — saves new articles to a local database, skipping duplicates by URL
4. **Serve** — exposes REST endpoints to list saved articles and view aggregate sentiment stats

## Tech stack

- **FastAPI** — web framework and routing
- **SQLAlchemy** — ORM / database layer
- **SQLite** — local file-based database (`news.db`, created automatically on first run)
- **VaderSentiment** — rule-based sentiment scoring (no ML model download required)
- **Pydantic / pydantic-settings** — request validation and environment config
- **Pytest** — test suite

## Project structure

```
news_sentiment_project/
├── .env                    # your local secrets (NEVER commit this)
├── .env.example            # template showing what variables are needed
├── requirements.txt
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── core/
│   │   ├── config.py         # loads .env into a typed settings object
│   │   └── database.py       # SQLAlchemy engine + session setup
│   ├── models/
│   │   └── article_model.py  # database table definition
│   ├── schemas/
│   │   └── article_schema.py # request/response validation shapes
│   ├── services/
│   │   ├── news_service.py   # talks to NewsAPI
│   │   └── ml_service.py     # runs sentiment analysis
│   └── api/v1/
│       ├── endpoints.py      # route handlers
│       └── router.py         # combines routes
└── tests/
    └── test_api.py
```

## Data flow

How a request travels through the system, end to end:

```
┌──────────┐     POST /api/v1/fetch      ┌─────────────────┐
│  Client  │ ──────────────────────────> │   endpoints.py   │
│ (Swagger │                              │  (route handler) │
│  / app)  │                              └────────┬──────────┘
└──────────┘                                       │
                                                    │ 1. calls
                                                    ▼
                                         ┌──────────────────────┐
                                         │   news_service.py     │
                                         │  fetch_articles(query) │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 2. HTTP GET
                                                    ▼
                                         ┌──────────────────────┐
                                         │   NewsAPI.org          │
                                         │   /v2/everything       │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 3. raw articles (JSON)
                                                    ▼
                                         ┌──────────────────────┐
                                         │   endpoints.py         │
                                         │   loops over articles  │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 4. for each article's text
                                                    ▼
                                         ┌──────────────────────┐
                                         │   ml_service.py        │
                                         │  analyze(text)          │
                                         │  -> (label, score)     │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 5. label + score attached
                                                    ▼
                                         ┌──────────────────────┐
                                         │  article_model.py       │
                                         │  (Article ORM object)   │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 6. db.add() + db.commit()
                                                    ▼
                                         ┌──────────────────────┐
                                         │   news.db (SQLite)      │
                                         │   articles table         │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 7. saved rows returned
                                                    ▼
                                         ┌──────────────────────┐
                                         │  article_schema.py      │
                                         │  (ArticleResponse)      │
                                         └──────────┬───────────┘
                                                    │
                                                    │ 8. JSON response
                                                    ▼
                                              back to Client
```

**Read paths** (`GET /articles`, `GET /analytics`) are simpler — they skip steps 1–6 entirely and go straight from `endpoints.py` to `news.db` via SQLAlchemy, then back out through the matching schema:

```
Client → GET /api/v1/articles → endpoints.py → database.py (get_db session)
        → query Article table in news.db → serialize via ArticleResponse → Client
```

**Why it's split this way:**
- `news_service.py` never touches the database, and `article_model.py` never talks to NewsAPI — each file has exactly one job.
- `ml_service.py` doesn't know where the text came from or where the result is going; it just takes text and returns a label + score. That's what makes it swappable for a different model later.
- `endpoints.py` is the only place that coordinates the whole sequence — everything else is a building block it calls in order.

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
source venv/bin/activate         # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
copy .env.example .env           # Windows
cp .env.example .env             # Mac/Linux
# then open .env and fill in your own NEWS_API_KEY (free from newsapi.org)
```

## Run

```bash
uvicorn src.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** for the interactive API docs (Swagger UI), where every endpoint can be tested directly in the browser.

## Endpoints

| Method | Path                  | Description                                                        |
|--------|-----------------------|----------------------------------------------------------------------|
| GET    | `/`                    | Health check                                                        |
| POST   | `/api/v1/fetch`        | Fetch articles for a search query, score sentiment, save new ones   |
| GET    | `/api/v1/articles`     | List saved articles, optional `sentiment` filter (positive/negative/neutral) |
| GET    | `/api/v1/analytics`    | Aggregate counts by sentiment + average sentiment score              |

**Example request body for `/fetch`:**
```json
{
  "query": "technology",
  "page_size": 10
}
```

## Running tests

```bash
pytest
```

## Notes

- Get a free `NEWS_API_KEY` at [newsapi.org](https://newsapi.org) — the free tier is for local/development use.
- The database is SQLite by default (`news.db`, created automatically). To switch to Postgres instead, change `DATABASE_URL` in `.env` and remove the SQLite-specific `connect_args` logic in `src/core/database.py`.
- `Base.metadata.create_all()` auto-creates tables on startup for convenience — for a production setup, use a migration tool like Alembic instead.
- Sentiment scoring uses VADER, a rule-based analyzer — no model download needed. The `ml_service.py` interface (`analyze(text) -> (label, score)`) is designed so it can be swapped for a trained model later without touching any other file.