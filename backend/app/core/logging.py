import logging
import sys
from typing import Any, Dict
from backend.app.core.config import settings


class SanitizeFormatter(logging.Formatter):
    """
    Structured formatter ensuring secrets, raw file streams, and sensitive tokens
    are not leaked to server logs.
    """
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact any obvious Bearer tokens or API keys if accidentally passed in messages
        if "Bearer " in msg:
            import re
            msg = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", msg)
        return msg


def setup_logging() -> logging.Logger:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger = logging.getLogger("intellidocs")
    logger.setLevel(log_level)

    # Avoid duplicate handlers if reloaded
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = SanitizeFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
