from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import (
    is_primary_developer,
    is_secondary_developer,
    get_rank,
)


OWNER_ID = 8331154497


# ==================================================
# مستويات الصلاحيات
# ==================================================

PERMISSION_LEVELS = {
    "عضو": 0,
    "مميز": 1,
    "ادمن": 2,
    "ادمن اساسي": 3,
    "المالك": 5,
}


# ==================================================
# هل الشخص يستطيع إدارة صلاحيات الآخرين؟
# ==================================================

def can_manage_permissions(user_id):

    # Dev الأساسي
    if is_primary_developer(user_id):
        return True

    # Dev المساعد
    if is_secondary_developer(user_id):
        return True

    # المالك
    if get_rank(user_id) == "المالك":
        return True

    return False


# ==================================================
# مستوى الشخص
# ==================================================

def get_permission_level(user_id):

    # Dev الأساسي
    if is_primary_developer(user_id):
        return 7

    # Dev المساعد
    if is_secondary_developer(user_id):
        return 6

    # الرتب العادية
    rank = get_rank(user_id)

    return PERMISSION_LEVELS.get(rank, 0)


# ==================================================
# هل يستطيع الشخص تعديل صلاحيات شخص آخر؟
#
# الترتيب:
#
# Dev الأساسي
# Dev المساعد
# المالك
# ادمن اساسي
# ادمن
# مميز
# عضو
# ==================================================

def can_manage_target(actor_id, target_id):

    actor_level = get_permission_level(actor_id)
    target_level = get_permission_level(target_id)

    # لا يملك صلاحية إدارة الصلاحيات
    if actor_level < 5:
        return False

    # لا يستطيع تعديل نفسه
    if actor_id == target_id:
        return False

    # لا يستطيع تعديل شخص مساوي أو أعلى منه
    if target_level >= actor_level:
        return False

    return True


# ==================================================
# حفظ منع / سماح
# ==================================================

def set_user_permission(
    chat_id,
    user_id,
    command,
    allowed
):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS group_user_permissions
        (
            chat_id INTEGER,
            user_id INTEGER,
            permission TEXT,
            allowed INTEGER DEFAULT 1,

            PRIMARY KEY
            (
                chat_id,
                user_id,
                permission
            )
        )
        """
    )

    cur.execute(
        """
        INSERT INTO group_user_permissions
        (
            chat_id,
            user_id,
            permission,
            allowed
        )
        VALUES
        (?, ?, ?, ?)

        ON CONFLICT(chat_id, user_id, permission)
        DO UPDATE SET
            allowed=excluded.allowed
        """,
        (
            chat_id,
            user_id,
            command,
            allowed
        )
    )

    conn.commit()
    conn.close()


# ==================================================
# فحص صلاحية الشخص لأمر معين
#
# النتيجة:
#
# سماح خاص  -> يسمح حتى لو الرتبة أقل
# منع خاص   -> يمنع حتى لو الرتبة تسمح
# لا يوجد   -> يرجع للنظام الطبيعي
# ==================================================

def check_user_permission(
    chat_id,
    user_id,
    command
):

    # Dev الأساسي لا يمكن منعه
    if is_primary_developer(user_id):
        return True

    conn = connect()
    cur = conn.cursor()

    # إنشاء الجدول إذا لم يكن موجودًا
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS group_user_permissions
        (
            chat_id INTEGER,
            user_id INTEGER,
            permission TEXT,
            allowed INTEGER DEFAULT 1,

            PRIMARY KEY
            (
                chat_id,
                user_id,
                permission
            )
        )
        """
    )

    cur.execute(
        """
        SELECT allowed
        FROM group_user_permissions
        WHERE chat_id=?
        AND user_id=?
        AND permission=?
        """,
        (
            chat_id,
            user_id,
            command
        )
    )

    result = cur.fetchone()

    conn.close()

    # لا يوجد منع أو سماح خاص
    if not result:
        return None

    # 1 = سماح
    # 0 = منع
    return bool(result[0])


