from html import escape

from telegram import Update
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
            CREATE TABLE IF NOT EXISTS group_ranks
            (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                rank TEXT NOT NULL DEFAULT 'عضو',

                PRIMARY KEY
                (
                    chat_id,
                    user_id
                )
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_group_ranks_chat
            ON group_ranks(chat_id)
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_group_ranks_user
            ON group_ranks(user_id)
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
#
# تستخدم للتوافق مع الأكواد القديمة.
# في القروب استخدم:
# get_rank(user_id, chat_id)
# ==================================================

def get_rank(
    user_id,
    chat_id=None
):

    # ==================================================
    # المطور الأساسي
    # ==================================================

    if user_id == OWNER_ID:
        return "Dev"

    # ==================================================
    # المطور الثانوي عالميًا
    # ==================================================

    if is_secondary_developer(user_id):
        return "Dev"

    # ==================================================
    # رتبة المجموعة
    # ==================================================

    if chat_id is not None:

        return get_group_rank(
            chat_id,
            user_id
        )

    # ==================================================
    # الكاش القديم
    # ==================================================

    if user_id in _rank_cache:

        return _rank_cache[
            user_id
        ]

    # ==================================================
    # الكاش المركزي
    # ==================================================

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

    # ==================================================
    # تحميل المستخدم
    # ==================================================

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

    # ==================================================
    # fallback
    # ==================================================

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
# جلب رتبة المستخدم داخل مجموعة
# ==================================================

def get_group_rank(
    chat_id,
    user_id
):

    if user_id == OWNER_ID:
        return "Dev"

    if is_secondary_developer(user_id):
        return "Dev"

    cache_key = (
        chat_id,
        user_id
    )

    if cache_key in _group_rank_cache:

        return _group_rank_cache[
            cache_key
        ]

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT rank
            FROM group_ranks
            WHERE chat_id=?
            AND user_id=?
            """,
            (
                chat_id,
                user_id
            )
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

        rank = "عضو"

    else:

        rank = normalize_rank(
            result[0]
        )

        if rank == "Dev":
            rank = "عضو"

    _group_rank_cache[
        cache_key
    ] = rank

    return rank


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

    target = parts[-1].strip()

    if target.isdigit():

        try:

            return await context.bot.get_chat(
                int(target)
            )

        except Exception:

            return None

    if target.startswith("@"):

        try:

            return await context.bot.get_chat(
                target
            )

        except Exception:

            return None

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
            "عضو",
            False
        ),

        "تنزيل المالك": (
            "عضو",
            False
        ),

        "تنزيل نائب المالك": (
            "عضو",
            False
        ),

        "تنزيل ادمن اساسي": (
            "عضو",
            False
        ),

        "تنزيل ادمن": (
            "عضو",
            False
        ),

        "تنزيل مميز": (
            "عضو",
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
# هل يقدر يعدل رتبة؟
# ==================================================

def can_change_rank(
    actor_id,
    target_id,
    new_rank,
    promoting,
    chat_id=None
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

    target_level = get_rank_level(
        target_id,
        chat_id
    )

    if target_id == OWNER_ID:

        return (
            False,
            "❌ لا يمكن تعديل المطور الأساسي."
        )

    if actor_dev == DEV_PRIMARY:
        return True, None

    if actor_dev == DEV_SECONDARY:

        if target_dev == DEV_PRIMARY:

            return (
                False,
                "❌ لا يمكنك تعديل المطور الأساسي."
            )

        if target_dev == DEV_SECONDARY:

            return (
                False,
                "❌ لا يمكنك تعديل مطور من نفس رتبتك."
            )

        if target_level >= actor_level:

            return (
                False,
                "❌ لا يمكنك تعديل رتبة مساوية أو أعلى منك."
            )

        if promoting:

            new_level = RANK_LEVELS.get(
                new_rank,
                0
            )

            if new_level >= actor_level:

                return (
                    False,
                    "❌ لا يمكنك رفع شخص إلى رتبة مساوية أو أعلى منك."
                )

        return True, None

    if target_level >= actor_level:

        return (
            False,
            "❌ لا يمكنك تعديل رتبة مساوية أو أعلى منك."
        )

    if promoting:

        new_level = RANK_LEVELS.get(
            new_rank,
            0
        )

        if new_level >= actor_level:

            return (
                False,
                "❌ لا يمكنك رفع شخص إلى رتبة مساوية أو أعلى منك."
            )

    return True, None


# ==================================================
# تحديث رتبة داخل المجموعة
# ==================================================

def update_group_rank(
    chat_id,
    user_id,
    rank
):

    rank = normalize_rank(
        rank
    )

    # Dev ليس رتبة مجموعة
    if rank == "Dev":

        rank = "عضو"

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO group_ranks
            (
                chat_id,
                user_id,
                rank
            )
            VALUES (?, ?, ?)

            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                rank=excluded.rank
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

    _group_rank_cache[
        (
            chat_id,
            user_id
        )
    ] = rank

    clear_command_permission_cache()


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

    clear_command_permission_cache()


# ==================================================
# التحديث القديم
#
# يبقى للتوافق مع الأكواد الأخرى.
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

        update_developer_rank(
            user_id,
            rank
        )

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
            FROM group_ranks
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
            DELETE FROM group_ranks
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
            FROM group_ranks
            WHERE chat_id=?
            AND rank IN
            (
                'المالك',
                'نائب المالك',
                'ادمن اساسي',
                'ادمن',
                'مميز'
            )
            ORDER BY user_id
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

                return (
                    info.first_name
                    or str(user_id)
                )

            except Exception:

                return str(user_id)

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
            msg
        )

        return



# ==================================================
# قوائم الرتب + قائمة Dev
# ==================================================

ROLE_LIST_NAMES = {
    "المميزين": "مميز",
    "الادمنية": "ادمن",
    "الادمنية الاساسيين": "ادمن اساسي",
    "نواب المالك": "نائب المالك",
    "المالكين": "المالك",
}


# ==================================================
# منشن حقيقي
# ==================================================

def role_mention(user_id, name=None):

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
# جلب أعضاء رتبة معينة
# ==================================================

def get_users_by_group_rank(
    chat_id,
    rank
):

    conn = connect()
    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id
            FROM group_ranks
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
#
# Dev عالمي وليس خاص بمجموعة
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
#
# المطور الأساسي لا يتأثر
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

    # --------------------------------------------------
    # مسح كاش المطورين
    # --------------------------------------------------

    _developer_cache.clear()

    _rank_cache.clear()

    clear_command_permission_cache()

    return int(
        deleted or 0
    )


# ==================================================
# صلاحية قائمة الرتبة
#
# لازم يكون المستخدم أعلى من الرتبة
#
# مثال:
# ادمن يستطيع رؤية المميزين
# ادمن لا يستطيع رؤية الادمنية
# ادمن اساسي يستطيع رؤية الادمنية
# المالك يستطيع رؤية الجميع
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
#
# لازم يكون أعلى من الرتبة
# ==================================================

def can_clear_rank_list(
    user_id,
    chat_id,
    rank
):

    # --------------------------------------------------
    # المالكين:
    # المطور الأساسي + المالك
    # --------------------------------------------------

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

        return user_level >= RANK_LEVELS["المالك"]

    # --------------------------------------------------
    # بقية الرتب
    # --------------------------------------------------

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
            FROM group_ranks
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
            DELETE FROM group_ranks
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
#
# قائمة Dev
# قائمة dev
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

    # ==================================================
    # المطور الأساسي فقط
    # ==================================================

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

    # ==================================================
    # جلب المطور الأساسي
    # ==================================================

    primary_mention = await get_user_mention(
        context,
        OWNER_ID
    )

    # ==================================================
    # جلب المساعدين
    # ==================================================

    developers = get_secondary_developers()

    # ==================================================
    # بناء القائمة
    # ==================================================

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

    # ==================================================
    # الزر
    # ==================================================

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

    # ==================================================
    # الصلاحية
    # ==================================================

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

    # ==================================================
    # جلب الأشخاص
    # ==================================================

    users = get_users_by_group_rank(
        chat.id,
        rank
    )

    # ==================================================
    # عنوان القائمة
    # ==================================================

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

    # ==================================================
    # الأعضاء
    # ==================================================

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

        message_text += (
            "لا يوجد\n"
        )

    # ==================================================
    # زر مسح القائمة
    # ==================================================

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
#
# مسح Dev
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

    # ==================================================
    # الصلاحية
    # ==================================================

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
#
# يمسح:
# - Dev المساعدين
# - المالكين
# - نواب المالك
# - الادمنية الاساسيين
# - الادمنية
# - المميزين
#
# ويُبقي المطور الأساسي
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

    # ==================================================
    # المطور الأساسي فقط
    # ==================================================

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

    # ==================================================
    # أولًا: رتب المجموعة
    # ==================================================

    counts = clear_group_ranks(
        chat.id
    )

    # ==================================================
    # ثانيًا: Dev المساعدين
    # ==================================================

    dev_count = clear_secondary_developers()

    # ==================================================
    # النتيجة
    # ==================================================

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

            owner_mention = await get_user_mention(
                context,
                OWNER_ID
            )

            await query.answer()

            try:

                await query.message.reply_text(
                    "• هذا الأمر للمطور الاساسي "
                    f"({owner_mention}) فقط !",
                    parse_mode="HTML"
                )

            except Exception:
                pass

            return

        # --------------------------------------------------
        # مسح المساعدين
        # --------------------------------------------------

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

    if target_rank not in (
        "مميز",
        "ادمن",
        "ادمن اساسي",
        "نائب المالك",
        "المالك",
    ):

        return

    # ==================================================
    # المجموعة
    # ==================================================

    message = query.message

    if not message:
        return

    chat = message.chat

    if not chat:
        return

    # ==================================================
    # الصلاحية
    # ==================================================

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

    # ==================================================
    # حذف القائمة
    # ==================================================

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

    command, new_rank, promoting = (
        get_rank_from_command(text)
    )

    if not command:
        return

    # ==================================================
    # رفع/تنزيل Dev
    # Dev عالمي
    # ==================================================

    if command == "رفع Dev":

        target = await get_target_user(
            update,
            context
        )

        if not target:

            await update.message.reply_text(
                "❌ حدد الشخص بالرد أو الآيدي."
            )

            return

        if target.id == actor.id:

            await update.message.reply_text(
                "❌ لا يمكنك تعديل رتبتك بنفسك."
            )

            return

        if target.id == OWNER_ID:

            await update.message.reply_text(
                "❌ لا يمكن تعديل رتبة الـDev الأساسي."
            )

            return

        if not is_primary_developer(
            actor.id
        ):

            await update.message.reply_text(
                "❌ هذا الأمر للمطور الأساسي فقط."
            )

            return

        if is_developer(
            target.id
        ):

            await update.message.reply_text(
                "❌ هذا الشخص Dev بالفعل."
            )

            return

        update_developer_rank(
            target.id,
            "Dev"
        )

        await update.message.reply_text(
            f"✅ تم رفع {target.first_name} إلى Dev."
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

            await update.message.reply_text(
                "❌ حدد الشخص بالرد أو الآيدي."
            )

            return

        if not is_primary_developer(
            actor.id
        ):

            await update.message.reply_text(
                "❌ هذا الأمر للمطور الأساسي فقط."
            )

            return

        if not is_secondary_developer(
            target.id
        ):

            await update.message.reply_text(
                "❌ هذا الشخص ليس Dev."
            )

            return

        update_developer_rank(
            target.id,
            "عضو"
        )

        await update.message.reply_text(
            f"✅ تم تنزيل {target.first_name} من Dev إلى عضو."
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

        await update.message.reply_text(
            "❌ حدد الشخص بالرد أو الآيدي.\n\n"
            "مثال:\n"
            "رفع ادمن\n"
            "رفع ادمن 123456789"
        )

        return

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل رتبتك بنفسك."
        )

        return

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكن تعديل رتبة الـDev الأساسي."
        )

        return

    allowed, reason = can_change_rank(
        actor.id,
        target.id,
        new_rank,
        promoting,
        chat_id
    )

    if not allowed:

        await update.message.reply_text(
            reason
        )

        return

    old_rank = get_rank(
        target.id,
        chat_id
    )

    update_group_rank(
        chat_id,
        target.id,
        new_rank
    )

    await update.message.reply_text(
        f"✅ تم تعديل رتبة {target.first_name}\n"
        f"• الرتبة السابقة ↤︎ {old_rank}\n"
        f"• الرتبة الجديدة ↤︎ {new_rank}"
    )
