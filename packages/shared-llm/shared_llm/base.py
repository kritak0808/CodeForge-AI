from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator, Dict, Any
from pydantic import BaseModel
import time

class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    provider: str
    finish_reason: str

class LLMProvider(ABC):
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate non-streaming completion"""
        pass
        
    @abstractmethod
    async def generate_completion_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate streaming completion"""
        pass
        
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens for text"""
        pass
        
    @abstractmethod
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        """Estimate cost in USD"""
        pass
        
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is accessible"""
        pass
