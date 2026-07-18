import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Quiet down noisy third-party loggers by default.
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
