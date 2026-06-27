import logging
import tiktoken

logger = logging.getLogger("shared-llm.token_counter")

class TokenCounter:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.encoder = None
        
        if provider == "openai":
            try:
                self.encoder = tiktoken.encoding_for_model(model)
            except Exception:
                try:
                    self.encoder = tiktoken.get_encoding("cl100k_base")
                except Exception as e:
                    logger.warning(f"Failed to initialize tiktoken for {model}: {e}")
        
    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.warning(f"Error encoding with tiktoken: {e}")
        
        # Fallback/Estimate for non-OpenAI or in case of errors
        # A general standard estimate is 4 characters per token
        return max(1, len(text) // 4)
