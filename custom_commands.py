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


from database import connect


async def custom_commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT old_command, new_command FROM custom_commands"
    )

    data = cur.fetchall()

    conn.close()


    if not data:
        await update.message.reply_text(
            "لا توجد أوامر مضافة"
        )
        return


    text = "📌 الأوامر المضافة:\n\n"

    for old, new in data:
        text += f"{old} ➜ {new}\n"


    await update.message.reply_text(text)




async def delete_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "أرسل الأمر الجديد الذي تريد حذفه"
    )

    context.user_data["delete_command"] = True




async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("delete_command"):
        return


    command = update.message.text.strip()


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        DELETE FROM custom_commands
        WHERE new_command = ?
        """,
        (command,)
    )


    conn.commit()
    conn.close()


    context.user_data.pop("delete_command")


    await update.message.reply_text(
        "✅ تم حذف الأمر المضاف"
    )




async def delete_all_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM custom_commands"
    )

    conn.commit()
    conn.close()


    await update.message.reply_text(
        "✅ تم حذف جميع الأوامر المضافة"
    )    



async def check_custom_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return


    text = update.message.text.strip()


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        SELECT old_command
        FROM custom_commands
        WHERE new_command = ?
        """,
        (text,)
    )


    result = cur.fetchone()


    conn.close()


    if not result:
        return


    old_command = result[0]


    update.message.text = old_command