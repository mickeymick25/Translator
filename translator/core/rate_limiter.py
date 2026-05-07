"""
Rate limiter adaptatif avec mémorisation des erreurs et persistance.

Provides adaptive rate limiting for API calls, remembering recent errors
to adjust delays dynamically. Supports JSON persistence for surviving
container restarts.
"""

import json
import logging
import time
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter that adapts automatically to rate limit errors.

    Memorizes recent errors to dynamically adjust the delay between
    requests. Supports persistence via JSON file to survive container
    restarts.

    Note: Uses a classic class (not @dataclass) because
    threading.Lock is not compatible with __eq__/__hash__ generated
    by dataclasses.
    """

    def __init__(
        self,
        base_delay: float = 0.2,
        max_delay: float = 10.0,
        memory_minutes: int = 30,
        error_threshold: int = 1,
        persist_path: str | None = None,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.memory_minutes = memory_minutes
        self.error_threshold = error_threshold
        self.persist_path = Path(persist_path) if persist_path else None

        self._error_timestamps: list[float] = []
        self._lock = Lock()

        # Load persisted errors if available
        if self.persist_path:
            self._load_persisted_errors()

    def _cleanup_old_errors(self) -> None:
        """Remove errors older than memory_minutes."""
        cutoff = time.time() - (self.memory_minutes * 60)
        self._error_timestamps = [t for t in self._error_timestamps if t > cutoff]

    def should_wait(self) -> tuple[bool, float]:
        """
        Determine whether to wait before the next request.

        Returns:
            Tuple (should_wait, wait_seconds)
            - should_wait: True if rate limiting is active (error threshold reached)
            - wait_seconds: Recommended delay in seconds
        """
        with self._lock:
            self._cleanup_old_errors()

            # No recent errors → no additional wait, just base delay
            if len(self._error_timestamps) < self.error_threshold:
                return False, self.base_delay

            # Calculate delay based on number of recent errors
            error_count = len(self._error_timestamps)
            multiplier = min(2 ** (error_count - self.error_threshold), 16)
            wait_seconds = min(self.base_delay * multiplier, self.max_delay)

            logger.debug(
                "Rate limit active: %d errors in memory, waiting %.1fs",
                error_count,
                wait_seconds,
            )

            return True, wait_seconds

    def record_error(self) -> None:
        """Record a rate limit error and persist if configured."""
        with self._lock:
            self._error_timestamps.append(time.time())
            logger.warning(
                "Rate limit error recorded. Total errors in memory: %d",
                len(self._error_timestamps),
            )
            self._persist_errors()

    def record_success(self) -> None:
        """
        Record a successful request.
        Optional — may be used for monitoring or delay decay in future.
        """
        # Future: could progressively reduce delay after N consecutive successes
        pass

    def _persist_errors(self) -> None:
        """Persist error timestamps to a JSON file.

        Called within the lock context from record_error(), so no
        additional locking is needed here.
        """
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("w", encoding="utf-8") as f:
                json.dump({"error_timestamps": self._error_timestamps}, f)
        except Exception as e:
            logger.warning("Failed to persist rate limiter state: %s", e)

    def _load_persisted_errors(self) -> None:
        """Load error timestamps from a persisted JSON file.

        Called from __init__ before the object is shared, so no
        locking is needed here.
        """
        if not self.persist_path or not self.persist_path.exists():
            return
        try:
            with self.persist_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._error_timestamps = data.get("error_timestamps", [])
            self._cleanup_old_errors()  # Clean expired timestamps
            if self._error_timestamps:
                logger.info(
                    "Loaded %d persisted rate limit errors from %s",
                    len(self._error_timestamps),
                    self.persist_path.name,
                )
        except Exception as e:
            logger.warning("Failed to load rate limiter state: %s", e)
            self._error_timestamps = []


# Global instance (lazy init)
_global_rate_limiter: RateLimiter | None = None


def get_rate_limiter(persist_path: str | None = None) -> RateLimiter:
    """
    Get the global rate limiter instance.
    Creates the instance on first call (lazy initialization).

    Args:
        persist_path: Optional path to the state file. Only used on first call.
            If not provided, uses config.RATE_LIMITER_STATE_PATH.

    Returns:
        The global RateLimiter instance.
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        from core.config import get_config

        config = get_config()
        effective_path = persist_path or config.RATE_LIMITER_STATE_PATH
        _global_rate_limiter = RateLimiter(persist_path=effective_path)
    return _global_rate_limiter
