"""Persistence layer: load and save the three JSON state files.

Three files in data/:
  searches.tracked          all saved searches + found items
  telegram_api_credentials  bot token + chat id
  ntfy_config               server URL + topic

All load functions return an empty dict when the file does not exist yet.
All save functions overwrite the file completely (no merging).
migrate_queries() converts the old nested format to the current flat format.
Run once via --migrate after upgrading from the previous version.
"""

import json
import os

from subito.config import DB_FILE, NTFY_FILE, TG_CREDS_FILE


def load_queries() -> dict:
    if not os.path.isfile(DB_FILE):
        return {}
    with open(DB_FILE) as f:
        return json.load(f)


def save_queries(queries: dict) -> None:
    with open(DB_FILE, "w") as f:
        f.write(json.dumps(queries))


def load_api_credentials() -> dict:
    if not os.path.isfile(TG_CREDS_FILE):
        return {}
    with open(TG_CREDS_FILE) as f:
        return json.load(f)


def save_api_credentials(credentials: dict) -> None:
    with open(TG_CREDS_FILE, "w") as f:
        f.write(json.dumps(credentials))


def load_ntfy_config() -> dict:
    if not os.path.isfile(NTFY_FILE):
        return {}
    with open(NTFY_FILE) as f:
        return json.load(f)


def save_ntfy_config(config: dict) -> None:
    with open(NTFY_FILE, "w") as f:
        f.write(json.dumps(config))


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
