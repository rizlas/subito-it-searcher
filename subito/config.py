"""Paths and shared configuration.

Defines DATA_DIR (relative to project root, Docker-safe) and the three JSON
file paths used by storage.py. AppConfig carries the notification on/off flags
so no module needs to import argparse.Namespace directly.
"""

from dataclasses import dataclass
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "searches.tracked")
TG_CREDS_FILE = os.path.join(DATA_DIR, "telegram_api_credentials")
NTFY_FILE = os.path.join(DATA_DIR, "ntfy_config")


@dataclass
class AppConfig:
    tgoff: bool = False
    ntfyoff: bool = False
    win_notifyoff: bool = False
