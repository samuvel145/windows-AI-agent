import logging
import logging.handlers
import sys
import os
from amdea import config

def scrub_secrets(d: dict) -> dict:
    """Replaces sensitive values in a dictionary with redacting labels."""
    if not isinstance(d, dict):
        return d
    scrubbed = d.copy()
    secret_keys = {"password", "key", "token", "secret", "authorization"}
    for k, v in scrubbed.items():
        if any(sk in k.lower() for sk in secret_keys):
            scrubbed[k] = "***REDACTED***"
        elif isinstance(v, dict):
            scrubbed[k] = scrub_secrets(v)
    return scrubbed

def setup_logging():
    log_dir = pathlib.Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "amdea.log"

    level = logging.DEBUG if os.getenv("AMDEA_DEBUG") == "true" else logging.INFO
    log_format = "{asctime} | {levelname:8} | {name:30} | {message}"
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Handlers
    file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter(log_format, style="{"))
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(log_format, style="{"))
    # Force UTF-8 for console output to avoid cp1252 encoding errors on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Suppress noise
    for noisy in ["httpx", "playwright", "openai", "asyncio"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

def get_logger(name: str):
    return logging.getLogger(name)

import pathlib
