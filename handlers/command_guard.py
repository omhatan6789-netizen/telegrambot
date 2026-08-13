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

    # ==================================================
    # أوامر الصلاحيات نفسها لا تدخل في الحارس
    # ==================================================

    if text.startswith("منع ") or text.startswith("سماح "):
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ==================================================
    # تحديد اسم الأمر
    # ==================================================

    command = text.split()[0]

    multi_word_commands = (
        "كشف المجموعة",
        "رفع الحظر",
        "رفع الكتم",
        "حظر عام",
        "كتم عام",
        "قفل امر",
        "فتح امر",
    )

    for item in multi_word_commands:

        if text == item or text.startswith(item + " "):

            command = item
            break

    # ==================================================
    # منع / سماح خاص للشخص
    # ==================================================

    special_permission = check_user_permission(
        chat_id,
        user_id,
        command
    )

    # ==================================================
    # منع خاص
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