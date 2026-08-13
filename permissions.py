from database import connect
from handlers.roles import get_rank, RANK_LEVELS


OWNER_ID = 8453977662


# ==================================================
# التحقق من Dev
# ==================================================

def is_developer(user_id):

    # Dev الأساسي
    if user_id == OWNER_ID:
        return True

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rank
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return False

    return result[0] == "Dev"


# ==================================================
# التحقق من المالك
# ==================================================

async def is_owner(user_id):

    # Dev الأساسي
    if user_id == OWNER_ID:
        return True

    # Dev المساعد ليس مالكًا
    rank = get_rank(user_id)

    return rank == "المالك"


# ==================================================
# التحقق من الأدمن
# ==================================================

async def is_admin(user_id):

    # Dev الأساسي
    if user_id == OWNER_ID:
        return True

    rank = get_rank(user_id)

    # Dev المساعد
    if rank == "Dev":
        return True

    return RANK_LEVELS.get(rank, 0) >= RANK_LEVELS.get(
        "ادمن",
        0
    )


# ==================================================
# صلاحية الأمر
# ==================================================

async def check_command_permission(
    user_id,
    command
):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rank
        FROM command_locks
        WHERE command=?
        """,
        (command,)
    )

    result = cur.fetchone()

    conn.close()

    # الأمر غير مقفول
    if not result:
        return True, None

    required_rank = result[0]

    user_rank = get_rank(user_id)

    # Dev الأساسي والمساعد يتجاوزون قفل الأوامر
    if is_developer(user_id):
        return True, None

    # الرتب العادية
    if (
        RANK_LEVELS.get(user_rank, 0)
        >=
        RANK_LEVELS.get(required_rank, 0)
    ):
        return True, None

    return False, required_rank