from typing import Dict
from .base import LLMProvider
from .config import LLMConfig
from .providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from .exceptions import ConfigurationError

class ProviderFactory:
    _cached_providers: Dict[str, LLMProvider] = {}
    
    @classmethod
    def create_provider(cls, config: LLMConfig) -> LLMProvider:
        """Create a new LLM provider instance from config."""
        provider_name = config.provider.lower()
        
        # Determine default model if not provided
        model = config.model
        if not model:
            if provider_name == "openai":
                model = "gpt-4o"
            elif provider_name == "anthropic":
                model = "claude-3-5-sonnet-20240620"
            elif provider_name == "gemini":
                model = "gemini-1.5-pro"
            else:
                raise ConfigurationError(f"Unsupported provider: {provider_name}")
                
        if provider_name == "openai":
            if not config.api_key:
                raise ConfigurationError("OpenAI API key is required but missing.")
            return OpenAIProvider(api_key=config.api_key, model=model)
        elif provider_name == "anthropic":
            if not config.api_key:
                raise ConfigurationError("Anthropic API key is required but missing.")
            return AnthropicProvider(api_key=config.api_key, model=model)
        elif provider_name == "gemini":
            if not config.api_key:
                raise ConfigurationError("Gemini API key is required but missing.")
            return GeminiProvider(api_key=config.api_key, model=model)
        else:
            raise ConfigurationError(f"Unsupported provider: {provider_name}")

    @classmethod
    def get_provider(cls, config: LLMConfig, use_cache: bool = True) -> LLMProvider:
        """Get or create cached provider instance based on config."""
        # Using api_key prefix to avoid exposing key in dict keys
        api_key_hash = hash(config.api_key) if config.api_key else ""
        cache_key = f"{config.provider}:{config.model or 'default'}:{api_key_hash}"
        
        if use_cache and cache_key in cls._cached_providers:
            return cls._cached_providers[cache_key]
            
        provider = cls.create_provider(config)
        if use_cache:
            cls._cached_providers[cache_key] = provider
        return provider
