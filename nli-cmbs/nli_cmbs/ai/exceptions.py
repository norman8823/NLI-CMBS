class AIGenerationError(Exception):
    """Base class for AI generation failures."""


class AIRateLimitError(AIGenerationError):
    """Raised when the Anthropic API rate limit is hit."""


class AIContextLengthError(AIGenerationError):
    """Raised when the input exceeds the model's context length."""


class AITimeoutError(AIGenerationError):
    """Raised when the API request times out."""
