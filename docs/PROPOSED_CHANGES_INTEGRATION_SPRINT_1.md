# Integration Sprint 1 - Proposed Changes

**Document Version:** 1.0  
**Created:** 2026-06-26  
**Scope:** All code changes required for Integration Sprint 1  
**Type:** Architecture and Implementation Changes  

---

## Executive Summary

This document details all proposed code changes for Integration Sprint 1, organized by component and phase. Changes are categorized as: **New Files**, **Modified Files**, **Deleted Files**, and **Configuration Changes**.

**Total Changes:**
- New Files: 35
- Modified Files: 15
- Deleted Files: 2
- Configuration Changes: 12

---

## Phase 1: Unified LLM Provider Implementation

### New Package: packages/shared-llm/

#### New Files

**1. packages/shared-llm/pyproject.toml**
```toml
[project]
name = "shared-llm"
version = "1.0.0"
description = "Unified LLM provider abstraction for CodeForge AI"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.12.0",
    "anthropic>=0.18.0",
    "google-generativeai>=0.3.0",
    "tiktoken>=0.5.0",
    "tenacity>=8.2.0",
    "pydantic>=2.6.4",
    "httpx>=0.25.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

**2. packages/shared-llm/setup.py**
```python
from setuptools import setup, find_packages

setup(
    name="shared-llm",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.12.0",
        "anthropic>=0.18.0",
        "google-generativeai>=0.3.0",
        "tiktoken>=0.5.0",
        "tenacity>=8.2.0",
        "pydantic>=2.6.4",
        "httpx>=0.25.0",
    ],
)
```

**3. packages/shared-llm/requirements.txt**
```
openai>=1.12.0
anthropic>=0.18.0
google-generativeai>=0.3.0
tiktoken>=0.5.0
tenacity>=8.2.0
pydantic>=2.6.4
httpx>=0.25.0
```

**4. packages/shared-llm/shared_llm/__init__.py**
```python
from .base import LLMProvider, LLMResponse
from .providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from .factory import ProviderFactory
from .config import LLMConfig
from .token_counter import TokenCounter
from .cost_tracker import CostTracker
from .exceptions import (
    LLMProviderError,
    RateLimitError,
    TransientError,
    ConfigurationError
)

__version__ = "1.0.0"
__all__ = [
    "LLMProvider",
    "LLMResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "ProviderFactory",
    "LLMConfig",
    "TokenCounter",
    "CostTracker",
    "LLMProviderError",
    "RateLimitError",
    "TransientError",
    "ConfigurationError",
]
```

**5. packages/shared-llm/shared_llm/base.py**
```python
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
```

**6. packages/shared-llm/shared_llm/providers.py**
```python
import logging
from typing import Optional, AsyncIterator
from openai import AsyncOpenAI
import anthropic
import google.generativeai as genai
from .base import LLMProvider, LLMResponse
from .exceptions import RateLimitError, TransientError
from .retry import with_retry

