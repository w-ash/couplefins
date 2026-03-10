import sys

from loguru import logger


def setup_logging(*, verbose: bool = False) -> None:
    logger.remove()

    level = "DEBUG" if verbose else "INFO"

    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    logger.add(
        "logs/couplefins.log",
        level="DEBUG",
        serialize=True,
        rotation="10 MB",
        retention="1 week",
        compression="gz",
        enqueue=True,
    )
