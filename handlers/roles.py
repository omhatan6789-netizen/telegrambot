from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
)
from telegram.ext import ContextTypes

from database import connect

from handlers.cache import (
    get_cached_user,
    get_user_data_sync,
    set_cached_rank,
)


# ==================================================
# الصلاحيات
# ==================================================

OWNER_ID = 8453977662


# ==================================================
# مستويات الرتب
# ==================================================

RANK_LEVELS = {
    "عضو": 0,
    "مميز": 1,
    "ادمن": 2,
    "ادمن اساسي": 3,
    "نائب المالك": 4,
    "المالك": 5,
    "Dev": 6,
}


# ==================================================
# أنواع المطور
# ==================================================

DEV_PRIMARY = "primary"
DEV_SECONDARY = "secondary"


# ==================================================
# الكاش
# ==================================================

_developer_cache = {}
_rank_cache = {}
_command_permission_cache = {}

_command_locks_cache = None

_group_rank_cache = {}


# ==================================================
# إنشاء جدول رتب المجموعات
# ==================================================

def create_group_ranks_table():

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS group_user_ranks
            (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                rank TEXT NOT NULL,

                PRIMARY KEY
                (
                    chat_id,
                    user_id,
                    rank
                )
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_group_user_ranks_user
            ON group_user_ranks(chat_id, user_id)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_group_user_ranks_rank
            ON group_user_ranks(chat_id, rank)
            """
        )

        try:

            cur.execute(
                """
                INSERT INTO group_user_ranks
                (
                    chat_id,
                    user_id,
                    rank
                )
                SELECT
                    chat_id,
                    user_id,
                    rank
                FROM group_ranks
                WHERE rank IN
                (
                    'مميز',
                    'ادمن',
                    'ادمن اساسي',
                    'نائب المالك',
                    'المالك'
                )
                ON CONFLICT
                (
                    chat_id,
                    user_id,
                    rank
                )
                DO NOTHING
                """
            )

        except Exception:

            pass

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
# مسح كاش الرتبة
# ==================================================

def clear_user_role_cache(
    user_id,
    chat_id=None
):

    _developer_cache.pop(
        user_id,
        None
    )

    _rank_cache.pop(
        user_id,
        None
    )

    if chat_id is not None:

        _group_rank_cache.pop(
            (
                chat_id,
                user_id
            ),
            None
        )

    else:

        keys = [
            key
            for key in _group_rank_cache
            if key[1] == user_id
        ]

        for key in keys:

            _group_rank_cache.pop(
                key,
                None
            )


# ==================================================
# مسح كاش جميع رتب المجموعة
# ==================================================

def clear_group_rank_cache(
    chat_id
):

    keys = [
        key
        for key in _group_rank_cache
        if key[0] == chat_id
    ]

    for key in keys:

        _group_rank_cache.pop(
            key,
            None
        )


# ==================================================
# مسح كاش صلاحيات الأوامر
# ==================================================

def clear_command_permission_cache():

    global _command_locks_cache

    _command_permission_cache.clear()

    _command_locks_cache = None


# ==================================================
# توحيد اسم الرتبة
# ==================================================

def normalize_rank(rank):

    if not rank:
        return "عضو"

    rank = str(rank).strip()

    if rank in RANK_LEVELS:
        return rank

    return "عضو"


# ==================================================
# الرتب العادية فقط
# ==================================================

NORMAL_RANKS = (
    "مميز",
    "ادمن",
    "ادمن اساسي",
    "نائب المالك",
    "المالك",
)


# ==================================================
# جلب أعلى رتبة من قائمة
# ==================================================

def get_highest_rank(
    ranks
):

    highest = "عضو"
    highest_level = 0

    for rank in ranks:

        rank = normalize_rank(rank)

        level = RANK_LEVELS.get(
            rank,
            0
        )

        if level > highest_level:

            highest = rank
            highest_level = level

    return highest


# ==================================================
# جلب جميع رتب المستخدم داخل المجموعة
# ==================================================

def get_group_ranks(
    chat_id,
    user_id
):

    if user_id == OWNER_ID:
        return ["Dev"]

    if is_secondary_developer(user_id):
        return ["Dev"]

    cache_key = (
        chat_id,
        user_id
    )

    if cache_key in _group_rank_cache:

        cached = _group_rank_cache[
            cache_key
        ]

        if isinstance(cached, list):
            return list(cached)

        if cached:
            return [cached]

        return ["عضو"]

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT rank
            FROM group_user_ranks
            WHERE chat_id=?
            AND user_id=?
            AND rank IN
            (
                'مميز',
                'ادمن',
                'ادمن اساسي',
                'نائب المالك',
                'المالك'
            )
            ORDER BY
                CASE rank
                    WHEN 'المالك' THEN 5
                    WHEN 'نائب المالك' THEN 4
                    WHEN 'ادمن اساسي' THEN 3
                    WHEN 'ادمن' THEN 2
                    WHEN 'مميز' THEN 1
                    ELSE 0
                END DESC
            """,
            (
                chat_id,
                user_id
            )
        )

        rows = cur.fetchall()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    ranks = []

    for row in rows:

        rank = normalize_rank(
            row[0]
        )

        if (
            rank in NORMAL_RANKS
            and rank not in ranks
        ):

            ranks.append(rank)

    if not ranks:
        ranks = ["عضو"]

    _group_rank_cache[
        cache_key
    ] = list(ranks)

    return list(ranks)


# ==================================================
# هل المستخدم يملك رتبة معينة؟
# ==================================================

def has_group_rank(
    chat_id,
    user_id,
    rank
):

    rank = normalize_rank(
        rank
    )

    if rank == "عضو":
        return True

    if rank == "Dev":
        return is_developer(user_id) is not None

    return rank in get_group_ranks(
        chat_id,
        user_id
    )


# ==================================================
# تحميل أقفال الأوامر
# ==================================================

