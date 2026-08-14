from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import check_command_permission
from permissions import check_user_permission


# ==================================================
# الأوامر المركبة
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
# استخراج اسم الأمر الحقيقي
# ==================================================

def get_command_name(text):

    text = (text or "").strip()

    if not text:
        return ""

    # نبحث عن أطول أمر مطابق أولاً
    # حتى لا يتم أخذ "اضف" بدل "اضف رد"
    possible = []

    for command in MULTI_WORD_COMMANDS:

        if text == command or text.startswith(command + " "):
            possible.append(command)

    if possible:
        return max(
            possible,
            key=len
        )

    # الأوامر ذات الكلمة الواحدة
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
    # منع / سماح ليست أوامر تحتاج للحارس
    # ==================================================

    if text == "منع" or text.startswith("منع "):
        return

    if text == "سماح" or text.startswith("سماح "):
        return

    # ==================================================
    # المستخدم
    # ==================================================

    if not update.effective_user:
        return

    if not update.effective_chat:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ==================================================
    # استخراج الأمر
    # ==================================================

    command = get_command_name(text)

    if not command:
        return

    # ==================================================
    # منع / سماح خاص للشخص
    # ==================================================

    special_permission = check_user_permission(
        chat_id,
        user_id,
        command
    )

    # --------------------------------------------------
    # ممنوع
    # --------------------------------------------------

    if special_permission is False:

        await update.message.reply_text(
            "🚫 ليس لديك صلاحية استخدام هذا الأمر."
        )

        raise ApplicationHandlerStop()

    # --------------------------------------------------
    # مسموح بشكل خاص
    # --------------------------------------------------

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