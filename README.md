# subito-it-searcher

Monitor subito.it and get notified when new items match your searches.

## Features

- Continuous polling with configurable delay and active time window
- Price range filtering per query
- Two independent notification channels: **Telegram** and **[ntfy](https://ntfy.sh)**, both can run simultaneously
- Interactive **Telegram bot mode**: manage searches and receive results via chat commands
- Windows 10 toast notifications
- Docker support

## Setup

### Install dependencies

```bash
pip3 install -r requirements.txt
```

For Windows 10 notifications, also install `win10toast`.

### Telegram configuration

1. Create a bot via [@BotFather](https://t.me/botfather). It will give you an API token
2. Either create a public channel and add the bot as administrator, or use your personal chat ID
3. Save the credentials:

```bash
python3 subito-searcher.py setup --telegram-token "YOUR_TOKEN" --telegram-chat-id "@your_channel"
```

### ntfy configuration

[ntfy](https://ntfy.sh) is a simple HTTP push notification service:

```bash
python3 subito-searcher.py setup --ntfy-server https://ntfy.sh --ntfy-topic your_topic_name
```

Telegram and ntfy are independent. If both are configured, new items are sent to both.

### Environment variables

All credentials and run parameters can be set via environment variables. Env vars take priority over config files.

|      Variable      |                Description                 |
| ------------------ | ------------------------------------------ |
| `TELEGRAM_TOKEN`   | Telegram bot API token                     |
| `TELEGRAM_CHAT_ID` | Telegram chat id                           |
| `NTFY_SERVER`      | ntfy server URL                            |
| `NTFY_TOPIC`       | ntfy topic                                 |
| `DELAY`            | Polling interval in seconds (default: 120) |
| `ACTIVE_HOUR`      | Hour when to start polling in 24h notation |
| `PAUSE_HOUR`       | Hour when to stop polling in 24h notation  |

### Docker

```bash
docker build -t subito-searcher .
docker run -v ./data:/app/data subito-searcher <flags>
```

Docker Compose:

```yaml
services:
  subito-searcher:
    build: .
    volumes:
      - ./data:/app/data
    environment:
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
    command: <flags>
```

## Usage

```bash
python3 subito-searcher.py --help
python3 subito-searcher.py <subcommand> --help
```

### Manage searches

```bash
# Add a search (--min-price and --max-price are optional)
python3 subito-searcher.py add Auto "https://www.subito.it/annunci-italia/vendita/usato/?q=auto"
python3 subito-searcher.py add Iphone "https://www.subito.it/annunci-italia/vendita/usato/?q=iphone" --min-price 50 --max-price 300

# Remove a search
python3 subito-searcher.py delete Auto

# List active searches
python3 subito-searcher.py list
python3 subito-searcher.py list --short
```

### Run modes

```bash
# Start polling loop (default, no subcommand needed)
python3 subito-searcher.py

# Custom polling interval and active time window
python3 subito-searcher.py --delay 30 --active-hour 8 --pause-hour 23

# Run all searches once and exit
python3 subito-searcher.py --refresh

# Interactive Telegram bot (responds to commands + pushes new items automatically)
python3 subito-searcher.py --bot --delay 120
```

### Bot commands

When running with `--bot`, send these commands to your Telegram bot:

| Command | Description |
| --- | --- |
| `/list` | Show all active searches |
| `/add <name> <url> [min] [max]` | Add a new search |
| `/delete <name>` | Remove a search |
| `/refresh` | Run all searches now and report new items |
| `/status` | Show last run time, delay, active window |
| `/help` | List all commands |

### Notification flags

```bash
--tgoff    # Disable Telegram notifications
--ntfyoff  # Disable ntfy notifications
--winoff   # Disable Windows toast notifications
```

### Migration

If upgrading from a previous version, run once to convert the stored searches file to the new format:

```bash
python3 subito-searcher.py migrate
```

## Project structure

```text
subito-searcher.py      # Entry point: parse args, load state, dispatch
subito/
  scraper.py            # Core: fetch, parse, diff. Edit here to fix site changes
  notifications.py      # Telegram and ntfy channels (independent)
  bot.py                # Interactive Telegram bot daemon
  queries.py            # add, delete, print helpers
  storage.py            # Load/save JSON state files + migration
  cli.py                # Subcommands and flags
  config.py             # Paths and AppConfig dataclass
data/                   # State files, gitignored, Docker volume
  searches.json
  telegram.json
  ntfy.json
```

## Troubleshooting

- **No Telegram messages**: confirm the bot is added to the channel as admin and the chat ID starts with `@`
- **No items found**: subito.it embeds results in a `__NEXT_DATA__` script tag. If the site redesigns, update the JSON path in `subito/scraper.py`
- **Test Telegram manually**: `https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHATID>&text=test`
