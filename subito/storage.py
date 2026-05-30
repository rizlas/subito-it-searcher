"""Persistence layer: load and save the three JSON state files.

Three files in data/:
  searches.json   all saved searches + found items
  telegram.json   bot token + chat id
  ntfy.json       server URL + topic

All load functions return an empty dict when the file does not exist yet.
All save functions overwrite the file completely (no merging).
migrate_queries() converts the old nested format to the current flat format.
Run once via --migrate after upgrading from the previous version.

Environment variables override file values (env > file > default):
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
  NTFY_SERVER, NTFY_TOPIC
"""

import json
import os

from subito.config import DATA_DIR, DB_FILE, NTFY_FILE, TG_CREDS_FILE


def load_queries() -> dict:
    if not os.path.isfile(DB_FILE):
        return {}
    with open(DB_FILE) as f:
        return json.load(f)


def save_queries(queries: dict) -> None:
    with open(DB_FILE, "w") as f:
        f.write(json.dumps(queries))


def load_api_credentials() -> dict:
    creds = {}
    if os.path.isfile(TG_CREDS_FILE):
        with open(TG_CREDS_FILE) as f:
            creds = json.load(f)
    if token := os.environ.get("TELEGRAM_TOKEN"):
        creds["token"] = token
    if chatid := os.environ.get("TELEGRAM_CHAT_ID"):
        creds["chatid"] = chatid
    return creds


def save_api_credentials(credentials: dict) -> None:
    with open(TG_CREDS_FILE, "w") as f:
        f.write(json.dumps(credentials))


def load_ntfy_config() -> dict:
    cfg = {}
    if os.path.isfile(NTFY_FILE):
        with open(NTFY_FILE) as f:
            cfg = json.load(f)
    if server := os.environ.get("NTFY_SERVER"):
        cfg["ntfy_server"] = server
    if topic := os.environ.get("NTFY_TOPIC"):
        cfg["ntfy_topic"] = topic
    return cfg


def save_ntfy_config(config: dict) -> None:
    with open(NTFY_FILE, "w") as f:
        f.write(json.dumps(config))


def migrate_files() -> list[str]:
    """Rename data files from the old naming convention to the new .json names.

    Old names: searches.tracked, telegram_api_credentials, ntfy_config
    New names: searches.json, telegram.json, ntfy.json

    Returns a list of rename descriptions for logging.
    Skips a rename if the destination already exists.
    """
    renames = [
        ("searches.tracked", "searches.json"),
        ("telegram_api_credentials", "telegram.json"),
        ("ntfy_config", "ntfy.json"),
    ]
    done = []
    for old_name, new_name in renames:
        old_path = os.path.join(DATA_DIR, old_name)
        new_path = os.path.join(DATA_DIR, new_name)
        if os.path.isfile(old_path) and not os.path.isfile(new_path):
            os.rename(old_path, new_path)
            done.append(f"{old_name} -> {new_name}")
    return done


def migrate_queries(old: dict) -> dict:
    """Convert the old nested structure to the new flat structure.

    Old: queries[name][url][min_price][max_price][link] = {title, price, location}
    New: queries[name] = {url, min_price (int|None), max_price (int|None),
                          items: {link: {title, price, location}}}
    """
    new = {}
    for name, urls in old.items():
        for url, min_prices in urls.items():
            for min_p, max_prices in min_prices.items():
                for max_p, items in max_prices.items():
                    new[name] = {
                        "url": url,
                        "min_price": None if min_p == "null" else int(min_p),
                        "max_price": None if max_p == "null" else int(max_p),
                        "items": items,
                    }
    return new
