from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import check_command_permission


async def command_guard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text

    if not text:
        return


    allowed, required = check_command_permission(
        update.effective_user.id,
        text
    )


    if not allowed:

        await update.message.reply_text(
            f"❌ هذا الأمر مخصص لرتبة `{required}` وفوق",
            parse_mode="Markdown"
        )

        raise ApplicationHandlerStop