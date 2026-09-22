import asyncio
import re
import time
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import (
    get_rank,
    get_rank_level,
)


# ==================================================
# كاش الكتم السريع
# ==================================================

_mute_cache = {}


# ==================================================
# الصلاحيات
# ==================================================

def _get_level(user_id, chat_id=None):
    """
    يدعم roles.py القديمة والجديدة.
    إذا كانت get_rank_level تقبل chat_id نستخدمه،
    وإلا نرجع للاستدعاء القديم.
    """
    try:
        if chat_id is not None:
            return get_rank_level(user_id, chat_id)
    except TypeError:
        pass
    except Exception:
        pass

    try:
        return get_rank_level(user_id)
    except Exception:
        return 0


def is_admin_or_higher(user_id, chat_id=None):
    return _get_level(user_id, chat_id) >= 2


def is_basic_admin_or_higher(user_id, chat_id=None):
    return _get_level(user_id, chat_id) >= 3


# ==================================================
# الوقت
# ==================================================

def now_timestamp():
    return int(time.time())


def timestamp_to_iso(timestamp):
    if timestamp is None:
        return None

    return datetime.fromtimestamp(
        timestamp,
        timezone.utc
    ).isoformat()


def iso_to_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return None


# ==================================================
# HTML
# ==================================================

def html_escape(value):
    if value is None:
        return ""

    value = str(value)

    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ==================================================
# إعدادات الإشراف
# ==================================================

def get_moderation_settings(chat_id):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT durations_enabled, reasons_enabled
            FROM moderation_settings
            WHERE chat_id=?
            """,
            (chat_id,)
        )

        row = cur.fetchone()

        if not row:
            cur.execute(
                """
                INSERT INTO moderation_settings
                (
                    chat_id,
                    durations_enabled,
                    reasons_enabled
                )
                VALUES (?, 0, 0)
                ON CONFLICT(chat_id) DO NOTHING
                """,
                (chat_id,)
            )

            conn.commit()

            return {
                "durations_enabled": False,
                "reasons_enabled": False,
            }

        return {
            "durations_enabled": bool(row[0]),
            "reasons_enabled": bool(row[1]),
        }

    finally:
        if cur:
            cur.close()

        conn.close()


def set_duration_setting(chat_id, enabled):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO moderation_settings
            (
                chat_id,
                durations_enabled
            )
            VALUES (?, ?)

            ON CONFLICT(chat_id)
            DO UPDATE SET
                durations_enabled=excluded.durations_enabled
            """,
            (
                chat_id,
                1 if enabled else 0
            )
        )

        conn.commit()

    finally:
        if cur:
            cur.close()

        conn.close()


def set_reason_setting(chat_id, enabled):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO moderation_settings
            (
                chat_id,
                reasons_enabled
            )
            VALUES (?, ?)

            ON CONFLICT(chat_id)
            DO UPDATE SET
                reasons_enabled=excluded.reasons_enabled
            """,
            (
                chat_id,
                1 if enabled else 0
            )
        )

        conn.commit()

    finally:
        if cur:
            cur.close()

        conn.close()


# ==================================================
# حفظ المستخدم
# ==================================================

def save_target_user(user):

    if not user:
        return

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users
            (
                user_id,
                username,
                first_name,
                messages,
                rank
            )
            VALUES (?, ?, ?, 0, 'عضو')

            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
            """,
            (
                user.id,
                user.username or "",
                user.first_name or ""
            )
        )

        conn.commit()

    finally:
        if cur:
            cur.close()

        conn.close()


# ==================================================
# استخراج الهدف
# ==================================================

async def resolve_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return None

    message = update.message

    # ==================================================
    # بالرد
    # ==================================================

    if message.reply_to_message:

        user = message.reply_to_message.from_user

        if user:
            await asyncio.to_thread(
                save_target_user,
                user
            )

            return user

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 2:
        return None

    target_value = None

    for part in parts[1:]:

        clean = part.strip()

        if clean.isdigit():
            target_value = clean
            break

        if clean.startswith("@"):
            target_value = clean
            break

    if not target_value:
        return None

    # ==================================================
    # ID
    # ==================================================

    if target_value.isdigit():

        user_id = int(target_value)

        row = await asyncio.to_thread(
            _get_user_by_id,
            user_id
        )

        if row:

            class StoredUser:
                pass

            user = StoredUser()

            user.id = row[0]
            user.username = row[1] or None
            user.first_name = row[2] or ""

            return user

        try:
            user = await context.bot.get_chat(
                user_id
            )

            if user:
                await asyncio.to_thread(
                    save_target_user,
                    user
                )

                return user

        except Exception:
            pass

        return None

    # ==================================================
    # Username
    # ==================================================

    username = target_value.lstrip("@").lower()

    row = await asyncio.to_thread(
        _get_user_by_username,
        username
    )

    if not row:
        return None

    class StoredUser:
        pass

    user = StoredUser()

    user.id = row[0]
    user.username = row[1] or None
    user.first_name = row[2] or ""

    return user


