import asyncio
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import ContextTypes

from database import connect

from handlers.roles import (
    OWNER_ID,
    get_rank_level,
    is_primary_developer,
    RANK_LEVELS,
)


# ==================================================
# الإعدادات
# ==================================================

DEFAULT_LIMIT = 3
DEFAULT_SECONDS = 5

DEFAULT_WARNING_DURATION = 3600
DEFAULT_PUNISHMENT_DURATION = 300

MAX_MESSAGES_MEMORY = 50


# ==================================================
# جلسات الإعداد
# ==================================================

repetition_sessions = {}


# ==================================================
# كاش الرسائل
#
# chat_id -> user_id -> deque
#
# نحفظ:
# (message_id, timestamp)
# ==================================================

_repetition_messages = defaultdict(
    lambda: defaultdict(
        lambda: deque(
            maxlen=MAX_MESSAGES_MEMORY
        )
    )
)


# ==================================================
# إنشاء جداول التكرار
# ==================================================

def create_repetition_tables():

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        # --------------------------------------------------
        # إضافة إعدادات التكرار إلى جدول الحماية الموجود
        # --------------------------------------------------

        columns = {
            "repetition_warning_duration": (
                "INTEGER DEFAULT 3600"
            ),
            "repetition_punishment_duration": (
                "INTEGER DEFAULT 300"
            ),
            "repetition_rank": (
                "TEXT DEFAULT 'عضو'"
            ),
        }

        for column, definition in columns.items():

            try:

                cur.execute(
                    f"""
                    ALTER TABLE protection_settings
                    ADD COLUMN {column} {definition}
                    """
                )

            except Exception:

                # العمود موجود مسبقًا
                try:
                    conn.rollback()
                except Exception:
                    pass

        # --------------------------------------------------
        # تحذيرات التكرار
        #
        # كل تحذير له وقت انتهاء مستقل.
        # --------------------------------------------------

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repetition_warnings
            (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                warning_id SERIAL PRIMARY KEY,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_repetition_warnings_user
            ON repetition_warnings
            (
                chat_id,
                user_id
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_repetition_warnings_expiry
            ON repetition_warnings
            (
                expires_at
            )
            """
        )

        conn.commit()

    except Exception:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# إنشاء إعدادات المجموعة إذا لم تكن موجودة
# ==================================================

def ensure_repetition_settings(chat_id):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO protection_settings
            (
                chat_id,
                repetition_enabled,
                repetition_limit,
                repetition_seconds,
                repetition_action,
                repetition_warning_duration,
                repetition_punishment_duration,
                repetition_rank
            )
            VALUES (?, 0, ?, ?, 'mute', ?, ?, 'عضو')

            ON CONFLICT(chat_id)
            DO NOTHING
            """,
            (
                chat_id,
                DEFAULT_LIMIT,
                DEFAULT_SECONDS,
                DEFAULT_WARNING_DURATION,
                DEFAULT_PUNISHMENT_DURATION,
            )
        )

        conn.commit()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# جلب إعدادات التكرار
# ==================================================

def get_repetition_settings(chat_id):

    ensure_repetition_settings(
        chat_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                repetition_enabled,
                repetition_limit,
                repetition_seconds,
                repetition_action,
                repetition_warning_duration,
                repetition_punishment_duration,
                repetition_rank
            FROM protection_settings
            WHERE chat_id=?
            """,
            (
                chat_id,
            )
        )

        row = cur.fetchone()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    if not row:

        return {
            "enabled": False,
            "limit": DEFAULT_LIMIT,
            "seconds": DEFAULT_SECONDS,
            "action": "mute",
            "warning_duration": DEFAULT_WARNING_DURATION,
            "punishment_duration": DEFAULT_PUNISHMENT_DURATION,
            "rank": "عضو",
        }

    return {
        "enabled": bool(row[0]),
        "limit": int(row[1] or DEFAULT_LIMIT),
        "seconds": int(row[2] or DEFAULT_SECONDS),
        "action": row[3] or "mute",
        "warning_duration": int(
            row[4] or DEFAULT_WARNING_DURATION
        ),
        "punishment_duration": int(
            row[5] or DEFAULT_PUNISHMENT_DURATION
        ),
        "rank": row[6] or "عضو",
    }


# ==================================================
# تحديث إعداد
# ==================================================

def update_repetition_setting(
    chat_id,
    column,
    value
):

    allowed_columns = {
        "repetition_enabled",
        "repetition_limit",
        "repetition_seconds",
        "repetition_action",
        "repetition_warning_duration",
        "repetition_punishment_duration",
        "repetition_rank",
    }

    if column not in allowed_columns:
        raise ValueError(
            "Invalid repetition setting"
        )

    ensure_repetition_settings(
        chat_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            f"""
            UPDATE protection_settings
            SET {column}=?
            WHERE chat_id=?
            """,
            (
                value,
                chat_id
            )
        )

        conn.commit()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# تحويل المدة
#
# 3ث
# 5د
# 1س
# 2ي
# ==================================================

DURATION_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*"
    r"(ث|ثانية|ثواني|د|دقيقة|دقائق|س|ساعة|ساعات|ي|يوم|أيام)"
    r"\s*$"
)


def parse_duration_token(token):

    if not token:
        return None

    match = DURATION_PATTERN.match(
        str(token)
    )

    if not match:
        return None

    number = float(
        match.group(1)
    )

    if number < 1:
        return None

    unit = match.group(2)

    if unit in (
        "ث",
        "ثانية",
        "ثواني",
    ):

        multiplier = 1

    elif unit in (
        "د",
        "دقيقة",
        "دقائق",
    ):

        multiplier = 60

    elif unit in (
        "س",
        "ساعة",
        "ساعات",
    ):

        multiplier = 3600

    else:

        multiplier = 86400

    return int(
        number * multiplier
    )


# ==================================================
# تنسيق المدة
# ==================================================

def format_duration(seconds):

    seconds = int(seconds)

    if seconds % 86400 == 0:

        value = seconds // 86400

        return f"{value} يوم"

    if seconds % 3600 == 0:

        value = seconds // 3600

        return f"{value} ساعة"

    if seconds % 60 == 0:

        value = seconds // 60

        return f"{value} دقيقة"

    return f"{seconds} ثانية"


# ==================================================
# هل الرتبة مستهدفة؟
# ==================================================

def repetition_rank_allowed(
    user_id,
    chat_id,
    selected_rank
):

    # المطور الأساسي مستثنى دائمًا
    if user_id == OWNER_ID:
        return False

    if is_primary_developer(
        user_id
    ):
        return False

    level = get_rank_level(
        user_id,
        chat_id
    )

    if selected_rank == "عضو":

        return level == 0

    if selected_rank == "المالك":

        return 0 <= level <= 5

    if selected_rank == "Dev":

        return 0 <= level <= 6

    return level == 0


# ==================================================
# تنظيف الرسائل القديمة من الكاش
# ==================================================

def cleanup_user_messages(
    chat_id,
    user_id,
    seconds
):

    now = datetime.now(
        timezone.utc
    )

    messages = _repetition_messages[
        chat_id
    ][
        user_id
    ]

    while messages:

        _, created_at = messages[0]

        age = (
            now - created_at
        ).total_seconds()

        if age <= seconds:
            break

        messages.popleft()


# ==================================================
# إضافة رسالة
# ==================================================

def add_repetition_message(
    chat_id,
    user_id,
    message_id,
    seconds
):

    cleanup_user_messages(
        chat_id,
        user_id,
        seconds
    )

    messages = _repetition_messages[
        chat_id
    ][
        user_id
    ]

    now = datetime.now(
        timezone.utc
    )

    messages.append(
        (
            message_id,
            now
        )
    )

    # لا نحتاج أكثر من limit رسائل
    return list(messages)


# ==================================================
# جلب الرسائل التي سيتم حذفها
# ==================================================

def get_last_repetition_messages(
    chat_id,
    user_id,
    limit
):

    messages = _repetition_messages[
        chat_id
    ][
        user_id
    ]

    if not messages:
        return []

    return [
        message_id
        for message_id, _ in list(
            messages
        )[-limit:]
    ]


# ==================================================
# تصفير عداد المستخدم
# ==================================================

def reset_repetition_messages(
    chat_id,
    user_id
):

    try:

        _repetition_messages[
            chat_id
        ].pop(
            user_id,
            None
        )

    except Exception:
        pass


# ==================================================
# حذف رسائل التكرار
# ==================================================

async def delete_repetition_messages(
    bot,
    chat_id,
    message_ids
):

    for message_id in message_ids:

        try:

            await bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception:
            pass


# ==================================================
# تنظيف التحذيرات المنتهية
# ==================================================

def cleanup_expired_warnings(
    chat_id,
    user_id
):

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM repetition_warnings
            WHERE chat_id=?
            AND user_id=?
            AND expires_at <= ?
            """,
            (
                chat_id,
                user_id,
                now
            )
        )

        conn.commit()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# عدد التحذيرات الفعالة
# ==================================================

def get_warning_count(
    chat_id,
    user_id
):

    cleanup_expired_warnings(
        chat_id,
        user_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM repetition_warnings
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        row = cur.fetchone()

        return int(
            row[0] or 0
        )

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# إضافة تحذير
# ==================================================

def add_warning(
    chat_id,
    user_id,
    duration
):

    expires_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            seconds=duration
        )
    ).replace(
        tzinfo=None
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO repetition_warnings
            (
                chat_id,
                user_id,
                expires_at
            )
            VALUES (?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                expires_at
            )
        )

        conn.commit()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# مسح تحذيرات المستخدم
