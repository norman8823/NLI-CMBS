from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://nli:nli@localhost:5432/nli_cmbs"
    EDGAR_USER_AGENT: str = "NLIntelligence/1.0 (contact@nlintelligence.com)"
    EDGAR_BASE_URL: str = "https://data.sec.gov"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 4096
    ANTHROPIC_TIMEOUT: int = 120

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
