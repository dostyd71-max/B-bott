import sys
sys.path.insert(0, '/data/user/0/ru.iiec.pydroid3/files/aarch64-linux-android/')

import json
import random
import time
import logging
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

BOT_TOKEN    = "8664939937:AAGjjyZ3VfPY2YXp996YwNPRzGgYZe9DAko"

VIDEOS_FILE  = "videos.txt.py"
USERS_FILE   = "users.json"

UNLOCK_TIMER = 45

AD_LINKS = [
    "https://www.effectivecpmnetwork.com/sv07qnajbb?key=1f69dc6d466030073eaf49bfd0a8edd7",
    "https://omg10.com/4/10213320",
    "https://www.effectivecpmnetwork.com/jrtna0n5?key=4d11c7c16ef4195cc8febfa939ca3bc3",
]

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# VIDEO LINK LOADER
# ─────────────────────────────────────────────

def load_video_links() -> list:
    path = Path(VIDEOS_FILE)
    if not path.exists():
        logger.warning(f"{VIDEOS_FILE} not found – starting with empty list.")
        return []
    links = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("http"):
            links.append(line)
    logger.info(f"Loaded {len(links)} video links from {VIDEOS_FILE}")
    return links


# ─────────────────────────────────────────────
# USER DATA
# ─────────────────────────────────────────────

def load_users() -> dict:
    if not Path(USERS_FILE).exists():
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error("users.json is corrupted – starting fresh.")
        return {}


def save_users(users: dict) -> None:
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def get_user(users: dict, uid: int) -> dict:
    key = str(uid)
    if key not in users:
        users[key] = {
            "seen_videos": [],
            "unlocks": 0,
            "ad_index": 0,
            "link_sent_at": 0,
        }
    return users[key]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_unseen_videos(user: dict) -> list:
    all_links = load_video_links()
    seen      = set(user["seen_videos"])
    unseen    = [v for v in all_links if v not in seen]
    random.shuffle(unseen)
    return unseen


def current_ad_link(user: dict) -> str:
    return AD_LINKS[user["ad_index"] % len(AD_LINKS)]


def advance_ad_link(user: dict) -> None:
    user["ad_index"] = (user["ad_index"] + 1) % len(AD_LINKS)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Get Videos",   callback_data="get_videos")],
        [InlineKeyboardButton("📊 My Stats",     callback_data="my_stats")],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")],
    ])


def unlock_keyboard(ad_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Complete Task to Unlock", url=ad_url)],
        [InlineKeyboardButton("🔓 I completed the task",   callback_data="claimed")],
    ])


# ─────────────────────────────────────────────
# SEND VIDEOS
# ─────────────────────────────────────────────

async def send_videos(count: int, user: dict, uid: int,
                      context: ContextTypes.DEFAULT_TYPE) -> int:
    unseen  = get_unseen_videos(user)
    to_send = unseen[:count]

    for link in to_send:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🎬 Here is your video:\n{link}",
            )
            user["seen_videos"].append(link)
            logger.info(f"Sent video link to user {uid}")
        except Exception as e:
            logger.error(f"Failed to send video to {uid}: {e}")

    return len(to_send)


# ─────────────────────────────────────────────
# SEND UNLOCK PROMPT
# ─────────────────────────────────────────────

async def send_unlock_prompt(uid: int, user: dict,
                              context: ContextTypes.DEFAULT_TYPE) -> None:
    ad_url = current_ad_link(user)
    user["link_sent_at"] = time.time()

    await context.bot.send_message(
        chat_id=uid,
        text=(
            "🔐 *Want 2 more videos?* Complete this quick task:\n\n"
            "1️⃣  Tap *Complete Task to Unlock* below\n"
            "2️⃣  Visit the link (stay a moment)\n"
            "3️⃣  Come back and tap *I completed the task*"
        ),
        parse_mode="Markdown",
        reply_markup=unlock_keyboard(ad_url),
    )
    logger.info(f"Sent unlock prompt to user {uid}")


# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Babe"

    users = load_users()
    user  = get_user(users, uid)

    logger.info(f"/start from user {uid} ({name})")

    await update.message.reply_text(
        f"Hey {name}! 🔥 Welcome to *Secret Baddie Unlock*\n\n"
        "I've got exclusive videos waiting for you 👀\n"
        "Here's a free one to get you started 🎁",
        parse_mode="Markdown",
    )

    sent = await send_videos(1, user, uid, context)
    if sent == 0:
        await update.message.reply_text(
            "🎉 You've already unlocked everything! Check back soon for new drops."
        )
    else:
        await update.message.reply_text(
            "Tap *Get Videos* to unlock more 🔓",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    save_users(users)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid   = update.effective_user.id
    users = load_users()
    user  = get_user(users, uid)

    total_vids = len(load_video_links())
    seen_count = len(user["seen_videos"])
    remaining  = total_vids - seen_count

    await update.message.reply_text(
        f"📊 *Your Stats*\n\n"
        f"🎬 Videos watched : {seen_count}\n"
        f"🔓 Unlocks earned : {user['unlocks']}\n"
        f"📦 Videos left    : {remaining}",
        parse_mode="Markdown",
    )
    save_users(users)


async def adminstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users         = load_users()
    total_users   = len(users)
    total_unlocks = sum(u.get("unlocks", 0) for u in users.values())

    await update.message.reply_text(
        f"🛡 *Admin Stats*\n\n"
        f"👥 Total users   : {total_users}\n"
        f"🔓 Total unlocks : {total_unlocks}",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# BUTTON HANDLER
# ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    uid   = query.from_user.id
    data  = query.data
    users = load_users()
    user  = get_user(users, uid)

    if data == "get_videos":
        logger.info(f"User {uid} tapped Get Videos")
        unseen = get_unseen_videos(user)

        if not unseen:
            await query.message.reply_text(
                "🎉 *You have unlocked all videos!*\n\n"
                "New content added daily. Come back in 12 hours 🕛",
                parse_mode="Markdown",
            )
        else:
            sent = await send_videos(2, user, uid, context)
            if sent > 0:
                await send_unlock_prompt(uid, user, context)
            else:
                await query.message.reply_text(
                    "🎉 *You have unlocked all videos!*\n\n"
                    "New content added daily. Come back in 12 hours 🕛",
                    parse_mode="Markdown",
                )

    elif data == "claimed":
        elapsed = time.time() - user.get("link_sent_at", 0)
        logger.info(f"User {uid} claimed after {elapsed:.1f}s")

        if elapsed < UNLOCK_TIMER:
            await query.message.reply_text(
                "⏳ Please make sure you visited the link completely and try again!"
            )
        else:
            user["unlocks"] += 1
            advance_ad_link(user)

            unseen = get_unseen_videos(user)
            if not unseen:
                await query.message.reply_text(
                    "🎉 *You have unlocked all videos!*\n\n"
                    "New content added daily. Come back in 12 hours 🕛",
                    parse_mode="Markdown",
                )
            else:
                sent = await send_videos(2, user, uid, context)
                if sent > 0:
                    still_unseen = get_unseen_videos(user)
                    if still_unseen:
                        await send_unlock_prompt(uid, user, context)
                    else:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=(
                                "🎉 *You have unlocked all videos!*\n\n"
                                "New content added daily. Come back in 12 hours 🕛"
                            ),
                            parse_mode="Markdown",
                        )

    elif data == "my_stats":
        total_vids = len(load_video_links())
        seen_count = len(user["seen_videos"])
        remaining  = total_vids - seen_count

        await query.message.reply_text(
            f"📊 *Your Stats*\n\n"
            f"🎬 Videos watched : {seen_count}\n"
            f"🔓 Unlocks earned : {user['unlocks']}\n"
            f"📦 Videos left    : {remaining}",
            parse_mode="Markdown",
        )

    elif data == "how_it_works":
        await query.message.reply_text(
            "ℹ️ *How Secret Baddie Unlock Works*\n\n"
            "1️⃣  Tap *Get Videos* to receive 2 exclusive videos\n"
            "2️⃣  Tap *Complete Task to Unlock* and visit the link\n"
            "3️⃣  Wait a moment, then tap *I completed the task*\n"
            "4️⃣  Unlock 2 more videos instantly! 🎬\n\n"
            "New videos drop daily 🔥",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    save_users(users)


# ─────────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error: {context.error}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main() -> None:
    print("=" * 50)
    print("  Secret Baddie Unlock Bot  –  Starting up")
    print("=" * 50)

    video_links = load_video_links()
    print(f"  Videos loaded  : {len(video_links)}")
    print(f"  Ad links ready : {len(AD_LINKS)}")
    print(f"  Unlock timer   : {UNLOCK_TIMER}s")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("stats",      stats_command))
    app.add_handler(CommandHandler("adminstats", adminstats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    print("  Bot is running...\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
