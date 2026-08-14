from telegram import Update
from telegram.ext import ContextTypes

from database import connect
from handlers.roles import get_rank


OWNER_ID = 8453977662


RANKS = {
    "عضو": 0,
    "مميز": 1,
    "ادمن": 2,
    "ادمن اساسي": 3,
    "نائب المالك": 4,
    "المالك": 5,
    "Dev": 6
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

    # ==========================================
    # تحديد الشخص
    # ==========================================

    target = await get_target(update)

    if not target:

        await update.message.reply_text(
            "❌ استخدم الأمر بالرد أو الآيدي أو اليوزر."
        )

        return

    # ==========================================
    # جلب الرتبة الحالية
    # ==========================================

    rank = get_rank(target.id)

    # ==========================================
    # قاعدة البيانات
    # ==========================================

    conn = connect()
    cur = conn.cursor()

    # الحظر
    cur.execute(
        """
        SELECT ban_type, until_time, reason, by_user
        FROM bans
        WHERE user_id=?
        """,
        (target.id,)
    )

    ban = cur.fetchone()

    # الكتم
    cur.execute(
        """
        SELECT mute_type, until_time, reason, by_user
        FROM mutes
        WHERE user_id=?
        """,
        (target.id,)
    )

    mute = cur.fetchone()

    conn.close()

    # ==========================================
    # معلومات الشخص
    # ==========================================

    username = ""

    if getattr(target, "username", None):
        username = f"\n🔗 @{target.username}"

    text = f"""
👤 {target.first_name}{username}

🆔 {target.id}

🛡 الرتبة: {rank}
"""

    # ==========================================
    # الحظر
    # ==========================================

    if ban:

        ban_type = (
            "عام"
            if ban[0] == "global"
            else "عادي"
        )

        text += f"""

🚫 الحظر: ✅ {ban_type}

⏱ المدة:
{ban[1] if ban[1] else "دائم"}

📝 السبب:
{ban[2] if ban[2] else "بدون سبب"}

👮 بواسطة:
{ban[3] if ban[3] else "غير معروف"}
"""

    else:

        text += """

🚫 الحظر: ❌ لا
"""

    # ==========================================
    # الكتم
    # ==========================================

    if mute:

        mute_type = (
            "عام"
            if mute[0] == "global"
            else "عادي"
        )

        text += f"""

🔇 الكتم: ✅ {mute_type}

⏱ المدة:
{mute[1] if mute[1] else "دائم"}

📝 السبب:
{mute[2] if mute[2] else "بدون سبب"}

👮 بواسطة:
{mute[3] if mute[3] else "غير معروف"}
"""

    else:

        text += """

🔇 الكتم: ❌ لا
"""

    # ==========================================
    # إرسال الكشف
    # ==========================================

    await update.message.reply_text(text)


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



async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    target = await get_target(update)

    if not target:
        await update.message.reply_text(
            "❌ استخدم الرد على الشخص أو الآيدي."
        )
        return


    # منع حظر النفس
    if target.id == update.effective_user.id:
        await update.message.reply_text(
            "❌ ما يمديك تحظر نفسك."
        )
        return


    # منع حظر البوت
    if target.id == context.bot.id:
        await update.message.reply_text(
            "❌ ما يمديك تحظر البوت."
        )
        return


    # منع حظر المطور
    if target.id == OWNER_ID:
        await update.message.reply_text(
            "❌ مايمديك تحظر المطور."
        )
        return


    # فحص الصلاحية
    if not has_permission(
        update.effective_user.id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية استخدام هذا الأمر."
        )
        return


    until = None

    parts = update.message.text.split()

    until = None
    reason = None


    if len(parts) >= 2:
        until = parse_time(parts[1])


    if len(parts) >= 3:
        reason = " ".join(parts[2:])
    else:
        reason = "بدون سبب"


    await context.bot.ban_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        until_date=until
    )


    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO bans
        (
            user_id,
            ban_type,
            until_time,
            reason,
            by_user
        )
        VALUES (?,?,?,?,?)
        """,
        (
            target.id,
            "normal",
            str(until) if until else None,
            reason,
            update.effective_user.id
        )
    )

    conn.commit()
    conn.close()


    await update.message.reply_text(
        f"🚫 تم حظر {target.first_name}\n"
        f"📝 السبب: {reason}"
    )

async def unban_user(update, context):

    if not update.message:
        return


    target = await get_target(update)


    if not target:
        await update.message.reply_text(
            "❌ استخدم رفع الحظر بالرد على الشخص أو الآيدي"
        )
        return


    if target.id == OWNER_ID:
        await update.message.reply_text(
            "❌ لا يمكن تعديل حظر المطور"
        )
        return


    if not has_permission(
        update.effective_user.id,
        target.id
    ):
        await update.message.reply_text(
            "❌ لا تملك صلاحية رفع الحظر عن هذا الشخص"
        )
        return


    try:

        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            only_if_banned=True
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ لم يتم رفع الحظر: {e}"
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
        f"✅ تم رفع الحظر عن {target.first_name}"
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



    # التأكد من صلاحية البوت
    bot_member = await context.bot.get_chat_member(
        update.effective_chat.id,
        bot.id
    )


    if not bot_member.can_restrict_members:
        await update.message.reply_text(
            "❌ أعطِ البوت صلاحية تقييد الأعضاء"
        )
        return



    until_date = None
    reason = None

    parts = update.message.text.split()


    if len(parts) >= 2:
        until_date = parse_time(parts[1])


    if len(parts) >= 3:
        reason = " ".join(parts[2:])
    else:
        reason = "بدون سبب"


    from telegram import ChatPermissions


    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id,

        permissions=ChatPermissions(
            can_send_messages=False
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
            mute_type,
            until_time,
            reason,
            by_user
        )
        VALUES (?,?,?,?,?)
        """,
        (
            target.id,
            "normal",
            str(until_date) if until_date else None,
            reason,
            update.effective_user.id
        )
    )


    conn.commit()
    conn.close()



    if until_date:
        await update.message.reply_text(
            f"🔇 تم كتم {target.first_name}\n"
            f"⏱ المدة: {parts[1]}\n"
            f"📝 السبب: {reason}"
        )

    else:
        await update.message.reply_text(
            f"🔇 تم كتم {target.first_name}\n"
            f"📝 السبب: {reason}"
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