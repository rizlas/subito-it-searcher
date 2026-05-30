#!/usr/bin/env python3
"""Entry point: parse args, load state, dispatch.

Run modes:
  --refresh   run all searches once and exit
  --daemon    poll on a timer forever (use --delay, --active-hour, --pause-hour)
  --bot       interactive Telegram bot daemon (see subito/bot.py)
  --migrate   convert searches.tracked from old nested format to new flat format,
              run once after upgrading from a previous version

Nothing else lives here. All logic is in the subito/ package.
"""

from datetime import datetime, time
import logging
import time as t

from subito import queries as q
from subito import scraper, storage
from subito.cli import build_parser
from subito.config import AppConfig

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

    queries = storage.load_queries()
    credentials = storage.load_api_credentials()
    ntfy_config = storage.load_ntfy_config()
    cfg = AppConfig(
        tgoff=args.tgoff,
        ntfyoff=args.ntfyoff,
        win_notifyoff=args.win_notifyoff,
    )

    # --- Migration ---
    if args.migrate:
        migrated = storage.migrate_queries(queries)
        storage.save_queries(migrated)
        logger.info(f"Migrated {len(migrated)} search(es). File updated.")
        return

    # --- Display ---
    if args.list:
        q.print_queries(queries)

    if args.short_list:
        q.print_sitrep(queries)

    # --- Search management ---
    if args.url is not None and args.name is not None:
        q.add(queries, args.url, args.name, args.min_price, args.max_price)
        scraper.run_query(
            args.name, queries[args.name], False, queries, cfg, credentials, ntfy_config
        )
        logger.info(f"Query '{args.name}' added.")

    if args.delete is not None:
        q.delete(queries, args.delete)
        logger.info(f"Query '{args.delete}' deleted.")

    # --- Credential / config setup ---
    if args.token is not None and args.chatid is not None:
        credentials["token"] = args.token
        credentials["chatid"] = args.chatid
        storage.save_api_credentials(credentials)
        logger.info("Telegram credentials saved.")

    if args.ntfy_server is not None and args.ntfy_topic is not None:
        ntfy_config["ntfy_server"] = args.ntfy_server
        ntfy_config["ntfy_topic"] = args.ntfy_topic
        storage.save_ntfy_config(ntfy_config)
        logger.info("ntfy config saved.")

    # --- Run modes ---
    active_hour = int(args.active_hour) if args.active_hour is not None else 0
    pause_hour = int(args.pause_hour) if args.pause_hour is not None else 0

    if args.refresh:
        scraper.refresh(queries, True, cfg, credentials, ntfy_config)

    storage.save_queries(queries)

    if args.bot:
        from subito.bot import run_bot

        run_bot(
            queries=queries,
            credentials=credentials,
            ntfy_config=ntfy_config,
            cfg=cfg,
            delay=int(args.delay),
            active_hour=active_hour,
            pause_hour=pause_hour,
        )
        return

    if args.daemon:
        notify = False
        while True:
            if _in_between(datetime.now().time(), time(active_hour), time(pause_hour)):
                scraper.refresh(queries, notify, cfg, credentials, ntfy_config)
                notify = True
                logger.info(f"Next poll in {args.delay} seconds.")
                storage.save_queries(queries)
            t.sleep(int(args.delay))


if __name__ == "__main__":
    main()
