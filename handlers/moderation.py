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

    # لا أحد يقدر على المطور
    if target_id == OWNER_ID:
        return False

    # لا أحد يكتم أو يحظر نفسه
    if actor_id == target_id:
        return False


    actor_rank = get_rank(actor_id)
    target_rank = get_rank(target_id)


    actor_level = RANKS.get(actor_rank, 0)
    target_level = RANKS.get(target_rank, 0)

    print("Actor:", actor_id, actor_rank)
    print("Target:", target_id, target_rank)
    
    return actor_level > target_level
    

async def can_bot_action(update, context):

    bot = await context.bot.get_me()

    # إذا الهدف هو البوت
    if update.message.reply_to_message:
        if update.message.reply_to_message.from_user.id == bot.id:
            await update.message.reply_text(
                "❌ لا يمكن كتم أو حظر البوت"
            )
            return False


    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        bot.id
    )


    if not member.can_restrict_members:

        await update.message.reply_text(
            "❌ أعطِ البوت صلاحية حظر وكتم الأعضاء"
        )

        return False


    return True


def get_duration(text):

    parts = text.split()

    for part in parts:
        if part.endswith(("ث", "د", "س", "ي")):
            return parse_time(part)

    return None

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
    if not await can_bot_action(update, context):
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

    await context.bot.unban_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id
    )

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

    await context.bot.ban_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id
    )

    await update.message.reply_text(
        f"🚫 تم حظر {target.first_name}"
    )

    # بعد الحصول على target مباشرة

    if target.id == update.effective_user.id:
        await update.message.reply_text("❌ ما يمديك تكتم أو تحظر نفسك.")
        return

    if target.id == context.bot.id:
        await update.message.reply_text("❌ ما يمديك تكتم أو تحظر البوت.")
        return

    if target.id == OWNER_ID:
        await update.message.reply_text("❌ لا يمكن معاقبة المالك.")
        return

    if not has_permission(update.effective_user.id, target.id):
        await update.message.reply_text("❌ لا تملك صلاحية استخدام هذا الأمر.")
        return


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
            "❌ استخدم الكتم بالرد على الشخص أو الآيدي"
        )
        return


    # منع كتم المطور أو النفس أو البوت
    bot = await context.bot.get_me()

    if target.id == OWNER_ID:
        await update.message.reply_text(
            "❌ لا يمكن كتم المطور"
        )
        return


    if target.id == update.effective_user.id:
        await update.message.reply_text(
            "❌ لا يمكنك كتم نفسك"
        )
        return


    if target.id == bot.id:
        await update.message.reply_text(
            "❌ لا يمكن كتم البوت"
        )
        return


    # فحص الصلاحيات
    if not has_permission(
        update.effective_user.id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية كتم هذا الشخص"
        )
        return



    # التأكد أن البوت لديه صلاحية الكتم
    bot_member = await context.bot.get_chat_member(
        update.effective_chat.id,
        bot.id
    )


    if not bot_member.can_restrict_members:
        await update.message.reply_text(
            "❌ أعطِ البوت صلاحية تقييد الأعضاء"
        )
        return



    # قراءة المدة
    until_date = None

    parts = update.message.text.split()

    if len(parts) >= 2:
        until_date = parse_time(parts[1])



    from telegram import ChatPermissions


    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id,

        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        ),

            until_date=until_date
        )



    # حفظ في قاعدة البيانات
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
            "normal"
        )
    )


    conn.commit()
    conn.close()



    if until_date:
        await update.message.reply_text(
            f"🔇 تم كتم {target.first_name}\n"
            f"⏱ المدة: {update.message.text.split()[-1]}"
        )

    else:
        await update.message.reply_text(
            f"🔇 تم كتم {target.first_name}"
        )



async def unmute_user(update, context):

    if not update.message:
        return


    target = await get_target(update)

    if not target:
        await update.message.reply_text(
            "❌ استخدم الرد على الشخص أو الآيدي"
        )
        return


    # فك الكتم من تيليجرام
    from telegram import ChatPermissions


    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id,

        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )


    # حذف الكتم من قاعدة البيانات
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
        f"🔊 تم رفع الكتم عن {target.first_name}"
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