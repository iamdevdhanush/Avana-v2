"""
Timing utility for pipeline execution tracing.
Logs start time, end time, and duration for every instrumented step.
"""
import logging
import time

logger = logging.getLogger(__name__)


class Timer:
    def __init__(self, step_name: str):
        self.step_name = step_name
        self.start = 0.0
        self.end = 0.0

    def __enter__(self):
        self.start = time.time()
        logger.info(
            f"\n╔══════════════════════════════════════════════════╗\n"
            f"║ STEP START: {self.step_name}\n"
            f"║ START TIME: {self._fmt(self.start)}\n"
            f"╚══════════════════════════════════════════════════╝"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = time.time()
        duration = round(self.end - self.start, 3)
        status = "FAILED" if exc_type else "OK"
        logger.info(
            f"\n┌──────────────────────────────────────────────────┐\n"
            f"│ STEP END: {self.step_name}\n"
            f"│ START TIME: {self._fmt(self.start)}\n"
            f"│ END TIME:   {self._fmt(self.end)}\n"
            f"│ DURATION:   {duration:.3f}s\n"
            f"│ STATUS:     {status}\n"
            f"└──────────────────────────────────────────────────┘"
        )

    @staticmethod
    def _fmt(ts: float) -> str:
        return time.strftime("%H:%M:%S", time.localtime(ts)) + f".{int((ts % 1) * 1000):03d}"