logger = logging.getLogger("shared-llm.providers")

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4-turbo"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        from .token_counter import TokenCounter
        self.token_counter = TokenCounter("openai", model)
        from .cost_tracker import CostTracker
        self.cost_tracker = CostTracker()
        
    @with_retry
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cost_usd=self.cost_tracker.calculate_cost(
                    "openai",
                    response.model,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                ),
                latency_ms=latency_ms,
                provider="openai",
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
            
    async def generate_completion_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise
            
    def count_tokens(self, text: str) -> int:
        return self.token_counter.count_tokens(text)
        
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        return self.cost_tracker.calculate_cost(
            "openai",
            model,
            input_tokens,
            output_tokens
        )
        
    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        from .token_counter import TokenCounter
        self.token_counter = TokenCounter("anthropic", model)
        from .cost_tracker import CostTracker
        self.cost_tracker = CostTracker()
        
    @with_retry
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.time()
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                cost_usd=self.cost_tracker.calculate_cost(
                    "anthropic",
                    response.model,
                    response.usage.input_tokens,
                    response.usage.output_tokens
                ),
                latency_ms=latency_ms,
                provider="anthropic",
                finish_reason=response.stop_reason
            )
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
            
    async def generate_completion_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise
            
    def count_tokens(self, text: str) -> int:
        return self.token_counter.count_tokens(text)
        
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        return self.cost_tracker.calculate_cost(
            "anthropic",
            model,
            input_tokens,
            output_tokens
        )
        
    async def health_check(self) -> bool:
        try:
            await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        genai.configure(api_key=api_key)
        self.model = model
        from .token_counter import TokenCounter
        self.token_counter = TokenCounter("gemini", model)
        from .cost_tracker import CostTracker
        self.cost_tracker = CostTracker()
        
    @with_retry
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.time()
        
        try:
            model = genai.GenerativeModel(self.model)
            
            if system_prompt:
                full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
            else:
                full_prompt = prompt
                
            response = await model.generate_content_async(full_prompt, **kwargs)
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Gemini doesn't provide token usage, estimate
            input_tokens = self.token_counter.count_tokens(full_prompt)
            output_tokens = self.token_counter.count_tokens(response.text)
            
            return LLMResponse(
                content=response.text,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_usd=self.cost_tracker.calculate_cost(
                    "gemini",
                    self.model,
                    input_tokens,
                    output_tokens
                ),
                latency_ms=latency_ms,
                provider="gemini",
                finish_reason="stop"
            )
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
            
    async def generate_completion_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        try:
            model = genai.GenerativeModel(self.model)
            
            if system_prompt:
                full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
            else:
                full_prompt = prompt
                
            response = await model.generate_content_async(full_prompt, stream=True, **kwargs)
            
            async for chunk in response:
                yield chunk.text
        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            raise
            
    def count_tokens(self, text: str) -> int:
        return self.token_counter.count_tokens(text)
        
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        return self.cost_tracker.calculate_cost(
            "gemini",
            model,
            input_tokens,
            output_tokens
        )
        
    async def health_check(self) -> bool:
        try:
            model = genai.GenerativeModel(self.model)
            await model.generate_content_async("test")
            return True
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False
```

**7. packages/shared-llm/shared_llm/token_counter.py**
```python
import logging
from typing import Optional
import tiktoken

logger = logging.getLogger("shared-llm.token_counter")

class TokenCounter:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.tokenizer = self._get_tokenizer()
        
    def _get_tokenizer(self):
        if self.provider == "openai":
            try:
                return tiktoken.encoding_for_model(self.model)
            except KeyError:
                return tiktoken.get_encoding("cl100k_base")
        return None
        
    def count_tokens(self, text: str) -> int:
        if self.provider == "openai" and self.tokenizer:
            return len(self.tokenizer.encode(text))
        elif self.provider == "anthropic":
            return self._count_anthropic_tokens(text)
        elif self.provider == "gemini":
            return self._count_gemini_tokens(text)
        else:
            return self._estimate_tokens(text)
            
    def _count_anthropic_tokens(self, text: str) -> int:
        # Anthropic uses ~4 chars per token approximation
        return len(text) // 4
        
    def _count_gemini_tokens(self, text: str) -> int:
        # Gemini uses ~4 chars per token approximation
        return len(text) // 4
        
    def _estimate_tokens(self, text: str) -> int:
        # Fallback estimation
        return len(text.split()) * 1.3
```

**8. packages/shared-llm/shared_llm/cost_tracker.py**
```python
import logging
from typing import Dict
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("shared-llm.cost_tracker")

# Pricing per 1M tokens (USD)
PRICING = {
    "openai": {
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    },
    "anthropic": {
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
    "gemini": {
        "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
    }
}

class CostTracker:
    def __init__(self):
        self.total_cost_usd = 0.0
        self.costs_by_provider: Dict[str, float] = defaultdict(float)
        self.costs_by_model: Dict[str, float] = defaultdict(float)
        self.usage_history = []
        
    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        if provider not in PRICING:
            logger.warning(f"Unknown provider: {provider}")
            return 0.0
            
        if model not in PRICING[provider]:
            logger.warning(f"Unknown model for {provider}: {model}")
            return 0.0
            
        pricing = PRICING[provider][model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Track costs
        self.total_cost_usd += total_cost
        self.costs_by_provider[provider] += total_cost
        self.costs_by_model[model] += total_cost
        
        self.usage_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": total_cost
        })
        
        return total_cost
        
    def get_total_cost(self) -> float:
        return self.total_cost_usd
        
    def get_cost_by_provider(self, provider: str) -> float:
        return self.costs_by_provider.get(provider, 0.0)
        
    def get_cost_by_model(self, model: str) -> float:
        return self.costs_by_model.get(model, 0.0)
        
    def get_usage_history(self):
        return self.usage_history
        
    def reset(self):
        self.total_cost_usd = 0.0
        self.costs_by_provider.clear()
        self.costs_by_model.clear()
        self.usage_history.clear()