def _get_user_by_id(user_id):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id, username, first_name
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        return cur.fetchone()

    finally:
        if cur:
            cur.close()

        conn.close()


def _get_user_by_username(username):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id, username, first_name
            FROM users
            WHERE LOWER(username)=?
            LIMIT 1
            """,
            (username,)
        )

        return cur.fetchone()

    finally:
        if cur:
            cur.close()

        conn.close()


# ==================================================
# منشن المستخدم
# ==================================================

def mention_user(user):

    if not user:
        return ""

    name = (
        getattr(user, "first_name", None)
        or getattr(user, "username", None)
        or str(user.id)
    )

    name = html_escape(name)

    return (
        f'<a href="tg://user?id={user.id}">'
        f'{name}'
        f'</a>'
    )


# ==================================================
# استخراج المدة
# ==================================================

DURATION_PATTERN = re.compile(
    r"^(\d+)\s*"
    r"(ث|ثانية|ثواني|"
    r"د|دقيقة|دقائق|"
    r"س|ساعة|ساعات|"
    r"ي|يوم|أيام)$",
    re.IGNORECASE
)


def parse_duration_token(token):

    token = token.strip()

    match = DURATION_PATTERN.match(token)

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    if amount <= 0:
        return None

    if unit in ("ث", "ثانية", "ثواني"):
        return amount

    if unit in ("د", "دقيقة", "دقائق"):
        return amount * 60

    if unit in ("س", "ساعة", "ساعات"):
        return amount * 60 * 60

    if unit in ("ي", "يوم", "أيام"):
        return amount * 24 * 60 * 60

    return None


# ==================================================
# تحليل أمر العقوبة
# ==================================================

ACTION_NAMES = {
    "كتم": "mute",
    "تقييد": "restrict",
    "حظر": "ban",
}


def parse_moderation_command(
    text,
    durations_enabled,
    reasons_enabled
):

    parts = text.strip().split()

    if not parts:
        return None

    action_word = parts[0]

    if action_word not in ACTION_NAMES:
        return None

    action = ACTION_NAMES[action_word]

    rest = parts[1:]

    duration = None
    duration_index = None
    target_index = None

    # ==================================================
    # البحث عن المدة
    # ==================================================

    for i, part in enumerate(rest):

        parsed = parse_duration_token(part)

        if parsed is not None:

            duration_index = i

            if durations_enabled:
                duration = parsed
            else:
                # المدة غير مفعلة، نتجاهلها
                duration = None

            break

    # ==================================================
    # البحث عن الهدف
    # ==================================================

    for i, part in enumerate(rest):

        if i == duration_index:
            continue

        clean = part.strip()

        if clean.isdigit() or clean.startswith("@"):
            target_index = i
            break

    # ==================================================
    # السبب
    # ==================================================

    reason_parts = []

    for i, part in enumerate(rest):

        if i == duration_index:
            continue

        if i == target_index:
            continue

        reason_parts.append(part)

    reason = None

    if reason_parts and reasons_enabled:
        reason = " ".join(reason_parts)

    return {
        "action": action,
        "duration": duration,
        "reason": reason,
    }


# ==================================================
# اسم العقوبة
# ==================================================

def action_name(action):

    if action == "mute":
        return "الكتم"

    if action == "restrict":
        return "التقييد"

    if action == "ban":
        return "الحظر"

    return action


# ==================================================
# تنسيق المدة
# ==================================================

def format_duration(seconds):

    seconds = int(seconds)

    if seconds % 86400 == 0:
        amount = seconds // 86400
        return f"{amount} يوم"

    if seconds % 3600 == 0:
        amount = seconds // 3600
        return f"{amount} ساعة"

    if seconds % 60 == 0:
        amount = seconds // 60
        return f"{amount} دقيقة"

    return f"{seconds} ثانية"


# ==================================================
# حفظ الكتم
# ==================================================

def save_mute(
    chat_id,
    user,
    until_time,
    reason,
    by_user
):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bot_mutes
            (
                chat_id,
                user_id,
                username,
                first_name,
                until_time,
                reason,
                by_user
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                until_time=excluded.until_time,
                reason=excluded.reason,
                by_user=excluded.by_user
            """,
            (
                chat_id,
                user.id,
                getattr(user, "username", None),
                getattr(user, "first_name", None),
                until_time,
                reason,
                by_user
            )
        )

        conn.commit()

    finally:
        if cur:
            cur.close()

        conn.close()

    key = (
        chat_id,
        user.id
    )

    if until_time is None:
        _mute_cache[key] = True
    else:
        timestamp = iso_to_timestamp(
            until_time
        )

        if timestamp is not None:
            _mute_cache[key] = timestamp
        else:
            _mute_cache[key] = True


