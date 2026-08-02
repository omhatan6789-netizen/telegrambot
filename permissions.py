from database import connect


OWNER_ID = 8453977662



async def is_owner(user_id):

    if user_id == OWNER_ID:
        return True

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rank
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return False

    return result[0] == "مالك"



async def is_admin(user_id):

    if user_id == OWNER_ID:
        return True

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rank
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return False


    return result[0] in [
        "مالك",
        "🤍 نائب المالك",
        "🟣 ادمن اساسي",
        "🛡 ادمن"
    ]


from handlers.roles import get_rank, RANK_LEVELS


async def check_command_permission(user_id, command):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT min_rank
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


    if RANK_LEVELS.get(user_rank, 0) >= RANK_LEVELS.get(required_rank, 0):
        return True, None


    return False, required_rank   



