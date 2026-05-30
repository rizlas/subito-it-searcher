#!/usr/bin/env python3
"""Entry point: parse args, load state, dispatch.

Nothing else lives here. All logic is in the subito/ package.
Run with --help to see all options.
"""

from datetime import datetime, time
import logging
import logging.handlers
import os
import time as t

from subito import queries as q
from subito import scraper, storage
from subito.bot import run_bot
from subito.cli import build_parser
from subito.config import DATA_DIR, AppConfig

logger = logging.getLogger(__name__)


def _in_between(now: time, start: time, end: time) -> bool:
    if start < end:
        return start <= now < end
    elif start == end:
        return True
    else:
        return start <= now or now < end


def main() -> None:
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(DATA_DIR, "errors.log"),
        maxBytes=1_000_000,
        backupCount=3,
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logging.getLogger().addHandler(file_handler)

    queries = storage.load_queries()
    credentials = storage.load_api_credentials()
    ntfy_config = storage.load_ntfy_config()
    cfg = AppConfig(
        tgoff=args.tgoff,
        ntfyoff=args.ntfyoff,
        win_notifyoff=args.win_notifyoff,
    )

    # Priority: CLI flag > env var > default
    delay = args.delay or int(os.environ.get("DELAY", 120))
    active_hour = args.active_hour or int(os.environ.get("ACTIVE_HOUR", 0))
    pause_hour = args.pause_hour or int(os.environ.get("PAUSE_HOUR", 0))

    # Subcommands

    if args.command == "add":
        q.add(
            queries,
            args.url,
            args.name,
            args.min_price,
            args.max_price,
            shipping_only=args.shipping_only,
            tuttosubito_only=args.tuttosubito_only,
        )
        scraper.run_query(
            args.name, queries[args.name], False, queries, cfg, credentials, ntfy_config
        )
        storage.save_queries(queries)
        logger.info(f"Search '{args.name}' added.")
        return

    if args.command == "delete":
        q.delete(queries, args.name)
        storage.save_queries(queries)
        logger.info(f"Search '{args.name}' deleted.")
        return

    if args.command == "list":
        if args.short:
            q.print_sitrep(queries)
        else:
            q.print_queries(queries)
        return

    if args.command == "migrate":
        confirm = input(
            "Migrate data files and search format? This will rename files and "
            "overwrite searches.json. [Y/n] "
        )
        if confirm.strip() != "Y":
            logger.info("Migration cancelled.")
            return
        renamed = storage.migrate_files()
        for r in renamed:
            logger.info(f"Renamed: {r}")
        queries = storage.load_queries()
        migrated = storage.migrate_queries(queries)
        storage.save_queries(migrated)
        logger.info(f"Migrated {len(migrated)} search(es).")
        return

    if args.command == "setup":
        if args.token and args.chatid:
            credentials["token"] = args.token
            credentials["chatid"] = args.chatid
            storage.save_api_credentials(credentials)
            logger.info("Telegram credentials saved.")
        if args.ntfy_server and args.ntfy_topic:
            ntfy_config["ntfy_server"] = args.ntfy_server
            ntfy_config["ntfy_topic"] = args.ntfy_topic
            storage.save_ntfy_config(ntfy_config)
            logger.info("ntfy config saved.")
        return

    # Run modes

    if args.refresh:
        scraper.refresh(queries, True, cfg, credentials, ntfy_config)
        storage.save_queries(queries)
        return

    if args.bot:
        run_bot(
            queries=queries,
            credentials=credentials,
            ntfy_config=ntfy_config,
            cfg=cfg,
            delay=delay,
            active_hour=active_hour,
            pause_hour=pause_hour,
        )
        return

    # Default: polling loop
    notify = False
    try:
        while True:
            if _in_between(datetime.now().time(), time(active_hour), time(pause_hour)):
                scraper.refresh(queries, notify, cfg, credentials, ntfy_config)
                notify = True
                logger.info(f"Next poll in {delay} seconds.")
                storage.save_queries(queries)
            t.sleep(delay)
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
