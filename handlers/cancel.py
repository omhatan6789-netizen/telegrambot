from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "تم الغاء الامر بنجاح ."
    )

    return ConversationHandler.END
