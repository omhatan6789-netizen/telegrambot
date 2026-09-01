from telegram import Update
from telegram.ext import ContextTypes

from button_colors import (
    COLOR_STYLES,
    get_button_color,
    set_button_color
)

from database import connect

from handlers.roles import (
    is_primary_developer,
    is_secondary_developer,
    get_rank
)


# ==================================================
# الجلسات
# ==================================================

color_sessions = {}


# ==================================================
# الصلاحية
# ==================================================

def can_change_button_color(user_id):

    # المالك
    if get_rank(user_id) == "المالك":
        return True

    # المطور الأساسي
    if is_primary_developer(user_id):
        return True

    # المطور المساعد
    if is_secondary_developer(user_id):
        return True

    return False


# ==================================================
# التحقق من وجود الزر
# ==================================================

def button_exists(button_text):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT button_text
        FROM button_colors
        WHERE button_text=?
        """,
        (button_text,)
    )

    result = cur.fetchone()

    conn.close()

    return result is not None


# ==================================================
# بدء تعديل اللون
# ==================================================

async def change_button_color_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.effective_chat.type not in (
        "group",
        "supergroup"
    ):
        return

    user_id = update.effective_user.id

    if not can_change_button_color(user_id):

        return

    chat_id = update.effective_chat.id

    color_sessions[chat_id] = {
        "user_id": user_id,
        "step": "button"
    }

    await update.message.reply_text(
        "• طيب ياحلو ارسل اسم الزر الي تبي تغير لونه،"
    )


# ==================================================
# استقبال اسم الزر / اللون
# ==================================================

async def change_button_color_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.effective_chat.type not in (
        "group",
        "supergroup"
    ):
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    session = color_sessions.get(chat_id)

    if not session:
        return

    # الجلسة لصاحبها فقط
    if session["user_id"] != user_id:
        return

    text = update.message.text

    if not text:
        return

    # ==================================================
    # اسم الزر
    # ==================================================

    if session["step"] == "button":

        # مطابق 100%
        button_name = text

        if not button_exists(button_name):

            await update.message.reply_text(
                "• مضيع يالحبيب، تاكد من اسم الزر."
            )

            return

        session["button"] = button_name
        session["step"] = "color"

        await update.message.reply_text(
            "• اوكيه، ارسل اللون الي تبيه.\n"
            "ملاحظة: عندك ( احمر، ازرق، اخضر، شفاف، فقط! )"
        )

        return

    # ==================================================
    # اللون
    # ==================================================

    if session["step"] == "color":

        color = text

        if color not in COLOR_STYLES:

            await update.message.reply_text(
                "• قلت لك بس فيه احمر وازرق واخضر وشفاف!!"
            )

            return

        button_name = session["button"]

        if not set_button_color(
            button_name,
            color
        ):

            await update.message.reply_text(
                "• مضيع يالحبيب، تاكد من اسم الزر."
            )

            color_sessions.pop(
                chat_id,
                None
            )

            return

        color_sessions.pop(
            chat_id,
            None
        )

        await update.message.reply_text(
            "• تم عدلت لونه ياحلو يمديك تتاكد الحين!"
        )