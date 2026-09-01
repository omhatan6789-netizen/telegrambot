from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from button_colors import (
    COLOR_STYLES,
    set_button_color,
    button_exists
)

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

    user = update.effective_user

    if not user:
        return

    user_id = user.id

    # التحقق من الصلاحية
    if not can_change_button_color(user_id):
        return

    chat_id = update.effective_chat.id

    # إنشاء جلسة جديدة
    color_sessions[chat_id] = {
        "user_id": user_id,
        "step": "button"
    }

    await update.message.reply_text(
        "• طيب ياحلو ارسل اسم الزر الي تبي تغير لونه،"
    )

    # نوقف بقية الـ handlers لهذا الـ Update
    raise ApplicationHandlerStop


# ==================================================
# استقبال اسم الزر / اللون
# ==================================================

async def change_button_color_handler(update, context):
    if not update.message:
        return

    if update.effective_chat.type not in ("group", "supergroup"):
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    session = color_sessions.get(chat_id)

    if not session:
        return

    if session["user_id"] != user_id:
        return

    text = update.message.text

    if not text:
        return

    # ==============================
    # اختيار الزر
    # ==============================

    if session["step"] == "button":

        button_name = text.strip()

        if not button_exists(button_name):
            await update.message.reply_text(
                "• مضيع يالحبيب، تاكد من اسم الزر."
            )

            # إلغاء العملية بالكامل
            color_sessions.pop(chat_id, None)

            raise ApplicationHandlerStop

        session["button"] = button_name
        session["step"] = "color"

        await update.message.reply_text(
            "• اوكيه، ارسل اللون الي تبيه.\n"
            "ملاحظة: عندك ( احمر، ازرق، اخضر، شفاف، فقط! )"
        )

        raise ApplicationHandlerStop

    # ==============================
    # اختيار اللون
    # ==============================

    if session["step"] == "color":

        color = text.strip()

        if color not in COLOR_STYLES:
            await update.message.reply_text(
                "• قلت لك بس فيه احمر وازرق واخضر وشفاف!!"
            )

            raise ApplicationHandlerStop

        button_name = session["button"]

        if not set_button_color(button_name, color):
            await update.message.reply_text(
                "• مضيع يالحبيب، تاكد من اسم الزر."
            )

            color_sessions.pop(chat_id, None)

            raise ApplicationHandlerStop

        # انتهت العملية بنجاح
        color_sessions.pop(chat_id, None)

        await update.message.reply_text(
            "• تم عدلت لونه ياحلو يمديك تتاكد الحين!"
        )

        raise ApplicationHandlerStop