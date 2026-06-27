import pytest
from shared_llm.config import LLMConfig
from shared_llm.factory import ProviderFactory
from shared_llm.providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from shared_llm.exceptions import ConfigurationError

def test_factory_openai():
    config = LLMConfig(provider="openai", api_key="sk-test", model="gpt-4o")
    provider = ProviderFactory.get_provider(config, use_cache=False)
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4o"

def test_factory_anthropic():
    config = LLMConfig(provider="anthropic", api_key="ant-test", model="claude-3-5-sonnet-20240620")
    provider = ProviderFactory.get_provider(config, use_cache=False)
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-3-5-sonnet-20240620"

def test_factory_gemini():
    config = LLMConfig(provider="gemini", api_key="gem-test", model="gemini-1.5-pro")
    provider = ProviderFactory.get_provider(config, use_cache=False)
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-1.5-pro"

def test_factory_missing_key():
    config = LLMConfig(provider="openai", api_key="", model="gpt-4o")
    with pytest.raises(ConfigurationError):
        ProviderFactory.get_provider(config, use_cache=False)

def test_factory_caching():
    config1 = LLMConfig(provider="openai", api_key="sk-test-key", model="gpt-4o")
    config2 = LLMConfig(provider="openai", api_key="sk-test-key", model="gpt-4o")
    
    p1 = ProviderFactory.get_provider(config1, use_cache=True)
    p2 = ProviderFactory.get_provider(config2, use_cache=True)
    assert p1 is p2