# ==================================================
# حفظ التقييد
# ==================================================

def save_restriction(
    chat_id,
    user,
    until_time,
    reason,
    by_user
):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO restrictions
            (
                chat_id,
                user_id,
                username,
                first_name,
                until_time,
                reason,
                by_user
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                until_time=excluded.until_time,
                reason=excluded.reason,
                by_user=excluded.by_user
            """,
            (
                chat_id,
                user.id,
                getattr(user, "username", None),
                getattr(user, "first_name", None),
                until_time,
                reason,
                by_user
            )
        )

        conn.commit()

    finally:
        if cur:
            cur.close()

        conn.close()


# ==================================================
# حفظ الحظر
# ==================================================

def save_ban(
    chat_id,
    user,
    until_time,
    reason,
    by_user
):

    conn = connect()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO moderation_bans
            (
                chat_id,
                user_id,
                username,
                first_name,
                until_time,
                reason,
                by_user
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                until_time=excluded.until_time,
                reason=excluded.reason,
                by_user=excluded.by_user
            """,
            (
                chat_id,
                user.id,
                getattr(user, "username", None),
                getattr(user, "first_name", None),
                until_time,
                reason,
                by_user
            )
        )

        conn.commit()

    finally:
        if cur:
            cur.close()

        conn.close()


# ==================================================
# رسالة العقوبة
# ==================================================

def moderation_message(
    action,
    target,
    duration,
    reason=None,
    actor_rank=None
):

    mention = mention_user(target)

    if action == "mute":

        text = (
            "تم كتمته لين يهجد بعدين فكوه\n"
            f"المستخدم ↤︎ {mention}"
        )

    elif action == "restrict":

        text = (
            "تم قيَّدته لين يهجد بعدين فكوه\n"
            f"المستخدم ↤︎ {mention}"
        )

    else:

        rank = actor_rank or "عضو"

        text = (
            f"تم حظرته لعيونك يـ "
            f"{html_escape(rank)}\n"
            f"المستخدم ↤︎ {mention}"
        )

    if duration is not None:

        text += (
            "\n"
            f"مدة {action_name(action)} ↤︎ "
            f"{format_duration(duration)}"
        )

    if reason:

        text += (
            "\n"
            f"السبب ↤︎ {html_escape(reason)}"
        )

    return text


# ==================================================
# تنفيذ العقوبة
# ==================================================