```

**9. packages/shared-llm/shared_llm/config.py**
```python
from typing import Dict, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator

class LLMConfig(BaseSettings):
    # Provider Selection
    PRIMARY_PROVIDER: str = "openai"
    BACKUP_PROVIDER: str = "anthropic"
    
    # Default Models
    DEFAULT_MODEL: str = "gpt-4-turbo"
    
    # Per-Agent Model Selection
    AGENT_MODELS: Dict[str, str] = {
        "ResearchAgent": "gpt-4-turbo",
        "ArchitectAgent": "gpt-4",
        "DatabaseAgent": "gpt-4-turbo",
        "BackendAgent": "gpt-4-turbo",
        "FrontendAgent": "gpt-4-turbo",
        "QAAgent": "gpt-4-turbo",
        "SecurityAgent": "gpt-4",
        "DevOpsAgent": "gpt-4-turbo",
        "CostOptimizationAgent": "gpt-4",
        "ObservabilityAgent": "gpt-4-turbo",
        "AutonomousControllerAgent": "gpt-4",
    }
    
    # API Keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY_MIN: int = 2
    RETRY_DELAY_MAX: int = 10
    
    # Cost Limits
    DAILY_COST_LIMIT_USD: float = 100.0
    COST_ALERT_THRESHOLD_USD: float = 50.0
    
    # Timeout Configuration
    REQUEST_TIMEOUT: int = 60
    STREAM_TIMEOUT: int = 120
    
    model_config = {"extra": "ignore"}
    
    @field_validator("PRIMARY_PROVIDER", "BACKUP_PROVIDER")
    @classmethod
    def validate_provider(cls, v):
        valid_providers = ["openai", "anthropic", "gemini"]
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of {valid_providers}")
        return v
        
    def get_model_for_agent(self, agent_id: str) -> str:
        return self.AGENT_MODELS.get(agent_id, self.DEFAULT_MODEL)
```

**10. packages/shared-llm/shared_llm/factory.py**
```python
import logging
from typing import Optional
from .config import LLMConfig
from .providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from .base import LLMProvider

logger = logging.getLogger("shared-llm.factory")

class ProviderFactory:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._providers: Dict[str, LLMProvider] = {}
        
    async def get_provider(self, agent_id: Optional[str] = None) -> LLMProvider:
        """Get provider for agent, with fallback"""
        model = self.config.get_model_for_agent(agent_id) if agent_id else self.config.DEFAULT_MODEL
        provider_name = self.config.PRIMARY_PROVIDER
        
        try:
            provider = await self._create_provider(provider_name, model)
            if await provider.health_check():
                logger.info(f"Using primary provider: {provider_name}")
                return provider
        except Exception as e:
            logger.warning(f"Primary provider failed: {e}")
            
        # Fallback to backup provider
        backup_name = self.config.BACKUP_PROVIDER
        logger.info(f"Falling back to backup provider: {backup_name}")
        return await self._create_provider(backup_name, model)
        
    async def _create_provider(self, provider_name: str, model: str) -> LLMProvider:
        cache_key = f"{provider_name}:{model}"
        
        if cache_key in self._providers:
            return self._providers[cache_key]
            
        if provider_name == "openai":
            if not self.config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")
            provider = OpenAIProvider(
                api_key=self.config.OPENAI_API_KEY,
                model=model
            )
        elif provider_name == "anthropic":
            if not self.config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            provider = AnthropicProvider(
                api_key=self.config.ANTHROPIC_API_KEY,
                model=model
            )
        elif provider_name == "gemini":
            if not self.config.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not configured")
            provider = GeminiProvider(
                api_key=self.config.GEMINI_API_KEY,
                model=model
            )
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
            
        self._providers[cache_key] = provider
        return provider
```

**11. packages/shared-llm/shared_llm/exceptions.py**
```python
class LLMProviderError(Exception):
    """Base exception for LLM provider errors"""
    pass

class RateLimitError(LLMProviderError):
    """Raised when rate limit is exceeded"""
    pass

class TransientError(LLMProviderError):
    """Raised for transient errors that can be retried"""
    pass

