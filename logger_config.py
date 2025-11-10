import logging
import os
import sys
import json

def setup_logger():
    """
    Configures a JSON-based logger that outputs to stdout.
    Reads LOG_LEVEL from environment variables (default: INFO).
    """
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Custom formatter to handle JSON encoding of the message
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "level": record.levelname,
                "message": record.getMessage()
            }
            return json.dumps(log_record)

    formatter = JsonFormatter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[handler], force=True)