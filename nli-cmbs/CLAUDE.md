# NLI-CMBS — Claude Code Project Instructions

## Project Overview
NLI-CMBS is an open-source tool that ingests SEC EDGAR ABS-EE CMBS filings (EX-102 XML exhibits), parses structured loan-level data, and generates AI-powered surveillance reports via the Anthropic API. Built with FastAPI, SQLAlchemy (async), PostgreSQL, and the Anthropic Python SDK.

## Architecture Quick Reference
```
nli_cmbs/
├── ai/              # Anthropic API client + prompt templates
│   ├── client.py    # AnthropicClient wrapper (AsyncAnthropic SDK)
│   ├── prompts.py   # System/user prompts for surveillance reports
│   └── exceptions.py
├── api/             # FastAPI endpoints
│   ├── endpoints/   # Route handlers
│   └── router.py
├── db/
│   ├── models.py    # SQLAlchemy ORM models (Deal, Loan, Filing, LoanSnapshot, Report, etc.)
│   ├── engine.py    # DB engine setup
│   └── session.py   # Async session factory
├── edgar/           # SEC EDGAR integration
│   ├── xml_parser.py  # Ex102Parser — parses ABS-EE XML into structured data
│   ├── client.py      # EDGAR HTTP client
│   ├── filing_fetcher.py
│   └── cik_resolver.py
├── schemas/         # Pydantic schemas
├── services/        # Business logic
│   ├── report_service.py   # Surveillance report generation + caching
│   ├── blurb_service.py    # Per-loan AI blurbs
│   ├── deal_service.py
│   ├── ingest_service.py
│   ├── metrics.py          # Deal-level computed metrics (WA DSCR, WA LTV, etc.)
│   └── backfill_service.py
├── cli.py           # CLI commands (resolve, scan, fetch-filing, etc.)
├── config.py        # Pydantic settings (ANTHROPIC_MODEL, DATABASE_URL, etc.)
└── main.py          # FastAPI app factory
```

## Key Conventions

### Database
- PostgreSQL with async SQLAlchemy (`asyncpg`)
- Alembic for migrations (run from `nli-cmbs/` directory)
- UUIDs as primary keys everywhere
- All timestamps use `func.now()` defaults

### AI Integration
- Anthropic Python SDK (`anthropic.AsyncAnthropic`), NOT raw HTTP
- Model configured via `settings.ANTHROPIC_MODEL` (currently `claude-sonnet-4-6`)
- Retry logic built into `AnthropicClient` for rate limits and server errors

### CLI
- Uses `python -m nli_cmbs.cli <command>` pattern
- Activate venv first: `source venv/bin/activate`

### Code Style
- `ruff` for linting and formatting
- Type hints everywhere (Python 3.11+ union syntax: `str | None`)
- Async/await throughout the stack

## Development Commands
```bash
# Activate environment
source venv/bin/activate

# Run linter
ruff check .

# Run tests (skip integration tests)
pytest tests/ -x --ignore=tests/test_integration.py -q

# Run migrations
alembic upgrade head

# Start server
uvicorn nli_cmbs.main:app --port 8001 --reload
```

## Important: Evaluation Infrastructure
The file `EVAL_INFRA_PROMPT.md` in the repo root contains detailed specs for adding evaluation/scoring infrastructure. This is the post-hackathon foundation work. See `.claude/commands/build-eval-infra.md` for the autonomous execution command.
