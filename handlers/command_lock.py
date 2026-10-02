from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import clear_command_permission_cache


# ==================================================
# الرتب المتاحة لقفل الأوامر
# ==================================================

RANKS = [
    "Dev",
    "المالك",
    "نائب المالك",
    "ادمن اساسي",
    "ادمن",
    "مميز",
]


# ==================================================
# قفل أمر
# ==================================================

async def lock_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text or ""

    command = text.replace(
        "قفل امر ",
        "",
        1
    ).strip()

    if not command:

        await update.message.reply_text(
            "❌ اكتب اسم الأمر\n"
            "مثال:\n"
            "قفل امر اضف رد"
        )

        return

    context.user_data["lock_command"] = command

    ranks_text = "\n".join(
        f"{i}- {rank}"
        if i == 1
        else f"{i} - {rank}"
        for i, rank in enumerate(RANKS, 1)
    )

    await update.message.reply_text(
        "• حسنًا اختر الرتبة التي تريدها :\n\n"
        f"```\n{ranks_text}\n```\n\n"
        f"- سيتم وضع امر ↤︎ `{command}` له فقط",
        parse_mode="Markdown"
    )


# ==================================================
# حفظ رتبة القفل
# ==================================================

async def save_lock_rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if "lock_command" not in context.user_data:
        return

    if not update.message or not update.message.text:
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
        (command, rank)
        VALUES (?, ?)
        """,
        (
            command,
            rank
        )
    )

    conn.commit()
    conn.close()

    del context.user_data["lock_command"]

    clear_command_permission_cache()

    await update.message.reply_text(
        f"✅ تم قفل الأمر `{command}` على رتبة `{rank}` وفوق",
        parse_mode="Markdown"
    )


# ==================================================
# فتح أمر
# ==================================================

async def open_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text or ""

    command = text.replace(
        "فتح امر ",
        "",
        1
    ).strip()

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

    clear_command_permission_cache()

    await update.message.reply_text(
        f"✅ تم فتح الأمر `{command}`",
        parse_mode="Markdown"
    )