class ConfigurationError(LLMProviderError):
    """Raised when configuration is invalid"""
    pass

class AuthenticationError(LLMProviderError):
    """Raised when authentication fails"""
    pass

class QuotaExceededError(LLMProviderError):
    """Raised when quota is exceeded"""
    pass
```

**12. packages/shared-llm/shared_llm/retry.py**
```python
import logging
from functools import wraps
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from .exceptions import RateLimitError, TransientError

logger = logging.getLogger("shared-llm.retry")

def with_retry(func):
    """Decorator for retry logic with exponential backoff"""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, TransientError)),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
        
    return wrapper
```

---

## Phase 2: Agent Refactoring

### Modified Files

**1. apps/agent-workers/agent.py**

**Changes:**
- Remove `mock_vector_rag_retriever()` function (lines 49-75)
- Remove `mock_package_registry_verifier()` function (lines 77-103)
- Modify `BaseAgentAbstraction.execute_task()` to use LLM provider
- Add LLM provider injection to agent constructors
- Integrate Qdrant for real vector RAG
- Implement real PyPI/NPM API calls

**Before:**
```python
def mock_vector_rag_retriever(query: str) -> str:
    """Simulates retrieving chunks from Qdrant vector database"""
    query_lower = query.lower()
    if "fastapi" in query_lower:
        return "### FastAPI Docs (v0.110.0)\n..."
    # ... more hardcoded responses
```

**After:**
```python
async def vector_rag_retriever(
    query: str, 
    qdrant_manager: QdrantManager,
    llm_provider: LLMProvider
) -> str:
    """Retrieves relevant documentation from Qdrant vector database"""
    # Generate embedding for query
    embedding = await llm_provider.generate_completion(
        prompt=f"Generate embedding for: {query}",
        system_prompt="You are an embedding generator. Return only the embedding vector."
    )
    
    # Search Qdrant
    results = qdrant_manager.search_similarity(
        collection_name="documentation",
        query_vector=embedding,
        limit=5
    )
    
    # Return relevant context
    return "\n".join([r.payload.get("content", "") for r in results])
```

**2. apps/agent-workers/requirements.txt**

**Changes:**
- Add `shared-llm>=1.0.0`
- Add `shared-memory>=1.0.0`

**Before:**
```
crewai>=0.22.0
langchain>=0.1.13
langchain-openai>=0.1.1
langchain-anthropic>=0.1.4
pydantic>=2.6.4
kafka-python>=2.0.2
qdrant-client>=1.8.0
redis>=5.0.3
requests>=2.31.0
opentelemetry-api>=1.23.0
opentelemetry-sdk>=1.23.0
```

**After:**
```
crewai>=0.22.0
langchain>=0.1.13
langchain-openai>=0.1.1
langchain-anthropic>=0.1.4
pydantic>=2.6.4
kafka-python>=2.0.2
qdrant-client>=1.8.0
redis>=5.0.3
requests>=2.31.0
opentelemetry-api>=1.23.0
opentelemetry-sdk>=1.23.0
shared-llm>=1.0.0
shared-memory>=1.0.0
```

**3. apps/agent-workers/main.py**

**Changes:**
- Import LLM provider factory
- Initialize LLM provider configuration
- Initialize Qdrant manager
- Pass LLM provider to agent constructors

**Before:**
```python
from agent import agent_registry, ResearchAgent

# Register agents
agent_registry.register_agent(ResearchAgent())
```

**After:**
```python
from agent import agent_registry, ResearchAgent
from shared_llm import ProviderFactory, LLMConfig
from shared_memory.qdrant import QdrantManager

# Initialize LLM provider
config = LLMConfig()
provider_factory = ProviderFactory(config)

# Initialize Qdrant
qdrant_manager = QdrantManager(url="http://localhost:6333")

# Register agents with LLM provider
llm_provider = await provider_factory.get_provider("ResearchAgent")
agent_registry.register_agent(
    ResearchAgent(llm_provider=llm_provider, qdrant_manager=qdrant_manager)
)
```

---

## Phase 3: Infrastructure Integration

### New Files

**1. .env**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/codeforge

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_DISABLED=false

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_DISABLED=false

# Qdrant
QDRANT_URL=http://localhost:6333

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# Security
SECRET_KEY=your-production-secret-key-min-32-characters
JWT_SECRET=your-jwt-secret-key-min-32-characters

# Environment
ENV=production
```

