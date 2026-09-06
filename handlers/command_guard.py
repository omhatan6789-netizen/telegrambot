import asyncio

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop
)

from handlers.roles import (
    check_command_permission
)

from permissions import (
    check_user_permission
)


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


    "سباق الكلمات",
    "انهاء سباق الكلمات",
]

    
# ==================================================
# الجلسات التي تنتظر إدخال المستخدم
# ==================================================

def is_waiting_for_input(
    context,
    user_id
):

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

    # ==================================================
    # user_data
    # ==================================================

    try:

        for key in waiting_keys:

            if key in context.user_data:

                return True

    except Exception:

        pass

    # ==================================================
    # جلسات الردود
    # ==================================================

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

    # ==================================================
    # جلسات الألعاب والأسئلة
    # ==================================================

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

    # ==================================================
    # جلسة تعديل لون الزر
    # ==================================================

    try:

        from handlers.button_colors import (
            color_sessions
        )

        for session in color_sessions.values():

            if (
                session.get("user_id")
                == user_id
            ):

                return True

    except Exception:

        pass

    return False


# ==================================================
# استخراج اسم الأمر
# ==================================================

def get_command_name(text):

    text = (
        text or ""
    ).strip()

    if not text:
        return ""

    matches = []

    for command in MULTI_WORD_COMMANDS:

        if (
            text == command
            or text.startswith(
                command + " "
            )
        ):

            matches.append(command)

    if matches:

        return max(
            matches,
            key=len
        )

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

    # ==================================================
    # النص
    # ==================================================

    text = (
        update.message.text or ""
    ).strip()

    if not text:
        return

    # ==================================================
    # المستخدم
    # ==================================================

    user = update.effective_user

    if not user:
        return

    chat = update.effective_chat

    if not chat:
        return

    user_id = user.id
    chat_id = chat.id

    # ==================================================
    # جلسة متعددة الخطوات
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

    command = get_command_name(
        text
    )

    if not command:
        return

    # ==================================================
    # أوامر سباق الكلمات
    # يتم التعامل معها داخل لعبة سباق الكلمات
    # ==================================================

    word_race_commands = (
        "سباق الكلمات",
        "خروج",
        ".الطور",
        ".توزيع",
        ".اضافة",
        ".ابدا",
        ".كمل",
        "انهاء سباق الكلمات",
    )

    if (
        command in word_race_commands
        or text.startswith(".اضافة ")
    ):
        return

    # ==================================================
    # أوامر الحظر والكتم
    # ==================================================

    moderation_commands = (

        "حظر",
        "كتم",

        "رفع الحظر",
        "رفع الكتم",

        "حظر عام",
        "كتم عام",
    )

    if command in moderation_commands:

        return

    # ==================================================
    # مهم:
    # هنا لا نشغل psycopg2 داخل event loop
    #
    # يتم تنفيذ فحص الصلاحية في Thread
    # ==================================================

    try:

        special_permission = (
            await asyncio.to_thread(
                check_user_permission,
                chat_id,
                user_id,
                command
            )
        )

    except Exception as e:

        print(
            f"⚠️ خطأ في فحص صلاحية المستخدم: {e}"
        )

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
    # فحص قفل الأمر
    #
    # أيضًا خارج event loop
    # ==================================================

    try:

        allowed, required = (
            await asyncio.to_thread(
                check_command_permission,
                user_id,
                command
            )
        )

    except Exception as e:

        print(
            f"⚠️ خطأ في فحص قفل الأمر: {e}"
        )

        return

    # ==================================================
    # الأمر مقفول
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