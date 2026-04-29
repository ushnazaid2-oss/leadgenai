"""
Circuit Breaker pattern for external API resilience.
Prevents cascading failures when external services (Twilio, SendGrid, WhatsApp) are down.
"""

import time
import asyncio
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    States:
    - CLOSED: Normal — requests pass through
    - OPEN: Failing — requests immediately rejected for `reset_timeout` seconds
    - HALF_OPEN: Testing — allow one request to check if service recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: int = 60,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def _should_allow_request(self) -> bool:
        """Determine if a request should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info(f"Circuit breaker [{self.name}]: OPEN → HALF_OPEN")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def _on_success(self):
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info(f"Circuit breaker [{self.name}]: HALF_OPEN → CLOSED (recovered)")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _on_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker [{self.name}]: HALF_OPEN → OPEN (still failing)")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker [{self.name}]: CLOSED → OPEN "
                f"(failed {self.failure_count} times)"
            )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an async function through the circuit breaker."""
        if not self._should_allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker [{self.name}] is OPEN. "
                f"Service unavailable. Retry after {self.reset_timeout}s."
            )

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    @property
    def status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""
    pass


# Pre-configured circuit breakers for each external service
email_circuit = CircuitBreaker("email", failure_threshold=5, reset_timeout=120)
whatsapp_circuit = CircuitBreaker("whatsapp", failure_threshold=5, reset_timeout=120)
twilio_circuit = CircuitBreaker("twilio", failure_threshold=3, reset_timeout=180)
openai_circuit = CircuitBreaker("openai", failure_threshold=3, reset_timeout=60)
