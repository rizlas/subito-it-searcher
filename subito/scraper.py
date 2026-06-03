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

Extracted fields per item:
  title, link, date, location, price
  shipping        bool  /item_shippable key "1"
  tuttosubito     bool  /item_shipping_type == "Spedizione con TuttoSubito"
  verified_dealer bool  proTransactionsEnabled + tuttosubito
"""

from datetime import datetime
import json
import logging
import time

from bs4 import BeautifulSoup
from curl_cffi import requests

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",  # noqa: E501
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",  # noqa: E501
}


def run_query(
    name: str,
    search: dict,
    notify: bool,
    cfg: AppConfig,
    credentials: dict,
    ntfy_config: dict,
) -> list[str] | None:
    """Fetch one search page, diff against cache, return messages for new items.

    Mutates search['items'] in-place (adds new items, removes sold ones).
    Returns a list of formatted message strings for each new item found,
    or None if an anti-bot challenge was detected (caller should abort the run).
    """
    url = search["url"]
    min_price = search["min_price"]  # int or None
    max_price = search["max_price"]  # int or None
    tuttosubito_only = search.get("tuttosubito_only", False)
    items = search["items"]

    logger.info(f'Running query "{name}" - {url}')

    msg = []

    # Fetch and parse
    page = requests.get(url, headers=HEADERS, impersonate="chrome124", timeout=15)

    _antibot = ("captcha-delivery.com", "Please enable JS", "dd.js")
    if page.status_code == 403 or any(m in page.text for m in _antibot):
        logger.warning(
            "Bot detection triggered. "
            "Stop the script, wait a few hours, open subito.it in a browser and "
            "solve any captcha, then restart."
        )
        return None

    soup = BeautifulSoup(page.text, "html.parser")

    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag:
        logger.warning(
            f"Could not find JSON data on page for '{name}'. "
            "Aborting cycle — possible anti-bot challenge or site structure change."
        )
        return None

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

            # Shipping
            shippable_feature = features.get("/item_shippable")
            shipping = (
                shippable_feature is not None
                and shippable_feature.get("values", [{}])[0].get("key") == "1"
            )

            # TuttoSubito: shipping handled by subito.it (buyer protection)
            shipping_type = (
                features.get("/item_shipping_type", {})
                .get("values", [{}])[0]
                .get("value", "")
            )
            tuttosubito = shipping_type == "Spedizione con TuttoSubito"

            # Verified dealer: registered shop + TuttoSubito transaction
            advertiser = product.get("advertiser", {})
            verified_dealer = (
                advertiser.get("proTransactionsEnabled") is True and tuttosubito
            )

            is_sold = product.get("sold", False)

        except Exception as e:
            logger.warning(f"Skipped item in '{name}': {e}")
            continue

        # Remove sold items from cache
        if is_sold:
            if link in items:
                del items[link]
            continue

        # Filters
        if tuttosubito_only and not tuttosubito:
            continue
        if min_price is not None and price != "Unknown price" and price < min_price:
            continue
        if max_price is not None and price != "Unknown price" and price > max_price:
            continue

        if link not in items:
            badges = []
            if tuttosubito:
                badges.append("TuttoSubito")
            if verified_dealer:
                badges.append("Rivenditore verificato")
            badge_str = f" [{', '.join(badges)}]" if badges else ""

            tmp = (
                f"{date}\n"
                f"*{title}*\n"
                f"€ {price}{badge_str}\n"
                f"{location}\n"
                f"{link}\n"
            )
            msg.append(tmp)
            items[link] = {
                "title": title,
                "price": price,
                "location": location,
                "date": date,
                "shipping": shipping,
                "tuttosubito": tuttosubito,
                "verified_dealer": verified_dealer,
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
) -> bool:
    """Run all queries. Returns False if aborted due to anti-bot detection."""
    try:
        query_list = list(queries.items())
        for i, (name, search) in enumerate(query_list):
            result = run_query(name, search, notify, cfg, credentials, ntfy_config)
            if result is None:
                logger.warning("Aborting refresh cycle to protect IP reputation.")
                return False
            if i < len(query_list) - 1 and cfg.query_delay > 0:
                logger.debug(f"Waiting {cfg.query_delay}s before next query.")
                time.sleep(cfg.query_delay)
    except requests.exceptions.ConnectionError:
        logger.warning("Connection error")
    except requests.exceptions.Timeout:
        logger.warning("Server timeout error")
    except requests.exceptions.HTTPError:
        logger.warning("HTTP error")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    return True
