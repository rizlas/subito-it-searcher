"""Notification channels: Telegram and ntfy, both independent.

Each channel has an is_*_active() guard (checks credentials exist and the
flag is not disabled) and a send_*_messages() function. scraper.py calls
both independently: if both are configured, both fire.

Known limitation: send_telegram_messages() builds a GET URL with the message
text inline, which can break on special characters. Switch to a POST with a
JSON body if that becomes a problem.
"""

import logging
import platform

import requests

from subito.config import AppConfig

logger = logging.getLogger(__name__)

# Windows-only toast notifications
if platform.system() == "Windows":
    from win10toast import ToastNotifier

    _toaster = ToastNotifier()


def is_telegram_active(credentials: dict, cfg: AppConfig) -> bool:
    return not cfg.tgoff and "chatid" in credentials and "token" in credentials


def send_telegram_messages(messages: list, credentials: dict) -> None:
    for msg in messages:
        url = (
            "https://api.telegram.org/bot"
            + credentials["token"]
            + "/sendMessage?chat_id="
            + credentials["chatid"]
            + "&parse_mode=markdown"
            + "&text="
            + msg
        )
        requests.get(url)


def is_ntfy_active(ntfy_config: dict, cfg: AppConfig) -> bool:
    return (
        not cfg.ntfyoff and "ntfy_server" in ntfy_config and "ntfy_topic" in ntfy_config
    )


def send_ntfy_messages(messages: list, ntfy_config: dict) -> None:
    url = f"{ntfy_config['ntfy_server'].rstrip('/')}/{ntfy_config['ntfy_topic']}"
    for msg in messages:
        try:
            requests.post(url, data=msg.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to send ntfy notification: {e}")


def notify_windows(query_name: str) -> None:
    if platform.system() == "Windows":
        _toaster.show_toast("New announcements", "Query: " + query_name)
