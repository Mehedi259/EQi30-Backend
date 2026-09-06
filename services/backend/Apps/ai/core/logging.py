import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Context variable to hold the request ID across async tasks
request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class JSONFormatter(logging.Formatter):
    """
    Custom JSON log formatter to output logs as structured JSON strings.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_object: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx_var.get(),
        }

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_fields"):
            log_object.update(getattr(record, "extra_fields"))

        return json.dumps(log_object)


class ConsoleFormatter(logging.Formatter):
    """
    Console log formatter with request ID enrichment.
    """

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx_var.get()
        req_part = f"[{req_id}] " if req_id != "-" else ""
        record.msg = f"{req_part}{record.msg}"
        return super().format(record)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure application logging.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to prevent duplicate logging
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level.upper())

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        handler.setFormatter(ConsoleFormatter(fmt))

    root_logger.addHandler(handler)

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").handlers = root_logger.handlers


def get_logger(name: str) -> logging.Logger:
    """
    Retrieve a named logger instance.
    """
    return logging.getLogger(name)