async def moderation_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.effective_chat:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    text = (
        update.message.text or ""
    ).strip()

    settings = await asyncio.to_thread(
        get_moderation_settings,
        chat_id
    )

    parsed = parse_moderation_command(
        text,
        settings["durations_enabled"],
        settings["reasons_enabled"]
    )

    if not parsed:
        return

    target = await resolve_target(
        update,
        context
    )

    if not target:
        return

    action = parsed["action"]
    duration = parsed["duration"]
    reason = parsed["reason"]

    # ==================================================
    # المدة الافتراضية للكتم
    # ==================================================

    if (
        action == "mute"
        and settings["durations_enabled"]
        and duration is None
    ):
        duration = 60 * 60

    # ==================================================
    # منع البوت
    # ==================================================

    if target.id == context.bot.id:

        await update.message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return

    # ==================================================
    # منع معاقبة النفس
    # ==================================================

    if target.id == actor.id:

        self_messages = {
            "mute":
                "• اعرف ان الحياة صعبة بس ماتوصل لمرحلة انك تكتم نفسك 😔 .",

            "restrict":
                "• اعرف ان الحياة صعبة بس ماتوصل لمرحلة انك تقيد نفسك 😔 .",

            "ban":
                "• اعرف ان الحياة صعبة بس ماتوصل لمرحلة انك تحظر نفسك 😔 .",
        }

        await update.message.reply_text(
            self_messages[action]
        )

        return

    # ==================================================
    # رتبة الهدف
    # ==================================================

    target_level = await asyncio.to_thread(
        _get_level,
        target.id,
        chat_id
    )

    if target_level >= actor_level:

        higher_messages = {
            "mute":
                "صحصح شف من الي تبي تكتمه ياورع!",

            "restrict":
                "صحصح شف من الي تبي تقيده ياورع!",

            "ban":
                "صحصح شف من الي تبي تحظره ياورع!",
        }

        await update.message.reply_text(
            higher_messages[action]
        )

        return

    until_timestamp = None

    if duration is not None:
        until_timestamp = (
            now_timestamp() + duration
        )

    until_time = timestamp_to_iso(
        until_timestamp
    )

    asyncio.create_task(
        asyncio.to_thread(
            save_target_user,
            target
        )
    )

    actor_rank_task = None

    if action == "ban":

        actor_rank_task = asyncio.create_task(
            asyncio.to_thread(
                get_rank,
                actor.id
            )
        )

    # ==================================================
    # الكتم
    # ==================================================

    if action == "mute":

        asyncio.create_task(
            asyncio.to_thread(
                save_mute,
                chat_id,
                target,
                until_time,
                reason,
                actor.id
            )
        )

        await update.message.reply_text(
            moderation_message(
                action,
                target,
                duration,
                reason
            ),
            parse_mode="HTML"
        )

        return

    # ==================================================
    # التقييد
    # ==================================================

    if action == "restrict":

        try:

            from telegram import ChatPermissions

            permissions = ChatPermissions(
                can_send_messages=False
            )

            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target.id,
                permissions=permissions,
                until_date=(
                    until_timestamp
                    if until_timestamp
                    else None
                )
            )

        except Exception:
            return

        asyncio.create_task(
            asyncio.to_thread(
                save_restriction,
                chat_id,
                target,
                until_time,
                reason,
                actor.id
            )
        )

        await update.message.reply_text(
            moderation_message(
                action,
                target,
                duration,
                reason
            ),
            parse_mode="HTML"
        )

        return

    # ==================================================
    # الحظر
    # ==================================================

    if action == "ban":

        try:

            await context.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=target.id,
                until_date=(
                    until_timestamp
                    if until_timestamp
                    else None
                )
            )

        except Exception:
            return

        asyncio.create_task(
            asyncio.to_thread(
                save_ban,
                chat_id,
                target,
                until_time,
                reason,
                actor.id
            )
        )

        try:

            actor_rank = await asyncio.wait_for(
                actor_rank_task,
                timeout=0.05
            )

        except Exception:

            actor_rank = "عضو"

        await update.message.reply_text(
            moderation_message(
                action,
                target,
                duration,
                reason,
                actor_rank
            ),
            parse_mode="HTML"
        )

        return


# ==================================================
# التحقق من الكتم
# ==================================================

def get_active_mute(
    chat_id,
    user_id
):

    key = (
        chat_id,
        user_id
    )

    if key in _mute_cache:

        cached = _mute_cache[key]

        if cached is False:
            return False

        if cached is True:
            return True

        if now_timestamp() < cached:
            return True

        _mute_cache[key] = False

        try:
            delete_mute(
                chat_id,
                user_id
            )
        except Exception:
            pass

        return False

    row = _get_mute_row(
        chat_id,
        user_id
    )

    if not row:

        _mute_cache[key] = False

        return False

    until_time = row[0]

    if until_time is None:

        _mute_cache[key] = True

        return True

    until = iso_to_timestamp(
        until_time
    )

    if until is None:

        _mute_cache[key] = False

        return False

    if now_timestamp() >= until:

        _mute_cache[key] = False

        try:
            delete_mute(
                chat_id,
                user_id
            )
        except Exception:
            pass

        return False

    _mute_cache[key] = until

    return True


