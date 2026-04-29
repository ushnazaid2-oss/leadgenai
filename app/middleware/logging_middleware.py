"""
Structured JSON logging middleware.
Logs all requests/responses with timing, and separates API, task, and error logs.
"""

import time
import uuid
import logging
import json
import sys
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO"):
    """Configure structured logging with separate handlers for API, tasks, and errors."""
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    json_formatter = JSONFormatter()

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Console handler (human-readable in dev)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    root_logger.addHandler(console_handler)

    # API log file (JSON)
    api_handler = logging.FileHandler(log_dir / "api.log")
    api_handler.setFormatter(json_formatter)
    api_logger = logging.getLogger("api")
    api_logger.addHandler(api_handler)

    # Task log file (Celery tasks)
    task_handler = logging.FileHandler(log_dir / "tasks.log")
    task_handler.setFormatter(json_formatter)
    task_logger = logging.getLogger("celery")
    task_logger.addHandler(task_handler)

    # Error log file
    error_handler = logging.FileHandler(log_dir / "errors.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    root_logger.addHandler(error_handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every HTTP request/response with timing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Attach request ID to request state
        request.state.request_id = request_id

        logger = logging.getLogger("api")

        # Log request
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
            },
        )

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            # Log response
            logger.info(
                f"← {response.status_code} ({duration_ms}ms)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"✕ Error: {str(e)} ({duration_ms}ms)",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "duration_ms": duration_ms,
                },
            )
            raise
