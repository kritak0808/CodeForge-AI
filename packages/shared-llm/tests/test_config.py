from shared_llm.config import LLMConfig

def test_config_parsing():
    config = LLMConfig(
        provider="openai",
        api_key="test-key",
        model="gpt-4o",
        temperature=0.5,
        max_tokens=2048,
        fallback_provider="gemini",
        extra_kwargs={"top_p": 0.9}
    )
    assert config.provider == "openai"
    assert config.api_key == "test-key"
    assert config.model == "gpt-4o"
    assert config.temperature == 0.5
    assert config.max_tokens == 2048
    assert config.fallback_provider == "gemini"
    assert config.extra_kwargs == {"top_p": 0.9}
