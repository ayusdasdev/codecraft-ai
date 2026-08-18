import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level)