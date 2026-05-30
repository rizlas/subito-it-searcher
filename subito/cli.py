"""Command-line interface: subcommands for actions, flags for run control.

Subcommands: add, delete, list, migrate, setup
Run modes (top-level flags): default polling, --refresh, --bot
"""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor subito.it and get notified when new items match your searches."
        ),
    )

    parser.add_argument(
        "--refresh",
        "-r",
        dest="refresh",
        action="store_true",
        help="Run all searches once and exit",
    )
    parser.set_defaults(refresh=False)

    parser.add_argument(
        "--bot",
        dest="bot",
        action="store_true",
        help="Start interactive Telegram bot",
    )
    parser.set_defaults(bot=False)

    parser.add_argument(
        "--delay",
        dest="delay",
        default=None,
        type=int,
        help="Polling interval in seconds (default: 120)",
    )
    parser.add_argument(
        "--active-hour",
        "-ah",
        dest="active_hour",
        type=int,
        help="Hour when to start polling in 24h notation (e.g. 8 for 08:00)",
    )
    parser.add_argument(
        "--pause-hour",
        "-ph",
        dest="pause_hour",
        type=int,
        help="Hour when to stop polling in 24h notation (e.g. 23 for 23:00)",
    )

    # Notifications flags
    notif = parser.add_argument_group("notifications")
    notif.add_argument(
        "--tgoff",
        dest="tgoff",
        action="store_true",
        help="Disable Telegram notifications",
    )
    parser.set_defaults(tgoff=False)
    notif.add_argument(
        "--ntfyoff",
        dest="ntfyoff",
        action="store_true",
        help="Disable ntfy notifications",
    )
    parser.set_defaults(ntfyoff=False)
    notif.add_argument(
        "--winoff",
        dest="win_notifyoff",
        action="store_true",
        help="Disable Windows toast notifications",
    )
    parser.set_defaults(win_notifyoff=False)

    # Subcommands
    sub = parser.add_subparsers(dest="command")

    # Add
    p_add = sub.add_parser("add", help="Add a new search")
    p_add.add_argument("name", help="Name for this search")
    p_add.add_argument("url", help="Subito.it search URL")
    p_add.add_argument(
        "--min-price", dest="min_price", type=int, help="Minimum price (e.g. 50)"
    )
    p_add.add_argument(
        "--max-price", dest="max_price", type=int, help="Maximum price (e.g. 200)"
    )

    # Delete
    p_del = sub.add_parser("delete", help="Delete a search")
    p_del.add_argument("name", help="Name of the search to delete")

    # List
    p_list = sub.add_parser("list", help="List active searches")
    p_list.add_argument(
        "--short",
        dest="short",
        action="store_true",
        help="Compact output",
    )
    p_list.set_defaults(short=False)

    # Migrate
    sub.add_parser(
        "migrate",
        help="Migrate searches.tracked from old nested format to the new format",
    )

    # Setup
    p_setup = sub.add_parser("setup", help="Configure notification channels")

    tg = p_setup.add_argument_group("telegram")
    tg.add_argument("--telegram-token", dest="token", help="Telegram bot API token")
    tg.add_argument("--telegram-chat-id", dest="chatid", help="Telegram chat id")

    ntfy = p_setup.add_argument_group("ntfy")
    ntfy.add_argument("--ntfy-server", dest="ntfy_server", help="ntfy server URL")
    ntfy.add_argument("--ntfy-topic", dest="ntfy_topic", help="ntfy topic")

    return parser
