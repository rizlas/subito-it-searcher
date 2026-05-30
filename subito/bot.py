"""Interactive Telegram bot daemon: two-way Telegram interface.

Two things run concurrently inside one asyncio event loop:
  _polling_loop()    asyncio.Task that calls scraper.run_query() on the delay
                     interval and pushes new items to the chat automatically.
  Command handlers   respond to /list /add /delete /refresh /status /help.

All shared state (queries, credentials, config) lives in app.bot_data, a plain dict
attached to the PTB Application. Both the loop and the handlers read and write the same
dict safely because asyncio is single-threaded cooperative.

The same token handles both push notifications and command responses. No extra setup
beyond --add-token / --add-chat-id.

Launch with:  python subito-searcher.py --bot [--delay 120] [--active-hour 8]
              [--pause-hour 23]

Requires token + chatid already configured (same credentials used for push notifications
in daemon mode).
"""

import asyncio
from datetime import datetime, time
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from subito import queries as q
from subito import scraper, storage
from subito.config import AppConfig

logger = logging.getLogger(__name__)


def _searches_text(queries: dict) -> str:
    return q.format_searches(queries, bold=True) or "No active searches."


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Subito Searcher Bot*\n\n"
        "Available commands:\n"
        "/list - show active searches\n"
        "/add `<name> <url> [min] [max]` - add a search\n"
        "/delete `<name>` - remove a search\n"
        "/refresh - run all searches now\n"
        "/status - show daemon state\n"
        "/help - this message"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data
    text = _searches_text(state["queries"])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /add `<name> <url> [minPrice] [maxPrice]`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    state = context.application.bot_data
    name = args[0]
    url = args[1]
    min_price = args[2] if len(args) > 2 else None
    max_price = args[3] if len(args) > 3 else None

    q.add(state["queries"], url, name, min_price, max_price)
    scraper.run_query(
        name,
        state["queries"][name],
        False,
        state["queries"],
        state["cfg"],
        state["credentials"],
        state["ntfy_config"],
    )
    storage.save_queries(state["queries"])
    await update.message.reply_text(
        f"Search *{name}* added.", parse_mode=ParseMode.MARKDOWN
    )


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /delete `<name>`", parse_mode=ParseMode.MARKDOWN
        )
        return

    state = context.application.bot_data
    name = args[0]
    if name not in state["queries"]:
        await update.message.reply_text(
            f"No search named *{name}* found.", parse_mode=ParseMode.MARKDOWN
        )
        return

    q.delete(state["queries"], name)
    storage.save_queries(state["queries"])
    await update.message.reply_text(
        f"Search *{name}* deleted.", parse_mode=ParseMode.MARKDOWN
    )


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data
    await update.message.reply_text("Running all searches...")

    all_msgs = []
    for name, search in state["queries"].items():
        new = scraper.run_query(
            name,
            search,
            False,
            state["queries"],
            state["cfg"],
            state["credentials"],
            state["ntfy_config"],
        )
        all_msgs.extend(new)

    storage.save_queries(state["queries"])

    if all_msgs:
        for m in all_msgs:
            await update.message.reply_text(m, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Nothing new.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data
    last = state.get("last_run")
    last_str = last.strftime("%Y-%m-%d %H:%M:%S") if last else "never"
    text = (
        f"*Daemon status*\n"
        f"Last run: {last_str}\n"
        f"Delay: {state['delay']}s\n"
        f"Active window: {state['active_hour']}:00 → {state['pause_hour']}:00\n"
        f"Searches tracked: {len(state['queries'])}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def _in_between(now: time, start: time, end: time) -> bool:
    if start < end:
        return start <= now < end
    elif start == end:
        return True
    else:
        return start <= now or now < end


async def _polling_loop(app: Application) -> None:
    notify = False  # suppress notifications on first run to avoid a flood
    while True:
        state = app.bot_data
        now = datetime.now().time()
        if _in_between(now, time(state["active_hour"]), time(state["pause_hour"])):
            all_msgs = []
            for name, search in state["queries"].items():
                new = scraper.run_query(
                    name,
                    search,
                    False,
                    state["queries"],
                    state["cfg"],
                    state["credentials"],
                    state["ntfy_config"],
                )
                all_msgs.extend(new)

            if notify and all_msgs:
                for m in all_msgs:
                    await app.bot.send_message(
                        chat_id=state["credentials"]["chatid"],
                        text=m,
                        parse_mode=ParseMode.MARKDOWN,
                    )

            storage.save_queries(state["queries"])
            state["last_run"] = datetime.now()
            notify = True

        await asyncio.sleep(state["delay"])


async def _post_init(app: Application) -> None:
    asyncio.create_task(_polling_loop(app))


def run_bot(
    queries: dict,
    credentials: dict,
    ntfy_config: dict,
    cfg: AppConfig,
    delay: int,
    active_hour: int,
    pause_hour: int,
) -> None:
    app = ApplicationBuilder().token(credentials["token"]).post_init(_post_init).build()

    app.bot_data.update(
        {
            "queries": queries,
            "credentials": credentials,
            "ntfy_config": ntfy_config,
            "cfg": cfg,
            "delay": delay,
            "active_hour": active_hour,
            "pause_hour": pause_hour,
            "last_run": None,
        }
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("Bot started. Waiting for commands...")
    app.run_polling()
