## Contact

For support contact [@Vm_0011](https://t.me/Vm_0011) on Telegram.

Use only on systems you own or are explicitly permitted to load-test.

# Vm panel (Telegram)

Whitelisted operators, local journal, `/bgmi` worker hook. Configure with `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS`. 

## Features

- Whitelist add/remove/list and optional time-bound pass tracking in memory
- Local journal (`log.txt`) and `/mylogs` filtered by Telegram user id
- `/bgmi` dispatches an external worker binary configured in code
- Optional per-user cooldown (configurable constant)
- Operator-only maintenance: logs export, broadcast, bulk clears

## Prerequisites

- Python 3.10+ (3.14 works with current wheels)
- Dependencies: see `requirement.txt` (`pyTelegramBotAPI`, `Flask`, `python-dotenv`, …)
- A Telegram bot token from BotFather

## Getting Started

### Installation

```sh
git clone <your-fork-or-mirror>.git
cd <repo>
./setup.sh   # or: python -m venv .venv && pip install -r requirement.txt
cp .env.example .env
```

Fill `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ADMIN_IDS` (comma-separated numeric ids)

### Usage

```sh
./run.sh          # runs m.py
./run.sh watcher  # optional process supervisor
```

## Bot commands

See `/help` inside Telegram for the live strings. In short: members get `/start`, `/help`, `/rules`, `/plan`, `/myinfo`, `/mylogs`, and `/bgmi` when whitelisted; operators get maintenance commands (`/add`, `/remove`, `/allusers`, `/logs`, `/clearlogs`, `/clearusers`, `/broadcast`, `/admincmd`).

## Layout

- `m.py` — bot entrypoint
- `watcher.py` — optional restarter with aiogram ping
- `keep_alive.py` — small Flask bind for platform health checks
- `users.txt` — whitelist
- `log.txt` — journal

## Logging

Append-only journal in `log.txt`; operators can download it with `/logs`. Line format is visible in `record_command_logs` / `log_command` in `m.py`.

## License

MIT (see repository if a `LICENSE` file is present).

## Disclaimer

You are responsible for compliance with law and with any contract that covers the hosts you touch. This software is provided as-is.

## Contributing

If you wish to contribute to this project, feel free to submit a pull request or open an issue on GitHub.

