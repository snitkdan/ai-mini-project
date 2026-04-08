# logger.py
"""Centralised logging configuration for the project."""

import logging


def _configure() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return logging.getLogger("app")


logger = _configure()
