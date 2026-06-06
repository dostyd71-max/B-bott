import json
import random
import time
import logging
from pathlib import Path
from datetime import time as dtime

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

BOT_TOKEN         = "8664939937:AAGjjyZ3VfPY2YXp996YwNPRzGgYZe9DAko"
CHANNEL_ID        = "@daniel4060"
VIDEOS_FILE       = "videos.txt"
USERS_FILE        = "users.json"
UNLOCK_TIMER      = 45
VIDEOS_PER_UNLOCK = 3

ADSTERRA = "https://www.effectivecpmnetwork.com/sv07qnajbb?key=1f69dc6d466030073eaf49bfd0a8edd7"
MONETAG  = "https://omg10.com/4/10213320"
KADAM    = "https://viiukuhe.com/dc/?blockID=423240&tb=https%3A%2F%2Fwww.profitablecpmratenetwork.com%2F"

NOTIFICATIONS = [
    "🔥 *Psst... new baddies are waiting for you!*\n\nYou've got unseen videos sitting there. Come unlock them before someone else does 👀",
    "😍 *Your daily dose of exclusive content is ready!*\n\nTap below and unlock your videos now 🔓",
    "💦 *Still thinking about it?*\n\nThe hottest content is just one task away. Come get it 🎬🔥",
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
# VIDEO ID LOADER
# ─────────────────────────────────────────────

def load_video_ids():
    path = Path(VIDEOS_FILE)
    if not path.exists():
        logger.warning(f"{VIDEOS_FILE} not found.")
        return []
    ids = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.isdigit():
            ids.append(int(line))
    logger.info(f"Loaded {len(ids)} video IDs")
    return ids


# ─────────────────────────────────────────────
# USER DATA
# ─────────────────────────────────────────────

def load_users():
    if not Path(USERS_FILE).exists():
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def get_user(users, uid):
    key = str(uid)
    if key not in users:
        users[key] = {
            "seen_videos": [],
            "unlocks": 0,
            "link_sent_at": 0,
            "link_clicked_at": 0,
            "first_unlock_time": 0,
        }
    return users[key]


# ─────────────────────────────────────────────
# AD LINK LOGIC
# ─────────────────────────────────────────────

def get_ad_link(user):
    now = time.time()
    first_unlock = user.get("first_unlock_time", 0)
    if first_unlock > 0 and (now - first_unlock) > 86400:
        user["unlocks"] = 0
        user["first_unlock_time"] = now
    unlocks = user.get("unlocks", 0)
    if unlocks < 2:
        return ADSTERRA
    elif unlocks == 2:
        return MONETAG
    else:
        return KADAM


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_unseen_videos(user):
    all_ids = load_video_ids()
    seen = set(user["seen_videos"])
    unseen = [v for v in all_ids if v not in seen]
    random.shuffle(unseen)
    return unseen


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Get Videos",   callback_data="get_videos")],
        [InlineKeyboardButton("📊 My Stats",     callback_data="my_stats")],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")],
    ])


def unlock_keyboard(ad_url):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Complete Task to Unlock", url=ad_url)],
        [InlineKeyboardButton("🔓 I completed the task",   callback_data="claimed")],
    ])


# ─────────────────────────────────────────────
# FORWARD VIDEOS
# ─────────────────────────────────────────────

async def forward_videos(count, user, uid, context):
    unseen = get_unseen_videos(user)
    to_send = unseen[:count]
    for msg_id in to_send:
        try:
            await context.bot.forward_message(
                chat_id=uid,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id,
            )
            user["seen_videos"].append(msg_id)
            logger.info(f"Forwarded video {msg_id} to user {uid}")
        except Exception as e:
            logger.error(f"Failed to forward video {msg_id} to {uid}: {e}")
    return len(to_send)


# ─────────────────────────────────────────────
# SEND UNLOCK PROMPT
# ─────────────────────────────────────────────

async def send_unlock_prompt(uid, user, context):
    ad_url = get_ad_link(user)
    user["link_sent_at"] = time.time()
    user["link_clicked_at"] = 0
    await context.bot.send_message(
        chat_id=uid,
        text=(
            "🔐 *Want 3 more videos?* Complete this quick task:\n\n"
            "1️⃣  Tap *Complete Task to Unlock* below\n"
            "2️⃣  Visit the link (stay a moment)\n"
            "3️⃣  Come back and tap *I completed the task*"
        ),
        parse_mode="Markdown",
        reply_markup=unlock_keyboard(ad_url),
    )


# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    sent = await forward_videos(1, user, uid, context)
    if sent == 0:
        await update.message.reply_text(
            "🎉 You've already unlocked everything! Check back soon."
        )
    else:
        await update.message.reply_text(
            "Tap *Get Videos* to unlock more 🔓",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
    save_users(users)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    users = load_users()
    user  = get_user(users, uid)
    total_vids = len(load_video_ids())
    seen_count = len(user["seen_videos"])
    await update.message.reply_text(
        f"📊 *Your Stats*\n\n"
        f"🎬 Videos watched : {seen_count}\n"
        f"🔓 Unlocks earned : {user['unlocks']}\n"
        f"📦 Videos left    : {total_vids - seen_count}",
        parse_mode="Markdown",
    )
    save_users(users)


async def adminstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    total_users   = len(users)
    total_unlocks = sum(u.get("unlocks", 0) for u in users.values())
    await update.message.reply_text(
        f"🛡 *Admin Stats*\n\n"
        f"👥 Total users   : {total_users}\n"
        f"🔓 Total unlocks : {total_unlocks}",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────

async def send_notifications(context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    if not users:
        return
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 10:
        message = NOTIFICATIONS[0]
    elif hour < 17:
        message = NOTIFICATIONS[1]
    else:
        message = NOTIFICATIONS[2]

    sent_count = 0
    for uid_str, user in users.items():
        if get_unseen_videos(user):
            try:
                await context.bot.send_message(
                    chat_id=int(uid_str),
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(),
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to notify {uid_str}: {e}")
    logger.info(f"Notified {sent_count} users")


# ─────────────────────────────────────────────
# BUTTON HANDLER
# ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "🎉 *You have unlocked all videos!*\n\nNew content added daily. Come back in 12 hours 🕛",
                parse_mode="Markdown",
            )
        else:
            sent = await forward_videos(VIDEOS_PER_UNLOCK, user, uid, context)
            if sent > 0:
                await send_unlock_prompt(uid, user, context)
            else:
                await query.message.reply_text(
                    "🎉 *You have unlocked all videos!*\n\nNew content added daily. Come back in 12 hours 🕛",
                    parse_mode="Markdown",
                )

    elif data == "claimed":
        elapsed      = time.time() - user.get("link_sent_at", 0)
        link_clicked = user.get("link_clicked_at", 0)
        logger.info(f"User {uid} claimed after {elapsed:.1f}s clicked={link_clicked > 0}")

        if link_clicked == 0:
            await query.message.reply_text(
                "⚠️ Please tap *Complete Task to Unlock* first and visit the link!",
                parse_mode="Markdown",
            )
        elif elapsed < UNLOCK_TIMER:
            await query.message.reply_text(
                "⏳ Please make sure you visited the link completely and try again!"
            )
        else:
            user["unlocks"] += 1
            if user.get("first_unlock_time", 0) == 0:
                user["first_unlock_time"] = time.time()
            unseen = get_unseen_videos(user)
            if not unseen:
                await query.message.reply_text(
                    "🎉 *You have unlocked all videos!*\n\nNew content added daily. Come back in 12 hours 🕛",
                    parse_mode="Markdown",
                )
            else:
                sent = await forward_videos(VIDEOS_PER_UNLOCK, user, uid, context)
                if sent > 0:
                    if get_unseen_videos(user):
                        await send_unlock_prompt(uid, user, context)
                    else:
                        await context.bot.send_message(
                            chat_id=uid,
                            text="🎉 *You have unlocked all videos!*\n\nNew content added daily. Come back in 12 hours 🕛",
                            parse_mode="Markdown",
                        )

    elif data == "my_stats":
        total_vids = len(load_video_ids())
        seen_count = len(user["seen_videos"])
        await query.message.reply_text(
            f"📊 *Your Stats*\n\n"
            f"🎬 Videos watched : {seen_count}\n"
            f"🔓 Unlocks earned : {user['unlocks']}\n"
            f"📦 Videos left    : {total_vids - seen_count}",
            parse_mode="Markdown",
        )

    elif data == "how_it_works":
        await query.message.reply_text(
            "ℹ️ *How Secret Baddie Unlock Works*\n\n"
            "1️⃣  Tap *Get Videos* to receive 3 exclusive videos\n"
            "2️⃣  Tap *Complete Task to Unlock* and visit the link\n"
            "3️⃣  Wait a moment, then tap *I completed the task*\n"
            "4️⃣  Unlock 3 more videos instantly! 🎬\n\n"
            "New videos drop daily 🔥",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    save_users(users)


# ─────────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Secret Baddie Unlock Bot  -  Starting up")
    print("=" * 50)
    video_ids = load_video_ids()
    print(f"  Videos loaded  : {len(video_ids)}")
    print(f"  Ad links ready : 3 (Adsterra > Monetag > Kadam)")
    print(f"  Unlock timer   : {UNLOCK_TIMER}s")
    print(f"  Videos/unlock  : {VIDEOS_PER_UNLOCK}")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("stats",      stats_command))
    app.add_handler(CommandHandler("adminstats", adminstats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    job_queue = app.job_queue
    job_queue.run_daily(send_notifications, time=dtime(9, 0))
    job_queue.run_daily(send_notifications, time=dtime(14, 0))
    job_queue.run_daily(send_notifications, time=dtime(20, 0))

    print("  Bot is running...\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()