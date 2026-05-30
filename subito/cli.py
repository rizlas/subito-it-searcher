"""Command-line interface: all flags defined in one place.

Every argument is declared inside build_parser(). To add, remove, or rename
a flag, this is the only file to touch. Includes --migrate for one-time
data format upgrades (see storage.migrate_queries).
"""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    # Search management
    parser.add_argument("--add", dest="name", help="Name of new tracking to be added")
    parser.add_argument("--url", help="URL for your new tracking's search query")
    parser.add_argument(
        "--min-price", dest="min_price", help="Minimum price for the query"
    )
    parser.add_argument(
        "--max-price", dest="max_price", help="Maximum price for the query"
    )
    parser.add_argument("--delete", help="Name of the search you want to delete")

    # Execution modes
    parser.add_argument(
        "--refresh",
        "-r",
        dest="refresh",
        action="store_true",
        help="Refresh search results once",
    )
    parser.set_defaults(refresh=False)

    parser.add_argument(
        "--daemon",
        "-d",
        dest="daemon",
        action="store_true",
        help="Keep refreshing search results forever (default delay 120 seconds)",
    )
    parser.set_defaults(daemon=False)

    parser.add_argument(
        "--bot",
        dest="bot",
        action="store_true",
        help="Run as an interactive Telegram bot daemon (requires token + chatid)",
    )
    parser.set_defaults(bot=False)

    parser.add_argument(
        "--active-hour",
        "-ah",
        dest="active_hour",
        help="Hour when to be active in 24h notation",
    )
    parser.add_argument(
        "--pause-hour",
        "-ph",
        dest="pause_hour",
        help="Hour when to pause in 24h notation",
    )
    parser.add_argument(
        "--delay",
        dest="delay",
        help="Delay for the daemon option (in seconds)",
    )
    parser.set_defaults(delay=120)

    parser.add_argument(
        "--migrate",
        dest="migrate",
        action="store_true",
        help="Migrate searches.tracked from the old nested format to the new format",
    )
    parser.set_defaults(migrate=False)

    # Display
    parser.add_argument(
        "--list",
        dest="list",
        action="store_true",
        help="Print a list of current trackings",
    )
    parser.set_defaults(list=False)

    parser.add_argument(
        "--short-list",
        dest="short_list",
        action="store_true",
        help="Print a more compact list",
    )
    parser.set_defaults(short_list=False)

    # Notification control
    parser.add_argument(
        "--tgoff",
        dest="tgoff",
        action="store_true",
        help="Turn off Telegram messages",
    )
    parser.set_defaults(tgoff=False)

    parser.add_argument(
        "--notifyoff",
        dest="win_notifyoff",
        action="store_true",
        help="Turn off Windows notifications",
    )
    parser.set_defaults(win_notifyoff=False)

    parser.add_argument(
        "--ntfyoff",
        dest="ntfyoff",
        action="store_true",
        help="Turn off ntfy notifications",
    )
    parser.set_defaults(ntfyoff=False)

    # Telegram setup
    parser.add_argument(
        "--add-token", dest="token", help="Telegram setup: add bot API token"
    )
    parser.add_argument(
        "--add-chat-id", dest="chatid", help="Telegram setup: add bot chat id"
    )

    # ntfy setup
    parser.add_argument("--ntfy-server", dest="ntfy_server", help="Set ntfy server URL")
    parser.add_argument(
        "--ntfy-topic", dest="ntfy_topic", help="Set ntfy topic for notifications"
    )

    return parser
