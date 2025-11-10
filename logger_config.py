import logging
import os
import sys

def setup_logger():
    """
    Configures a JSON-based logger that outputs to stdout.
    Reads LOG_LEVEL from environment variables (default: INFO).
    """
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Use a custom formatter to output logs as JSON strings
    # This makes them easy to parse on the frontend
    formatter = logging.Formatter(
        '{"level": "%(levelname)s", "message": "%(message)s"}'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[handler], force=True)