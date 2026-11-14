"""Shared logging setup for command-line scripts."""
from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a concise root logger once."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
