from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import (
    clear_command_permission_cache,
    get_rank_level,
)


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
# التحقق من صلاحية المالك
# ==================================================

def is_owner_or_above(user_id, chat_id):

    try:
        return get_rank_level(
            user_id,
            chat_id
        ) >= 5
    except Exception:
        return False


# ==================================================
# قفل أمر
# ==================================================

async def lock_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # ==================================================
    # المالك وفوق فقط
    # ==================================================

    if not is_owner_or_above(
        user.id,
        chat.id
    ):

        await update.message.reply_text(
            "• اعذرني بس هذا الامر للمالك وفوق فقط ."
        )

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

    await update.message.reply_text(
        "• حسنًا اختر الرتبة التي تريدها :\n"
        f"1 - `{RANKS[0]}`\n"
        f"2 - `{RANKS[1]}`\n"
        f"3 - `{RANKS[2]}`\n"
        f"4 - `{RANKS[3]}`\n"
        f"5 - `{RANKS[4]}`\n"
        f"6 - `{RANKS[5]}`\n\n\n"
        f"- سيتم وضع امر ↤︎ {command} له فقط",
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

    if not update.message:
        return

    rank = (
        update.message.text or ""
    ).strip()

    if rank not in RANKS:
        return

    command = context.user_data.get(
        "lock_command"
    )

    if not command:
        return

    try:

        conn = connect()
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM command_locks
            WHERE command=?
            """,
            (command,)
        )

        cur.execute(
            """
            INSERT INTO command_locks
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

        clear_command_permission_cache()

    except Exception as e:

        print(
            f"⚠️ خطأ في حفظ قفل الأمر: {e}"
        )

        try:
            conn.close()
        except Exception:
            pass

        return

    del context.user_data["lock_command"]

    await update.message.reply_text(
        f"✅ تم قفل الأمر {command} على رتبة {rank} وفوق"
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

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # ==================================================
    # المالك وفوق فقط
    # ==================================================

    if not is_owner_or_above(
        user.id,
        chat.id
    ):

        await update.message.reply_text(
            "• اعذرني بس هذا الامر للمالك وفوق فقط ."
        )

        return

    text = update.message.text or ""

    command = text.replace(
        "فتح امر ",
        "",
        1
    ).strip()

    if not command:
        return

    try:

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

    except Exception as e:

        print(
            f"⚠️ خطأ في فتح الأمر: {e}"
        )

        try:
            conn.close()
        except Exception:
            pass

        return

    await update.message.reply_text(
        f"✅ تم فتح الأمر {command}"
    )