def _load_command_locks():

    global _command_locks_cache

    if _command_locks_cache is not None:
        return _command_locks_cache

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT command, rank
            FROM command_locks
            """
        )

        rows = cur.fetchall()

        _command_locks_cache = {
            row[0]: normalize_rank(row[1])
            for row in rows
            if row[0]
        }

        return _command_locks_cache

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# هل المستخدم Dev؟
# ==================================================

def is_developer(user_id):

    if user_id == OWNER_ID:
        return DEV_PRIMARY

    if user_id in _developer_cache:

        return _developer_cache[
            user_id
        ]

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT developer_type
            FROM developers
            WHERE user_id=?
            """,
            (user_id,)
        )

        result = cur.fetchone()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()

    if not result:

        _developer_cache[user_id] = None

        return None

    developer_type = result[0]

    _developer_cache[user_id] = developer_type

    return developer_type


# ==================================================
# المطور الأساسي
# ==================================================

def is_primary_developer(user_id):

    return (
        is_developer(user_id)
        == DEV_PRIMARY
    )


# ==================================================
# المطور الثانوي
# ==================================================

def is_secondary_developer(user_id):

    return (
        is_developer(user_id)
        == DEV_SECONDARY
    )


# ==================================================
# جلب رتبة المستخدم العامة
# ==================================================

def get_rank(
    user_id,
    chat_id=None
):

    if user_id == OWNER_ID:
        return "Dev"

    if is_secondary_developer(user_id):
        return "Dev"

    if chat_id is not None:

        return get_group_rank(
            chat_id,
            user_id
        )

    if user_id in _rank_cache:

        return _rank_cache[
            user_id
        ]

    cached = get_cached_user(
        user_id
    )

    if cached is not None:

        rank = normalize_rank(
            cached.get(
                "rank",
                "عضو"
            )
        )

        _rank_cache[user_id] = rank

        return rank

    data = get_user_data_sync(
        user_id
    )

    if data is not None:

        rank = normalize_rank(
            data.get(
                "rank",
                "عضو"
            )
        )

        _rank_cache[user_id] = rank

        return rank

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT rank
            FROM ranks
            WHERE user_id=?
            """,
            (user_id,)
        )

        rank_data = cur.fetchone()

        if rank_data and rank_data[0]:

            rank = normalize_rank(
                rank_data[0]
            )

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
                VALUES (?, '', '', 0, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    rank=excluded.rank
                """,
                (
                    user_id,
                    rank
                )
            )

            conn.commit()

            set_cached_rank(
                user_id,
                rank
            )

            _rank_cache[user_id] = rank

            return rank

        _rank_cache[user_id] = "عضو"

        return "عضو"

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# جلب أعلى رتبة المستخدم داخل مجموعة
# ==================================================

def get_group_rank(
    chat_id,
    user_id
):

    ranks = get_group_ranks(
        chat_id,
        user_id
    )

    return get_highest_rank(
        ranks
    )


# ==================================================
# مستوى الرتبة
# ==================================================

def get_rank_level(
    user_id,
    chat_id=None
):

    if user_id == OWNER_ID:
        return 7

    if is_secondary_developer(user_id):
        return 6

    if chat_id is not None:

        rank = get_group_rank(
            chat_id,
            user_id
        )

    else:

        rank = get_rank(
            user_id
        )

    return RANK_LEVELS.get(
        rank,
        0
    )


# ==================================================
# صلاحية الأمر
# ==================================================

def check_command_permission(
    user_id,
    command,
    chat_id=None
):

    cache_key = (
        user_id,
        command,
        chat_id
    )

    if cache_key in _command_permission_cache:

        return _command_permission_cache[
            cache_key
        ]

    command_locks = _load_command_locks()

    required_rank = command_locks.get(
        command
    )

    if not required_rank:

        result = (
            True,
            None
        )

        _command_permission_cache[
            cache_key
        ] = result

        return result

    user_level = get_rank_level(
        user_id,
        chat_id
    )

    required_level = RANK_LEVELS.get(
        required_rank,
        0
    )

    if is_developer(user_id):

        result = (
            True,
            None
        )

        _command_permission_cache[
            cache_key
        ] = result

        return result

    if user_level >= required_level:

        result = (
            True,
            None
        )

        _command_permission_cache[
            cache_key
        ] = result

        return result

    result = (
        False,
        required_rank
    )

    _command_permission_cache[
        cache_key
    ] = result

    return result


# ==================================================
# جلب الشخص المستهدف
# ==================================================

