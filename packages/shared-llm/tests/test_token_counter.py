from shared_llm.token_counter import TokenCounter

def test_token_counter_openai():
    counter = TokenCounter("openai", "gpt-4o")
    # Real tiktoken encoding should return correct token count
    tokens = counter.count_tokens("Hello world!")
    assert tokens > 0
    assert isinstance(tokens, int)

def test_token_counter_fallback():
    counter = TokenCounter("anthropic", "claude-3-sonnet-20240229")
    tokens = counter.count_tokens("Hello world!")
    # For "Hello world!" length is 12, fallback is max(1, 12 // 4) = 3
    assert tokens == 3

def test_token_counter_empty():
    counter = TokenCounter("openai", "gpt-4o")
    assert counter.count_tokens("") == 0
