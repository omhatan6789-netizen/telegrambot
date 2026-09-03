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
# Cache للصلاحيات
# ==================================================

_user_permission_cache = {}


# ==================================================
# مسح Cache
# ==================================================

def clear_user_permission_cache(
    chat_id=None,
    user_id=None,
    command=None
):

    # مسح كامل
    if (
        chat_id is None
        and user_id is None
        and command is None
    ):

        _user_permission_cache.clear()

        return

    key = (
        chat_id,
        user_id,
        normalize_command(command)
        if command
        else None
    )

    _user_permission_cache.pop(
        key,
        None
    )


# ==================================================
# توحيد اسم الأمر
# ==================================================

def normalize_command(command):

    if not command:
        return ""

    return " ".join(
        command.strip().split()
    )


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

    return (
        get_permission_level(user_id)
        > 0
    )


# ==================================================
# هل يستطيع تعديل صلاحيات شخص؟
# ==================================================

def can_manage_target(
    actor_id,
    target_id
):

    if actor_id == target_id:
        return False

    actor_level = get_permission_level(
        actor_id
    )

    target_level = get_permission_level(
        target_id
    )

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

    command = normalize_command(
        command
    )

    if not command:
        return

    conn = connect()
    cur = conn.cursor()

    try:

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

            ON CONFLICT(
                chat_id,
                user_id,
                permission
            )
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

    except Exception:

        conn.rollback()

        raise

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()

    clear_user_permission_cache(
        chat_id=chat_id,
        user_id=user_id,
        command=command
    )


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

    command = normalize_command(
        command
    )

    if not command:
        return None

    # ==================================================
    # Dev الأساسي
    # ==================================================

    if is_primary_developer(user_id):
        return True

    # ==================================================
    # Cache
    # ==================================================

    cache_key = (
        chat_id,
        user_id,
        command
    )

    if cache_key in _user_permission_cache:

        return _user_permission_cache[
            cache_key
        ]

    # ==================================================
    # DB
    # ==================================================

    conn = connect()

    try:

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

        try:
            cur.close()
        except Exception:
            pass

    finally:

        conn.close()

    # ==================================================
    # لا يوجد تخصيص
    # ==================================================

    if not result:

        _user_permission_cache[
            cache_key
        ] = None

        return None

    permission = bool(
        result[0]
    )

    _user_permission_cache[
        cache_key
    ] = permission

    return permission


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

    # بالرد
    if message.reply_to_message:

        return (
            message.reply_to_message.from_user
        )

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 3:
        return None

    target_text = parts[-1].strip()

    # آيدي
    if target_text.isdigit():

        try:

            return await context.bot.get_chat(
                int(target_text)
            )

        except Exception:

            return None

    # يوزر
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

    if action not in (
        "منع",
        "سماح"
    ):
        return

    actor = update.effective_user

    if not actor:
        return

    # ==================================================
    # صلاحية الإدارة
    # ==================================================

    if not can_manage_permissions(
        actor.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للمطور والمالك فقط."
        )

        return

    # ==================================================
    # بالرد
    # ==================================================

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

    # ==================================================
    # باليوزر / الآيدي
    # ==================================================

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

    command = normalize_command(
        command
    )

    if not command:

        await update.message.reply_text(
            "❌ اكتب اسم الأمر الذي تريد منعه أو السماح به."
        )

        return

    # ==================================================
    # منع تعديل النفس
    # ==================================================

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات نفسك."
        )

        return

    # ==================================================
    # حماية المطور الأساسي
    # ==================================================

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل صلاحيات المطور الأساسي."
        )

        return

    # ==================================================
    # فحص صلاحية تعديل الهدف
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
    # الحفظ
    # ==================================================

    allowed = (
        1
        if action == "سماح"
        else 0
    )

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
        RANK_LEVELS.get(
            rank,
            0
        )
        >=
        RANK_LEVELS.get(
            "ادمن",
            0
        )
    )