async def get_target_user(
    update,
    context
):

    if not update.message:
        return None

    message = update.message

    # --------------------------------------------------
    # الرد على رسالة
    # --------------------------------------------------

    if message.reply_to_message:

        replied_user = (
            message.reply_to_message.from_user
        )

        if replied_user:
            return replied_user

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 2:
        return None

    # --------------------------------------------------
    # البحث عن ID أو Username
    # --------------------------------------------------

    for part in parts[1:]:

        target = part.strip()

        # ==================================================
        # ID
        # ==================================================

        if target.isdigit():

            try:

                return await context.bot.get_chat(
                    int(target)
                )

            except Exception:

                continue

        # ==================================================
        # Username
        # ==================================================

        if target.startswith("@"):

            username = target[1:].strip()

            if not username:
                continue

            conn = connect()
            cur = None
            row = None

            try:

                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT user_id, username, first_name
                    FROM users
                    WHERE LOWER(username)=LOWER(?)
                    LIMIT 1
                    """,
                    (username,)
                )

                row = cur.fetchone()

            except Exception:

                row = None

            finally:

                if cur is not None:

                    try:
                        cur.close()
                    except Exception:
                        pass

                conn.close()

            if row:

                user_id = int(row[0])

                first_name = (
                    row[2]
                    or username
                )

                try:

                    return await context.bot.get_chat(
                        user_id
                    )

                except Exception:

                    return User(
                        id=user_id,
                        first_name=str(first_name),
                        is_bot=False,
                        username=username
                    )

    return None


# ==================================================
# استخراج أمر الرتبة
# ==================================================

def get_rank_from_command(text):

    text = (
        text or ""
    ).strip()

    commands = {

        "رفع Dev": (
            "Dev",
            True
        ),

        "رفع المالك": (
            "المالك",
            True
        ),

        "رفع نائب المالك": (
            "نائب المالك",
            True
        ),

        "رفع ادمن اساسي": (
            "ادمن اساسي",
            True
        ),

        "رفع ادمن": (
            "ادمن",
            True
        ),

        "رفع مميز": (
            "مميز",
            True
        ),

        "تنزيل Dev": (
            "Dev",
            False
        ),

        "تنزيل المالك": (
            "المالك",
            False
        ),

        "تنزيل نائب المالك": (
            "نائب المالك",
            False
        ),

        "تنزيل ادمن اساسي": (
            "ادمن اساسي",
            False
        ),

        "تنزيل ادمن": (
            "ادمن",
            False
        ),

        "تنزيل مميز": (
            "مميز",
            False
        ),
    }

    for command in sorted(
        commands,
        key=len,
        reverse=True
    ):

        if (
            text == command
            or text.startswith(
                command + " "
            )
        ):

            rank, promoting = (
                commands[command]
            )

            return (
                command,
                rank,
                promoting
            )

    return (
        None,
        None,
        None
    )


# ==================================================
# رسالة عدم صلاحية رتبة معينة
# ==================================================

def rank_permission_message(
    rank
):

    level = RANK_LEVELS.get(
        rank,
        0
    )

    required = None

    for candidate, candidate_level in RANK_LEVELS.items():

        if candidate_level == level + 1:

            required = candidate

            break

    if required == "Dev":

        return (
            "• اعذرني بس هذا الأمر لـ ↤︎〖 Dev 〗 فقط ."
        )

    if required:

        return (
            "• اعذرني بس هذا الأمر لـ ↤︎"
            f"〖 {required} 〗 فقط ."
        )

    return (
        "• اعذرني بس ما عندك الصلاحية لهذا الأمر ."
    )


# ==================================================
# هل يقدر يضيف رتبة؟
# ==================================================

def can_promote_rank(
    actor_id,
    target_id,
    new_rank,
    chat_id
):

    actor_dev = is_developer(
        actor_id
    )

    target_dev = is_developer(
        target_id
    )

    actor_level = get_rank_level(
        actor_id,
        chat_id
    )

    new_level = RANK_LEVELS.get(
        new_rank,
        0
    )

    # --------------------------------------------------
    # Dev
    # --------------------------------------------------

    if new_rank == "Dev":

        if actor_dev != DEV_PRIMARY:

            return (
                False,
                "• اعذرني بس هذا الأمر للمطور الأساسي فقط ."
            )

        if target_id == OWNER_ID:

            return (
                False,
                "❌ لا يمكن تعديل المطور الأساسي."
            )

        if target_dev == DEV_SECONDARY:

            return (
                False,
                "• المستخدم Dev مسبقًا."
            )

        return True, None

    # --------------------------------------------------
    # المطور الأساسي
    # --------------------------------------------------

    if actor_dev == DEV_PRIMARY:

        return True, None

    # --------------------------------------------------
    # المطور الثانوي
    # --------------------------------------------------

    if actor_dev == DEV_SECONDARY:

        if target_id == OWNER_ID:

            return (
                False,
                "❌ لا يمكنك تعديل المطور الأساسي."
            )

        if target_dev == DEV_SECONDARY:

            return (
                False,
                "❌ لا يمكنك تعديل مطور من نفس رتبتك."
            )

        if new_level >= actor_level:

            return (
                False,
                rank_permission_message(
                    new_rank
                )
            )

        return True, None

    # --------------------------------------------------
    # المستخدم العادي
    # --------------------------------------------------

    if target_id == OWNER_ID:

        return (
            False,
            "❌ لا يمكن تعديل المطور الأساسي."
        )

    if target_dev == DEV_SECONDARY:

        return (
            False,
            "❌ لا يمكنك تعديل مطور Dev."
        )

    if new_level >= actor_level:

        return (
            False,
            rank_permission_message(
                new_rank
            )
        )

    return True, None


# ==================================================
# هل يقدر ينزل رتبة؟
# ==================================================

def can_demote_rank(
    actor_id,
    target_id,
    rank,
    chat_id
):

    actor_dev = is_developer(
        actor_id
    )

    target_dev = is_developer(
        target_id
    )

    actor_level = get_rank_level(
        actor_id,
        chat_id
    )

    target_rank_level = RANK_LEVELS.get(
        rank,
        0
    )

    # --------------------------------------------------
    # تنزيل Dev
    # --------------------------------------------------

    if rank == "Dev":

        if actor_dev != DEV_PRIMARY:

            return (
                False,
                "• اعذرني بس هذا الأمر للمطور الأساسي فقط ."
            )

        if target_id == OWNER_ID:

            return (
                False,
                "❌ لا يمكن تعديل المطور الأساسي."
            )

        if target_dev != DEV_SECONDARY:

            return (
                False,
                "❌ هذا الشخص ليس Dev."
            )

        return True, None

    # --------------------------------------------------
    # المطور الأساسي
    # --------------------------------------------------

    if actor_dev == DEV_PRIMARY:

        return True, None

    # --------------------------------------------------
    # المطور الثانوي
    # --------------------------------------------------

    if actor_dev == DEV_SECONDARY:

        if target_id == OWNER_ID:

            return (
                False,
                "❌ لا يمكنك تعديل المطور الأساسي."
            )

        if target_dev == DEV_SECONDARY:

            return (
                False,
                "❌ لا يمكنك تعديل مطور من نفس رتبتك."
            )

        if target_rank_level >= actor_level:

            return (
                False,
                rank_permission_message(
                    rank
                )
            )

        return True, None

    # --------------------------------------------------
    # المستخدم العادي
    # --------------------------------------------------

    if target_id == OWNER_ID:

        return (
            False,
            "❌ لا يمكن تعديل المطور الأساسي."
        )

    if target_dev == DEV_SECONDARY:

        return (
            False,
            "❌ لا يمكنك تعديل مطور Dev."
        )

    if target_rank_level >= actor_level:

        return (
            False,
            rank_permission_message(
                rank
            )
        )

    return True, None


# ==================================================
# التوافق مع الأكواد القديمة
# ==================================================

def can_change_rank(
    actor_id,
    target_id,
    new_rank,
    promoting,
    chat_id=None
):

    if chat_id is None:

        return (
            False,
            "❌ هذا الأمر داخل المجموعة فقط."
        )

    if promoting:

        return can_promote_rank(
            actor_id,
            target_id,
            new_rank,
            chat_id
        )

    return can_demote_rank(
        actor_id,
        target_id,
        new_rank,
        chat_id
    )


# ==================================================
# إضافة رتبة للمستخدم
# ==================================================

def add_group_rank(
    chat_id,
    user_id,
    rank
):

    rank = normalize_rank(
        rank
    )

    if rank not in NORMAL_RANKS:
        return

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO group_user_ranks
            (
                chat_id,
                user_id,
                rank
            )
            VALUES (?, ?, ?)

            ON CONFLICT
            (
                chat_id,
                user_id,
                rank
            )
            DO NOTHING
            """,
            (
                chat_id,
                user_id,
                rank
            )
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

    clear_user_role_cache(
        user_id,
        chat_id
    )

    clear_command_permission_cache()


