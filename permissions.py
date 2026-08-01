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
        "🟣 ادمن أساسي",
        "🛡 ادمن"
    ]