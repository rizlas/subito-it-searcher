"""Core scraping logic: the most important file in the project.

run_query() is the full cycle for one search:
  HTTP fetch, BeautifulSoup parse, find __NEXT_DATA__ script tag,
  walk JSON to items.list, extract title/price/location/shipping,
  diff against cache, return new items as a list of message strings.

If subito.it changes its page structure, this is where you fix it. The JSON
path is: props -> pageProps -> initialState -> items -> originalList.

refresh() iterates over all saved searches and calls run_query() for each,
with network error handling wrapped around the whole loop.

HEADERS at the top is the browser impersonation block. Do not change it
unless the site starts blocking requests.
"""

from datetime import datetime
import json
import logging

from bs4 import BeautifulSoup
import requests

from subito.config import AppConfig
from subito.notifications import (
    is_ntfy_active,
    is_telegram_active,
    notify_windows,
    send_ntfy_messages,
    send_telegram_messages,
)

logger = logging.getLogger(__name__)

# Browser-like headers to avoid bot detection on subito.it
HEADERS = {
    "Accept": '"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"',  # noqa: E501
    "Accept-Encoding": '"gzip, deflate"',
    "Accept-Language": '"en-US,en;q=0.5"',
    "Connection": '"keep-alive"',
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Brave";v="128"',
    "Sec-Ch-Ua-Mobile": '"?0"',
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": '"document"',
    "Sec-Fetch-Mode": '"navigate"',
    "Sec-Fetch-Site": '"none"',
    "Sec-Fetch-User": '"?1"',
    "Sec-Gpc": '"1"',
    "Upgrade-Insecure-Requests": '"1"',
    "User-Agent": '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"',  # noqa: E501
}


def run_query(
    name: str,
    search: dict,
    notify: bool,
    queries: dict,
    cfg: AppConfig,
    credentials: dict,
    ntfy_config: dict,
) -> list[str]:
    """Fetch one search page, diff against cache, return messages for new items.

    Mutates search['items'] in-place (adds new items, removes sold ones).
    Returns a list of formatted message strings for each new item found.
    """
    url = search["url"]
    min_price = search["min_price"]  # int or None
    max_price = search["max_price"]  # int or None
    items = search["items"]

    logger.info(f'Running query "{name}" - {url}')

    msg = []

    # Fetch and parse
    page = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(page.text, "html.parser")

    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag:
        logger.error("Could not find JSON data on page (Next.js data not found).")
        return msg

    json_data = json.loads(script_tag.string)

    # Path into Next.js hydration data where subito.it stores search results
    try:
        items_list = json_data["props"]["pageProps"]["initialState"]["items"][
            "originalList"
        ]
    except KeyError:
        items_list = []

    # Process each item
    for product in items_list:

        try:
            item_key = product.get("urn")
            if not item_key:
                continue

            title = product.get("subject", "No Title")
            link = product.get("urls", {}).get("default", "")
            raw_date = product.get("date", "")
            try:
                date = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S").strftime(
                    "%d-%m-%Y %H:%M:%S"
                )
            except ValueError:
                date = raw_date
            location = (
                product.get("geo", {}).get("town", {}).get("value", "Unknown town")
                + " ("
                + product.get("geo", {})
                .get("city", {})
                .get("shortName", "Unknown province")
                + ")"
            )

            # Price
            raw_price = None
            price = "Unknown price"
            features = product.get("features", {})
            price_feature = features.get("/price")
            if price_feature and "values" in price_feature:
                raw_price = price_feature["values"][0].get("key")
            if raw_price:
                try:
                    price = int(raw_price)
                except ValueError:
                    pass

            shipping = None
            shipping_feature = features.get("/item_shippable")
            if shipping_feature:
                raw_shipping = shipping_feature["values"][0].get("value")
                if raw_shipping:
                    shipping = "(Shipping available)"

            is_sold = product.get("sold", False)

        except Exception:
            continue

        # Remove sold items from cache
        if is_sold:
            if link in items:
                del items[link]
            continue

        # Price filter
        if min_price is None or price == "Unknown price" or price >= min_price:
            if max_price is None or price == "Unknown price" or price <= max_price:
                if link not in items:
                    tmp = (
                        f"{date}\n"
                        f"*{title}*\n"
                        f"€ {price} {shipping}\n"
                        f"{location}\n"
                        f"{link}\n"
                    )
                    msg.append(tmp)
                    items[link] = {
                        "title": title,
                        "price": price,
                        "location": location,
                        "date": date,
                    }
                    logger.debug(f"New result: {title} - {price} - {location}")

    # Notify and report
    if msg:
        if notify:
            if not cfg.win_notifyoff:
                notify_windows(name)
            if is_telegram_active(credentials, cfg):
                send_telegram_messages(msg, credentials)
            if is_ntfy_active(ntfy_config, cfg):
                send_ntfy_messages(msg, ntfy_config)
            items_text = "\n".join(msg)
            logger.info(f"{len(msg)} new item(s) found:\n{items_text}")
    else:
        logger.info("All lists are already up to date.")

    return msg


def refresh(
    queries: dict,
    notify: bool,
    cfg: AppConfig,
    credentials: dict,
    ntfy_config: dict,
) -> None:
    try:
        for name, search in queries.items():
            run_query(name, search, notify, queries, cfg, credentials, ntfy_config)
    except requests.exceptions.ConnectionError:
        logger.warning("Connection error")
    except requests.exceptions.Timeout:
        logger.warning("Server timeout error")
    except requests.exceptions.HTTPError:
        logger.warning("HTTP error")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