# ==================================================
# حذف رتبة معينة من المستخدم
# ==================================================

def remove_group_rank(
    chat_id,
    user_id,
    rank
):

    rank = normalize_rank(
        rank
    )

    if rank not in NORMAL_RANKS:
        return False

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM group_user_ranks
            WHERE chat_id=?
            AND user_id=?
            AND rank=?
            """,
            (
                chat_id,
                user_id,
                rank
            )
        )

        deleted = cur.rowcount

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

    clear_user_role_cache(
        user_id,
        chat_id
    )

    clear_command_permission_cache()

    return bool(deleted)


# ==================================================
# تحديث رتبة داخل المجموعة
# ==================================================

def update_group_rank(
    chat_id,
    user_id,
    rank
):

    add_group_rank(
        chat_id,
        user_id,
        rank
    )


# ==================================================
# تحديث Dev العالمي
# ==================================================

def update_developer_rank(
    user_id,
    rank
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        if rank == "Dev":

            cur.execute(
                """
                INSERT INTO developers
                (
                    user_id,
                    developer_type,
                    added_by
                )
                VALUES (?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    developer_type='secondary',
                    added_by=excluded.added_by
                """,
                (
                    user_id,
                    DEV_SECONDARY,
                    OWNER_ID
                )
            )

        else:

            cur.execute(
                """
                DELETE FROM developers
                WHERE user_id=?
                AND developer_type='secondary'
                """,
                (
                    user_id,
                )
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

    _developer_cache.pop(
        user_id,
        None
    )

    _rank_cache.pop(
        user_id,
        None
    )

    clear_group_rank_cache_for_user(
        user_id
    )

    clear_command_permission_cache()


# ==================================================
# مسح كاش مجموعات مستخدم
# ==================================================

def clear_group_rank_cache_for_user(
    user_id
):

    keys = [
        key
        for key in _group_rank_cache
        if key[1] == user_id
    ]

    for key in keys:

        _group_rank_cache.pop(
            key,
            None
        )


# ==================================================
# التحديث القديم
# ==================================================

def update_user_rank(
    user_id,
    rank
):

    rank = normalize_rank(
        rank
    )

    if rank == "Dev":

        update_developer_rank(
            user_id,
            "Dev"
        )

    else:

        set_cached_rank(
            user_id,
            rank
        )

        _rank_cache[user_id] = rank

    clear_command_permission_cache()

    try:

        from permissions import (
            clear_user_permission_cache
        )

        clear_user_permission_cache()

    except Exception:

        pass


# ==================================================
# مسح رتب المجموعة
# ==================================================

def clear_group_ranks(
    chat_id
):

    conn = connect()
    cur = None

    counts = {
        "المالك": 0,
        "نائب المالك": 0,
        "ادمن اساسي": 0,
        "ادمن": 0,
        "مميز": 0,
    }

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT rank, COUNT(*)
            FROM group_user_ranks
            WHERE chat_id=?
            AND rank IN
            (
                'المالك',
                'نائب المالك',
                'ادمن اساسي',
                'ادمن',
                'مميز'
            )
            GROUP BY rank
            """,
            (
                chat_id,
            )
        )

        rows = cur.fetchall()

        for rank, count in rows:

            rank = normalize_rank(
                rank
            )

            if rank in counts:

                counts[rank] = int(
                    count
                )

        cur.execute(
            """
            DELETE FROM group_user_ranks
            WHERE chat_id=?
            """,
            (
                chat_id,
            )
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

    clear_group_rank_cache(
        chat_id
    )

    clear_command_permission_cache()

    return counts


# ==================================================
# جلب جميع أعضاء مجموعة حسب الرتب
# ==================================================

def get_group_rank_users(
    chat_id
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id, rank
            FROM group_user_ranks
            WHERE chat_id=?
            AND rank IN
            (
                'المالك',
                'نائب المالك',
                'ادمن اساسي',
                'ادمن',
                'مميز'
            )
            ORDER BY
                CASE rank
                    WHEN 'المالك' THEN 5
                    WHEN 'نائب المالك' THEN 4
                    WHEN 'ادمن اساسي' THEN 3
                    WHEN 'ادمن' THEN 2
                    WHEN 'مميز' THEN 1
                    ELSE 0
                END DESC,
                user_id
            """,
            (
                chat_id,
            )
        )

        return cur.fetchall()

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# منشن حقيقي
# ==================================================

def role_mention(
    user_id,
    name=None
):

    if name is None:
        name = str(user_id)

    name = escape(
        str(name)
    )

    return (
        f'<a href="tg://user?id={user_id}">'
        f'{name}'
        f'</a>'
    )


# ==================================================
# جلب اسم + منشن المستخدم
# ==================================================

async def get_user_mention(
    context,
    user_id
):

    try:

        user = await context.bot.get_chat(
            user_id
        )

        name = (
            getattr(user, "first_name", None)
            or getattr(user, "title", None)
            or getattr(user, "username", None)
            or str(user_id)
        )

        return role_mention(
            user_id,
            name
        )

    except Exception:

        return role_mention(
            user_id,
            str(user_id)
        )


# ==================================================
# أوامر عرض الرتب
# ==================================================

async def roles_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    chat = update.effective_chat

    chat_id = (
        chat.id
        if chat
        else None
    )

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # رتبتي
    # ==================================================

    if text == "رتبتي":

        rank = get_rank(
            user.id,
            chat_id
        )

        safe_rank = escape(
            rank
        )

        await update.message.reply_text(
            f"• رتبتك هي ↤︎ "
            f"<tg-spoiler>{safe_rank}</tg-spoiler>",
            parse_mode="HTML"
        )

        return

    # ==================================================
    # رتبته
    # ==================================================

    if (
        text == "رتبته"
        or text.startswith("رتبته ")
    ):

        target = await get_target_user(
            update,
            context
        )

        if not target:
            return

        rank = get_rank(
            target.id,
            chat_id
        )

        safe_rank = escape(
            rank
        )

        await update.message.reply_text(
            f"• رتبته هي ↤︎ {safe_rank}",
            parse_mode="HTML"
        )

        return

    # ==================================================
    # كشف المجموعة
    # ==================================================

    if text == "كشف المجموعة":

        allowed, required = (
            check_command_permission(
                user.id,
                "كشف المجموعة",
                chat_id
            )
        )

        if not allowed:

            await update.message.reply_text(
                f"❌ هذا الأمر لـ {required} وفوق فقط"
            )

            return

        rows = get_group_rank_users(
            chat_id
        )

        owner = []
        deputy = []
        basic = []
        admins = []
        vip = []

        async def get_name(
            user_id
        ):

            try:

                info = await context.bot.get_chat(
                    user_id
                )

                if info.username:
                    return f"@{info.username}"

                return role_mention(
                    user_id,
                    info.first_name
                    or str(user_id)
                )

            except Exception:

                return role_mention(
                    user_id,
                    str(user_id)
                )

        for user_id, rank in rows:

            name = await get_name(
                user_id
            )

            if rank == "المالك":

                owner.append(name)

            elif rank == "نائب المالك":

                deputy.append(name)

            elif rank == "ادمن اساسي":

                basic.append(name)

            elif rank == "ادمن":

                admins.append(name)

            elif rank == "مميز":

                vip.append(name)

        msg = """
كشف المجموعة: 📋

• قائمة المالك
━━━━━━━━━━━━
"""

        if owner:

            for i, name in enumerate(
                owner,
                1
            ):

                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة نواب المالك
━━━━━━━━━━━━
"""

        if deputy:

            for i, name in enumerate(
                deputy,
                1
            ):

                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة الادمنية الاساسيين
━━━━━━━━━━━━
"""

        if basic:

            for i, name in enumerate(
                basic,
                1
            ):

                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة الادمنية
━━━━━━━━━━━━
"""

        if admins:

            for i, name in enumerate(
                admins,
                1
            ):

                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة المميزين
━━━━━━━━━━━━
"""

        if vip:

            for i, name in enumerate(
                vip,
                1
            ):

                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        await update.message.reply_text(
            msg,
            parse_mode="HTML"
        )

        return


# ==================================================
# قوائم الرتب
# ==================================================

ROLE_LIST_NAMES = {
    "المميزين": "مميز",
    "الادمنية": "ادمن",
    "الادمنية الاساسيين": "ادمن اساسي",
    "نواب المالك": "نائب المالك",
    "المالكين": "المالك",
}


# ==================================================
# جلب أعضاء رتبة معينة
# ==================================================

def get_users_by_group_rank(
    chat_id,
    rank
):

    rank = normalize_rank(
        rank
    )

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id
            FROM group_user_ranks
            WHERE chat_id=?
            AND rank=?
            ORDER BY user_id
            """,
            (
                chat_id,
                rank
            )
        )

        rows = cur.fetchall()

        return [
            int(row[0])
            for row in rows
        ]

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# جلب المطورين المساعدين
# ==================================================

def get_secondary_developers():

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id
            FROM developers
            WHERE developer_type=?
            ORDER BY user_id
            """,
            (
                DEV_SECONDARY,
            )
        )

        rows = cur.fetchall()

        return [
            int(row[0])
            for row in rows
        ]

    finally:

        if cur is not None:

            try:
                cur.close()
            except Exception:
                pass

        conn.close()


# ==================================================
# مسح المطورين المساعدين
# ==================================================

def clear_secondary_developers():

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM developers
            WHERE developer_type=?
            """,
            (
                DEV_SECONDARY,
            )
        )

        deleted = cur.rowcount

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

    _developer_cache.clear()
    _rank_cache.clear()
    _group_rank_cache.clear()

    clear_command_permission_cache()

    return int(
        deleted or 0
    )