**2. .env.production**
```bash
# Production Environment Configuration
ENV=production

# Database
DATABASE_URL=postgresql+asyncpg://user:password@production-db:5432/codeforge

# Redis
REDIS_URL=redis://production-redis:6379/0
REDIS_DISABLED=false

# Kafka
KAFKA_BOOTSTRAP_SERVERS=production-kafka:9092
KAFKA_DISABLED=false

# Qdrant
QDRANT_URL=http://production-qdrant:6333

# LLM Providers
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GEMINI_API_KEY=${GEMINI_API_KEY}

# Security
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${JWT_SECRET}

# Cost Limits
DAILY_COST_LIMIT_USD=500.0
COST_ALERT_THRESHOLD_USD=250.0
```

### Modified Files

**1. apps/api/app/config.py**

**Changes:**
- Add QDRANT_URL configuration
- Update default values
- Remove disabled flags
- Add configuration validation

**Before:**
```python
class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./codeforge_dev.db"

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_DISABLED: bool = True

    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_DISABLED: bool = True
```

**After:**
```python
class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/codeforge"

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_DISABLED: bool = False

    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_DISABLED: bool = False

    # Qdrant Settings
    QDRANT_URL: str = "http://localhost:6333"
```

### Deleted Files

**1. demo_workflow.py** (MockKafkaPublisher class)

**Before:**
```python
class MockKafkaPublisher:
    def __init__(self):
        self.published_events = []

    def publish(self, topic: str, payload: dict) -> bool:
        self.published_events.append((topic, payload))
        # ... mock implementation
```

**After:**
```python
from event_publisher import KafkaEventPublisher

# Use real Kafka publisher
event_pub = KafkaEventPublisher(
    bootstrap_servers="localhost:9092"
)
```

---

## Phase 4: Backend Integration

### Modified Files

**1. apps/api/tests/conftest.py**

**Changes:**
- Remove mock_kafka fixture
- Use real Kafka in integration tests

**Before:**
```python
@pytest.fixture(scope="session", autouse=True)
def mock_kafka():
    with patch("event_publisher.KafkaProducer", side_effect=Exception("Mock Kafka Down")):
        with patch("event_publisher.KafkaConsumer", side_effect=Exception("Mock Kafka Down")):
            yield
```

**After:**
```python
@pytest.fixture(scope="session")
def real_kafka():
    """Use real Kafka for integration tests"""
    from event_publisher import KafkaEventPublisher
    publisher = KafkaEventPublisher(bootstrap_servers="localhost:9092")
    yield publisher
```

---

## Phase 5: Frontend Integration

### Modified Files

**1. apps/web/src/lib/api.ts**

**Changes:**
- Add authentication headers
- Add error handling
- Add retry logic
- Add type safety

**Before:**
```typescript
const API_BASE = 'http://localhost:8000/api/v1';

export async function fetchProjects() {
  const response = await fetch(`${API_BASE}/projects`);
  return response.json();
}
```

**After:**
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface ApiResponse<T> {
  data: T;
  error?: string;
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const token = localStorage.getItem('token');
  
  const config: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  };

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}

