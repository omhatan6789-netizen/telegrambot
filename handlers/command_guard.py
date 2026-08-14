from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import check_command_permission
from permissions import check_user_permission

# ==================================================
# جلسات الردود
# ==================================================

from handlers.replies import (
    add_reply_sessions,
    add_special_reply_sessions,
    delete_special_reply_sessions,
    edit_special_reply_sessions,
    edit_reply_sessions,
    delete_reply_sessions,
)


# ==================================================
# جلسات الألعاب
# ==================================================

try:
    from games.games_manager import (
        add_game_sessions,
        add_question_sessions,
    )
except Exception:
    add_game_sessions = {}
    add_question_sessions = {}


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
# معرفة هل المستخدم داخل جلسة
# ==================================================

def user_has_active_session(user_id, context):

    # --------------------------------------------------
    # جلسات context.user_data
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

    for key in waiting_keys:

        if key in context.user_data:
            return True


    # --------------------------------------------------
    # جلسات الردود
    # --------------------------------------------------

    if user_id in add_reply_sessions:
        return True

    if user_id in add_special_reply_sessions:
        return True

    if user_id in delete_special_reply_sessions:
        return True

    if user_id in edit_special_reply_sessions:
        return True

    if user_id in edit_reply_sessions:
        return True

    if user_id in delete_reply_sessions:
        return True


    # --------------------------------------------------
    # جلسات الألعاب
    # --------------------------------------------------

    if user_id in add_game_sessions:
        return True

    if user_id in add_question_sessions:
        return True


    return False


# ==================================================
# استخراج اسم الأمر
# ==================================================

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


# ==================================================
# معرفة هل الرسالة أمر
# ==================================================

def is_bot_command(text):

    text = (text or "").strip()

    if not text:
        return False


    # --------------------------------------------------
    # الأوامر متعددة الكلمات
    # --------------------------------------------------

    for command in MULTI_WORD_COMMANDS:

        if (
            text == command
            or text.startswith(command + " ")
        ):
            return True


    # --------------------------------------------------
    # الأوامر المفردة
    # --------------------------------------------------

    first_word = text.split()[0]


    single_commands = {

        "ايدي",

        "رتبتي",
        "رتبته",

        "كشف",

        "حظر",
        "كتم",

        "توب",

        "كلمات",

        "انمي",

        "اسئلة",
    }


    if first_word in single_commands:
        return True


    return False


# ==================================================
# حارس الأوامر
# ==================================================

async def command_guard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    text = (
        update.message.text or ""
    ).strip()


    if not text:
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
    # التأكد من المستخدم والقروب
    # ==================================================

    if not update.effective_user:
        return


    if not update.effective_chat:
        return


    user_id = update.effective_user.id
    chat_id = update.effective_chat.id


    # ==================================================
    # إذا المستخدم داخل جلسة
    #
    # لا نفحص رسالته كأمر جديد
    #
    # مهم جدًا للآتي:
    #
    # اضف رد
    # اضف رد مميز
    # تعديل رد
    # تعديل رد مميز
    # مسح رد
    # مسح رد مميز
    # اضف لعبة
    # اضف سؤال
    #
    # وغيرها
    # ==================================================

    if user_has_active_session(
        user_id,
        context
    ):
        return


    # ==================================================
    # إذا الرسالة ليست أمرًا
    # لا نتدخل
    #
    # هذا مهم للألعاب والردود العادية
    # ==================================================

    if not is_bot_command(text):
        return


    # ==================================================
    # استخراج اسم الأمر
    # ==================================================

    command = get_command_name(text)


    if not command:
        return


    # ==================================================
    # منع / سماح الخاص
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


    # ==================================================
    # مسموح
    # ==================================================

    return