from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import connect
import copy


OWNER_ID = 8453977662

WAIT_OLD, WAIT_NEW = range(2)

add_command_sessions = {}


# ==================================================
# إضافة أمر
# ==================================================

async def add_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    user_id = update.effective_user.id

    add_command_sessions[user_id] = {}

    await update.message.reply_text(
        "حسناً، أرسل الأمر القديم"
    )

    return WAIT_OLD


# ==================================================
# استقبال الأمر القديم
# ==================================================

async def receive_old_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id not in add_command_sessions:
        return

    if not update.message or not update.message.text:
        return WAIT_OLD

    old = update.message.text.strip()

    if not old:
        await update.message.reply_text(
            "• أرسل الأمر القديم"
        )
        return WAIT_OLD

    add_command_sessions[user_id]["old"] = old

    await update.message.reply_text(
        "حسناً، أرسل الأمر الجديد"
    )

    return WAIT_NEW


# ==================================================
# استقبال الأمر الجديد
# ==================================================

async def receive_new_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id not in add_command_sessions:
        return ConversationHandler.END

    if not update.message or not update.message.text:
        return WAIT_NEW

    new = update.message.text.strip()

    if not new:
        await update.message.reply_text(
            "• أرسل الأمر الجديد"
        )
        return WAIT_NEW

    old = add_command_sessions[user_id]["old"]

    if old == new:
        await update.message.reply_text(
            "• الأمر الجديد لازم يكون مختلف عن الأمر القديم"
        )
        return WAIT_NEW

    conn = connect()
    cur = conn.cursor()

    # إذا كان الاسم الجديد مستخدمًا كاختصار من قبل
    # نحذفه ونستبدله بالاختصار الجديد
    cur.execute(
        """
        DELETE FROM custom_commands
        WHERE new_command = ?
        """,
        (new,)
    )

    cur.execute(
        """
        INSERT INTO custom_commands
        (
            old_command,
            new_command
        )
        VALUES (?, ?)
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
        f"✅ تم إضافة الأمر\n\n"
        f"{new} يعمل الآن مثل {old}"
    )

    return ConversationHandler.END


# ==================================================
# قائمة الأوامر
# ==================================================

async def custom_commands_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT old_command, new_command
        FROM custom_commands
        ORDER BY new_command
        """
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
        text += f"{new} ➜ {old}\n"

    await update.message.reply_text(text)


# ==================================================
# بدء حذف أمر
# ==================================================

async def delete_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "أرسل الأمر الجديد الذي تريد حذفه"
    )

    context.user_data["delete_command"] = True


# ==================================================
# حذف أمر
# ==================================================

async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get("delete_command"):
        return

    if not update.message or not update.message.text:
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

    deleted = cur.rowcount

    conn.commit()
    conn.close()

    context.user_data.pop(
        "delete_command",
        None
    )

    if deleted:
        await update.message.reply_text(
            "✅ تم حذف الأمر المضاف"
        )
    else:
        await update.message.reply_text(
            "• ما لقيت هذا الأمر ضمن الأوامر المضافة"
        )


# ==================================================
# حذف جميع الأوامر
# ==================================================

async def delete_all_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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


# ==================================================
# الحصول على الأمر الأصلي
# ==================================================

def get_custom_command(text: str):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT old_command
        FROM custom_commands
        WHERE new_command = ?
        LIMIT 1
        """,
        (text,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return None

    return result[0]


# ==================================================
# حل الاختصارات المتسلسلة
#
# مثال:
#
# أ -> ب
# ب -> كلمات
#
# أ
# ↓
# ب
# ↓
# كلمات
# ==================================================

def resolve_custom_command(text: str):

    current = text
    visited = set()

    while True:

        if current in visited:
            return None

        visited.add(current)

        old_command = get_custom_command(current)

        if not old_command:
            break

        current = old_command

    if current == text:
        return None

    return current


# ==================================================
# تشغيل الأمر كأنه مكتوب من المستخدم
# ==================================================

async def check_custom_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return False

    if not update.message.text:
        return False

    text = update.message.text.strip()

    old_command = resolve_custom_command(text)

    if not old_command:
        return False

    # --------------------------------------------------
    # نسخة مستقلة من الـ Update
    # --------------------------------------------------

    fake_update = copy.deepcopy(update)

    # --------------------------------------------------
    # تغيير النص في النسخة فقط
    # --------------------------------------------------

    fake_update.message.text = old_command

    # --------------------------------------------------
    # تشغيل النسخة من خلال Application نفسها
    #
    # بهذا الشكل Telegram يعيد فحص جميع الـ handlers
    # بنفس ترتيب main.py الأصلي.
    # --------------------------------------------------

    await context.application.process_update(
        fake_update
    )

    return True
