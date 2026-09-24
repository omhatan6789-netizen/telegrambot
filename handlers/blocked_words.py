import asyncio
import re

from datetime import (
    datetime,
    timezone,
    timedelta,
)

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)

from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import (
    connect,
    acquire_schema_lock,
)

from handlers.roles import get_rank_level

from handlers.moderation import (
    save_mute,
    save_restriction,
    save_ban,
    delete_restriction_record,
    mention_user,
    html_escape,
    parse_duration_token,
)


# ==================================================
# إعدادات عامة
# ==================================================

OWNER_ID = 8453977662

MIN_RANK_LEVEL = 4

# --------------------------------------------------
# الرتبة المطلوبة لإدارة الكلمات المحظورة
# نائب المالك وفوق
# --------------------------------------------------

MANAGE_MIN_RANK_LEVEL = 4

# --------------------------------------------------
# الكلمات المحظورة تؤثر بالعقوبة فقط على:
#
# عضو  = 0
# مميز = 1
#
# ادمن وفوق = حذف الرسالة فقط
# OWNER_ID = استثناء كامل
# --------------------------------------------------

BLOCKED_WORDS_MAX_AFFECTED_RANK = 1

LIST_1 = 1
LIST_2 = 2

BLOCKED_PERMISSION_MESSAGE = (
    "• هذا الأمر لـ نائب المالك وفوق فقط ."
)

RIYADH_TZ = timezone(
    timedelta(hours=3)
)


# ==================================================
# جلسات الإضافة / الحذف / إعداد العقوبة
# ==================================================

_blocked_sessions = {}


# ==================================================
# 🚀 كاش الكلمات المحظورة
#
# key:
# (chat_id, list_id)
#
# value:
# list of words
#
# مهم:
# وجود key في القاموس يعني أن الكاش محمّل
# حتى لو كانت القائمة فارغة.
# ==================================================

_blocked_words_cache = {}


# ==================================================
# 🚀 كاش إعدادات الكلمات المحظورة
#
# key:
# (chat_id, list_id)
#
# value:
# dict
# ==================================================

_blocked_settings_cache = {}


# ==================================================
# 🚀 كاش Regex
#
# key:
# word
#
# value:
# compiled regex
# ==================================================

_blocked_regex_cache = {}


# ==================================================
# قفل خفيف لتحديث الكاش
# ==================================================

_blocked_cache_lock = asyncio.Lock()


# ==================================================
# الصلاحيات
# ==================================================

def get_blocked_level(
    user_id,
    chat_id
):

    try:

        return int(
            get_rank_level(
                user_id,
                chat_id
            )
        )

    except TypeError:

        try:

            return int(
                get_rank_level(
                    user_id
                )
            )

        except Exception:

            return 0

    except Exception:

        return 0


def can_manage_blocked_words(
    user_id,
    chat_id
):

    return (
        get_blocked_level(
            user_id,
            chat_id
        ) >= MANAGE_MIN_RANK_LEVEL
    )


def can_be_affected_by_blocked_words(
    user_id,
    chat_id
):

    """
    الكلمات المحظورة تؤثر بالعقوبة فقط على:
    عضو + مميز.

    ادمن وفوق:
    حذف الرسالة فقط.
    """

    # المالك الأساسي مستثنى بالكامل
    if user_id == OWNER_ID:
        return False

    level = get_blocked_level(
        user_id,
        chat_id
    )

    return (
        level <= BLOCKED_WORDS_MAX_AFFECTED_RANK
    )


# ==================================================
# 🚀 تنظيف كاش القروب
# ==================================================

def invalidate_blocked_words_cache(
    chat_id,
    list_id=None
):

    if list_id is None:

        for current_list_id in (
            LIST_1,
            LIST_2
        ):

            _blocked_words_cache.pop(
                (
                    chat_id,
                    current_list_id
                ),
                None
            )

            _blocked_settings_cache.pop(
                (
                    chat_id,
                    current_list_id
                ),
                None
            )

        # Regex cache عالمي،
        # ولا نحتاج حذفه هنا لأن الكلمات نفسها
        # سيتم تحميلها من جديد.
        return

    _blocked_words_cache.pop(
        (
            chat_id,
            list_id
        ),
        None
    )

    _blocked_settings_cache.pop(
        (
            chat_id,
            list_id
        ),
        None
    )


# ==================================================
# قاعدة البيانات
# ==================================================

def ensure_blocked_words_tables():

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        # ==================================================
        # 🔒 قفل إنشاء الجداول الموحد
        # ==================================================

        acquire_schema_lock(conn)

        # ==================================================
        # الكلمات
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS blocked_words_v2
        (
            chat_id BIGINT NOT NULL,
            list_id INTEGER NOT NULL,
            word TEXT NOT NULL,

            PRIMARY KEY
            (
                chat_id,
                list_id,
                word
            )
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_blocked_words_v2_lookup
        ON blocked_words_v2
        (
            chat_id,
            list_id
        )
        """)

        # ==================================================
        # إعدادات القوائم
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS blocked_words_settings_v2
        (
            chat_id BIGINT NOT NULL,
            list_id INTEGER NOT NULL,

            enabled INTEGER DEFAULT 0,

            action TEXT DEFAULT 'mute',
            duration INTEGER,

            warning_duration INTEGER,
            warning_action TEXT,
            warning_punishment_duration INTEGER,

            PRIMARY KEY
            (
                chat_id,
                list_id
            )
        )
        """)

        # ==================================================
        # جدول قديم للتوافق
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS blocked_words_opened_v2
        (
            chat_id BIGINT NOT NULL,
            list_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,

            PRIMARY KEY
            (
                chat_id,
                list_id,
                user_id
            )
        )
        """)

        # ==================================================
        # إنذارات الكلمات
        # ==================================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS blocked_words_warnings_v2
        (
            chat_id BIGINT NOT NULL,
            list_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,

            warning_id BIGINT
            GENERATED BY DEFAULT AS IDENTITY
            PRIMARY KEY,

            expires_at BIGINT NOT NULL,
            created_at BIGINT NOT NULL
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_blocked_words_warnings_lookup
        ON blocked_words_warnings_v2
        (
            chat_id,
            list_id,
            user_id
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_blocked_words_warnings_expiry
        ON blocked_words_warnings_v2
        (
            expires_at
        )
        """)

        # ==================================================
        # إنشاء إعدادات القائمة الأولى
        # ==================================================

        cur.execute("""
        INSERT INTO blocked_words_settings_v2
        (
            chat_id,
            list_id
        )
        SELECT
            chat_id,
            1
        FROM blocked_words_settings
        ON CONFLICT
        (
            chat_id,
            list_id
        )
        DO NOTHING
        """)

        # ==================================================
        # نقل إعدادات النظام القديم
        # ==================================================

        cur.execute("""
        UPDATE blocked_words_settings_v2 AS new
        SET
            enabled = old.enabled,
            action = old.action
        FROM blocked_words_settings AS old
        WHERE
            new.chat_id = old.chat_id
            AND new.list_id = 1
        """)

        # ==================================================
        # نقل الكلمات القديمة
        # ==================================================

        cur.execute("""
        INSERT INTO blocked_words_v2
        (
            chat_id,
            list_id,
            word
        )
        SELECT
            chat_id,
            1,
            word
        FROM blocked_words
        ON CONFLICT
        (
            chat_id,
            list_id,
            word
        )
        DO NOTHING
        """)

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# إعدادات افتراضية
# ==================================================