export async function fetchProjects(): Promise<ApiResponse<Project[]>> {
  return apiRequest<Project[]>('/projects');
}
```

---

## Summary of Changes

### New Files (35)

**Shared LLM Package (12):**
1. packages/shared-llm/pyproject.toml
2. packages/shared-llm/setup.py
3. packages/shared-llm/requirements.txt
4. packages/shared-llm/shared_llm/__init__.py
5. packages/shared-llm/shared_llm/base.py
6. packages/shared-llm/shared_llm/providers.py
7. packages/shared-llm/shared_llm/token_counter.py
8. packages/shared-llm/shared_llm/cost_tracker.py
9. packages/shared-llm/shared_llm/config.py
10. packages/shared-llm/shared_llm/factory.py
11. packages/shared-llm/shared_llm/exceptions.py
12. packages/shared-llm/shared_llm/retry.py

**Configuration (2):**
13. .env
14. .env.production

**Documentation (21):**
15. docs/INTEGRATION_SPRINT_1_PLAN.md
16. docs/USER_REVIEW_INTEGRATION_SPRINT_1.md
17. docs/PROPOSED_CHANGES_INTEGRATION_SPRINT_1.md
18. docs/VERIFICATION_PLAN_INTEGRATION_SPRINT_1.md
19-35. Additional documentation files (testing, deployment, etc.)

### Modified Files (15)

**Agent Workers (3):**
1. apps/agent-workers/agent.py
2. apps/agent-workers/requirements.txt
3. apps/agent-workers/main.py

**API Configuration (1):**
4. apps/api/app/config.py

**Frontend (1):**
5. apps/web/src/lib/api.ts

**Tests (1):**
6. apps/api/tests/conftest.py

**Frontend Pages (8):**
7. apps/web/src/app/dashboard/page.tsx
8. apps/web/src/app/projects/page.tsx
9. apps/web/src/app/pipelines/page.tsx
10. apps/web/src/app/approvals/page.tsx
11. apps/web/src/app/agents/page.tsx
12. apps/web/src/app/observability/page.tsx
13. apps/web/src/app/cost/page.tsx
14. apps/web/src/app/security/page.tsx
15. apps/web/src/app/workflows/page.tsx

### Deleted Files (2)

1. demo_workflow.py (MockKafkaPublisher class)
2. apps/api/tests/conftest.py (mock_kafka fixture)

### Configuration Changes (12)

**Environment Variables:**
1. DATABASE_URL - Change from SQLite to PostgreSQL
2. REDIS_DISABLED - Change from True to False
3. KAFKA_DISABLED - Change from True to False
4. QDRANT_URL - Add new configuration
5. OPENAI_API_KEY - Add required value
6. ANTHROPIC_API_KEY - Add required value
7. GEMINI_API_KEY - Add required value
8. SECRET_KEY - Update to production value
9. JWT_SECRET - Update to production value
10. DAILY_COST_LIMIT_USD - Add new configuration
11. COST_ALERT_THRESHOLD_USD - Add new configuration
12. ENV - Set to production

---

## Impact Analysis

### Breaking Changes

1. **Agent Interface Changes**
   - Agents now require LLM provider injection
   - Agent constructors changed signature
   - **Impact:** All agent instantiation code must be updated

2. **Database Changes**
   - Migration from SQLite to PostgreSQL
   - **Impact:** Data migration required, schema changes

3. **Infrastructure Changes**
   - Redis and Kafka must be running
   - **Impact:** Development environment setup required

### Non-Breaking Changes

1. **Configuration Changes**
   - New environment variables
   - **Impact:** Configuration files must be updated

2. **Frontend API Changes**
   - Enhanced error handling
   - **Impact:** Improved user experience, no breaking changes

3. **Test Changes**
   - Mock removal in integration tests
   - **Impact:** Tests require real infrastructure

### Performance Impact

1. **Positive:**
   - Real AI execution provides better results
   - Proper caching improves performance
   - Optimized database queries

2. **Negative:**
   - Real API calls increase latency
   - Vector database queries add overhead
   - Infrastructure dependencies add complexity

### Security Impact

1. **Positive:**
   - Proper authentication and authorization
   - Security headers implemented
   - Secrets management

2. **Negative:**
   - Increased attack surface with more services
   - API key management required

---

## Migration Strategy

### Phase 1: LLM Provider (Week 1-2)

1. Create shared-llm package
2. Implement providers
3. Test in isolation
4. Document usage

### Phase 2: Agent Refactoring (Week 3)

1. Refactor agents one by one
2. Test each agent thoroughly
3. Monitor costs
4. Maintain rollback capability

### Phase 3: Infrastructure (Week 4)

1. Set up infrastructure locally
2. Migrate database
3. Enable services
4. Test integration

### Phase 4-5: Integration (Week 5)

1. Backend integration
2. Frontend integration
3. End-to-end testing
4. Performance testing

### Phase 6-10: Production (Week 6-8)

1. Production hardening
2. Deployment preparation
3. Comprehensive testing
4. Documentation

---

## Rollback Plan

### Phase 1 Rollback

1. Remove shared-llm package
2. Revert agent changes
3. Restore mock implementations
4. Update dependencies

### Phase 2 Rollback

1. Restore agent code from git
2. Revert dependency changes
3. Restore mock implementations
4. Restart services

### Phase 3 Rollback

1. Disable Redis and Kafka
2. Revert to SQLite
3. Remove Qdrant dependency
4. Update configuration

### Phase 4-5 Rollback

1. Restore frontend mock data
2. Revert API changes
3. Restore test mocks
4. Restart services

---

**End of Proposed Changes**