def _get_mute_row(
    chat_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT until_time
            FROM bot_mutes
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        return cur.fetchone()

    finally:

        if cur:
            cur.close()

        conn.close()


def delete_mute(
    chat_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM bot_mutes
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        conn.commit()

    finally:

        if cur:
            cur.close()

        conn.close()

    _mute_cache[
        (chat_id, user_id)
    ] = False


# ==================================================
# حذف رسالة المكتوم
# ==================================================

async def check_muted_message(
    update,
    context
):

    if not update.message:
        return

    if not update.effective_chat:
        return

    user = update.effective_user

    if not user:
        return

    chat_id = update.effective_chat.id

    is_muted = await asyncio.to_thread(
        get_active_mute,
        chat_id,
        user.id
    )

    if not is_muted:
        return

    try:
        await update.message.delete()
    except Exception:
        pass


# ==================================================
# جلب القيود
# ==================================================

def get_user_restrictions(
    chat_id,
    user_id
):

    conn = connect()
    cur = None

    result = []

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM bot_mutes
            WHERE chat_id=?
            AND user_id=?
            LIMIT 1
            """,
            (
                chat_id,
                user_id
            )
        )

        if cur.fetchone():
            result.append("كتم")

        cur.execute(
            """
            SELECT 1
            FROM restrictions
            WHERE chat_id=?
            AND user_id=?
            LIMIT 1
            """,
            (
                chat_id,
                user_id
            )
        )

        if cur.fetchone():
            result.append("تقييد")

        cur.execute(
            """
            SELECT 1
            FROM moderation_bans
            WHERE chat_id=?
            AND user_id=?
            LIMIT 1
            """,
            (
                chat_id,
                user_id
            )
        )

        if cur.fetchone():
            result.append("حظر")

        return result

    finally:

        if cur:
            cur.close()

        conn.close()


# ==================================================
# حذف قيد
# ==================================================

def delete_restriction_record(
    table,
    chat_id,
    user_id
):

    allowed = {
        "bot_mutes",
        "restrictions",
        "moderation_bans"
    }

    if table not in allowed:
        return

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            f"""
            DELETE FROM {table}
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        conn.commit()

    finally:

        if cur:
            cur.close()

        conn.close()

    if table == "bot_mutes":

        _mute_cache[
            (chat_id, user_id)
        ] = False


# ==================================================
# إلغاء الكتم
# ==================================================

async def unmute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await remove_one_restriction(
        update,
        context,
        "mute"
    )


# ==================================================
# إلغاء التقييد
# ==================================================

async def unrestrict_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await remove_one_restriction(
        update,
        context,
        "restrict"
    )


# ==================================================
# إلغاء الحظر
# ==================================================

async def unban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    actor = update.effective_user

    if not actor:
        return

    chat_id = (
        update.effective_chat.id
        if update.effective_chat
        else None
    )

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 3:
        return

    await remove_one_restriction(
        update,
        context,
        "ban"
    )


# ==================================================
# إزالة قيد واحد
# ==================================================

async def remove_one_restriction(
    update,
    context,
    action
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    if action == "ban" and actor_level < 3:
        return

    target = await resolve_target(
        update,
        context
    )

    if not target:
        return

    if target.id == context.bot.id:

        await update.message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return

    # ==================================================
    # إلغاء الكتم
    # ==================================================

    if action == "mute":

        await asyncio.to_thread(
            delete_restriction_record,
            "bot_mutes",
            chat_id,
            target.id
        )

        text = (
            "فكيت عنه الكتم يارب يعقل 🙏🏻\n"
            f"• المستخدم ↤︎ {mention_user(target)}"
        )

    # ==================================================
    # إلغاء التقييد
    # ==================================================

    elif action == "restrict":

        try:

            from telegram import ChatPermissions

            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
                can_manage_topics=True,
            )

            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target.id,
                permissions=permissions
            )

        except Exception:
            return

        await asyncio.to_thread(
            delete_restriction_record,
            "restrictions",
            chat_id,
            target.id
        )

        text = (
            "فكيت عنه يارب يعقل 🙏🏻\n"
            f"• المستخدم ↤︎ {mention_user(target)}"
        )

    # ==================================================
    # إلغاء الحظر
    # ==================================================

    else:

        try:

            await context.bot.unban_chat_member(
                chat_id=chat_id,
                user_id=target.id,
                only_if_banned=False
            )

        except Exception:
            return

        await asyncio.to_thread(
            delete_restriction_record,
            "moderation_bans",
            chat_id,
            target.id
        )

        text = (
            "فكيت عنه يارب يعقل 🙏🏻\n"
            f"المستخدم ↤︎ {mention_user(target)}"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ==================================================
# رفع القيود
# ==================================================

async def clear_restrictions_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    target = await resolve_target(
        update,
        context
    )

    if not target:
        return

    if target.id == context.bot.id:

        await update.message.reply_text(
            "هذا بوت ياغبي😭😭 …"
        )

        return

    restrictions = await asyncio.to_thread(
        get_user_restrictions,
        chat_id,
        target.id
    )

    if "كتم" in restrictions:

        await asyncio.to_thread(
            delete_restriction_record,
            "bot_mutes",
            chat_id,
            target.id
        )

    if "تقييد" in restrictions:

        try:

            from telegram import ChatPermissions

            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
                can_manage_topics=True,
            )

            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target.id,
                permissions=permissions
            )

        except Exception:
            pass

        await asyncio.to_thread(
            delete_restriction_record,
            "restrictions",
            chat_id,
            target.id
        )

    if "حظر" in restrictions:

        if actor_level >= 3:

            try:

                await context.bot.unban_chat_member(
                    chat_id=chat_id,
                    user_id=target.id,
                    only_if_banned=False
                )

            except Exception:
                pass

            await asyncio.to_thread(
                delete_restriction_record,
                "moderation_bans",
                chat_id,
                target.id
            )

    await update.message.reply_text(
        "• تم رفع القيود عنه، قيوده كانت ( "
        + "، ".join(restrictions)
        + " )\n"
        + f"المستخدم ↤︎ {mention_user(target)}",
        parse_mode="HTML"
    )