def ensure_list_settings(
    chat_id,
    list_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO blocked_words_settings_v2
        (
            chat_id,
            list_id
        )
        VALUES
        (
            ?,
            ?
        )
        ON CONFLICT
        (
            chat_id,
            list_id
        )
        DO NOTHING
        """, (
            chat_id,
            list_id
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# قراءة الإعدادات من DB
# ==================================================

def get_settings(
    chat_id,
    list_id
):

    ensure_list_settings(
        chat_id,
        list_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        SELECT
            enabled,
            action,
            duration,
            warning_duration,
            warning_action,
            warning_punishment_duration
        FROM blocked_words_settings_v2
        WHERE
            chat_id=?
            AND list_id=?
        """, (
            chat_id,
            list_id
        ))

        row = cur.fetchone()

        if not row:

            return {
                "enabled": False,
                "action": "mute",
                "duration": None,
                "warning_duration": None,
                "warning_action": None,
                "warning_punishment_duration": None,
            }

        return {
            "enabled": bool(row[0]),
            "action": row[1] or "mute",
            "duration": row[2],
            "warning_duration": row[3],
            "warning_action": row[4],
            "warning_punishment_duration": row[5],
        }

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# 🚀 قراءة إعدادات الكاش
# ==================================================

def get_cached_settings_sync(
    chat_id,
    list_id
):

    key = (
        chat_id,
        list_id
    )

    if key in _blocked_settings_cache:

        return _blocked_settings_cache[key]

    settings = get_settings(
        chat_id,
        list_id
    )

    _blocked_settings_cache[key] = settings

    return settings


async def get_cached_settings(
    chat_id,
    list_id
):

    return await asyncio.to_thread(
        get_cached_settings_sync,
        chat_id,
        list_id
    )


# ==================================================
# تعديل حالة القائمة
# ==================================================

