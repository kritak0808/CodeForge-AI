import functools
import logging
from typing import Any, Callable, TypeVar, cast
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from .exceptions import RateLimitError, TransientError

logger = logging.getLogger("shared-llm.retry")

F = TypeVar("F", bound=Callable[..., Any])

def with_retry(func: F) -> F:
    """Decorator to retry async LLM completion calls on transient or rate limit errors."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Configure retry behavior
        retryer = retry(
            reraise=True,
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((RateLimitError, TransientError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        # Use tenacity to run the decorated function
        return await retryer(func)(*args, **kwargs)
    
    return cast(F, wrapper)