# ==================================================
# القوائم
# ==================================================

LIST_TABLES = {
    "mute": (
        "bot_mutes",
        "قائمه المكتومين",
        "مسح المكتومين"
    ),

    "restrict": (
        "restrictions",
        "قائمه المقيدين",
        "مسح المقيدين"
    ),

    "ban": (
        "moderation_bans",
        "قائمه المحظورين",
        "مسح المحظورين"
    ),
}


def get_list_rows(
    chat_id,
    table
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            f"""
            SELECT user_id, username, first_name
            FROM {table}
            WHERE chat_id=?
            ORDER BY user_id
            """,
            (chat_id,)
        )

        return cur.fetchall()

    finally:

        if cur:
            cur.close()

        conn.close()


def list_message(
    kind,
    rows
):

    table, title, button_text = LIST_TABLES[kind]

    text = (
        f"• {title}\n"
        "━━━━━━━━━━━━\n"
    )

    if not rows:

        text += "لا يوجد\n"

    else:

        for index, row in enumerate(
            rows,
            1
        ):

            user_id = row[0]
            username = row[1]
            first_name = row[2]

            if username:

                display = (
                    "@"
                    + str(username).lstrip("@")
                )

            else:

                name = (
                    first_name
                    or str(user_id)
                )

                display = (
                    f'<a href="tg://user?id={user_id}">'
                    f'{html_escape(name)}'
                    f'</a>'
                )

            text += (
                f"{index} - {display}\n"
            )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"moderation:clear:{kind}"
                )
            ]
        ]
    )

    return text, keyboard


async def moderation_lists_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 3:
        return

    text = (
        update.message.text or ""
    ).strip()

    if text == "المكتومين":
        kind = "mute"

    elif text == "المقيدين":
        kind = "restrict"

    elif text == "المحظورين":
        kind = "ban"

    else:
        return

    rows = await asyncio.to_thread(
        get_list_rows,
        chat_id,
        LIST_TABLES[kind][0]
    )

    message_text, keyboard = list_message(
        kind,
        rows
    )

    await update.message.reply_text(
        message_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ==================================================
# مسح قائمة كاملة
# ==================================================

async def clear_list_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    actor = query.from_user

    chat_id = (
        query.message.chat.id
        if query.message
        else None
    )

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 3:

        await query.answer(
            "هذا الأمر للأدمن الأساسي وفوق فقط!",
            show_alert=True
        )

        return

    await query.answer()

    data = query.data or ""

    parts = data.split(":")

    if len(parts) != 3:
        return

    kind = parts[2]

    if kind not in LIST_TABLES:
        return

    if not query.message:
        return

    chat_id = query.message.chat.id

    table = LIST_TABLES[kind][0]

    rows = await asyncio.to_thread(
        get_list_rows,
        chat_id,
        table
    )

    for row in rows:

        user_id = row[0]

        if kind == "restrict":

            try:

                from telegram import ChatPermissions

                permissions = ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_invite_users=True,
                    can_manage_topics=True,
                )

                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=permissions
                )

            except Exception:
                pass

        elif kind == "ban":

            try:

                await context.bot.unban_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    only_if_banned=False
                )

            except Exception:
                pass

    await asyncio.to_thread(
        _clear_list_table,
        table,
        chat_id
    )

    if kind == "mute":

        for row in rows:

            _mute_cache[
                (chat_id, row[0])
            ] = False

    title = LIST_TABLES[kind][2]

    await query.edit_message_text(
        f"• تم {title} ."
    )


def _clear_list_table(
    table,
    chat_id
):

    allowed = {
        "bot_mutes",
        "restrictions",
        "moderation_bans"
    }

    if table not in allowed:
        return

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            f"""
            DELETE FROM {table}
            WHERE chat_id=?
            """,
            (chat_id,)
        )

        conn.commit()

    finally:

        if cur:
            cur.close()

        conn.close()


# ==================================================
# تفعيل المدة
# ==================================================

async def enable_durations_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    await asyncio.to_thread(
        set_duration_setting,
        chat_id,
        True
    )

    await update.message.reply_text(
        "• تم تفعيل المدة للمشرفين ."
    )


# ==================================================
# تعطيل المدة
# ==================================================

async def disable_durations_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    await asyncio.to_thread(
        set_duration_setting,
        chat_id,
        False
    )

    await update.message.reply_text(
        "• تم تعطيل المدة للمشرفين ."
    )