# ==================================================
# صلاحية قائمة الرتبة
# ==================================================

def can_view_rank_list(
    user_id,
    chat_id,
    rank
):

    if user_id == OWNER_ID:
        return True

    if is_primary_developer(
        user_id
    ):
        return True

    if is_secondary_developer(
        user_id
    ):
        return True

    user_level = get_rank_level(
        user_id,
        chat_id
    )

    target_level = RANK_LEVELS.get(
        rank,
        0
    )

    return (
        user_level > target_level
    )


# ==================================================
# رسالة عدم السماح بفتح القائمة
# ==================================================

def rank_list_permission_message(
    rank
):

    if rank == "ادمن":

        return (
            "• هذا الامر للأدمن الاساسي وفوق ."
        )

    if rank == "ادمن اساسي":

        return (
            "• هذا الأمر لـ المالك وفوق ."
        )

    if rank == "المالك":

        return (
            "• هذا الامر لـ نواف والـ Dev فقط ."
        )

    return (
        "• هذا الأمر لرتبة اعلى منك ."
    )


# ==================================================
# صلاحية مسح قائمة رتبة
# ==================================================

def can_clear_rank_list(
    user_id,
    chat_id,
    rank
):

    if rank == "المالك":

        if user_id == OWNER_ID:
            return True

        if is_primary_developer(
            user_id
        ):
            return True

        user_level = get_rank_level(
            user_id,
            chat_id
        )

        return (
            user_level >= RANK_LEVELS["المالك"]
        )

    if user_id == OWNER_ID:
        return True

    if is_primary_developer(
        user_id
    ):
        return True

    user_level = get_rank_level(
        user_id,
        chat_id
    )

    target_level = RANK_LEVELS.get(
        rank,
        0
    )

    return (
        user_level > target_level
    )


