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

from subito import notifications, scraper, storage
from subito import queries as q
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

    # Priority: CLI flag > env var > default
    delay = args.delay or int(os.environ.get("DELAY", 120))
    active_hour = args.active_hour or int(os.environ.get("ACTIVE_HOUR", 0))
    pause_hour = args.pause_hour or int(os.environ.get("PAUSE_HOUR", 0))
    query_delay = (
        args.query_delay
        if args.query_delay is not None
        else int(os.environ.get("QUERY_DELAY", 60))
    )
    bot_detection_sleep = (
        args.bot_detection_sleep
        if args.bot_detection_sleep is not None
        else int(os.environ.get("BOT_DETECTION_SLEEP", 86400))
    )

    cfg = AppConfig(
        tgoff=args.tgoff,
        ntfyoff=args.ntfyoff,
        win_notifyoff=args.win_notifyoff,
        query_delay=query_delay,
        bot_detection_sleep=bot_detection_sleep,
    )

    # Subcommands

    if args.command == "add":
        q.add(
            queries,
            args.url,
            args.name,
            args.min_price,
            args.max_price,
            tuttosubito_only=args.tuttosubito_only,
        )
        scraper.run_query(
            args.name, queries[args.name], False, cfg, credentials, ntfy_config
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
            q.print_list_short(queries)
        else:
            q.print_list(queries)
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
                ok = scraper.refresh(queries, notify, cfg, credentials, ntfy_config)
                notify = True
                storage.save_queries(queries)
                if not ok:
                    h = cfg.bot_detection_sleep // 3600
                    msg = f"Bot detection triggered. Polling paused for {h}h."
                    logger.warning(msg)
                    if notifications.is_telegram_active(credentials, cfg):
                        notifications.send_telegram_messages([msg], credentials)
                    if notifications.is_ntfy_active(ntfy_config, cfg):
                        notifications.send_ntfy_messages([msg], ntfy_config)
                    t.sleep(cfg.bot_detection_sleep)
                    continue
                logger.info(f"Next poll in {delay} seconds.")
            t.sleep(delay)
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