# ==================================================

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
            DELETE FROM repetition_warnings
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
        )

        deleted = cur.rowcount

        conn.commit()

        return deleted

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# مسح جميع التحذيرات المنتهية
# ==================================================

def cleanup_all_expired_warnings():

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM repetition_warnings
            WHERE expires_at <= ?
            """,
            (
                now,
            )
        )

        conn.commit()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# اسم العقوبة
# ==================================================

ACTION_NAMES = {
    "mute": "كتم",
    "restrict": "تقييد",
    "ban": "حظر",
}


# ==================================================
# تنفيذ العقوبة
# ==================================================

async def punish_user(
    update,
    context,
    user,
    action,
    duration
):

    chat = update.effective_chat

    if not chat:
        return False

    chat_id = chat.id

    mention = (
        f'<a href="tg://user?id={user.id}">'
        f'{user.first_name or "المستخدم"}'
        f'</a>'
    )

    try:

        # ==================================================
        # كتم
        # ==================================================

        if action == "mute":

            until_date = (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    seconds=duration
                )
            )

            permissions = ChatPermissions(
                can_send_messages=False
            )

            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=permissions,
                until_date=until_date
            )

            duration_text = format_duration(
                duration
            )

            text = (
                "• تم كتمك بسبب التكرار\n"
                f"العقوبة: كتم لمدة {duration_text}\n\n"
                f"المستخدم ↤︎ {mention}"
            )

        # ==================================================
        # تقييد
        # ==================================================

        elif action == "restrict":

            until_date = (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    seconds=duration
                )
            )

            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False,
            )

            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=permissions,
                until_date=until_date
            )

            duration_text = format_duration(
                duration
            )

            text = (
                "• تم تقييدك بسبب التكرار\n"
                f"العقوبة: تقييد لمدة {duration_text}\n\n"
                f"المستخدم ↤︎ {mention}"
            )

        # ==================================================
        # حظر
        # ==================================================

        elif action == "ban":

            await context.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user.id
            )

            text = (
                "• تم حظرك بسبب التكرار\n"
                "العقوبة: حظر\n\n"
                f"المستخدم ↤︎ {mention}"
            )

        else:

            return False

        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )

        return True

    except Exception as e:

        print(
            "❌ خطأ في عقوبة التكرار:",
            e
        )

        return False


# ==================================================
# معالجة التكرار
# ==================================================

async def repetition_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message:
        return

    if not user:
        return

    if not chat:
        return

    # الخاص لا يحتاج تكرار
    if chat.type == "private":
        return

    settings = get_repetition_settings(
        chat.id
    )

    if not settings["enabled"]:
        return

    # ==================================================
    # تحديد الرتبة
    # ==================================================

    if not repetition_rank_allowed(
        user.id,
        chat.id,
        settings["rank"]
    ):
        return

    # ==================================================
    # إضافة الرسالة
    # ==================================================

    messages = add_repetition_message(
        chat.id,
        user.id,
        message.message_id,
        settings["seconds"]
    )

    # ==================================================
    # لم يصل للحد
    # ==================================================

    if len(messages) < settings["limit"]:
        return

    # ==================================================
    # حذف آخر N رسائل فقط
    # ==================================================

    message_ids = get_last_repetition_messages(
        chat.id,
        user.id,
        settings["limit"]
    )

    await delete_repetition_messages(
        context.bot,
        chat.id,
        message_ids
    )

    reset_repetition_messages(
        chat.id,
        user.id
    )

    # ==================================================
    # التحذيرات الحالية
    # ==================================================

    warning_count = get_warning_count(
        chat.id,
        user.id
    )

    # ==================================================
    # التحذير الثالث = عقوبة مباشرة
    # ==================================================

    if warning_count >= 2:

        punished = await punish_user(
            update,
            context,
            user,
            settings["action"],
            settings["punishment_duration"]
        )

        if punished:

            clear_warnings(
                chat.id,
                user.id
            )

        return

    # ==================================================
    # إضافة تحذير
    # ==================================================

    add_warning(
        chat.id,
        user.id,
        settings["warning_duration"]
    )

    new_warning_count = (
        warning_count + 1
    )

    # ==================================================
    # رسالة التحذير
    # ==================================================

    mention = (
        f'<a href="tg://user?id={user.id}">'
        f'{user.first_name or "المستخدم"}'
        f'</a>'
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            f"⚠️ تحذير التكرار {new_warning_count}/3\n\n"
            f"المستخدم ↤︎ {mention}"
        ),
        parse_mode="HTML"
    )


# ==================================================
# تفعيل التكرار
# ==================================================

async def enable_repetition(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if not chat.type in (
        "group",
        "supergroup"
    ):
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    update_repetition_setting(
        chat.id,
        "repetition_enabled",
        1
    )

    await update.message.reply_text(
        "✅ تم تفعيل حماية التكرار."
    )


# ==================================================
# تعطيل التكرار
# ==================================================

async def disable_repetition(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    update_repetition_setting(
        chat.id,
        "repetition_enabled",
        0
    )

    # لا نمسح الإعدادات أو التحذيرات
    reset_repetition_messages(
        chat.id,
        user.id
    )

    await update.message.reply_text(
        "✅ تم تعطيل حماية التكرار."
    )


# ==================================================
# بدء ضع تكرار
# ==================================================

async def set_repetition_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    text = (
        update.message.text or ""
    ).strip()

    parts = text.split()

    # --------------------------------------------------
    # إذا كتب:
    # ضع تكرار 5
    # --------------------------------------------------

    if len(parts) >= 3:

        try:

            limit = int(
                parts[2]
            )

        except ValueError:

            limit = 0

        if limit < 1:

            await update.message.reply_text(
                "❌ عدد التكرار يجب أن يكون 1 أو أكثر."
            )

            return

        repetition_sessions[
            user.id
        ] = {
            "chat_id": chat.id,
            "limit": limit,
            "type": "repetition_duration",
        }

        await update.message.reply_text(
            "حسنًا، ارسل المدة التي تريدها ."
        )

        return

    await update.message.reply_text(
        "حسنًا، ارسل عدد التكرار أولًا.\n"
        "مثال:\n"
        "ضع تكرار 5"
    )


# ==================================================
# استقبال مدة التكرار
# ==================================================

async def receive_repetition_duration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    session = repetition_sessions.get(
        user.id
    )

    if not session:
        return

    if session.get("chat_id") != chat.id:
        return

    if session.get("type") != "repetition_duration":
        return

    text = (
        update.message.text or ""
    ).strip()

    duration = parse_duration_token(
        text
    )

    if duration is None:

        await update.message.reply_text(
            "❌ المدة غير صحيحة.\n"
            "أمثلة: 3ث - 5د - 1س - 2ي"
        )

        return

    update_repetition_setting(
        chat.id,
        "repetition_limit",
        session["limit"]
    )

    update_repetition_setting(
        chat.id,
        "repetition_seconds",
        duration
    )

    repetition_sessions.pop(
        user.id,
        None
    )

    await update.message.reply_text(
        "✅ تم حفظ إعداد التكرار.\n\n"
        f"عدد الرسائل ↤︎ {session['limit']}\n"
        f"المدة ↤︎ {format_duration(duration)}"
    )


# ==================================================
# مدة التحذير
# ==================================================

async def set_warning_duration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    text = (
        update.message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 4:

        await update.message.reply_text(
            "❌ مثال:\n"
            "تعيين مدة انذار 1س"
        )

        return

    duration = parse_duration_token(
        parts[-1]
    )

    if duration is None:

        await update.message.reply_text(
            "❌ المدة غير صحيحة."
        )

        return

    update_repetition_setting(
        chat.id,
        "repetition_warning_duration",
        duration
    )

    await update.message.reply_text(
        "✅ تم تعيين مدة الانذار إلى "
        f"{format_duration(duration)}."
    )


# ==================================================
# بدء تغيير العقوبة
# ==================================================

async def change_repetition_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "كتم",
                    callback_data="repetition_action:mute"
                ),
                InlineKeyboardButton(
                    "تقييد",
                    callback_data="repetition_action:restrict"
                ),
            ],
            [
                InlineKeyboardButton(
                    "حظر",
                    callback_data="repetition_action:ban"
                )
            ],
        ]
    )

    await update.message.reply_text(
        "حسنًا، ارسل العقوبة الجديدة .",
        reply_markup=keyboard
    )


# ==================================================
# Callback العقوبة
# ==================================================

async def repetition_action_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = query.from_user
    chat = query.message.chat

    if not chat:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await query.answer(
            "❌ ليس لديك الصلاحية.",
            show_alert=True
        )

        return

    action = (
        query.data.split(
            ":",
            1
        )[1]
    )

    if action not in (
        "mute",
        "restrict",
        "ban"
    ):
        return

    update_repetition_setting(
        chat.id,
        "repetition_action",
        action
    )

    await query.edit_message_text(
        "✅ تم تغيير عقوبة التكرار إلى "
        f"{ACTION_NAMES[action]}."
    )


# ==================================================
# مدة كتم التكرار
# ==================================================

async def set_mute_duration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await _set_punishment_duration(
        update,
        "mute"
    )


# ==================================================
# مدة تقييد التكرار
# ==================================================

async def set_restrict_duration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await _set_punishment_duration(
        update,
        "restrict"
    )


# ==================================================
# حفظ مدة العقوبة
# ==================================================

async def _set_punishment_duration(
    update,
    requested_action
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    text = (
        update.message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 4:

        await update.message.reply_text(
            "❌ المدة غير صحيحة."
        )

        return

    duration = parse_duration_token(
        parts[-1]
    )

    if duration is None:

        await update.message.reply_text(
            "❌ المدة غير صحيحة."
        )

        return

    settings = get_repetition_settings(
        chat.id
    )

    current_action = settings[
        "action"
    ]

    # --------------------------------------------------
    # إذا العقوبة الحالية مختلفة
    # --------------------------------------------------

    if current_action != requested_action:

        await update.message.reply_text(
            "❌ العقوبة الحالية هي "
            f"{ACTION_NAMES.get(current_action, current_action)}.\n\n"
            f"استخدم أمر مدة "
            f"{ACTION_NAMES[ current_action ]} "
            "للتكرار."
        )

        return

    update_repetition_setting(
        chat.id,
        "repetition_punishment_duration",
        duration
    )

    await update.message.reply_text(
        "✅ تم تعيين مدة العقوبة إلى "
        f"{format_duration(duration)}."
    )


# ==================================================
# رتبة التكرار
# ==================================================

async def set_repetition_rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if get_rank_level(
        user.id,
        chat.id
    ) < 3 and not is_primary_developer(
        user.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    text = (
        update.message.text or ""
    ).strip()

    parts = text.split(
        maxsplit=3
    )

    if len(parts) < 4:

        await update.message.reply_text(
            "❌ اختر رتبة التكرار.\n"
            "مثال:\n"
            "ضع رتبة التكرار المالك"
        )

        return

    rank = parts[3].strip()

    if rank not in (
        "عضو",
        "المالك",
        "Dev"
    ):

        await update.message.reply_text(
            "❌ الرتبة المتاحة:\n"
            "عضو\n"
            "المالك\n"
            "Dev"
        )

        return

    update_repetition_setting(
        chat.id,
        "repetition_rank",
        rank
    )

    await update.message.reply_text(
        f"☑️ تم تعيين رتبة التكرار إلى {rank}."
    )


# ==================================================
# مسح انذاراته
# ==================================================

async def clear_user_repetition_warnings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    actor = update.effective_user

    if not chat or not actor:
        return

    if get_rank_level(
        actor.id,
        chat.id
    ) < 3 and not is_primary_developer(
        actor.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    target = None

    if update.message.reply_to_message:

        target = (
            update.message.reply_to_message.from_user
        )

    else:

        text = (
            update.message.text or ""
        ).strip()

        parts = text.split()

        if len(parts) >= 3:

            value = parts[-1]

            if value.isdigit():

                try:

                    target = await context.bot.get_chat(
                        int(value)
                    )

                except Exception:
                    target = None

    if not target:

        await update.message.reply_text(
            "❌ استخدم الأمر بالرد على الشخص أو بالآيدي."
        )

        return

    deleted = clear_warnings(
        chat.id,
        target.id
    )

    reset_repetition_messages(
        chat.id,
        target.id
    )

    if deleted:

        await update.message.reply_text(
            "☑️ تم مسح جميع انذاراته."
        )

    else:

        await update.message.reply_text(
            "• الشخص هذا ماعنده انذارات من قبل."
        )


# ==================================================
# مسح التحذيرات المنتهية دوريًا
# ==================================================

async def repetition_expiry_loop(
    application
):

    while True:

        try:

            await asyncio.to_thread(
                cleanup_all_expired_warnings
            )

        except Exception as e:

            print(
                "⚠️ خطأ في تنظيف تحذيرات التكرار:",
                e
            )

        await asyncio.sleep(
            30
        )