# ==================================================
# رسالة عدم السماح بمسح القائمة
# ==================================================

def rank_clear_permission_message(
    rank
):

    if rank == "مميز":

        return (
            "• هذا الامر للأدمن وفوق ."
        )

    if rank == "ادمن":

        return (
            "• هذا الامر للأدمن الاساسي وفوق ."
        )

    if rank == "ادمن اساسي":

        return (
            "• هذا الأمر لـ المالك وفوق ."
        )

    if rank == "نائب المالك":

        return (
            "• هذا الأمر لـ المالك وفوق ."
        )

    if rank == "المالك":

        return (
            "• هذا الامر لـ نواف والـ Dev فقط ."
        )

    return (
        "• هذا الأمر لرتبة اعلى منك ."
    )


# ==================================================
# حذف قائمة رتبة
# ==================================================

def clear_rank_list(
    chat_id,
    rank
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM group_user_ranks
            WHERE chat_id=?
            AND rank=?
            """,
            (
                chat_id,
                rank
            )
        )

        row = cur.fetchone()

        count = int(
            row[0] or 0
        )

        cur.execute(
            """
            DELETE FROM group_user_ranks
            WHERE chat_id=?
            AND rank=?
            """,
            (
                chat_id,
                rank
            )
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

    clear_group_rank_cache(
        chat_id
    )

    clear_command_permission_cache()

    return count


# ==================================================
# قائمة Dev
# ==================================================

async def dev_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    if not is_primary_developer(
        actor.id
    ):

        owner_mention = await get_user_mention(
            context,
            OWNER_ID
        )

        await update.message.reply_text(
            "• هذا الأمر للمطور الاساسي "
            f"({owner_mention}) فقط !",
            parse_mode="HTML"
        )

        return

    primary_mention = await get_user_mention(
        context,
        OWNER_ID
    )

    developers = get_secondary_developers()

    text = (
        "اهلًا بك عزيزي المطور في قائمة Dev "
        "الخاص بك🎖️\n\n"
        "المطور الاساسي👇🏻\n\n"
        f"{primary_mention}\n\n\n"

        "المساعدين 🎖️\n\n"
        "—————————————————\n\n"
    )

    if developers:

        for index, user_id in enumerate(
            developers,
            1
        ):

            mention = await get_user_mention(
                context,
                user_id
            )

            text += (
                f"{index} - {mention}\n\n"
            )

    else:

        text += "مافيه احد رتبته Dev حاليًا.\n"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "مسح القائمة",
                    callback_data="roles_clear:Dev"
                )
            ]
        ]
    )

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==================================================
# قائمة رتبة عادية
# ==================================================

async def rank_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user
    chat = update.effective_chat

    if not actor or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    text = (
        update.message.text or ""
    ).strip()

    rank = ROLE_LIST_NAMES.get(
        text
    )

    if not rank:
        return

    if not can_view_rank_list(
        actor.id,
        chat.id,
        rank
    ):

        await update.message.reply_text(
            rank_list_permission_message(
                rank
            )
        )

        return

    users = get_users_by_group_rank(
        chat.id,
        rank
    )

    text_map = {
        "مميز": "المميزين",
        "ادمن": "الادمنية",
        "ادمن اساسي": "الادمنية الاساسيين",
        "نائب المالك": "نواب المالك",
        "المالك": "المالكين",
    }

    title = text_map[
        rank
    ]

    message_text = (
        f"• قائمة {title}\n"
        "━━━━━━━━━━━━\n"
    )

    if users:

        for index, user_id in enumerate(
            users,
            1
        ):

            mention = await get_user_mention(
                context,
                user_id
            )

            message_text += (
                f"{index} - {mention}\n\n"
            )

    else:

        message_text += "لا يوجد\n"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "مسح القائمة",
                    callback_data=(
                        f"roles_clear:{rank}"
                    )
                )
            ]
        ]
    )

    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==================================================
# حذف Dev من الأمر
# ==================================================

async def clear_dev_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    if not is_primary_developer(
        actor.id
    ):

        owner_mention = await get_user_mention(
            context,
            OWNER_ID
        )

        await update.message.reply_text(
            "• هذا الأمر للمطور الاساسي "
            f"({owner_mention}) فقط !",
            parse_mode="HTML"
        )

        return

    deleted = clear_secondary_developers()

    await update.message.reply_text(
        "• تم مسح جميع مطورين Dev المساعدين بنجاح .\n"
        f"「 {deleted} 」Dev/مساعدين المطور"
    )


# ==================================================
# مسح رتبة عادية
# ==================================================

async def clear_rank_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user
    chat = update.effective_chat

    if not actor or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    text = (
        update.message.text or ""
    ).strip()

    command_ranks = {
        "مسح المميزين": "مميز",
        "مسح الادمنية": "ادمن",
        "مسح الادمنية الاساسيين": "ادمن اساسي",
        "مسح نواب المالك": "نائب المالك",
        "مسح المالكين": "المالك",
    }

    rank = command_ranks.get(
        text
    )

    if not rank:
        return

    if not can_clear_rank_list(
        actor.id,
        chat.id,
        rank
    ):

        await update.message.reply_text(
            rank_clear_permission_message(
                rank
            )
        )

        return

    deleted = clear_rank_list(
        chat.id,
        rank
    )

    title_map = {
        "مميز": "المميزين",
        "ادمن": "الادمنية",
        "ادمن اساسي": "الادمنية الاساسيين",
        "نائب المالك": "نواب المالك",
        "المالك": "المالكين",
    }

    await update.message.reply_text(
        "• تم مسح القائمة بنجاح .\n"
        f"「 {deleted} 」{title_map[rank]}"
    )


# ==================================================
# مسح الرتب كلها
# ==================================================

async def clear_all_ranks_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user
    chat = update.effective_chat

    if not actor or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    if not is_primary_developer(
        actor.id
    ):

        owner_mention = await get_user_mention(
            context,
            OWNER_ID
        )

        await update.message.reply_text(
            "• هذا الأمر للمطور الاساسي "
            f"({owner_mention}) فقط !",
            parse_mode="HTML"
        )

        return

    counts = clear_group_ranks(
        chat.id
    )

    dev_count = clear_secondary_developers()

    await update.message.reply_text(
        "• تم مسح الكل بنجاح .\n"
        f"「 {dev_count} 」Dev/مساعدين المطور\n"
        f"• المالكين ↤︎「 {counts['المالك']} 」\n"
        f"• نوّاب المالك ↤︎「 {counts['نائب المالك']} 」\n"
        f"• الادمنية الاساسيين ↤︎「 {counts['ادمن اساسي']} 」\n"
        f"• الادمنية ↤︎「 {counts['ادمن']} 」\n"
        f"• المميزين ↤︎「 {counts['مميز']} 」"
    )


# ==================================================
# Callback حذف القوائم
# ==================================================

async def roles_clear_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    actor = query.from_user

    if not actor:
        return

    data = query.data or ""

    if not data.startswith(
        "roles_clear:"
    ):
        return

    target_rank = data.split(
        ":",
        1
    )[1]

    # ==================================================
    # قائمة Dev
    # ==================================================

    if target_rank == "Dev":

        if not is_primary_developer(
            actor.id
        ):

            await query.answer(
                "• رح اطلب من نواف يحولك ملكية البوت احسن .",
                show_alert=True
            )

            return

        deleted = clear_secondary_developers()

        await query.answer(
            "☑️ تم مسح القائمة."
        )

        try:

            await query.edit_message_text(
                "• تم مسح القائمة بنجاح .\n"
                f"「 {deleted} 」Dev/مساعدين المطور"
            )

        except Exception as e:

            print(
                "⚠️ خطأ في تعديل قائمة Dev:",
                e
            )

        return

    # ==================================================
    # التأكد أن الرتبة صحيحة
    # ==================================================

    if target_rank not in NORMAL_RANKS:
        return

    message = query.message

    if not message:
        return

    chat = message.chat

    if not chat:
        return

    if not can_clear_rank_list(
        actor.id,
        chat.id,
        target_rank
    ):

        await query.answer(
            rank_clear_permission_message(
                target_rank
            ),
            show_alert=True
        )

        return

    deleted = clear_rank_list(
        chat.id,
        target_rank
    )

    title_map = {
        "مميز": "المميزين",
        "ادمن": "الادمنية",
        "ادمن اساسي": "الادمنية الاساسيين",
        "نائب المالك": "نواب المالك",
        "المالك": "المالكين",
    }

    await query.answer(
        "☑️ تم مسح القائمة."
    )

    try:

        await query.edit_message_text(
            "• تم مسح القائمة بنجاح .\n"
            f"「 {deleted} 」{title_map[target_rank]}"
        )

    except Exception as e:

        print(
            "⚠️ خطأ في تعديل قائمة الرتبة:",
            e
        )


# ==================================================
# تنزيل جميع الرتب الأقل من رتبة الفاعل
# ==================================================

def clear_lower_group_ranks(
    chat_id,
    user_id,
    actor_level
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM group_user_ranks
            WHERE chat_id=?
            AND user_id=?
            AND rank IN
            (
                'مميز',
                'ادمن',
                'ادمن اساسي',
                'نائب المالك',
                'المالك'
            )
            AND
            CASE rank
                WHEN 'مميز' THEN 1
                WHEN 'ادمن' THEN 2
                WHEN 'ادمن اساسي' THEN 3
                WHEN 'نائب المالك' THEN 4
                WHEN 'المالك' THEN 5
                ELSE 0
            END < ?
            """,
            (
                chat_id,
                user_id,
                actor_level
            )
        )

        deleted = cur.rowcount

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

    clear_user_role_cache(
        user_id,
        chat_id
    )

    clear_command_permission_cache()

    return int(
        deleted or 0
    )