# ==================================================
# تفعيل الأسباب
# ==================================================

async def enable_reasons_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    await asyncio.to_thread(
        set_reason_setting,
        chat_id,
        True
    )

    await update.message.reply_text(
        "• تم تفعيل الاسباب ."
    )


# ==================================================
# تعطيل الأسباب
# ==================================================

async def disable_reasons_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat_id = update.effective_chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    await asyncio.to_thread(
        set_reason_setting,
        chat_id,
        False
    )

    await update.message.reply_text(
        "• تم تعطيل الاسباب ."
    )


# ==================================================
# إلغاء المدة تلقائيًا
# ==================================================

async def moderation_expiry_loop(
    application
):

    while True:

        try:

            current = now_timestamp()

            current_iso = timestamp_to_iso(
                current
            )

            expired = await asyncio.to_thread(
                _get_expired_moderations,
                current_iso
            )

            mute_rows = expired["mutes"]
            restriction_rows = expired["restrictions"]
            ban_rows = expired["bans"]

            for chat_id, user_id in mute_rows:

                _mute_cache[
                    (chat_id, user_id)
                ] = False

            for chat_id, user_id in restriction_rows:

                try:

                    from telegram import ChatPermissions

                    permissions = ChatPermissions(
                        can_send_messages=True,
                        can_send_audios=True,
                        can_send_documents=True,
                        can_send_photos=True,
                        can_send_videos=True,
                        can_send_video_notes=True,
                        can_send_voice_notes=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True,
                        can_manage_topics=True,
                    )

                    await application.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        permissions=permissions
                    )

                except Exception:
                    pass

                await asyncio.to_thread(
                    delete_restriction_record,
                    "restrictions",
                    chat_id,
                    user_id
                )

            for chat_id, user_id in ban_rows:

                try:

                    await application.bot.unban_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        only_if_banned=False
                    )

                except Exception:
                    pass

                await asyncio.to_thread(
                    delete_restriction_record,
                    "moderation_bans",
                    chat_id,
                    user_id
                )

        except Exception as e:

            print(
                f"⚠️ خطأ في نظام انتهاء عقوبات الإشراف: {e}"
            )

        await asyncio.sleep(5)


