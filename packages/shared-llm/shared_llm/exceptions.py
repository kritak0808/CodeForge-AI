class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass

class RateLimitError(LLMProviderError):
    """Exception raised when API rate limits are hit."""
    pass

class TransientError(LLMProviderError):
    """Exception raised for transient issues like server overload or timeouts."""
    pass

class ConfigurationError(LLMProviderError):
    """Exception raised when there are configuration issues (e.g. missing API keys)."""
    pass