# ==================================================
# رفع وتنزيل الرتب
# ==================================================

async def change_rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    if not actor:
        return

    chat = update.effective_chat

    chat_id = (
        chat.id
        if chat
        else None
    )

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # تنزيل الكل
    # ==================================================

    if text == "تنزيل الكل":

        if chat_id is None:
            return

        target = await get_target_user(
            update,
            context
        )

        if not target:
            return

        if target.id == OWNER_ID:

            await update.message.reply_text(
                "❌ لا يمكن تعديل المطور الأساسي."
            )

            return

        actor_dev = is_developer(
            actor.id
        )

        target_dev = is_developer(
            target.id
        )

        actor_level = get_rank_level(
            actor.id,
            chat_id
        )

        target_level = get_rank_level(
            target.id,
            chat_id
        )

        # ==================================================
        # Dev الأساسي / المساعد
        # ==================================================

        if actor_dev in (
            DEV_PRIMARY,
            DEV_SECONDARY
        ):

            # المساعد لا يستطيع إزالة Dev من نفسه
            if (
                actor_dev == DEV_SECONDARY
                and target.id == actor.id
            ):

                await update.message.reply_text(
                    "❌ لا يمكنك إزالة Dev من نفسك."
                )

                return

            # Dev يستطيع تنزيل جميع الرتب العادية
            # ولا يتم المساس برتبة Dev العالمية.
            deleted = clear_lower_group_ranks(
                chat_id,
                target.id,
                6
            )

            await update.message.reply_text(
                "• تم تنزيل جميع الرتب الأقل منه بنجاح .\n"
                f"• المستخدم ↤︎ "
                f"{await get_user_mention(context, target.id)}\n"
                f"• عدد الرتب التي تم تنزيلها ↤︎「 {deleted} 」",
                parse_mode="HTML"
            )

            return

        # ==================================================
        # المستخدم العادي
        #
        # لازم أعلى رتبة الهدف مساوية لأعلى رتبة الفاعل
        # ==================================================

        if target_level != actor_level:

            await update.message.reply_text(
                "• عيب عيب احترم الي اعلى منك . "
            )

            return

        deleted = clear_lower_group_ranks(
            chat_id,
            target.id,
            actor_level
        )

        await update.message.reply_text(
            "• تم تنزيل جميع الرتب الأقل منه بنجاح .\n"
            f"• المستخدم ↤︎ "
            f"{await get_user_mention(context, target.id)}\n"
            f"• عدد الرتب التي تم تنزيلها ↤︎「 {deleted} 」",
            parse_mode="HTML"
        )

        return

    command, new_rank, promoting = (
        get_rank_from_command(text)
    )

    if not command:
        return

    # ==================================================
    # رفع Dev
    # ==================================================

    if command == "رفع Dev":

        target = await get_target_user(
            update,
            context
        )

        if not target:
            return

        if target.id == actor.id:

            await update.message.reply_text(
                "❌ لا يمكنك رفع نفسك إلى Dev."
            )

            return

        if target.id == OWNER_ID:

            await update.message.reply_text(
                "❌ لا يمكن تعديل رتبة الـDev الأساسي."
            )

            return

        if is_developer(
            target.id
        ):

            await update.message.reply_text(
                "• تم رفعه Dev مسبقًا .\n"
                f"• المستخدم ↤︎ "
                f"{await get_user_mention(context, target.id)}",
                parse_mode="HTML"
            )

            return

        allowed, reason = can_promote_rank(
            actor.id,
            target.id,
            "Dev",
            chat_id
        )

        if not allowed:

            await update.message.reply_text(
                reason
            )

            return

        update_developer_rank(
            target.id,
            "Dev"
        )

        await update.message.reply_text(
            "• تم رفعه Dev بنجاح .\n"
            f"• المستخدم ↤︎ "
            f"{await get_user_mention(context, target.id)}",
            parse_mode="HTML"
        )

        return

    # ==================================================
    # تنزيل Dev
    # ==================================================

    if command == "تنزيل Dev":

        target = await get_target_user(
            update,
            context
        )

        if not target:
            return

        if target.id == actor.id:

            await update.message.reply_text(
                "❌ لا يمكنك إزالة Dev من نفسك."
            )

            return

        allowed, reason = can_demote_rank(
            actor.id,
            target.id,
            "Dev",
            chat_id
        )

        if not allowed:

            await update.message.reply_text(
                reason
            )

            return

        update_developer_rank(
            target.id,
            "عضو"
        )

        await update.message.reply_text(
            "• تم تنزيله من Dev بنجاح .\n"
            f"• المستخدم ↤︎ "
            f"{await get_user_mention(context, target.id)}",
            parse_mode="HTML"
        )

        return

    # ==================================================
    # الرتب العادية تحتاج قروب
    # ==================================================

    if chat_id is None:
        return

    target = await get_target_user(
        update,
        context
    )

    if not target:
        return

    # --------------------------------------------------
    # المالك الأساسي
    # --------------------------------------------------

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكن تعديل رتبة الـDev الأساسي."
        )

        return

    # ==================================================
    # رفع رتبة
    # ==================================================

    if promoting:

        allowed, reason = can_promote_rank(
            actor.id,
            target.id,
            new_rank,
            chat_id
        )

        if not allowed:

            await update.message.reply_text(
                reason
            )

            return

        if has_group_rank(
            chat_id,
            target.id,
            new_rank
        ):

            await update.message.reply_text(
                f"• تم رفعه {new_rank} مسبقًا .\n"
                f"• المستخدم ↤︎ "
                f"{await get_user_mention(context, target.id)}",
                parse_mode="HTML"
            )

            return

        add_group_rank(
            chat_id,
            target.id,
            new_rank
        )

        await update.message.reply_text(
            f"• تم رفعه {new_rank} بنجاح .\n"
            f"• المستخدم ↤︎ "
            f"{await get_user_mention(context, target.id)}",
            parse_mode="HTML"
        )

        return

    # ==================================================
    # تنزيل رتبة
    # ==================================================

    allowed, reason = can_demote_rank(
        actor.id,
        target.id,
        new_rank,
        chat_id
    )

    if not allowed:

        await update.message.reply_text(
            reason
        )

        return

    if not has_group_rank(
        chat_id,
        target.id,
        new_rank
    ):

        await update.message.reply_text(
            f"• تم تنزيله من {new_rank} مسبقًا .\n"
            f"• المستخدم ↤︎ "
            f"{await get_user_mention(context, target.id)}",
            parse_mode="HTML"
        )

        return

    remove_group_rank(
        chat_id,
        target.id,
        new_rank
    )

    await update.message.reply_text(
        f"• تم تنزيله من {new_rank} بنجاح .\n"
        f"• المستخدم ↤︎ "
        f"{await get_user_mention(context, target.id)}",
        parse_mode="HTML"
    )
