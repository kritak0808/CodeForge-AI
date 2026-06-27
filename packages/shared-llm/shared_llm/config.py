from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class LLMConfig(BaseModel):
    provider: str = Field(..., description="LLM provider name: 'openai', 'anthropic', or 'gemini'")
    api_key: str = Field(..., description="API Key for the provider")
    model: Optional[str] = Field(None, description="Model name (e.g. 'gpt-4o', 'claude-3-5-sonnet-20240620')")
    temperature: float = Field(0.7, description="Sampling temperature")
    max_tokens: int = Field(4096, description="Max tokens to generate")
    fallback_provider: Optional[str] = Field(None, description="Fallback provider name if primary fails")
    extra_kwargs: Dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific kwargs")