def set_enabled(
    chat_id,
    list_id,
    enabled
):

    ensure_list_settings(
        chat_id,
        list_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        UPDATE blocked_words_settings_v2
        SET enabled=?
        WHERE
            chat_id=?
            AND list_id=?
        """, (
            1 if enabled else 0,
            chat_id,
            list_id
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    key = (
        chat_id,
        list_id
    )

    cached = _blocked_settings_cache.get(
        key
    )

    if cached is not None:

        cached["enabled"] = bool(
            enabled
        )

    else:

        _blocked_settings_cache[
            key
        ] = get_settings(
            chat_id,
            list_id
        )


# ==================================================
# تعديل العقوبة المباشرة
# ==================================================

def set_direct_action(
    chat_id,
    list_id,
    action,
    duration
):

    ensure_list_settings(
        chat_id,
        list_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        UPDATE blocked_words_settings_v2
        SET
            action=?,
            duration=?
        WHERE
            chat_id=?
            AND list_id=?
        """, (
            action,
            duration,
            chat_id,
            list_id
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    key = (
        chat_id,
        list_id
    )

    cached = _blocked_settings_cache.get(
        key
    )

    if cached is not None:

        cached["action"] = action
        cached["duration"] = duration

    else:

        _blocked_settings_cache[
            key
        ] = get_settings(
            chat_id,
            list_id
        )


# ==================================================
# تعديل عقوبة الإنذار
# ==================================================

def set_warning_action(
    chat_id,
    list_id,
    warning_duration,
    warning_action,
    warning_punishment_duration
):

    ensure_list_settings(
        chat_id,
        list_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        UPDATE blocked_words_settings_v2
        SET
            action='warning',
            warning_duration=?,
            warning_action=?,
            warning_punishment_duration=?
        WHERE
            chat_id=?
            AND list_id=?
        """, (
            warning_duration,
            warning_action,
            warning_punishment_duration,
            chat_id,
            list_id
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    key = (
        chat_id,
        list_id
    )

    cached = _blocked_settings_cache.get(
        key
    )

    if cached is not None:

        cached["action"] = "warning"

        cached["warning_duration"] = (
            warning_duration
        )

        cached["warning_action"] = (
            warning_action
        )

        cached[
            "warning_punishment_duration"
        ] = warning_punishment_duration

    else:

        _blocked_settings_cache[
            key
        ] = get_settings(
            chat_id,
            list_id
        )


# ==================================================
# الكلمات
# ==================================================

def get_words(
    chat_id,
    list_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        SELECT word
        FROM blocked_words_v2
        WHERE
            chat_id=?
            AND list_id=?
        ORDER BY word
        """, (
            chat_id,
            list_id
        ))

        return [
            row[0]
            for row in cur.fetchall()
        ]

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# 🚀 تحميل الكلمات إلى الكاش
# ==================================================

def get_cached_words_sync(
    chat_id,
    list_id
):

    key = (
        chat_id,
        list_id
    )

    if key in _blocked_words_cache:

        return _blocked_words_cache[key]

    words = get_words(
        chat_id,
        list_id
    )

    _blocked_words_cache[key] = words

    return words


async def get_cached_words(
    chat_id,
    list_id
):

    return await asyncio.to_thread(
        get_cached_words_sync,
        chat_id,
        list_id
    )


# ==================================================
# إضافة كلمات
# ==================================================

def add_words(
    chat_id,
    list_id,
    words
):

    if not words:
        return

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        for word in words:

            cur.execute("""
            INSERT INTO blocked_words_v2
            (
                chat_id,
                list_id,
                word
            )
            VALUES
            (
                ?,
                ?,
                ?
            )
            ON CONFLICT
            (
                chat_id,
                list_id,
                word
            )
            DO NOTHING
            """, (
                chat_id,
                list_id,
                word
            ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    key = (
        chat_id,
        list_id
    )

    cached = _blocked_words_cache.get(
        key
    )

    if cached is not None:

        for word in words:

            if word not in cached:

                cached.append(
                    word
                )

        cached.sort()

        for word in words:

            _blocked_regex_cache.pop(
                word,
                None
            )


# ==================================================
# حذف كلمات
# ==================================================

def delete_words(
    chat_id,
    list_id,
    words
):

    if not words:
        return

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        for word in words:

            cur.execute("""
            DELETE FROM blocked_words_v2
            WHERE
                chat_id=?
                AND list_id=?
                AND word=?
            """, (
                chat_id,
                list_id,
                word
            ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    key = (
        chat_id,
        list_id
    )

    cached = _blocked_words_cache.get(
        key
    )

    if cached is not None:

        words_set = set(
            words
        )

        cached[:] = [
            word
            for word in cached
            if word not in words_set
        ]

    for word in words:

        _blocked_regex_cache.pop(
            word,
            None
        )


# ==================================================
# توافق مع النظام القديم
# ==================================================

def was_opened_before(
    chat_id,
    list_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        SELECT 1
        FROM blocked_words_opened_v2
        WHERE
            chat_id=?
            AND list_id=?
            AND user_id=?
        LIMIT 1
        """, (
            chat_id,
            list_id,
            user_id
        ))

        return bool(
            cur.fetchone()
        )

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


def mark_opened(
    chat_id,
    list_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO blocked_words_opened_v2
        (
            chat_id,
            list_id,
            user_id
        )
        VALUES
        (
            ?,
            ?,
            ?
        )
        ON CONFLICT
        (
            chat_id,
            list_id,
            user_id
        )
        DO NOTHING
        """, (
            chat_id,
            list_id,
            user_id
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# تنظيف الكلمة
# ==================================================

def normalize_word(
    word
):

    word = (
        word
        .replace("\r", " ")
        .replace("\n", " ")
    )

    word = re.sub(
        r"\s+",
        " ",
        word
    )

    return word.strip()


def extract_input_words(
    text
):

    if not text:
        return []

    result = []

    for line in text.splitlines():

        word = normalize_word(
            line
        )

        if not word:
            continue

        if word not in result:

            result.append(
                word
            )

    return result


# ==================================================
# Regex للكلمات
# ==================================================

def get_blocked_regex(
    word
):

    cached = _blocked_regex_cache.get(
        word
    )

    if cached is not None:

        return cached

    normalized = normalize_word(
        word
    )

    if not normalized:
        return None

    escaped = re.escape(
        normalized
    )

    pattern = re.compile(
        rf"(?<!\w)"
        rf"{escaped}"
        rf"(?!\w)",
        flags=re.UNICODE
    )

    _blocked_regex_cache[
        word
    ] = pattern

    return pattern


def word_matches(
    text,
    word
):

    if not text or not word:
        return False

    regex = get_blocked_regex(
        word
    )

    if regex is None:
        return False

    return bool(
        regex.search(text)
    )


def find_blocked_word(
    text,
    words
):

    for word in words:

        if word_matches(
            text,
            word
        ):

            return word

    return None


# ==================================================
# الوقت
# ==================================================

def current_timestamp():

    return int(
        datetime.now(
            timezone.utc
        ).timestamp()
    )


def format_until(
    timestamp
):

    if timestamp is None:

        return "لا توجد مدة"

    dt = datetime.fromtimestamp(
        timestamp,
        RIYADH_TZ
    )

    return dt.strftime(
        "%Y/%m/%d - %H:%M:%S"
    )


# ==================================================
# رسائل العقوبات
# ==================================================

def punishment_keyboard(
    action,
    chat_id,
    user_id
):

    action_ar = {
        "mute": "رفع الكتم ☑️",
        "restrict": "رفع القيود ☑️",
        "ban": "رفع الحظر ☑️",
    }

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    action_ar[action],
                    callback_data=(
                        f"bw:lift:"
                        f"{action}:"
                        f"{chat_id}:"
                        f"{user_id}"
                    )
                )
            ]
        ]
    )


def punishment_message(
    action,
    target,
    until_timestamp
):

    mention = mention_user(
        target
    )

    if action == "mute":

        return (
            f"🔐 تَمَّ كتم {mention} "
            f"[{target.id}].\n"
            f"⏰ لمدة حتى: "
            f"{format_until(until_timestamp)}"
        )

    if action == "restrict":

        return (
            f"🔐 قُيِّدَ {mention} "
            f"[{target.id}].\n"
            f"⏰ لمدة حتى: "
            f"{format_until(until_timestamp)}"
        )

    return (
        f"🔐 تَمَّ حظر {mention} "
        f"[{target.id}].\n"
        f"⏰ لمدة حتى: "
        f"{format_until(until_timestamp)}"
    )


# ==================================================
# تنفيذ العقوبة
# ==================================================

async def apply_punishment(
    update,
    context,
    chat_id,
    target,
    action,
    duration
):

    until_timestamp = None

    if duration is not None:

        until_timestamp = (
            current_timestamp()
            + int(duration)
        )

    until_time = None

    if until_timestamp is not None:

        until_time = (
            datetime.fromtimestamp(
                until_timestamp,
                timezone.utc
            ).isoformat()
        )

    # ==================================================
    # الكتم
    # ==================================================

    if action == "mute":

        await asyncio.to_thread(
            save_mute,
            chat_id,
            target,
            until_time,
            None,
            context.bot.id
        )

    # ==================================================
    # التقييد
    # ==================================================

    elif action == "restrict":

        try:

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

        except Exception as e:

            print(
                f"⚠️ فشل تقييد مستخدم بسبب كلمة محظورة: {e}"
            )

            return False

        await asyncio.to_thread(
            save_restriction,
            chat_id,
            target,
            until_time,
            None,
            context.bot.id
        )

    # ==================================================
    # الحظر
    # ==================================================

    elif action == "ban":

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

        except Exception as e:

            print(
                f"⚠️ فشل حظر مستخدم بسبب كلمة محظورة: {e}"
            )

            return False

        await asyncio.to_thread(
            save_ban,
            chat_id,
            target,
            until_time,
            None,
            context.bot.id
        )

    else:

        return False

    # ==================================================
    # إرسال رسالة العقوبة
    #
    # نستخدم bot.send_message بدل
    # update.message.reply_text
    #
    # لأن الرسالة الأصلية قد تكون حُذفت.
    # ==================================================

    try:

        await context.bot.send_message(
            chat_id=chat_id,
            text=punishment_message(
                action,
                target,
                until_timestamp
            ),
            parse_mode="HTML",
            reply_markup=punishment_keyboard(
                action,
                chat_id,
                target.id
            )
        )

    except Exception as e:

        print(
            f"⚠️ فشل إرسال رسالة عقوبة الكلمات المحظورة: {e}"
        )

    return True


# ==================================================
# إنذارات الكلمات
# ==================================================

def cleanup_user_warnings(
    chat_id,
    list_id,
    user_id
):

    now = current_timestamp()

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        DELETE FROM blocked_words_warnings_v2
        WHERE
            chat_id=?
            AND list_id=?
            AND user_id=?
            AND expires_at<=?
        """, (
            chat_id,
            list_id,
            user_id,
            now
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


def get_active_warning_count(
    chat_id,
    list_id,
    user_id
):

    cleanup_user_warnings(
        chat_id,
        list_id,
        user_id
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        SELECT COUNT(*)
        FROM blocked_words_warnings_v2
        WHERE
            chat_id=?
            AND list_id=?
            AND user_id=?
        """, (
            chat_id,
            list_id,
            user_id
        ))

        row = cur.fetchone()

        return int(
            row[0]
        ) if row else 0

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


def add_blocked_warning(
    chat_id,
    list_id,
    user_id,
    duration
):

    now = current_timestamp()

    expires_at = (
        now + int(duration)
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO blocked_words_warnings_v2
        (
            chat_id,
            list_id,
            user_id,
            expires_at,
            created_at
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """, (
            chat_id,
            list_id,
            user_id,
            expires_at,
            now
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


def clear_blocked_warnings(
    chat_id,
    list_id,
    user_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        DELETE FROM blocked_words_warnings_v2
        WHERE
            chat_id=?
            AND list_id=?
            AND user_id=?
        """, (
            chat_id,
            list_id,
            user_id
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# رسالة الإنذار
# ==================================================

async def send_blocked_warning(
    update,
    context,
    target,
    count
):

    try:

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "• كتب كلمة محظورة وجاه انذار .\n"
                f"• المستخدم ↤︎ {mention_user(target)}\n"
                f"• عدد إنذاراته ↤︎ {count}"
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            f"⚠️ فشل إرسال إنذار الكلمات المحظورة: {e}"
        )


# ==================================================
# تطبيق نظام الإنذار
# ==================================================

async def handle_warning_punishment(
    update,
    context,
    chat_id,
    list_id,
    target,
    settings
):

    warning_duration = (
        settings["warning_duration"]
    )

    warning_action = (
        settings["warning_action"]
    )

    punishment_duration = (
        settings["warning_punishment_duration"]
    )

    if not warning_duration:
        return

    if not warning_action:
        return

    await asyncio.to_thread(
        add_blocked_warning,
        chat_id,
        list_id,
        target.id,
        warning_duration
    )

    count = await asyncio.to_thread(
        get_active_warning_count,
        chat_id,
        list_id,
        target.id
    )

    if count < 3:

        await send_blocked_warning(
            update,
            context,
            target,
            count
        )

        return

    await asyncio.to_thread(
        clear_blocked_warnings,
        chat_id,
        list_id,
        target.id
    )

    await apply_punishment(
        update,
        context,
        chat_id,
        target,
        warning_action,
        punishment_duration
    )


# ==================================================
# عرض القائمة
# ==================================================

def list_title(
    list_id
):

    if list_id == LIST_1:

        return "قائمة الكلمات المحظورة"

    return "قائمة الكلمات المحظورة2"


def list_command_name(
    list_id
):

    if list_id == LIST_1:

        return "الكلمات المحظورة"

    return "الكلمات المحظورة2"


def build_list_message_sync(
    chat_id,
    list_id
):

    words = get_cached_words_sync(
        chat_id,
        list_id
    )

    settings = get_cached_settings_sync(
        chat_id,
        list_id
    )

    title = list_title(
        list_id
    )

    if not words:

        text = (
            "لا توجد كلمات محظورة حاليًا ."
        )

    else:

        lines = [
            f"🚫 {title}:",
            ""
        ]

        for index, word in enumerate(
            words,
            1
        ):

            lines.append(
                f"{index} - {html_escape(word)}"
            )

        text = "\n".join(
            lines
        )

    status_text = (
        "الحالة: مفعلة 🟢"
        if settings["enabled"]
        else
        "الحالة: معطلة 🔴"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "اضافة كلمات ➕",
                    callback_data=(
                        f"bw:add:"
                        f"{list_id}:"
                        f"{chat_id}"
                    )
                ),
                InlineKeyboardButton(
                    "حذف كلمات 🗑️",
                    callback_data=(
                        f"bw:delete:"
                        f"{list_id}:"
                        f"{chat_id}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    status_text,
                    callback_data=(
                        f"bw:toggle:"
                        f"{list_id}:"
                        f"{chat_id}"
                    )
                )
            ]
        ]
    )

    return text, keyboard


async def build_list_message(
    chat_id,
    list_id
):

    return await asyncio.to_thread(
        build_list_message_sync,
        chat_id,
        list_id
    )


# ==================================================
# رسالة الترحيب
# ==================================================

def welcome_keyboard(
    chat_id,
    list_id
):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "هنا 👆🏻",
                    callback_data=(
                        f"bw:here:"
                        f"{list_id}:"
                        f"{chat_id}"
                    )
                ),
                InlineKeyboardButton(
                    "فتح القائمة بالخاص❕",
                    callback_data=(
                        f"bw:private:"
                        f"{list_id}:"
                        f"{chat_id}"
                    )
                )
            ]
        ]
    )


