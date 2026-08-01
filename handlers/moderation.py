from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank


OWNER_ID = 8453977662


RANKS = {
    "عضو": 0,
    "💎 مميز": 1,
    "🛡 ادمن": 2,
    "🟣 ادمن أساسي": 3,
    "🤍 نائب المالك": 4,
    "👑 المالك": 5
}


def has_permission(actor_id, target_id):

    if actor_id == OWNER_ID:
        return True

    actor_rank = get_rank(actor_id)
    target_rank = get_rank(target_id)

    return RANKS.get(actor_rank, 0) > RANKS.get(target_rank, 0)


async def get_target(update: Update):

    if not update.message:
        return None


    # الرد على رسالة
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user


    text = update.message.text.split(maxsplit=1)

    if len(text) < 2:
        return None


    value = text[1].strip()

    conn = connect()
    cur = conn.cursor()


    # آيدي
    if value.isdigit():

        cur.execute(
            """
            SELECT user_id, first_name
            FROM users
            WHERE user_id=?
            """,
            (int(value),)
        )

        data = cur.fetchone()

        conn.close()

        if not data:
            return None


        class User:
            pass

        user = User()
        user.id = data[0]
        user.first_name = data[1]

        return user


    # يوزر
    cur.execute(
        """
        SELECT user_id, first_name
        FROM users
        WHERE username=?
        """,
        (value.replace("@", ""),)
    )

    data = cur.fetchone()

    conn.close()

    if not data:
        return None


    class User:
        pass

    user = User()
    user.id = data[0]
    user.first_name = data[1]

    return user


# =====================
# كشف
# =====================

async def check_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    target = await get_target(update)

    if not target:

        await update.message.reply_text(
            "❌ استخدم الأمر بالرد أو الآيدي أو اليوزر."
        )

        return


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        SELECT rank
        FROM users
        WHERE user_id=?
        """,
        (target.id,)
    )

    rank = cur.fetchone()


    cur.execute(
        """
        SELECT ban_type
        FROM bans
        WHERE user_id=?
        """,
        (target.id,)
    )

    ban = cur.fetchone()


    cur.execute(
        """
        SELECT mute_type
        FROM mutes
        WHERE user_id=?
        """,
        (target.id,)
    )

    mute = cur.fetchone()


    conn.close()


    if rank:
        rank = rank[0]
    else:
        rank = "عضو"


    ban_text = "لا"

    if ban:
        if ban[0] == "global":
            ban_text = "عام"
        else:
            ban_text = "عادي"


    mute_text = "لا"

    if mute:
        if mute[0] == "global":
            mute_text = "عام"
        else:
            mute_text = "عادي"


    await update.message.reply_text(
        f"""👤 {target.first_name}

🆔 {target.id}
🛡 {rank}
🚫 الحظر: {ban_text}
🔇 الكتم: {mute_text}"""
    )