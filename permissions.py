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
# مستوى الشخص في نظام الصلاحيات
# ==================================================
#
# 3 = Dev الأساسي
# 2 = Dev المساعد
# 1 = المالك
# 0 = باقي الأشخاص
#
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
# هل يستطيع الشخص إدارة الصلاحيات؟
# ==================================================

def can_manage_permissions(user_id):

    return get_permission_level(user_id) > 0


# ==================================================
# هل يستطيع الشخص تعديل صلاحيات شخص آخر؟
# ==================================================

def can_manage_target(actor_id, target_id):

    actor_level = get_permission_level(actor_id)
    target_level = get_permission_level(target_id)

    # ليس لديه صلاحية
    if actor_level == 0:
        return False

    # ==============================================
    # Dev الأساسي
    # ==============================================

    if actor_level == 3:

        # يستطيع تعديل الجميع
        return True

    # ==============================================
    # Dev المساعد
    # ==============================================

    if actor_level == 2:

        # لا يستطيع تعديل Dev الأساسي
        if target_level == 3:
            return False

        # لا يستطيع تعديل Dev مساعد آخر
        if target_level == 2:
            return False

        # يستطيع تعديل المالك وباقي الرتب
        return True

    # ==============================================
    # المالك
    # ==============================================

    if actor_level == 1:

        # المالك لا يستطيع تعديل Dev الأساسي
        if target_level == 3:
            return False

        # المالك لا يستطيع تعديل Dev المساعد
        if target_level == 2:
            return False

        # يستطيع تعديل نفسه؟ لا
        # يتم منع ذلك في permission_command
        return True

    return False


# ==================================================
# حفظ منع / سماح لشخص
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
# فحص هل الشخص ممنوع من أمر معين
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

    return bool(result[0])


# ==================================================
# استخراج الشخص المستهدف
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
    # باليوزر / الآيدي
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

    text = (update.message.text or "").strip()

    if not text:
        return

    parts = text.split()

    if not parts:
        return

    action = parts[0]

    # ==============================================
    # نتأكد أنه منع أو سماح
    # ==============================================

    if action not in ("منع", "سماح"):
        return

    actor = update.effective_user

    # ==============================================
    # هل يملك صلاحية إدارة الصلاحيات؟
    # ==============================================

    if not can_manage_permissions(actor.id):

        await update.message.reply_text(
            "❌ هذا الأمر للمطور والمالك فقط."
        )

        return

    # ==============================================
    # استخراج الأمر والهدف
    # ==============================================

    if update.message.reply_to_message:

        # مثال:
        #
        # منع حظر
        #
        # [منع] [حظر]

        if len(parts) < 2:

            await update.message.reply_text(
                "❌ اكتب اسم الأمر.\n\n"
                "مثال:\n"
                "منع حظر"
            )

            return

        target = update.message.reply_to_message.from_user

        command = " ".join(parts[1:]).strip()

    else:

        # مثال:
        #
        # منع حظر @username
        # منع حظر 123456789

        if len(parts) < 3:

            await update.message.reply_text(
                "❌ الاستخدام:\n\n"
                "منع حظر @username\n"
                "منع حظر 123456789\n\n"
                "أو بالرد:\n"
                "منع حظر"
            )

            return

        command = " ".join(parts[1:-1]).strip()

        target = await get_permission_target(
            update,
            context
        )

        if not target:

            await update.message.reply_text(
                "❌ لم أستطع العثور على الشخص."
            )

            return

    # ==============================================
    # تأكد من وجود أمر
    # ==============================================

    if not command:

        await update.message.reply_text(
            "❌ اكتب اسم الأمر الذي تريد منعه أو السماح به."
        )

        return

    # ==============================================
    # لا يستطيع تعديل نفسه
    # ==============================================

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات نفسك."
        )

        return

    # ==============================================
    # حماية المستويات
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
    # منع / سماح
    # ==============================================

    allowed = 0 if action == "منع" else 1

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
# التحقق من الأدمن
# ==================================================

def is_admin(user_id):

    # Dev الأساسي
    if is_primary_developer(user_id):
        return True

    # Dev المساعد
    if is_secondary_developer(user_id):
        return True

    # الرتبة العادية
    rank = get_rank(user_id)

    return RANK_LEVELS.get(rank, 0) >= RANK_LEVELS.get("ادمن", 0)