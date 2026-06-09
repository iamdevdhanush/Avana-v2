import json
import logging
import logging.handlers
import sys
import uuid
from datetime import datetime, timezone
from typing import Callable
from fastapi import Request, Response


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if record.args:
            log_entry["extra"] = str(record.args)
        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO", log_file: str = "logs/avana.log") -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    json_formatter = JSONFormatter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(json_formatter)
    root_logger.addHandler(stream_handler)

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    for logger_name in ("httpx", "urllib3", "httpcore", "asyncio"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.getLogger("app").setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.info("Logging initialized", extra={"log_file": log_file, "level": level})


class RequestIDMiddleware:
    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid.uuid4())[:8]

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"X-Request-ID"] = request_id.encode()
                message["headers"] = [(k, v) for k, v in headers.items()]
            await send(message)

        async def receive_with_id():
            return await receive()

        await self.app(scope, receive_with_id, send_with_id)
