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
# جلسات إعداد التكرار
#
# المفتاح:
# (chat_id, user_id)
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
# كاش إعدادات التكرار
#
# chat_id -> settings
# ==================================================

_repetition_settings_cache = {}

_repetition_settings_cache_lock = None


def _get_settings_cache_lock():
    global _repetition_settings_cache_lock

    if _repetition_settings_cache_lock is None:
        _repetition_settings_cache_lock = asyncio.Lock()

    return _repetition_settings_cache_lock


def _invalidate_repetition_settings_cache(chat_id):
    _repetition_settings_cache.pop(
        chat_id,
        None
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
        #
        # IF NOT EXISTS حتى لا يحصل rollback كل مرة
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

            cur.execute(
                f"""
                ALTER TABLE protection_settings
                ADD COLUMN IF NOT EXISTS {column} {definition}
                """
            )

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

        # --------------------------------------------------
        # فهرس المستخدم
        # --------------------------------------------------

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

        # --------------------------------------------------
        # فهرس انتهاء التحذيرات
        # --------------------------------------------------

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

    except Exception as e:

        try:
            conn.rollback()
        except Exception:
            pass

        print(
            "❌ خطأ في إنشاء جداول التكرار:",
            e
        )

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

    # --------------------------------------------------
    # استخدم الكاش إذا موجود
    # --------------------------------------------------

    cached = _repetition_settings_cache.get(
        chat_id
    )

    if cached is not None:
        return cached.copy()

    # --------------------------------------------------
    # تأكد من وجود إعدادات المجموعة
    # --------------------------------------------------

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

        settings = {
            "enabled": False,
            "limit": DEFAULT_LIMIT,
            "seconds": DEFAULT_SECONDS,
            "action": "mute",
            "warning_duration": DEFAULT_WARNING_DURATION,
            "punishment_duration": DEFAULT_PUNISHMENT_DURATION,
            "rank": "عضو",
        }

    else:

        settings = {
            "enabled": bool(row[0]),
            "limit": max(
                1,
                int(
                    row[1]
                    or DEFAULT_LIMIT
                )
            ),
            "seconds": max(
                1,
                int(
                    row[2]
                    or DEFAULT_SECONDS
                )
            ),
            "action": (
                row[3]
                if row[3] in (
                    "mute",
                    "restrict",
                    "ban",
                )
                else "mute"
            ),
            "warning_duration": max(
                1,
                int(
                    row[4]
                    or DEFAULT_WARNING_DURATION
                )
            ),
            "punishment_duration": max(
                1,
                int(
                    row[5]
                    or DEFAULT_PUNISHMENT_DURATION
                )
            ),
            "rank": (
                row[6]
                if row[6] in RANK_LEVELS
                else "عضو"
            ),
        }

    # --------------------------------------------------
    # حفظ في الكاش
    # --------------------------------------------------

    _repetition_settings_cache[
        chat_id
    ] = settings.copy()

    return settings


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
                chat_id,
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

    # --------------------------------------------------
    # تحديث الكاش مباشرة
    # --------------------------------------------------

    _invalidate_repetition_settings_cache(
        chat_id
    )


# ==================================================
# تحويل المدة
#
# أمثلة:
#
# 3ث
# 5د
# 1س
# 2ي
#
# وكذلك:
#
# 3ثانية
# 5دقيقة
# 1ساعة
# 2يوم
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

    try:

        number = float(
            match.group(1)
        )

    except Exception:

        return None

    if number < 1:
        return None

    unit = match.group(2)

    # --------------------------------------------------
    # ثواني
    # --------------------------------------------------

    if unit in (
        "ث",
        "ثانية",
        "ثواني",
    ):

        multiplier = 1

    # --------------------------------------------------
    # دقائق
    # --------------------------------------------------

    elif unit in (
        "د",
        "دقيقة",
        "دقائق",
    ):

        multiplier = 60

    # --------------------------------------------------
    # ساعات
    # --------------------------------------------------

    elif unit in (
        "س",
        "ساعة",
        "ساعات",
    ):

        multiplier = 3600

    # --------------------------------------------------
    # أيام
    # --------------------------------------------------

    else:

        multiplier = 86400

    seconds = int(
        number * multiplier
    )

    if seconds < 1:
        return None

    return seconds


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
#
# الرتب:
#
# عضو = 0
# مميز = 1
# ادمن = 2
# ادمن اساسي = 3
# نائب المالك = 4
# المالك = 5
# Dev = 6
#
# إذا اخترنا مثلًا:
# المالك
#
# يتم استهداف:
# عضو
# مميز
# ادمن
# ادمن اساسي
# نائب المالك
# المالك
#
# Dev يستهدف الجميع، ما عدا المطور الأساسي.
# ==================================================

def repetition_rank_allowed(
    user_id,
    chat_id,
    selected_rank
):

    # --------------------------------------------------
    # المطور الأساسي مستثنى دائمًا
    # --------------------------------------------------

    if user_id == OWNER_ID:
        return False

    if is_primary_developer(
        user_id
    ):
        return False

    # --------------------------------------------------
    # تأكد أن الرتبة المختارة صحيحة
    # --------------------------------------------------

    if selected_rank not in RANK_LEVELS:
        selected_rank = "عضو"

    # --------------------------------------------------
    # رتبة المستخدم الحالية
    # --------------------------------------------------

    try:

        level = get_rank_level(
            user_id,
            chat_id
        )

    except TypeError:

        # توافق مع أي نسخة قديمة
        level = get_rank_level(
            user_id
        )

    except Exception:

        return False

    # --------------------------------------------------
    # استهداف الرتبة المختارة وما دونها
    # --------------------------------------------------

    selected_level = RANK_LEVELS[
        selected_rank
    ]

    return (
        level <= selected_level
    )


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

    return list(messages)


# ==================================================
# جلب آخر N رسائل
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

    if not message_ids:
        return

    # --------------------------------------------------
    # حذف بالتوازي حتى لا يكون الحذف بطيئًا
    # --------------------------------------------------

    async def delete_one(message_id):

        try:

            await bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception:
            pass

    await asyncio.gather(
        *[
            delete_one(message_id)
            for message_id in message_ids
        ],
        return_exceptions=True
    )


# ==================================================
# تنظيف التحذيرات المنتهية لمستخدم
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
                user_id,
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
                expires_at,
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
                user_id,
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
# أسماء العقوبات
# ==================================================

ACTION_NAMES = {
    "mute": "كتم",
    "restrict": "تقييد",
    "ban": "حظر",
}


# ==================================================
# صلاحية إعدادات التكرار
#
# ادمن اساسي وفوق
# ==================================================

def can_manage_repetition(
    user_id,
    chat_id
):

    if user_id == OWNER_ID:
        return True

    if is_primary_developer(
        user_id
    ):
        return True

    try:

        return (
            get_rank_level(
                user_id,
                chat_id
            ) >= 3
        )

    except TypeError:

        return (
            get_rank_level(
                user_id
            ) >= 3
        )

    except Exception:

        return False


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

        # ==================================================
        # إرسال رسالة العقوبة
        # ==================================================

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

    # ==================================================
    # التحقق الأساسي
    # ==================================================

    if not message:
        return

    if not user:
        return

    if not chat:
        return

    # --------------------------------------------------
    # المجموعات فقط
    # --------------------------------------------------

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    # ==================================================
    # تجاهل رسائل الخدمة
    # ==================================================

    if (
        message.new_chat_members
        or message.left_chat_member
        or message.new_chat_title
        or message.new_chat_photo
        or message.delete_chat_photo
        or message.group_chat_created
        or message.supergroup_chat_created
        or message.channel_chat_created
        or message.migrate_to_chat_id
        or message.migrate_from_chat_id
    ):
        return

    # ==================================================
    # تجاهل أوامر /
    # ==================================================

    if (
        message.text
        and message.text.startswith("/")
    ):
        return

    if (
        message.caption
        and message.caption.startswith("/")
    ):
        return

    # ==================================================
    # جلب إعدادات التكرار
    # ==================================================

    try:

        settings = get_repetition_settings(
            chat.id
        )

    except Exception as e:

        print(
            "❌ خطأ في جلب إعدادات التكرار:",
            e
        )

        return

    # --------------------------------------------------
    # غير مفعل
    # --------------------------------------------------

    if not settings["enabled"]:
        return

    # ==================================================
    # تحديد رتبة المستخدم
    # ==================================================

    try:

        allowed = repetition_rank_allowed(
            user.id,
            chat.id,
            settings["rank"]
        )

    except Exception as e:

        print(
            "❌ خطأ في تحديد رتبة التكرار:",
            e
        )

        return

    if not allowed:
        return

    # ==================================================
    # إضافة الرسالة
    #
    # أي رسالة من المستخدم تحسب:
    #
    # نص
    # صورة
    # فيديو
    # ملصق
    # صوت
    # GIF
    # وغيرها
    # ==================================================

    try:

        messages = add_repetition_message(
            chat.id,
            user.id,
            message.message_id,
            settings["seconds"]
        )

    except Exception as e:

        print(
            "❌ خطأ في إضافة رسالة التكرار:",
            e
        )

        return

    # ==================================================
    # لم يصل للحد
    # ==================================================

    if len(messages) < settings["limit"]:
        return

    # ==================================================
    # تم اكتشاف التكرار
    # ==================================================

    print(
        f"🔁 تكرار مكتشف | "
        f"chat={chat.id} | "
        f"user={user.id} | "
        f"count={len(messages)} | "
        f"limit={settings['limit']} | "
        f"seconds={settings['seconds']}"
    )

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

    # ==================================================
    # تصفير عداد الرسائل
    # ==================================================

    reset_repetition_messages(
        chat.id,
        user.id
    )

    # ==================================================
    # جلب التحذيرات الحالية
    # ==================================================

    try:

        warning_count = get_warning_count(
            chat.id,
            user.id
        )

    except Exception as e:

        print(
            "❌ خطأ في جلب تحذيرات التكرار:",
            e
        )

        return

    # ==================================================
    # التحذير الثالث = عقوبة مباشرة
    #
    # 0 -> تحذير 1
    # 1 -> تحذير 2
    # 2 -> عقوبة مباشرة
    # ==================================================

    if warning_count >= 2:

        print(
            f"🚨 العقوبة الثالثة للتكرار | "
            f"user={user.id} | "
            f"action={settings['action']}"
        )

        punished = await punish_user(
            update,
            context,
            user,
            settings["action"],
            settings["punishment_duration"]
        )

        # --------------------------------------------------
        # بعد العقوبة يتم تصفير جميع التحذيرات
        # --------------------------------------------------

        if punished:

            clear_warnings(
                chat.id,
                user.id
            )

        return

    # ==================================================
    # إضافة تحذير
    # ==================================================

    try:

        add_warning(
            chat.id,
            user.id,
            settings["warning_duration"]
        )

    except Exception as e:

        print(
            "❌ خطأ في إضافة تحذير التكرار:",
            e
        )

        return

    new_warning_count = (
        warning_count + 1
    )

    # ==================================================
    # منشن حقيقي
    # ==================================================

    mention = (
        f'<a href="tg://user?id={user.id}">'
        f'{user.first_name or "المستخدم"}'
        f'</a>'
    )

    # ==================================================
    # إرسال التحذير
    # ==================================================

    try:

        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"⚠️ تحذير التكرار {new_warning_count}/3\n\n"
                f"المستخدم ↤︎ {mention}"
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            "❌ خطأ في إرسال تحذير التكرار:",
            e
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

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if not can_manage_repetition(
        user.id,
        chat.id
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

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if not can_manage_repetition(
        user.id,
        chat.id
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

    # --------------------------------------------------
    # لا نمسح الإعدادات
    # ولا نمسح التحذيرات
    # --------------------------------------------------

    reset_repetition_messages(
        chat.id,
        user.id
    )

    await update.message.reply_text(
        "✅ تم تعطيل حماية التكرار."
    )


# ==================================================
# بدء:
#
# ضع تكرار 5
#
# ثم يطلب المدة
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

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if not can_manage_repetition(
        user.id,
        chat.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    text = (
        update.message.text or ""
    ).strip()

    parts = text.split()

    # ==================================================
    # الصيغة:
    #
    # ضع تكرار 5
    # ==================================================

    if len(parts) >= 3:

        try:

            limit = int(
                parts[2]
            )

        except (ValueError, TypeError):

            limit = 0

        if limit < 1:

            await update.message.reply_text(
                "❌ عدد التكرار يجب أن يكون 1 أو أكثر."
            )

            return

        # --------------------------------------------------
        # حفظ الجلسة بشكل صحيح
        # --------------------------------------------------

        repetition_sessions[
            (chat.id, user.id)
        ] = {
            "type": "repetition_duration",
            "limit": limit,
        }

        await update.message.reply_text(
            "حسنًا، ارسل المدة التي تريدها ."
        )

        return

    # ==================================================
    # إذا لم يكتب العدد
    # ==================================================

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

    # --------------------------------------------------
    # الجلسة مرتبطة بالمجموعة + المستخدم
    # --------------------------------------------------

    session_key = (
        chat.id,
        user.id
    )

    session = repetition_sessions.get(
        session_key
    )

    if not session:
        return

    if session.get(
        "type"
    ) != "repetition_duration":
        return

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # إذا أرسل أمرًا آخر بدل المدة
    #
    # لا نعتبره مدة ولا نرسل خطأ من هنا.
    # ==================================================

    command_like_patterns = (
        r"^تفعيل التكرار$",
        r"^تعطيل التكرار$",
        r"^ضع تكرار(?:\s+\d+)?$",
        r"^تعيين مدة انذار\s+",
        r"^تغيير عقوبة التكرار$",
        r"^ضع كتم تكرار\s+",
        r"^ضع تقييد تكرار\s+",
        r"^ضع رتبة التكرار\s+",
        r"^تغيير رتبة التكرار\s+",
        r"^مسح انذاراته",
    )

    for pattern in command_like_patterns:

        if re.match(
            pattern,
            text,
            flags=re.IGNORECASE
        ):

            return

    # ==================================================
    # تحويل المدة
    # ==================================================

    duration = parse_duration_token(
        text
    )

    if duration is None:

        await update.message.reply_text(
            "❌ المدة غير صحيحة.\n"
            "أمثلة: 3ث - 5د - 1س - 2ي"
        )

        return

    # ==================================================
    # حفظ العدد + المدة
    # ==================================================

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

    # --------------------------------------------------
    # حذف الجلسة
    # --------------------------------------------------

    repetition_sessions.pop(
        session_key,
        None
    )

    await update.message.reply_text(
        "✅ تم حفظ إعداد التكرار.\n\n"
        f"عدد الرسائل ↤︎ {session['limit']}\n"
        f"المدة ↤︎ {format_duration(duration)}"
    )


# ==================================================
# مدة التحذير
#
# تعيين مدة انذار 1س
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

    if not can_manage_repetition(
        user.id,
        chat.id
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
# تغيير عقوبة التكرار
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

    if not can_manage_repetition(
        user.id,
        chat.id
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

    user = query.from_user

    if not user:
        return

    message = query.message

    if not message:
        return

    chat = message.chat

    if not chat:
        return

    # ==================================================
    # التحقق من الصلاحية
    # ==================================================

    if not can_manage_repetition(
        user.id,
        chat.id
    ):

        await query.answer(
            "❌ ليس لديك الصلاحية.",
            show_alert=True
        )

        return

    # ==================================================
    # قراءة العقوبة
    # ==================================================

    data = query.data or ""

    if not data.startswith(
        "repetition_action:"
    ):
        return

    action = data.split(
        ":",
        1
    )[1]

    if action not in (
        "mute",
        "restrict",
        "ban"
    ):

        return

    # ==================================================
    # حفظ العقوبة
    # ==================================================

    update_repetition_setting(
        chat.id,
        "repetition_action",
        action
    )

    # ==================================================
    # إيقاف تحميل الزر
    # ==================================================

    await query.answer()

    # ==================================================
    # تعديل نفس الرسالة
    # ==================================================

    try:

        await query.edit_message_text(
            "• تم تعيين العقوبة الجديدة بنجاح . ☑️"
        )

    except Exception as e:

        print(
            "⚠️ خطأ في تعديل رسالة عقوبة التكرار:",
            e
        )


# ==================================================
# مدة كتم التكرار
#
# ضع كتم تكرار 10د
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
#
# ضع تقييد تكرار 10د
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

    if not can_manage_repetition(
        user.id,
        chat.id
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

        if requested_action == "mute":

            example = "ضع كتم تكرار 10د"

        else:

            example = "ضع تقييد تكرار 10د"

        await update.message.reply_text(
            "❌ المدة غير صحيحة.\n"
            f"مثال: {example}"
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

    # ==================================================
    # إذا العقوبة الحالية مختلفة
    # ==================================================

    if current_action != requested_action:

        current_name = ACTION_NAMES.get(
            current_action,
            current_action
        )

        if current_action == "mute":

            correct_command = (
                "ضع كتم تكرار 10د"
            )

        elif current_action == "restrict":

            correct_command = (
                "ضع تقييد تكرار 10د"
            )

        else:

            correct_command = (
                "الحظر لا يحتاج مدة."
            )

        await update.message.reply_text(
            "❌ العقوبة الحالية هي "
            f"{current_name}.\n\n"
            f"استخدم: {correct_command}"
        )

        return

    # ==================================================
    # حفظ المدة
    # ==================================================

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
#
# يدعم:
#
# ضع رتبة التكرار عضو
# ضع رتبة التكرار مميز
# ضع رتبة التكرار ادمن
# ضع رتبة التكرار ادمن اساسي
# ضع رتبة التكرار نائب المالك
# ضع رتبة التكرار المالك
# ضع رتبة التكرار Dev
#
# وكذلك:
#
# تغيير رتبة التكرار ...
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

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if not can_manage_repetition(
        user.id,
        chat.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # استخراج الرتبة بعد:
    #
    # ضع رتبة التكرار
    # أو
    # تغيير رتبة التكرار
    # ==================================================

    match = re.match(
        r"^(?:ضع|تغيير)\s+رتبة\s+التكرار\s+(.+?)\s*$",
        text,
        flags=re.IGNORECASE
    )

    if not match:

        await update.message.reply_text(
            "❌ اختر رتبة التكرار.\n"
            "مثال:\n"
            "ضع رتبة التكرار المالك"
        )

        return

    rank = match.group(1).strip()

    # ==================================================
    # توحيد بعض الصيغ
    # ==================================================

    rank_aliases = {
        "عضو": "عضو",
        "مميز": "مميز",
        "ادمن": "ادمن",
        "أدمن": "ادمن",
        "ادمن اساسي": "ادمن اساسي",
        "أدمن اساسي": "ادمن اساسي",
        "أدمن أساسي": "ادمن اساسي",
        "ادمن أساسي": "ادمن اساسي",
        "نائب المالك": "نائب المالك",
        "المالك": "المالك",
        "Dev": "Dev",
        "dev": "Dev",
    }

    rank = rank_aliases.get(
        rank,
        rank
    )

    # ==================================================
    # التحقق
    # ==================================================

    allowed_ranks = (
        "عضو",
        "مميز",
        "ادمن",
        "ادمن اساسي",
        "نائب المالك",
        "المالك",
        "Dev",
    )

    if rank not in allowed_ranks:

        await update.message.reply_text(
            "❌ الرتب المتاحة:\n"
            "عضو\n"
            "مميز\n"
            "ادمن\n"
            "ادمن اساسي\n"
            "نائب المالك\n"
            "المالك\n"
            "Dev"
        )

        return

    # ==================================================
    # الحفظ
    # ==================================================

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
#
# بالرد:
# مسح انذاراته
#
# أو:
# مسح انذاراته 123456789
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

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if not can_manage_repetition(
        actor.id,
        chat.id
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن الاساسي وفوق فقط."
        )

        return

    target = None

    # ==================================================
    # بالرد على الشخص
    # ==================================================

    if update.message.reply_to_message:

        target = (
            update.message.reply_to_message.from_user
        )

    # ==================================================
    # بالآيدي
    # ==================================================

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

    # ==================================================
    # لم يتم العثور على المستخدم
    # ==================================================

    if not target:

        await update.message.reply_text(
            "❌ استخدم الأمر بالرد على الشخص أو بالآيدي."
        )

        return

    # ==================================================
    # مسح التحذيرات
    # ==================================================

    deleted = clear_warnings(
        chat.id,
        target.id
    )

    # ==================================================
    # تصفير عداد التكرار أيضًا
    # ==================================================

    reset_repetition_messages(
        chat.id,
        target.id
    )

    # ==================================================
    # النتيجة
    # ==================================================

    if deleted:

        await update.message.reply_text(
            "☑️ تم مسح جميع انذاراته."
        )

    else:

        await update.message.reply_text(
            "• الشخص هذا ماعنده انذارات من قبل."
        )


# ==================================================
# تنظيف جلسات الإعداد القديمة
#
# إذا فتح شخص:
# ضع تكرار 5
#
# ولم يرسل المدة لفترة طويلة، نحذف الجلسة.
# ==================================================

async def cleanup_repetition_sessions():

    while True:

        try:

            now = datetime.now(
                timezone.utc
            )

            expired_keys = []

            for key, session in list(
                repetition_sessions.items()
            ):

                created_at = session.get(
                    "created_at"
                )

                if not created_at:
                    continue

                if (
                    now - created_at
                ).total_seconds() > 300:

                    expired_keys.append(
                        key
                    )

            for key in expired_keys:

                repetition_sessions.pop(
                    key,
                    None
                )

        except Exception as e:

            print(
                "⚠️ خطأ في تنظيف جلسات التكرار:",
                e
            )

        await asyncio.sleep(
            60
        )


# ==================================================
# تنظيف التحذيرات المنتهية دوريًا
# ==================================================

async def repetition_expiry_loop(
    application
):

    # --------------------------------------------------
    # تشغيل تنظيف الجلسات في الخلفية
    # --------------------------------------------------

    try:

        application.create_task(
            cleanup_repetition_sessions()
        )

    except Exception as e:

        print(
            "⚠️ تعذر تشغيل تنظيف جلسات التكرار:",
            e
        )

    # ==================================================
    # الحلقة الرئيسية
    # ==================================================

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
