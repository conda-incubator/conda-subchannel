"""
conda pip subcommand for CLI
"""

from __future__ import annotations

import argparse
from logging import getLogger

logger = getLogger(f"conda.{__name__}")


def configure_parser(parser: argparse.ArgumentParser): ...


def execute(args: argparse.Namespace) -> int:
    return 0
