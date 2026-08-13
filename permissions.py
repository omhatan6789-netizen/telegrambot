from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import (
    is_developer,
    is_primary_developer,
    is_secondary_developer,
    get_rank,
    RANK_LEVELS
)


OWNER_ID = 8453977662


# ==================================================
# توحيد اسم الأمر
# ==================================================

def normalize_command(command):

    if not command:
        return ""

    command = " ".join(
        command.strip().split()
    )

    return command


# ==================================================
# مستوى الشخص
# ==================================================

def get_permission_level(user_id):

    if is_primary_developer(user_id):
        return 3

    if is_secondary_developer(user_id):
        return 2

    if get_rank(user_id) == "المالك":
        return 1

    return 0


# ==================================================
# هل يستطيع إدارة الصلاحيات؟
# ==================================================

def can_manage_permissions(user_id):

    return get_permission_level(user_id) > 0


# ==================================================
# هل يستطيع تعديل صلاحيات شخص؟
# ==================================================

def can_manage_target(actor_id, target_id):

    if actor_id == target_id:
        return False

    actor_level = get_permission_level(actor_id)
    target_level = get_permission_level(target_id)

    if actor_level == 0:
        return False

    # Dev الأساسي
    if actor_level == 3:
        return True

    # Dev المساعد
    if actor_level == 2:

        if target_level >= 2:
            return False

        return True

    # المالك
    if actor_level == 1:

        if target_level >= 2:
            return False

        return True

    return False


# ==================================================
# حفظ الصلاحية
# ==================================================

def set_user_permission(
    chat_id,
    user_id,
    command,
    allowed
):

    command = normalize_command(command)

    if not command:
        return

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO group_user_permissions
        (
            chat_id,
            user_id,
            permission,
            allowed
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(chat_id, user_id, permission)
        DO UPDATE SET
            allowed=excluded.allowed
        """,
        (
            chat_id,
            user_id,
            command,
            int(allowed)
        )
    )

    conn.commit()
    conn.close()


# ==================================================
# فحص صلاحية الشخص
#
# None  = لا يوجد تخصيص
# False = ممنوع
# True  = مسموح
# ==================================================

def check_user_permission(
    chat_id,
    user_id,
    command
):

    command = normalize_command(command)

    # Dev الأساسي فوق النظام
    if is_primary_developer(user_id):
        return True

    conn = connect()
    cur = conn.cursor()

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

    if not result:
        return None

    return bool(result[0])


# ==================================================
# استخراج الشخص
# ==================================================

async def get_permission_target(
    update,
    context
):

    if not update.message:
        return None

    message = update.message
    text = (message.text or "").strip()

    # ==============================================
    # بالرد
    # ==============================================

    if message.reply_to_message:

        return message.reply_to_message.from_user

    # ==============================================
    # باليوزر أو الآيدي
    # ==============================================

    parts = text.split()

    if len(parts) < 3:
        return None

    target_text = parts[-1].strip()

    # ==============================================
    # آيدي
    # ==============================================

    if target_text.isdigit():

        try:

            return await context.bot.get_chat(
                int(target_text)
            )

        except Exception:

            return None

    # ==============================================
    # يوزر
    # ==============================================

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
# ==================================================

async def permission_command(
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

    parts = text.split()

    if not parts:
        return

    action = parts[0]

    if action not in ("منع", "سماح"):
        return

    actor = update.effective_user

    # ==============================================
    # صلاحية الإدارة
    # ==============================================

    if not can_manage_permissions(actor.id):

        await update.message.reply_text(
            "❌ هذا الأمر للمطور والمالك فقط."
        )

        return

    # ==============================================
    # بالرد
    #
    # منع حظر
    # سماح حظر
    # ==============================================

    if update.message.reply_to_message:

        if len(parts) < 2:

            await update.message.reply_text(
                "❌ اكتب اسم الأمر.\n\n"
                "مثال:\n"
                "منع حظر"
            )

            return

        target = (
            update.message
            .reply_to_message
            .from_user
        )

        command = " ".join(
            parts[1:]
        )

    # ==============================================
    # باليوزر / الآيدي
    #
    # منع حظر @username
    # منع حظر 123456789
    # ==============================================

    else:

        if len(parts) < 3:

            await update.message.reply_text(
                "❌ الاستخدام:\n\n"
                "منع حظر @username\n"
                "منع حظر 123456789\n\n"
                "أو بالرد على الشخص:\n"
                "منع حظر"
            )

            return

        command = " ".join(
            parts[1:-1]
        )

        target = await get_permission_target(
            update,
            context
        )

        if not target:

            await update.message.reply_text(
                "❌ لم أستطع العثور على الشخص."
            )

            return

    command = normalize_command(command)

    # ==============================================
    # التأكد من وجود الأمر
    # ==============================================

    if not command:

        await update.message.reply_text(
            "❌ اكتب اسم الأمر الذي تريد منعه أو السماح به."
        )

        return

    # ==============================================
    # منع تعديل النفس
    # ==============================================

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات نفسك."
        )

        return

    # ==============================================
    # حماية المطور الأساسي
    # ==============================================

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات المطور الأساسي."
        )

        return

    # ==============================================
    # فحص صلاحية تعديل الهدف
    # ==============================================

    if not can_manage_target(
        actor.id,
        target.id
    ):

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات هذا الشخص."
        )

        return

    # ==============================================
    # الحفظ
    # ==============================================

    allowed = 1 if action == "سماح" else 0

    set_user_permission(
        update.effective_chat.id,
        target.id,
        command,
        allowed
    )

    # ==============================================
    # الرد
    # ==============================================

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


# ==================================================
# هل الشخص أدمن؟
# ==================================================

def is_admin(user_id):

    if is_primary_developer(user_id):
        return True

    if is_secondary_developer(user_id):
        return True

    rank = get_rank(user_id)

    return (
        RANK_LEVELS.get(rank, 0)
        >= RANK_LEVELS.get("ادمن", 0)
    )