# ==================================================
# أمر القائمة
# ==================================================

async def blocked_words_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # تحديد القائمة
    # ==================================================

    list_aliases = {
        "الكلمات المحظورة": 1,
        "الكلمات المحظورة/ه": 1,
        "الكلمات المحظورة2": 2,
        "الكلمات المحظورة/ه2": 2,
    }

    list_id = list_aliases.get(
        text
    )

    # ==================================================
    # التفعيل / التعطيل
    # ==================================================

    if list_id is None:

        action_match = re.fullmatch(
            r"(تفعيل|تعطيل)\s+"
            r"(الكلمات المحظورة|الكلمات المحظورة/ه|"
            r"الكلمات المحظورة2|الكلمات المحظورة/ه2)",
            text
        )

        if action_match:

            command_action = (
                action_match.group(1)
            )

            command_list = (
                action_match.group(2)
            )

            list_id = list_aliases[
                command_list
            ]

            chat = update.effective_chat

            if not chat:
                return

            allowed = await asyncio.to_thread(
                can_manage_blocked_words,
                actor.id,
                chat.id
            )

            if not allowed:

                await update.message.reply_text(
                    BLOCKED_PERMISSION_MESSAGE
                )

                raise ApplicationHandlerStop

            enabled = (
                command_action == "تفعيل"
            )

            await asyncio.to_thread(
                set_enabled,
                chat.id,
                list_id,
                enabled
            )

            if enabled:

                await update.message.reply_text(
                    "• تم تفعيل الكلمات المحظورة ✅ ."
                )

            else:

                await update.message.reply_text(
                    "• تم تعطيل الكلمات المحظورة ✅ ."
                )

            raise ApplicationHandlerStop

        # ==================================================
        # إعداد العقوبة
        # ==================================================

        punishment_match = re.fullmatch(
            r"ضع عقوبة\s+"
            r"(الكلمات المحظورة|الكلمات المحظورة/ه|"
            r"الكلمات المحظورة2|الكلمات المحظورة/ه2)"
            r"\s+"
            r"(كتم|تقييد|حظر|انذار)",
            text
        )

        if punishment_match:

            command_list = (
                punishment_match.group(1)
            )

            punishment = (
                punishment_match.group(2)
            )

            list_id = list_aliases[
                command_list
            ]

            chat = update.effective_chat

            if not chat:
                return

            allowed = await asyncio.to_thread(
                can_manage_blocked_words,
                actor.id,
                chat.id
            )

            if not allowed:

                await update.message.reply_text(
                    BLOCKED_PERMISSION_MESSAGE
                )

                raise ApplicationHandlerStop

            if punishment == "انذار":

                _blocked_sessions[
                    (
                        actor.id,
                        chat.id
                    )
                ] = {
                    "type": "warning_setup",
                    "list_id": list_id,
                }

                await update.message.reply_text(
                    "تمام، أرسل مدة الانذار+ العقوبة الي بعد "
                    "الانذارات مع المدة بهذي الطريقة:\n\n"
                    "3د كتم 5ي"
                )

                raise ApplicationHandlerStop

            if punishment == "حظر":

                await asyncio.to_thread(
                    set_direct_action,
                    chat.id,
                    list_id,
                    "ban",
                    None
                )

                await update.message.reply_text(
                    "• تم وضع عقوبة الحظر على الكلمات المحظورة "
                    "بنجاح ✅ ."
                )

                raise ApplicationHandlerStop

            action = (
                "mute"
                if punishment == "كتم"
                else "restrict"
            )

            _blocked_sessions[
                (
                    actor.id,
                    chat.id
                )
            ] = {
                "type": "direct_duration",
                "list_id": list_id,
                "action": action,
            }

            if action == "mute":

                await update.message.reply_text(
                    "• حسنًا اختر مدة الكتم ."
                )

            else:

                await update.message.reply_text(
                    "• حسنًا اختر مدة التقييد ."
                )

            raise ApplicationHandlerStop

        return

    # ==================================================
    # القروب / الخاص
    # ==================================================

    chat = update.effective_chat

    if not chat:
        return

    # ==================================================
    # القروب
    # ==================================================

    if chat.type in (
        "group",
        "supergroup"
    ):

        allowed = await asyncio.to_thread(
            can_manage_blocked_words,
            actor.id,
            chat.id
        )

        if not allowed:

            await update.message.reply_text(
                BLOCKED_PERMISSION_MESSAGE
            )

            raise ApplicationHandlerStop

        mention = (
            f'<a href="tg://user?id={actor.id}">'
            f'{html_escape(actor.first_name or "المشرف")}'
            f'</a>'
        )

        await update.message.reply_text(
            f"اهلًا يالمشرف {mention}\n"
            f"اختر وين تبي تفك القائمة:",
            parse_mode="HTML",
            reply_markup=welcome_keyboard(
                chat.id,
                list_id
            )
        )

        raise ApplicationHandlerStop

    # ==================================================
    # الخاص
    # ==================================================

    if chat.type == "private":

        message_text, keyboard = (
            await build_list_message(
                chat.id,
                list_id
            )
        )

        await update.message.reply_text(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        raise ApplicationHandlerStop


# ==================================================
# جلسات الإدخال
# ==================================================

async def handle_blocked_session(
    update,
    context
):

    if not update.message:
        return False

    actor = update.effective_user

    if not actor:
        return False

    chat = update.effective_chat

    if not chat:
        return False

    key = (
        actor.id,
        chat.id
    )

    session = _blocked_sessions.get(
        key
    )

    if not session:
        return False

    origin_chat_id = session.get(
        "origin_chat_id",
        chat.id
    )

    allowed = await asyncio.to_thread(
        can_manage_blocked_words,
        actor.id,
        origin_chat_id
    )

    if not allowed:

        _blocked_sessions.pop(
            key,
            None
        )

        await update.message.reply_text(
            BLOCKED_PERMISSION_MESSAGE
        )

        return True

    # ==================================================
    # إضافة
    # ==================================================

    if session["type"] == "add":

        words = extract_input_words(
            update.message.text or ""
        )

        list_id = session["list_id"]

        if not words:

            await update.message.reply_text(
                "• لم يتم العثور على كلمات لإضافتها ."
            )

            return True

        await asyncio.to_thread(
            add_words,
            origin_chat_id,
            list_id,
            words
        )

        _blocked_sessions.pop(
            key,
            None
        )

        try:
            await update.message.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "تم حفظ الكلمات بنجاح ✅ .",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "↩️ رجوع لقائمة الكلمات",
                            callback_data=(
                                f"bw:back:"
                                f"{list_id}:"
                                f"{origin_chat_id}"
                            )
                        ),
                        InlineKeyboardButton(
                            "اغلاق القائمة",
                            callback_data=(
                                f"bw:close:"
                                f"{origin_chat_id}"
                            )
                        )
                    ]
                ]
            )
        )

        return True

    # ==================================================
    # حذف
    # ==================================================

    if session["type"] == "delete":

        words = extract_input_words(
            update.message.text or ""
        )

        list_id = session["list_id"]

        if not words:

            await update.message.reply_text(
                "• لم يتم العثور على كلمات لحذفها ."
            )

            return True

        await asyncio.to_thread(
            delete_words,
            origin_chat_id,
            list_id,
            words
        )

        _blocked_sessions.pop(
            key,
            None
        )

        try:
            await update.message.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "تم حذف الكلمات بنجاح ✅ .",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "↩️ رجوع لقائمة الكلمات",
                            callback_data=(
                                f"bw:back:"
                                f"{list_id}:"
                                f"{origin_chat_id}"
                            )
                        ),
                        InlineKeyboardButton(
                            "اغلاق القائمة",
                            callback_data=(
                                f"bw:close:"
                                f"{origin_chat_id}"
                            )
                        )
                    ]
                ]
            )
        )

        return True

    # ==================================================
    # مدة العقوبة
    # ==================================================

    if session["type"] == "direct_duration":

        token = (
            update.message.text or ""
        ).strip()

        duration = parse_duration_token(
            token
        )

        if duration is None:

            await update.message.reply_text(
                "• المدة غير صحيحة .\n"
                "• مثال: 5ي أو 30ث أو 50د أو 1س"
            )

            return True

        await asyncio.to_thread(
            set_direct_action,
            origin_chat_id,
            session["list_id"],
            session["action"],
            duration
        )

        _blocked_sessions.pop(
            key,
            None
        )

        await update.message.reply_text(
            "• تم حفظ إعداد العقوبة بنجاح ✅ ."
        )

        return True

    # ==================================================
    # إعداد الإنذار
    # ==================================================

    if session["type"] == "warning_setup":

        parts = (
            update.message.text or ""
        ).strip().split()

        if len(parts) not in (2, 3):

            await update.message.reply_text(
                "• الصيغة غير صحيحة .\n\n"
                "مثال:\n"
                "3د كتم 5ي"
            )

            return True

        warning_duration = parse_duration_token(
            parts[0]
        )

        if warning_duration is None:

            await update.message.reply_text(
                "• مدة الانذار غير صحيحة .\n\n"
                "مثال:\n"
                "3د كتم 5ي"
            )

            return True

        punishment_word = parts[1]

        punishment_map = {
            "كتم": "mute",
            "تقييد": "restrict",
            "حظر": "ban",
        }

        warning_action = punishment_map.get(
            punishment_word
        )

        if not warning_action:

            await update.message.reply_text(
                "• العقوبة غير صحيحة .\n\n"
                "استخدم: كتم أو تقييد أو حظر"
            )

            return True

        punishment_duration = None

        if warning_action in (
            "mute",
            "restrict"
        ):

            if len(parts) != 3:

                await update.message.reply_text(
                    "• يجب كتابة مدة العقوبة أيضًا .\n\n"
                    "مثال:\n"
                    "3د كتم 5ي"
                )

                return True

            punishment_duration = parse_duration_token(
                parts[2]
            )

            if punishment_duration is None:

                await update.message.reply_text(
                    "• مدة العقوبة غير صحيحة .\n\n"
                    "مثال:\n"
                    "3د كتم 5ي"
                )

                return True

        else:

            if len(parts) != 2:

                await update.message.reply_text(
                    "• الحظر دائم، اكتبها هكذا:\n\n"
                    "3د حظر"
                )

                return True

        await asyncio.to_thread(
            set_warning_action,
            origin_chat_id,
            session["list_id"],
            warning_duration,
            warning_action,
            punishment_duration
        )

        _blocked_sessions.pop(
            key,
            None
        )

        await update.message.reply_text(
            "• تم حفظ إعدادات الانذار بنجاح ✅ ."
        )

        return True

    return False


