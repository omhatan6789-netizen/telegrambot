from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import check_command_permission
from permissions import check_user_permission


# ==================================================
# الأوامر متعددة الكلمات
# ==================================================

MULTI_WORD_COMMANDS = [
    "كشف المجموعة",

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

    "نقاطي",

    "اوامر الادمن",
    "اوامر المطور",

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
]


# ==================================================
# العمليات التي تنتظر رسائل من المستخدم
# ==================================================

WAITING_KEYS = (
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
)


# ==================================================
# التحقق من وجود عملية متعددة الخطوات
# ==================================================

def is_waiting_for_input(context, user_id):
    """
    إذا كان المستخدم داخل عملية متعددة الخطوات
    لا نفحص رسائله كأوامر جديدة.
    """

    # ==================================================
    # أولاً: العمليات الموجودة في context.user_data
    # ==================================================

    for key in WAITING_KEYS:

        if key in context.user_data:
            return True

    # ==================================================
    # ثانياً: جلسات الردود
    # ==================================================

    try:

        from handlers.replies import (
            add_reply_sessions,
            edit_reply_sessions,
            delete_reply_sessions,

            add_special_reply_sessions,
            edit_special_reply_sessions,
            delete_special_reply_sessions
        )

        reply_sessions = (
            add_reply_sessions,
            edit_reply_sessions,
            delete_reply_sessions,

            add_special_reply_sessions,
            edit_special_reply_sessions,
            delete_special_reply_sessions
        )

        for sessions in reply_sessions:

            if user_id in sessions:
                return True

    except Exception:
        pass

    # ==================================================
    # ثالثاً: جلسات الألعاب والأسئلة
    # ==================================================

    try:

        from games.games_manager import (
            add_game_sessions,
            add_question_sessions
        )

        if user_id in add_game_sessions:
            return True

        if user_id in add_question_sessions:
            return True

    except Exception:
        pass

    return False


# ==================================================
# استخراج اسم الأمر
# ==================================================

def get_command_name(text):

    text = (text or "").strip()

    if not text:
        return ""

    # ==================================================
    # الأطول أولاً
    # ==================================================

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

    # ==================================================
    # أمر كلمة واحدة
    # ==================================================

    return text.split()[0]


# ==================================================
# حارس الأوامر
# ==================================================

async def command_guard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (update.message.text or "").strip()

    if not text:
        return

    # ==================================================
    # منع / سماح نفسها لا تدخل للحارس
    # ==================================================

    if text == "منع" or text.startswith("منع "):
        return

    if text == "سماح" or text.startswith("سماح "):
        return

    # ==================================================
    # التأكد من وجود المستخدم والقروب
    # ==================================================

    if not update.effective_user:
        return

    if not update.effective_chat:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ==================================================
    # إذا المستخدم داخل عملية متعددة الخطوات
    #
    # مهم:
    # نتحقق هنا بعد الحصول على user_id
    # لأن جلسات الردود محفوظة خارج context.user_data
    # ==================================================

    if is_waiting_for_input(
        context,
        user_id
    ):
        return

    # ==================================================
    # استخراج الأمر
    # ==================================================

    command = get_command_name(text)

    if not command:
        return

    # ==================================================
    # منع / سماح خاص
    # ==================================================

    special_permission = check_user_permission(
        chat_id,
        user_id,
        command
    )

    # ==================================================
    # ممنوع
    # ==================================================

    if special_permission is False:

        await update.message.reply_text(
            "🚫 ليس لديك صلاحية استخدام هذا الأمر."
        )

        raise ApplicationHandlerStop()

    # ==================================================
    # سماح خاص
    # ==================================================

    if special_permission is True:
        return

    # ==================================================
    # قفل الأمر حسب الرتبة
    # ==================================================

    allowed, required = check_command_permission(
        user_id,
        command
    )

    if not allowed:

        await update.message.reply_text(
            f"❌ هذا الأمر مخصص لرتبة {required} وفوق."
        )

        raise ApplicationHandlerStop()