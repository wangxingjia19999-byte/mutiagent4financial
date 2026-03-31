#!/usr/bin/env python
"""lianghua CLI 命令行工具入口"""
from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.cli import cli

if __name__ == "__main__":
    load_dotenv()
    cli()