# ==================================================
# 🚀 فحص الكلمات
#
# القواعد:
#
# OWNER_ID:
#   لا حذف ولا عقوبة.
#
# عضو / مميز:
#   حذف الرسالة + العقوبة.
#
# ادمن وفوق:
#   حذف الرسالة فقط.
#
# ==================================================

async def check_blocked_words(
    update,
    context
):

    if not update.message:
        return False

    if not update.effective_chat:
        return False

    if update.effective_chat.type not in (
        "group",
        "supergroup"
    ):
        return False

    actor = update.effective_user

    if not actor:
        return False

    # ==================================================
    # 👑 OWNER_ID
    #
    # استثناء كامل قبل أي فحص.
    # ==================================================

    if actor.id == OWNER_ID:
        return False

    text = (
        update.message.text or ""
    )

    if not text:
        return False

    chat_id = (
        update.effective_chat.id
    )

    # ==================================================
    # القائمة الأولى والثانية
    # ==================================================

    for list_id in (
        LIST_1,
        LIST_2
    ):

        # ==================================================
        # 🚀 الكلمات فقط من الكاش
        # ==================================================

        words = await get_cached_words(
            chat_id,
            list_id
        )

        if not words:
            continue

        # ==================================================
        # بحث عن كلمة محظورة
        # ==================================================

        matched = find_blocked_word(
            text,
            words
        )

        if not matched:
            continue

        # ==================================================
        # قراءة الإعدادات
        # ==================================================

        settings = await get_cached_settings(
            chat_id,
            list_id
        )

        # إذا القائمة معطلة
        if not settings["enabled"]:
            continue

        # ==================================================
        # فحص الرتبة
        # ==================================================

        level = await asyncio.to_thread(
            get_blocked_level,
            actor.id,
            chat_id
        )

        # ==================================================
        # 👑 OWNER_ID
        #
        # استثناء كامل.
        # ==================================================

        if actor.id == OWNER_ID:
            return False

        # ==================================================
        # 👮 ادمن وفوق
        #
        # حذف فقط بدون عقوبة.
        # ==================================================

        if level >= 2:

            try:

                await update.message.delete()

            except Exception as e:

                print(
                    f"⚠️ فشل حذف رسالة كلمة محظورة "
                    f"من ادمن وفوق: {e}"
                )

            return True

        # ==================================================
        # 👤 عضو / مميز
        #
        # حذف + عقوبة.
        # ==================================================

        if level <= BLOCKED_WORDS_MAX_AFFECTED_RANK:

            # ==================================================
            # حفظ المستخدم
            # ==================================================

            try:

                from handlers.moderation import (
                    save_target_user
                )

                await asyncio.to_thread(
                    save_target_user,
                    actor
                )

            except Exception:
                pass

            # ==================================================
            # حذف الرسالة أولًا
            # ==================================================

            try:

                await update.message.delete()

            except Exception as e:

                print(
                    f"⚠️ فشل حذف رسالة كلمة محظورة: {e}"
                )

            # ==================================================
            # عقوبة مباشرة
            # ==================================================

            if settings["action"] in (
                "mute",
                "restrict",
                "ban"
            ):

                duration = settings[
                    "duration"
                ]

                await apply_punishment(
                    update,
                    context,
                    chat_id,
                    actor,
                    settings["action"],
                    duration
                )

                return True

            # ==================================================
            # عقوبة الإنذار
            # ==================================================

            if settings["action"] == "warning":

                await handle_warning_punishment(
                    update,
                    context,
                    chat_id,
                    list_id,
                    actor,
                    settings
                )

                return True

            return True

        # ==================================================
        # أي رتبة أخرى غير معروفة:
        # حذف فقط بدون عقوبة.
        # ==================================================

        try:

            await update.message.delete()

        except Exception as e:

            print(
                f"⚠️ فشل حذف رسالة كلمة محظورة: {e}"
            )

        return True

    return False


