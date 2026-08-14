from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import check_command_permission
from permissions import check_user_permission


# ==================================================
# الأوامر التي تحتاج أكثر من كلمة
# ==================================================

MULTI_WORD_COMMANDS = [
    "كشف المجموعة",

    "رفع الحظر",
    "رفع الكتم",
    "حظر عام",
    "كتم عام",

    "قفل امر",
    "فتح امر",

    # الردود المميزة
    "اضف رد مميز",
    "تعديل رد مميز",
    "مسح رد مميز",
    "الردود المميزة",
    "مسح الردود المميزة",

    # الردود العادية
    "اضف رد",
    "تعديل رد",
    "مسح رد",
    "الردود",
    "مسح الردود",

    # الألعاب
    "اضف لعبة",
    "الالعاب",
    "اضف سؤال",
    "حذف سؤال",
    "حذف لعبة",
    "تفعيل لعبة",
    "تعطيل لعبة",
    "تفعيل الالعاب",
    "تعطيل الالعاب",

    # الرتب
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

    # أوامر الإدارة
    "اوامر الادمن",
    "اوامر المطور",

    # النقاط
    "نقاطي",
]


# ==================================================
# الجلسات التي تنتظر إدخال المستخدم
# ==================================================

def is_waiting_for_input(context, user_id):
    """
    يرجع True إذا كان المستخدم داخل عملية متعددة الخطوات.
    في هذه الحالة الحارس لا يتدخل في الرسائل التالية.
    """

    # --------------------------------------------------
    # جلسات موجودة في user_data
    # --------------------------------------------------

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
    )

    try:
        for key in waiting_keys:
            if key in context.user_data:
                return True
    except Exception:
        pass

    # --------------------------------------------------
    # جلسات الردود
    # --------------------------------------------------

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

    # --------------------------------------------------
    # جلسات الألعاب والأسئلة
    # --------------------------------------------------

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

    return False


# ==================================================
# استخراج اسم الأمر
# ==================================================

def get_command_name(text):

    text = (text or "").strip()

    if not text:
        return ""

    # --------------------------------------------------
    # الأطول أولًا
    # --------------------------------------------------

    matches = []

    for command in MULTI_WORD_COMMANDS:

        if (
            text == command
            or text.startswith(command + " ")
        ):
            matches.append(command)

    if matches:
        return max(matches, key=len)

    # --------------------------------------------------
    # أمر من كلمة واحدة
    # --------------------------------------------------

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

    # --------------------------------------------------
    # الحارس يتعامل مع الرسائل النصية فقط
    # --------------------------------------------------

    text = (update.message.text or "").strip()

    if not text:
        return

    # --------------------------------------------------
    # معلومات المستخدم
    # --------------------------------------------------

    if not update.effective_user:
        return

    if not update.effective_chat:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ==================================================
    # مهم جدًا:
    # إذا كان المستخدم داخل جلسة متعددة الخطوات
    # نخرج فورًا بدون أي فحص.
    #
    # هذا يسمح بـ:
    # اضف رد
    # ثم اسم الرد
    # ثم المحتوى
    #
    # وكذلك:
    # مسح رد
    # ثم اسم الرد
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
    # استخراج الأمر
    # ==================================================

    command = get_command_name(text)

    if not command:
        return

    # ==================================================
    # الصلاحيات الخاصة بالمستخدم
    # ==================================================

    try:

        special_permission = check_user_permission(
            chat_id,
            user_id,
            command
        )

    except Exception:
        # إذا حصل خطأ في نظام السماح/المنع
        # لا نخرب باقي البوت
        special_permission = None

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
    # فحص قفل الأمر حسب الرتبة
    # ==================================================

    try:

        allowed, required = check_command_permission(
            user_id,
            command
        )

    except Exception:
        # لا نوقف البوت إذا حصل خطأ في قاعدة بيانات الأقفال
        return

    # ==================================================
    # الأمر مقفول على رتبة أعلى
    # ==================================================

    if not allowed:

        await update.message.reply_text(
            f"❌ هذا الأمر مخصص لرتبة {required} وفوق."
        )

        raise ApplicationHandlerStop()

    # ==================================================
    # مسموح
    # ==================================================

    return