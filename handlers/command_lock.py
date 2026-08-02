from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank


RANKS = [
    "المالك",
    "نائب المالك",
    "ادمن اساسي",
    "ادمن",
    "مميز"
]


async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    text = update.message.text

    command = text.replace("قفل امر ", "").strip()

    if not command:
        await update.message.reply_text(
            "❌ اكتب اسم الأمر\nمثال:\nقفل امر اضف رد"
        )
        return


    context.user_data["lock_command"] = command


    await update.message.reply_text(
        f"""
• حسنًا اختر الرتبة التي تريدها :

1- `{RANKS[0]}`
2 - `{RANKS[1]}`
3 - `{RANKS[2]}`
4 - `{RANKS[3]}`
5 - `{RANKS[4]}`


- سيتم وضع امر ↤︎ `{command}` له فقط
""",
        parse_mode="Markdown"
    )



async def save_lock_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "lock_command" not in context.user_data:
        return


    rank = update.message.text.strip()


    if rank not in RANKS:
        return


    command = context.user_data["lock_command"]


    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO command_locks
        (command, min_rank)
        VALUES (?,?)
        """,
        (
            command,
            rank
        )
    )


    conn.commit()
    conn.close()


    del context.user_data["lock_command"]


    await update.message.reply_text(
        f"✅ تم قفل الأمر `{command}` على رتبة `{rank}` وفوق",
        parse_mode="Markdown"
    )



async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    command = text.replace("فتح امر ", "").strip()


    if not command:
        return


    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM command_locks
        WHERE command=?
        """,
        (command,)
    )


    conn.commit()
    conn.close()


    await update.message.reply_text(
        f"✅ تم فتح الأمر `{command}`",
        parse_mode="Markdown"
    )