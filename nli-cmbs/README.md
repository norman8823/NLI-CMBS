# NLI-CMBS

Free CMBS loan monitoring and data API for CRE professionals.
Search by deal ticker, property, or borrower. Built on public SEC EDGAR filings.

## Who is this for?

- **Mezz lenders** monitoring senior CMBS debt performance
- **Debt brokers** doing due diligence on CMBS deals
- **Special servicers** tracking loan-level delinquency and advances
- **CRE developers** needing a clean API for CMBS loan data

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/nlintelligence/nli-cmbs.git
cd nli-cmbs
cp .env.example .env
pip install -e ".[dev]"

# 2. Start PostgreSQL
docker-compose up -d

# 3. Run migrations (creates 6 tables)
alembic upgrade head

# 4. Seed known CMBS depositor CIKs
python -m nli_cmbs.cli seed-cik-mappings

# 5. Scan a deal — resolves CIK, fetches filing, downloads EX-102 XML
python -m nli_cmbs.cli scan "BMARK 2024-V6"
```

## CLI Commands

```bash
# Resolve a deal ticker to its SEC EDGAR CIK
python -m nli_cmbs.cli resolve "BBCMS 2023-C20"

# Fetch the latest ABS-EE filing for a deal
python -m nli_cmbs.cli fetch-filing "BMARK 2024-V6"

# Full scan: resolve + fetch + download EX-102 XML
python -m nli_cmbs.cli scan "BMARK 2024-V6"

# Seed depositor CIK mappings from built-in data
python -m nli_cmbs.cli seed-cik-mappings

# Check API health
python -m nli_cmbs.cli health
```

## API

Start the API server:

```bash
uvicorn nli_cmbs.main:app --reload
```

Endpoints:
- `GET /health` — Health check
- `GET /deals` — List all deals
- `GET /deals/{id}` — Get deal by ID
- `GET /deals/{ticker}/loans` — List loans for a deal
- `GET /loans/search?property_name=...&borrower_name=...` — Search loans

Swagger docs at `http://localhost:8000/docs`.

## Testing

```bash
# Unit tests (no network, no database)
pytest tests/ -v

# Integration tests (hits live EDGAR + requires PostgreSQL)
pytest -m integration tests/test_integration.py -v -s
```

## Architecture

1. **CIK Resolution** — 3-strategy pipeline: DB lookup (Kaggle-seeded) → EDGAR full-text search → depositor CIK traversal
2. **Filing Fetcher** — Finds ABS-EE filings and locates EX-102 XML exhibits via SEC EDGAR
3. **Loan Parser** — Extracts loan-level data from EX-102 XML (coming in Phase 2)
4. **API** — FastAPI endpoints for deal/loan queries and watchlist alerts

## License

MIT
