import asyncio
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop
)
from handlers.roles import (
    check_command_permission
)
MULTI_WORD_COMMANDS = [
    "كشف المجموعة",
    "كشف القيود",
    "رفع الحظر",
    "رفع الكتم",
    "حظر عام",
    "كتم عام",
    "قفل امر",
    "فتح امر",
    "اضف رد مميز",
    "تعديل رد مميز",
    "مسح رد مميز",
    "الردود المميزة",
    "مسح الردود المميزة",
    "اضف رد",
    "تعديل رد",
    "مسح رد",
    "الردود",
    "مسح الردود",
    "اضف لعبة",
    "الالعاب",
    "اضف سؤال",
    "حذف سؤال",
    "حذف لعبة",
    "تفعيل لعبة",
    "تعطيل لعبة",
    "تفعيل الالعاب",
    "تعطيل الالعاب",
    "رفع Dev",
    "تنزيل Dev",
    "رفع المالك",
    "تنزيل المالك",
    "رفع نائب المالك",
    "تنزيل نائب المالك",
    "رفع ادمن اساسي",
    "تنزيل ادمن اساسي",
    "رفع ادمن",
    "تنزيل ادمن",
    "رفع مميز",
    "تنزيل مميز",
    "اوامر الادمن",
    "اوامر المطور",
    "نقاطي",
    "سباق الكلمات",
    "انهاء سباق الكلمات",
]
def is_waiting_for_input(context, user_id):
    waiting_keys = (
        "add_reply",
        "edit_reply",
        "delete_reply",
        "add_special_reply",
        "edit_special_reply",
        "delete_special_reply",
        "add_game",
        "add_question",
        "lock_command",
        "custom_command",
        "delete_command",
        "button_color",
    )
    try:
        for key in waiting_keys:
            if key in context.user_data:
                return True
    except Exception:
        pass
    try:
        from handlers.replies import (
            add_reply_sessions,
            edit_reply_sessions,
            delete_reply_sessions,
            add_special_reply_sessions,
            edit_special_reply_sessions,
            delete_special_reply_sessions,
        )
        sessions = (
            add_reply_sessions,
            edit_reply_sessions,
            delete_reply_sessions,
            add_special_reply_sessions,
            edit_special_reply_sessions,
            delete_special_reply_sessions,
        )
        for session in sessions:
            if user_id in session:
                return True
    except Exception:
        pass
    try:
        from games.games_manager import (
            add_game_sessions,
            add_question_sessions,
        )
        if user_id in add_game_sessions:
            return True
        if user_id in add_question_sessions:
            return True
    except Exception:
        pass
    try:
        from handlers.button_colors import (
            color_sessions
        )
        for session in color_sessions.values():
            if session.get("user_id") == user_id:
                return True
    except Exception:
        pass
    return False
def get_command_name(text):
    text = (text or "").strip()
    if not text:
        return ""
    matches = []
    for command in MULTI_WORD_COMMANDS:
        if (
            text == command
            or text.startswith(command + " ")
        ):
            matches.append(command)
    if matches:
        return max(
            matches,
            key=len
        )
    return text.split()[0]
def command_lock_message(required):
    if required == "Dev":
        return "• اعذرني هذا الامر للـ Dev فقط ."
    if required == "المالك":
        return "• اعذرني بس هذا الامر للمالك وفوق فقط ."
    if required == "نائب المالك":
        return "• اعذرني بس هذا الامر لنائب المالك وفوق فقط ."
    if required == "ادمن اساسي":
        return "• اعذرني بس هذا الامر للادمن الاساسي وفوق فقط ."
    if required == "ادمن":
        return "• اعذرني بس هذا الامر للادمن وفوق فقط ."
    if required == "مميز":
        return "• اعذرني بس هذا الامر للمميز وفوق فقط ."
    return "• اعذرني بس ما عندك الصلاحية لهذا الامر ."
async def command_guard(
    update,
    context
):
    if not update.message:
        return
    text = (
        update.message.text or ""
    ).strip()
    if not text:
        return
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return
    user_id = user.id
    chat_id = chat.id
    # ==================================================
    # المستخدم داخل خطوة إدخال
    # ==================================================
    if is_waiting_for_input(
        context,
        user_id
    ):
        return
    # ==================================================
    # منع / سماح
    # ==================================================
    if (
        text == "منع"
        or text.startswith("منع ")
        or text == "سماح"
        or text.startswith("سماح ")
    ):
        return
    # ==================================================
    # قفل / فتح الأمر
    # ==================================================
    if (
        text.startswith("قفل امر ")
        or text.startswith("فتح امر ")
    ):
        return
    command = get_command_name(text)
    if not command:
        return
    # ==================================================
    # فحص قفل الأمر فقط
    # ==================================================
    try:
        allowed, required = await asyncio.to_thread(
            check_command_permission,
            user_id,
            command,
            chat_id
        )
    except Exception as e:
        print(
            f"⚠️ خطأ في فحص قفل الأمر: {e}"
        )
        return
    # ==================================================
    # الأمر مقفول والرتبة غير كافية
    # ==================================================
    if (
        required is not None
        and not allowed
    ):
        await update.message.reply_text(
            command_lock_message(
                required
            )
        )
        raise ApplicationHandlerStop()
    # ==================================================
    # إذا كان الأمر غير مقفول
    # أو الرتبة مسموحة
    #
    # نرجع بدون إيقاف المعالجات
    # ==================================================
    return
