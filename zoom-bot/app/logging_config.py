# app/logging_config.py
import logging
import sys

try:
    from colorlog import ColoredFormatter
except ImportError:
    # If colorlog is missing, fall back to standard logging
    ColoredFormatter = None


def setup_logger(name: str = None) -> logging.Logger:
    """
    Create and return a configured logger, with colored output when colorlog is available.
    """
    if ColoredFormatter:
        formatter = ColoredFormatter(
            fmt="%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Show every log level
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False

    return logger
