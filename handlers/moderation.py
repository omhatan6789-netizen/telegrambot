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

    # المالك لا يُمس
    if target_id == OWNER_ID:
        return False

    # المالك يقدر على الجميع
    if actor_id == OWNER_ID:
        return True


    actor_rank = get_rank(actor_id)
    target_rank = get_rank(target_id)


    actor_level = RANKS.get(actor_rank, 0)
    target_level = RANKS.get(target_rank, 0)


    print("ACTOR:", actor_id, actor_rank)
    print("TARGET:", target_id, target_rank)


    return actor_level > target_level


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


import datetime


def parse_time(text):

    if not text:
        return None

    try:
        if text.endswith("ث"):
            return datetime.datetime.now() + datetime.timedelta(
                seconds=int(text[:-1])
            )

        if text.endswith("د"):
            return datetime.datetime.now() + datetime.timedelta(
                minutes=int(text[:-1])
            )

        if text.endswith("س"):
            return datetime.datetime.now() + datetime.timedelta(
                hours=int(text[:-1])
            )

        if text.endswith("ي"):
            return datetime.datetime.now() + datetime.timedelta(
                days=int(text[:-1])
            )

    except:
        return None


    return None



async def ban_user(update, context):

    if not update.message:
        return

    target = await get_target(update)

    if not target:
        await update.message.reply_text(
            "❌ استخدم: حظر بالرد أو الآيدي"
        )
        return


    if not has_permission(
        update.effective_user.id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية"
        )
        return


    if target.id == OWNER_ID:
        await update.message.reply_text(
            "❌ لا يمكن حظر المالك"
        )
        return


    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id
        )

    except Exception as e:
        await update.message.reply_text(
            "❌ تأكد أن البوت مشرف ولديه صلاحية الحظر"
        )
        return


    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO bans
        (
            user_id,
            ban_type,
            until_time
        )
        VALUES (?, ?, ?)
        """,
        (
            target.id,
            "normal",
            None
        )
    )

    conn.commit()
    conn.close()


    await update.message.reply_text(
        f"🚫 تم حظر {target.first_name}"
    )



async def unban_user(update, context):

    target = await get_target(update)

    if not target:
        await update.message.reply_text(
            "❌ استخدم الرد أو الآيدي"
        )
        return


    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM bans
        WHERE user_id=?
        """,
        (target.id,)
    )

    conn.commit()
    conn.close()


    await update.message.reply_text(
        "✅ تم رفع الحظر"
    )



async def global_ban(update, context):

    target = await get_target(update)

    if not target:
        return


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        INSERT OR REPLACE INTO bans
        (
            user_id,
            ban_type
        )
        VALUES (?,?)
        """,
        (
            target.id,
            "global"
        )
    )


    conn.commit()
    conn.close()


    await update.message.reply_text(
        "🌍 تم حظره عام"
    )



async def mute_user(update, context):

    if not update.message:
        return


    target = await get_target(update)


    if not target:
        await update.message.reply_text(
            "❌ استخدم: كتم بالرد أو الآيدي"
        )
        return



    if not has_permission(
        update.effective_user.id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية"
        )
        return



    if target.id == OWNER_ID:
        await update.message.reply_text(
            "❌ لا يمكن كتم المالك"
        )
        return



    import datetime

    until = datetime.datetime.now() + datetime.timedelta(
        hours=1
    )



    from telegram import ChatPermissions


    try:

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=False
            ),
            until_date=until
        )


    except:

        await update.message.reply_text(
            "❌ تأكد أن البوت مشرف ولديه صلاحية الكتم"
        )

        return



    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        INSERT OR REPLACE INTO mutes
        (
            user_id,
            mute_type,
            until_time
        )
        VALUES (?, ?, ?)
        """,
        (
            target.id,
            "normal",
            str(until)
        )
    )


    conn.commit()
    conn.close()



    await update.message.reply_text(
        f"🔇 تم كتم {target.first_name} لمدة ساعة"
    )



async def unmute_user(update, context):

    if not update.message:
        return


    target = await get_target(update)


    if not target:
        return



    if not has_permission(
        update.effective_user.id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية"
        )
        return



    from telegram import ChatPermissions


    try:

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )

    except:
        pass



    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM mutes
        WHERE user_id=?
        """,
        (target.id,)
    )

    conn.commit()
    conn.close()



    await update.message.reply_text(
        "🔊 تم رفع الكتم"
    )



async def global_mute(update, context):

    target = await get_target(update)

    if not target:
        return


    conn = connect()
    cur = conn.cursor()


    cur.execute(
        """
        INSERT OR REPLACE INTO mutes
        (
            user_id,
            mute_type
        )
        VALUES (?,?)
        """,
        (
            target.id,
            "global"
        )
    )


    conn.commit()
    conn.close()


    await update.message.reply_text(
        "🌍 تم إضافة كتم عام"
    )