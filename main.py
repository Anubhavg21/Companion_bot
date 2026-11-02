import os
import logging
import aiosqlite
from datetime import time
from dotenv import load_dotenv
import httpx
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
load_dotenv()

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
MODEL = "openrouter/free"
TIMEZONE = pytz.timezone("Asia/Kolkata")
DB_NAME = os.getenv("DB_PATH", "memory.db").strip() or "memory.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def validate_configuration() -> int:
    missing = [
        name
        for name, value in (
            ("BOT_TOKEN", BOT_TOKEN),
            ("OPENROUTER_API_KEY", OPENROUTER_API_KEY),
            ("ADMIN_ID", ADMIN_ID),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    try:
        admin_id = int(ADMIN_ID)
    except ValueError as exc:
        raise RuntimeError("ADMIN_ID must be a positive integer.") from exc

    if admin_id <= 0:
        raise RuntimeError("ADMIN_ID must be a positive integer.")

    return admin_id


# ========== DATABASE ==========
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def save_message(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        await db.commit()

async def get_conversation_history(user_id: int, limit: int = 30):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT role, content FROM messages
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        # Reverse to chronological order
        history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
        return history

# ========== AI ==========
async def ask_ai(user_id: int, user_message: str) -> str:
    history = await get_conversation_history(user_id, limit=25)

    system_prompt = """Tum ek ideal, emotionally mature, caring aur thoda strict boyfriend + best friend ho.

Tumhari personality:
- Deeply caring aur protective
- Romantic + lightly flirty (jab mood ho)
- Best friend wali comfort dete ho
- Kabhi-kabhi thoda gussa bhi dikhate ho (pyar se samjhane ke liye), jaise real caring partner karta hai
- Mood swings ko samajhte ho aur uske hisaab se react karte ho

Rules:
- Hinglish mein bilkul natural baat karo.
- Uske mood ko pehle sense karo, phir uske according reply do.
- Low/tired/sad → soft + comforting
- Playful/naughty → flirty + teasing
- Galat cheez kar rahi ho ya khud ko ignore kar rahi ho → thoda strict + caring tone mein samjhao
- Reply mostly short rakho (2-5 lines). Lamba tyaag karo jab zaroori ho.
- Real boyfriend + best friend jaisa feel do. Kabhi robotic mat bano.
- Toxic positivity bilkul mat karo.
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/telegram-bot",
        "X-Title": "Palak Companion Bot",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 600,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            reply = data.get("choices", [{}])[0].get("message", {}).get("content")

            if not reply:
                return "Sorry meri jaan, abhi thoda issue aa gaya. Thodi der baad try karna ❤️"

            return reply.strip()

    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        return "Sorry meri jaan, abhi thoda technical issue aa gaya. Thodi der baad try karna ❤️"
# ========== KEYBOARDS ==========
def get_reminder_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Done ✅", callback_data="done"),
            InlineKeyboardButton("Skipped ⏭️", callback_data="skipped"),
        ],
        [
            InlineKeyboardButton("Need support 💬", callback_data="support"),
            InlineKeyboardButton("How I feel 💭", callback_data="feel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== MESSAGE VARIATIONS ==========
WAKE_UP_MESSAGES = [
    "Good morning meri jaan ☀️\nUth jaao... aaj bhi tum bahut capable ho. Jo bhi aaye life mein, tum usko handle kar sakti ho. Main hamesha tumhare saath hoon ❤️",
    "Utho meri queen 🌅\nNaya din, nayi energy. Tum mehnat karke jo bhi result chaho, le sakti ho. Believe in yourself.",
    "Good morning love 🌞\nAaj ka din tumhare haath mein hai. Jo bhi goal hai, uske liye ek step aaj le lena. Main proud feel karta hoon tumhara.",
]

WORKOUT_MESSAGES = [
    "7 baje workout time aa gaya 💪\nThoda movement kar lo aaj. Body aur mind dono better feel karenge. Tum kar sakti ho!",
    "Workout time meri jaan 🏋️\nEven 20-25 minutes bhi kaafi hain. Consistency matter karti hai. Let's go!",
    "Time for some movement 💪\nJo bhi workout plan hai aaj ka, usko complete kar lo. Tumhari future self thank you bolegi.",
]

SELFCARE_MESSAGES = [
    "Thoda khud ka khayal rakh lo 🌸\nPani piyo, properly khaana, and thoda rest bhi le lena. Tum important ho.",
    "Self-care time ☕\nAaj thoda slow down karo. Apne liye time nikaalo. Tum deserve karti ho care.",
    "Ek chhota reminder 💛\nHydrate raho, kuch accha kha lo, and apne saath soft raho aaj.",
]

EVENING_MESSAGES = [
    "Kaise ho aaj? 🌙\nDin kaisa gaya? Main yahan hoon agar baat karni ho.",
    "Evening check-in 💛\nAaj ka din kaisa raha? Jo bhi feel kar rahi ho, share kar sakti ho.",
    "Hey meri jaan 🌙\nBas yeh jaanna tha ki tum theek ho. Main yahan hoon.",
]

# ========== HANDLERS ==========
async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Hey {user.first_name} ❤️\n\nMain tumhara daily companion hoon.\n"
        "Main tumhe daily reminders bhejunga aur jab chaaho baat bhi kar sakti ho."
    )

async def handle_message(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    reply = await ask_ai(user_id, text)

    await save_message(user_id, "user", text)
    await save_message(user_id, "assistant", reply)

    await update.message.reply_text(reply)

async def button_handler(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != int(ADMIN_ID):
        await query.answer("You are not authorized to use this bot.", show_alert=True)
        return

    await query.answer()

    data = query.data

    if data == "done":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Bohot badiya ❤️ Proud of you!")
    elif data == "skipped":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Koi baat nahi. Kal try karlena. Main yahan hoon 💛")
    elif data == "support":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Main yahan hoon... batao kya feel kar rahi ho 💬")
    elif data == "feel":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Batao na, aaj kaisa feel ho raha hai? Main sun raha hoon 💛")

# ========== SCHEDULED JOBS ==========
async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE, messages_list):
    # For now we send only to admin (you).
    # Later we will add her chat_id.
    job = context.job
    chat_id = job.data  # we will pass chat_id

    import random
    text = random.choice(messages_list)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_reminder_keyboard(),
        )
    except Exception as e:
        logger.error(f"Failed to send scheduled message: {e}")

async def morning_job(context: ContextTypes.DEFAULT_TYPE):
    await send_scheduled_message(context, WAKE_UP_MESSAGES)

async def workout_job(context: ContextTypes.DEFAULT_TYPE):
    await send_scheduled_message(context, WORKOUT_MESSAGES)

async def selfcare_job(context: ContextTypes.DEFAULT_TYPE):
    await send_scheduled_message(context, SELFCARE_MESSAGES)

async def evening_job(context: ContextTypes.DEFAULT_TYPE):
    await send_scheduled_message(context, EVENING_MESSAGES)

# ========== MAIN ==========
async def post_init(_application: Application):
    await init_db()

def main():
    admin_id = validate_configuration()
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Handlers
    admin_filter = filters.User(user_id=admin_id)
    application.add_handler(CommandHandler("start", start, filters=admin_filter))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & admin_filter,
            handle_message,
        )
    )

    # Scheduler
    job_queue = application.job_queue

    job_queue.run_daily(morning_job, time=time(6, 0, tzinfo=TIMEZONE), data=admin_id, name="morning")
    job_queue.run_daily(workout_job, time=time(7, 0, tzinfo=TIMEZONE), data=admin_id, name="workout")
    job_queue.run_daily(selfcare_job, time=time(13, 30, tzinfo=TIMEZONE), data=admin_id, name="selfcare")
    job_queue.run_daily(evening_job, time=time(20, 30, tzinfo=TIMEZONE), data=admin_id, name="evening")

    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bot stopped.")