# ==================================================
# استخراج الشخص
#
# يدعم:
#
# بالرد
# @username
# ID
# ==================================================

async def get_permission_target(
    update,
    context
):

    if not update.message:
        return None

    message = update.message
    text = (message.text or "").strip()

    # ------------------------------------------
    # بالرد
    # ------------------------------------------

    if message.reply_to_message:

        return message.reply_to_message.from_user

    # ------------------------------------------
    # باليوزر / الآيدي
    # ------------------------------------------

    parts = text.split()

    if len(parts) < 3:
        return None

    target_text = parts[-1].strip()

    # ------------------------------------------
    # ID
    # ------------------------------------------

    if target_text.isdigit():

        try:

            return await context.bot.get_chat(
                int(target_text)
            )

        except Exception:

            return None

    # ------------------------------------------
    # Username
    # ------------------------------------------

    if target_text.startswith("@"):

        try:

            return await context.bot.get_chat(
                target_text
            )

        except Exception:

            return None

    return None


# ==================================================
# منع / سماح
#
# أمثلة:
#
# منع حظر @username
# منع حظر 123456789
# بالرد:
# منع حظر
#
# سماح حظر @username
# سماح حظر 123456789
# بالرد:
# سماح حظر
# ==================================================

async def permission_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (update.message.text or "").strip()

    if not text:
        return

    parts = text.split()

    if not parts:
        return

    action = parts[0]

    # ليس منع أو سماح
    if action not in (
        "منع",
        "سماح"
    ):
        return

    actor = update.effective_user

    # ==================================================
    # التحقق من صلاحية استخدام منع / سماح
    # ==================================================

    if not can_manage_permissions(actor.id):

        await update.message.reply_text(
            "❌ هذا الأمر للمطور والمالك فقط."
        )

        return

    # ==================================================
    # استخراج الأمر والهدف
    # ==================================================

    # ------------------------------------------
    # بالرد
    # ------------------------------------------

    if update.message.reply_to_message:

        if len(parts) < 2:

            await update.message.reply_text(
                "❌ اكتب اسم الأمر.\n\n"
                "مثال:\n"
                "منع حظر"
            )

            return

        target = update.message.reply_to_message.from_user

        command = " ".join(
            parts[1:]
        ).strip()

    # ------------------------------------------
    # باليوزر / الآيدي
    # ------------------------------------------

    else:

        if len(parts) < 3:

            await update.message.reply_text(
                "❌ الاستخدام:\n\n"
                "منع حظر @username\n"
                "منع حظر 123456789\n\n"
                "أو بالرد:\n"
                "منع حظر"
            )

            return

        command = " ".join(
            parts[1:-1]
        ).strip()

        target = await get_permission_target(
            update,
            context
        )

        if not target:

            await update.message.reply_text(
                "❌ لم أستطع العثور على الشخص."
            )

            return

    # ==================================================
    # التأكد من وجود الأمر
    # ==================================================

    if not command:

        await update.message.reply_text(
            "❌ اكتب اسم الأمر."
        )

        return

    # ==================================================
    # لا تعدل نفسك
    # ==================================================

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات نفسك."
        )

        return

    # ==================================================
    # حماية المطور الأساسي
    # ==================================================

    if is_primary_developer(target.id):

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات Dev الأساسي."
        )

        return

    # ==================================================
    # فحص مستوى الهدف
    # ==================================================

    if not can_manage_target(
        actor.id,
        target.id
    ):

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات هذا الشخص."
        )

        return

    # ==================================================
    # منع / سماح
    # ==================================================

    if action == "منع":

        allowed = 0

    else:

        allowed = 1

    set_user_permission(
        update.effective_chat.id,
        target.id,
        command,
        allowed
    )

    # ==================================================
    # الرد
    # ==================================================

    if action == "منع":

        await update.message.reply_text(
            f"🚫 تم منع {target.first_name} من الأمر:\n"
            f"↤︎ {command}"
        )

    else:

        await update.message.reply_text(
            f"✅ تم السماح لـ {target.first_name} بالأمر:\n"
            f"↤︎ {command}"
        )