def _get_expired_moderations(
    current_iso
):

    conn = connect()
    cur = None

    result = {
        "mutes": [],
        "restrictions": [],
        "bans": []
    }

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT chat_id, user_id
            FROM bot_mutes
            WHERE until_time IS NOT NULL
            AND until_time <= ?
            """,
            (current_iso,)
        )

        result["mutes"] = cur.fetchall()

        cur.execute(
            """
            DELETE FROM bot_mutes
            WHERE until_time IS NOT NULL
            AND until_time <= ?
            """,
            (current_iso,)
        )

        cur.execute(
            """
            SELECT chat_id, user_id
            FROM restrictions
            WHERE until_time IS NOT NULL
            AND until_time <= ?
            """,
            (current_iso,)
        )

        result["restrictions"] = cur.fetchall()

        cur.execute(
            """
            SELECT chat_id, user_id
            FROM moderation_bans
            WHERE until_time IS NOT NULL
            AND until_time <= ?
            """,
            (current_iso,)
        )

        result["bans"] = cur.fetchall()

        conn.commit()

        return result

    finally:

        if cur:
            cur.close()

        conn.close()


# ==================================================
# الإنذارات - النظام الموحد
# ==================================================

def get_warning_count(
    chat_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM warnings
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        row = cur.fetchone()

        return int(row[0]) if row else 0

    finally:

        if cur:
            cur.close()

        conn.close()


def add_warning(
    chat_id,
    user_id,
    source="manual"
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO warnings
            (
                chat_id,
                user_id,
                source
            )
            VALUES (?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                source
            )
        )

        conn.commit()

    finally:

        if cur:
            cur.close()

        conn.close()


def clear_warnings(
    chat_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM warnings
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        conn.commit()

    finally:

        if cur:
            cur.close()

        conn.close()


# ==================================================
# استخراج هدف للإنذار
# ==================================================

async def _resolve_warning_target(
    update,
    context
):

    return await resolve_target(
        update,
        context
    )


# ==================================================
# الإنذار
# ==================================================

async def warning_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    target = await _resolve_warning_target(
        update,
        context
    )

    if not target:
        return

    if target.id == actor.id:
        return

    if target.id == context.bot.id:
        return

    target_level = await asyncio.to_thread(
        _get_level,
        target.id,
        chat_id
    )

    # ==================================================
    # لا يمكن إنذار مساوي أو أعلى
    # ==================================================

    if target_level >= actor_level:

        await update.message.reply_text(
            "• اعذرني بس هذا الأمر لـ ↤︎〖 "
            "الرتبة الأعلى منك "
            "〗 فقط ."
        )

        return

    await asyncio.to_thread(
        save_target_user,
        target
    )

    await asyncio.to_thread(
        add_warning,
        chat_id,
        target.id,
        "manual"
    )

    count = await asyncio.to_thread(
        get_warning_count,
        chat_id,
        target.id
    )

    mention = mention_user(target)

    # ==================================================
    # الإنذار الثالث
    # ==================================================

    if count >= 3:

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "تقييد",
                        callback_data=(
                            f"repetition_punish:"
                            f"restrict:"
                            f"{target.id}"
                        )
                    ),
                    InlineKeyboardButton(
                        "كتم",
                        callback_data=(
                            f"repetition_punish:"
                            f"mute:"
                            f"{target.id}"
                        )
                    )
                ]
            ]
        )

        await update.message.reply_text(
            f"• المستخدم ↤︎ {mention}\n"
            f"• وصلت إنذاراته : {count}\n"
            "اختر العقوبة المناسبة له:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        return

    # ==================================================
    # الإنذارات الأولى والثانية
    # ==================================================

    await update.message.reply_text(
        "• تمام عطيته انذار .\n"
        f"• المستخدم ↤︎ {mention}\n"
        f"• عدد إنذاراته : {count}",
        parse_mode="HTML"
    )


# ==================================================
# مسح الإنذارات
# ==================================================

async def clear_warnings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    actor_level = await asyncio.to_thread(
        _get_level,
        actor.id,
        chat_id
    )

    if actor_level < 2:
        return

    target = await resolve_target(
        update,
        context
    )

    if not target:
        return

    target_level = await asyncio.to_thread(
        _get_level,
        target.id,
        chat_id
    )

    if target_level >= actor_level:
        return

    await asyncio.to_thread(
        clear_warnings,
        chat_id,
        target.id
    )

    await update.message.reply_text(
        "• تم مسح جميع إنذاراته .\n"
        f"• المستخدم ↤︎ {mention_user(target)}",
        parse_mode="HTML"
    )


# ==================================================
# كشف القيود
# ==================================================

async def reveal_restrictions_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    target = await resolve_target(
        update,
        context
    )

    if not target:
        return

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    restrictions = await asyncio.to_thread(
        get_user_restrictions,
        chat_id,
        target.id
    )

    warning_count = await asyncio.to_thread(
        get_warning_count,
        chat_id,
        target.id
    )

    text = (
        "• معلومات الكشف \n"
        "━━━━━━━━━━━━\n"
        f"• الحظر : "
        f"{'محظور' if 'حظر' in restrictions else 'غير محظور'}\n"
        f"• الكتم : "
        f"{'مكتوم' if 'كتم' in restrictions else 'غير مكتوم'}\n"
        f"• التقييد : "
        f"{'مقيد' if 'تقييد' in restrictions else 'غير مقيد'}\n"
        f"• الانذارات : {warning_count}"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ==================================================
# كشف
# ==================================================

async def reveal_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    target = await resolve_target(
        update,
        context
    )

    if not target:
        return

    user_id = target.id

    username = getattr(
        target,
        "username",
        None
    )

    if username:

        use = (
            "@"
            + username.lstrip("@")
        )

    else:

        use = ""

    chat_id = (
        update.effective_chat.id
        if update.effective_chat
        else None
    )

    rank = await asyncio.to_thread(
        get_rank,
        user_id,
        chat_id
    )

    messages = await asyncio.to_thread(
        _get_user_messages,
        user_id
    )

    if user_id == 8453977662:
        ste_text = (
            f"<tg-spoiler>"
            f"{html_escape(rank)}"
            f"</tg-spoiler>"
        )
    else:
        ste_text = html_escape(rank)

    text = (
        f"• ID : <code>{user_id}</code>\n"
        f"• USE : {html_escape(use)}\n"
        f"• STE : {ste_text}\n"
        f"• MSG : {messages}"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


def _get_user_messages(
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT messages
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        return row[0] if row else 0

    finally:

        if cur:
            cur.close()

        conn.close()


# ==================================================
# توافق مع repetition.py
# ==================================================

def cleanup_all_expired_warnings():
    """
    الإنذارات الجديدة دائمة ولا تنتهي.
    الدالة موجودة فقط للتوافق مع أي استدعاء قديم.
    """
    return 0


def set_warning_duration(*args, **kwargs):
    """
    لم تعد الإنذارات لها مدة.
    موجودة فقط للتوافق مع الكود القديم.
    """
    return None
