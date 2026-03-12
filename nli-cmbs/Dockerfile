FROM python:3.12-slim

WORKDIR /app

# Copy everything needed for the build
COPY pyproject.toml README.md ./
COPY nli_cmbs/ nli_cmbs/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "nli_cmbs.main:app", "--host", "0.0.0.0", "--port", "8000"]
