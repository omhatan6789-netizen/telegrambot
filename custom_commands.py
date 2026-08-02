from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import connect


OWNER_ID = 8453977662


WAIT_OLD, WAIT_NEW = range(2)


add_command_sessions = {}


async def add_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = update.effective_user.id

    add_command_sessions[user_id] = {}

    await update.message.reply_text(
        "حسناً، أرسل الأمر القديم"
    )

    return WAIT_OLD



async def receive_old_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id not in add_command_sessions:
        return


    old = update.message.text.strip()

    add_command_sessions[user_id]["old"] = old


    await update.message.reply_text(
        "حسناً، أرسل الأمر الجديد"
    )

    return WAIT_NEW



async def receive_new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    new = update.message.text.strip()


    old = add_command_sessions[user_id]["old"]


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        INSERT INTO custom_commands
        (
        old_command,
        new_command
        )
        VALUES (?,?)
        """,
        (
            old,
            new
        )
    )


    conn.commit()
    conn.close()


    del add_command_sessions[user_id]


    await update.message.reply_text(
        f"✅ تم إضافة الأمر\n\n{new} يعمل الآن مثل {old}"
    )


    return ConversationHandler.END