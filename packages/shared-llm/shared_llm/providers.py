import logging
import time
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
                finish_reason=response.choices[0].finish_reason or "stop"
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
            # Simple health check call
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
                finish_reason=response.stop_reason or "stop"
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
            async with self.client.messages.stream(
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
