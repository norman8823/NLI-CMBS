#!/bin/bash
# Weekly CMBS news ingestion and digest generation
# Crontab: 0 8 * * 1 /path/to/nli-cmbs/scripts/weekly_news_cron.sh
#
# Runs every Monday at 8am:
#   1. Ingests new Trepp articles from the past 7 days
#   2. Generates a consolidated market digest

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

LOG_FILE="$PROJECT_DIR/logs/news-ingest-$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$PROJECT_DIR/logs"

echo "=== Trepp News Ingestion — $(date) ===" | tee -a "$LOG_FILE"

# Run via docker-compose if available, otherwise use local venv
if [ -f docker-compose.yml ] && command -v docker-compose &> /dev/null; then
    docker-compose exec -T app python -m nli_cmbs.cli ingest-news --days 7 2>&1 | tee -a "$LOG_FILE"
    docker-compose exec -T app python -m nli_cmbs.cli news-digest --days 7 2>&1 | tee -a "$LOG_FILE"
else
    source .venv/bin/activate 2>/dev/null || true
    python -m nli_cmbs.cli ingest-news --days 7 2>&1 | tee -a "$LOG_FILE"
    python -m nli_cmbs.cli news-digest --days 7 2>&1 | tee -a "$LOG_FILE"
fi

echo "=== Done — $(date) ===" | tee -a "$LOG_FILE"
