import logging
import re
import sys
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Masks bot tokens and API keys in log records to prevent security leaks."""
    
    PATTERNS = [
        re.compile(r'\b\d{8,12}:[a-zA-Z0-9_-]{35}\b'),  # Telegram Bot Token pattern
        re.compile(r'AIza[0-9A-Za-z-_]{35}'),          # Google API Key pattern
        re.compile(r'sk-[a-zA-Z0-9]{20,60}'),          # OpenAI API Key pattern
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in self.PATTERNS:
                msg = pattern.sub("[REDACTED_SECRET]", msg)
            record.msg = msg
        return True


def setup_logger(name: str = "multilingual_butler", level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    log_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    # Silence noisy external libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    return logger


logger = setup_logger()