# ==================================================
# الراوتر الرئيسي
# ==================================================

async def blocked_words_message_handler(
    update,
    context
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    # ==================================================
    # جلسة إضافة / حذف / إعداد
    # ==================================================

    handled = await handle_blocked_session(
        update,
        context
    )

    if handled:

        raise ApplicationHandlerStop

    text = (
        update.message.text or ""
    ).strip()

    command_names = {
        "الكلمات المحظورة",
        "الكلمات المحظورة/ه",
        "الكلمات المحظورة2",
        "الكلمات المحظورة/ه2",
    }

    is_punishment_command = bool(
        re.fullmatch(
            r"ضع عقوبة\s+"
            r"(الكلمات المحظورة|الكلمات المحظورة/ه|"
            r"الكلمات المحظورة2|الكلمات المحظورة/ه2)"
            r"\s+"
            r"(كتم|تقييد|حظر|انذار)",
            text
        )
    )

    is_toggle_command = bool(
        re.fullmatch(
            r"(تفعيل|تعطيل)\s+"
            r"(الكلمات المحظورة|الكلمات المحظورة/ه|"
            r"الكلمات المحظورة2|الكلمات المحظورة/ه2)",
            text
        )
    )

    if (
        text in command_names
        or is_punishment_command
        or is_toggle_command
    ):

        await blocked_words_command(
            update,
            context
        )

        raise ApplicationHandlerStop

    # ==================================================
    # فحص الكلمات
    # ==================================================

    matched = await check_blocked_words(
        update,
        context
    )

    if matched:

        raise ApplicationHandlerStop


# ==================================================
# أزرار القائمة
# ==================================================

async def blocked_words_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    data = (
        query.data or ""
    )

    if not data.startswith(
        "bw:"
    ):
        return

    actor = query.from_user

    if not actor:
        return

    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    # ==================================================
    # ⚡ نرد على callback فورًا
    # ==================================================

    try:
        await query.answer()
    except Exception:
        pass

    # ==================================================
    # تحديد البيانات
    # ==================================================

    list_id = None
    origin_chat_id = None

    if action in (
        "here",
        "private",
        "add",
        "delete",
        "toggle",
        "back"
    ):

        if len(parts) != 4:
            return

        try:

            list_id = int(
                parts[2]
            )

            origin_chat_id = int(
                parts[3]
            )

        except Exception:

            return

    elif action == "close":

        if len(parts) != 3:
            return

        try:

            origin_chat_id = int(
                parts[2]
            )

        except Exception:

            return

    elif action == "lift":

        if len(parts) != 5:
            return

        punishment_action = parts[2]

        try:

            origin_chat_id = int(
                parts[3]
            )

            target_id = int(
                parts[4]
            )

        except Exception:

            return

        list_id = None

    else:

        return

    # ==================================================
    # صلاحية الإدارة
    # ==================================================

    allowed = await asyncio.to_thread(
        can_manage_blocked_words,
        actor.id,
        origin_chat_id
    )

    if not allowed:

        try:

            await query.answer(
                BLOCKED_PERMISSION_MESSAGE,
                show_alert=True
            )

        except Exception:
            pass

        return

    # ==================================================
    # هنا
    # ==================================================

    if action == "here":

        if not query.message:
            return

        text, keyboard = await build_list_message(
            origin_chat_id,
            list_id
        )

        try:

            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:

            print(
                f"⚠️ فشل فتح قائمة الكلمات هنا: {e}"
            )

        return

    # ==================================================
    # الخاص
    # ==================================================

    if action == "private":

        if not query.message:
            return

        text, keyboard = await build_list_message(
            origin_chat_id,
            list_id
        )

        try:

            await context.bot.send_message(
                chat_id=actor.id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            try:

                await query.edit_message_text(
                    "تم الإرسال بالخاص ✅ ."
                )

            except Exception:
                pass

        except Exception as e:

            print(
                f"⚠️ تعذر إرسال قائمة الكلمات بالخاص: {e}"
            )

            try:

                await query.edit_message_text(
                    "تعذر إرسال القائمة بالخاص."
                )

            except Exception:
                pass

        return

    # ==================================================
    # إضافة
    # ==================================================

    if action == "add":

        if not query.message:
            return

        session_chat_id = (
            query.message.chat.id
        )

        _blocked_sessions[
            (
                actor.id,
                session_chat_id
            )
        ] = {
            "type": "add",
            "list_id": list_id,
            "origin_chat_id": origin_chat_id,
        }

        await query.edit_message_text(
            "• حسنًا ارسل الكلمات التي تريد إضافتها .\n\n"
            "مثال:\n\n"
            "كلزق\n"
            "كلتبن\n"
            "ياكلب\n"
            "الخ…"
        )

        return

    # ==================================================
    # حذف
    # ==================================================

    if action == "delete":

        if not query.message:
            return

        session_chat_id = (
            query.message.chat.id
        )

        _blocked_sessions[
            (
                actor.id,
                session_chat_id
            )
        ] = {
            "type": "delete",
            "list_id": list_id,
            "origin_chat_id": origin_chat_id,
        }

        await query.edit_message_text(
            "• حسنًا ارسل الكلمات التي تريد حذفها .\n\n"
            "مثال:\n\n"
            "كلزق\n"
            "كلتبن\n"
            "ياكلب\n"
            "الخ…"
        )

        return

    # ==================================================
    # التفعيل / التعطيل
    # ==================================================

    if action == "toggle":

        settings = await get_cached_settings(
            origin_chat_id,
            list_id
        )

        new_status = not settings[
            "enabled"
        ]

        settings[
            "enabled"
        ] = new_status

        await asyncio.to_thread(
            set_enabled,
            origin_chat_id,
            list_id,
            new_status
        )

        if not query.message:
            return

        text, keyboard = await build_list_message(
            origin_chat_id,
            list_id
        )

        try:

            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:

            print(
                f"⚠️ فشل تحديث قائمة الكلمات: {e}"
            )

        return

    # ==================================================
    # رجوع
    # ==================================================

    if action == "back":

        if not query.message:
            return

        text, keyboard = await build_list_message(
            origin_chat_id,
            list_id
        )

        try:

            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:

            print(
                f"⚠️ فشل الرجوع لقائمة الكلمات: {e}"
            )

        return

    # ==================================================
    # إغلاق
    # ==================================================

    if action == "close":

        if query.message:

            try:
                await query.message.delete()
            except Exception:
                pass

        return

    # ==================================================
    # رفع العقوبة
    # ==================================================

    if action == "lift":

        target = None

        try:

            chat_member = await context.bot.get_chat_member(
                origin_chat_id,
                target_id
            )

            target = chat_member.user

        except Exception:

            class StoredUser:
                pass

            target = StoredUser()

            target.id = target_id
            target.username = None
            target.first_name = str(
                target_id
            )

        # ==================================================
        # رفع الكتم
        # ==================================================

        if punishment_action == "mute":

            await asyncio.to_thread(
                delete_restriction_record,
                "bot_mutes",
                origin_chat_id,
                target_id
            )

        # ==================================================
        # رفع التقييد
        # ==================================================

        elif punishment_action == "restrict":

            try:

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
                    chat_id=origin_chat_id,
                    user_id=target_id,
                    permissions=permissions
                )

            except Exception as e:

                print(
                    f"⚠️ فشل رفع القيود: {e}"
                )

            await asyncio.to_thread(
                delete_restriction_record,
                "restrictions",
                origin_chat_id,
                target_id
            )

        # ==================================================
        # رفع الحظر
        # ==================================================

        elif punishment_action == "ban":

            try:

                await context.bot.unban_chat_member(
                    chat_id=origin_chat_id,
                    user_id=target_id,
                    only_if_banned=False
                )

            except Exception as e:

                print(
                    f"⚠️ فشل رفع الحظر: {e}"
                )

            await asyncio.to_thread(
                delete_restriction_record,
                "moderation_bans",
                origin_chat_id,
                target_id
            )

        if query.message:

            try:

                await query.edit_message_reply_markup(
                    reply_markup=None
                )

            except Exception:
                pass

        return


# ==================================================
# تنظيف الإنذارات المنتهية
# ==================================================

def cleanup_expired_blocked_warnings():

    now = current_timestamp()

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute("""
        DELETE FROM blocked_words_warnings_v2
        WHERE expires_at<=?
        """, (
            now,
        ))

        conn.commit()

    finally:

        if cur:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# انتهاء مدة إنذارات الكلمات
# ==================================================

async def blocked_words_expiry_loop(
    application
):

    while True:

        try:

            await asyncio.to_thread(
                cleanup_expired_blocked_warnings
            )

        except Exception as e:

            print(
                f"⚠️ خطأ في انتهاء إنذارات الكلمات المحظورة: {e}"
            )

        await asyncio.sleep(15)
