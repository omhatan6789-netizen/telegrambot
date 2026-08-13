from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import check_command_permission
from permissions import check_user_permission


async def command_guard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (update.message.text or "").strip()

    if not text:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ==================================================
    # تحديد اسم الأمر
    # ==================================================

    command = text.split()[0]

    if text.startswith("كشف المجموعة"):
        command = "كشف المجموعة"

    elif text.startswith("رفع الحظر"):
        command = "رفع الحظر"

    elif text.startswith("رفع الكتم"):
        command = "رفع الكتم"

    elif text.startswith("حظر عام"):
        command = "حظر عام"

    elif text.startswith("كتم عام"):
        command = "كتم عام"

    elif text.startswith("قفل امر"):
        command = "قفل امر"

    elif text.startswith("فتح امر"):
        command = "فتح امر"

    # ==================================================
    # منع / سماح خاص للشخص
    # ==================================================

    special_permission = check_user_permission(
        chat_id,
        user_id,
        command
    )

    # --------------------------------------------------
    # منع خاص
    # --------------------------------------------------

    if special_permission is False:

        await update.message.reply_text(
            "🚫 ليس لديك صلاحية استخدام هذا الأمر."
        )

        raise ApplicationHandlerStop()

    # --------------------------------------------------
    # سماح خاص
    #
    # يتجاوز قفل الرتبة
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
            f"❌ هذا الأمر مخصص لرتبة `{required}` وفوق",
            parse_mode="Markdown"
        )

        raise ApplicationHandlerStop()