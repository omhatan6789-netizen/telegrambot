from telegram import Update
from telegram.ext import ContextTypes

from database import connect

from handlers.roles import (
    get_rank,
    is_primary_developer,
    is_secondary_developer
)


OWNER_ID = 8331154497


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

    # الشخص ما يقدر يعدل نفسه
    if actor_id == target_id:
        return False

    # Dev الأساسي يقدر على الجميع
    if is_primary_developer(actor_id):
        return True

    # ممنوع أي شخص يعدل Dev الأساسي
    if target_id == OWNER_ID:
        return False

    # Dev المساعد
    if is_secondary_developer(actor_id):

        # المساعد ما يقدر على مساعد آخر
        if is_secondary_developer(target_id):
            return False

        return True

    # باقي الرتب
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

async def get_target(update: Update, context=None):

    if not update.message:
        return None


    message = update.message


    # بالرد
    if message.reply_to_message:

        return message.reply_to_message.from_user



    text = message.text or ""

    parts = text.split()


    if len(parts) < 2:
        return None


    value = parts[-1]


    # ID

    if value.isdigit():

        user_id = int(value)


        class User:
            pass


        user = User()
        user.id = user_id
        user.first_name = str(user_id)


        if context:

            try:

                info = await context.bot.get_chat(
                    user_id
                )

                user.first_name = (
                    info.first_name
                    or str(user_id)
                )

                user.username = getattr(
                    info,
                    "username",
                    None
                )


            except:
                pass


        return user



    # USERNAME

    if value.startswith("@"):

        if context:

            try:

                info = await context.bot.get_chat(
                    value
                )

                return info


            except:
                pass



    return None


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

async def unban_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    # ==========================================
    # تحديد الشخص
    # ==========================================

    target = await get_target(update)

    # ==========================================
    # إذا لم نجده في قاعدة البيانات
    # نحاول أخذ الآيدي مباشرة من الأمر
    # ==========================================

    if not target:

        text = (update.message.text or "").strip()
        parts = text.split()

        if len(parts) >= 2:

            value = parts[1].strip()

            # آيدي مباشر
            if value.isdigit():

                class User:
                    pass

                target = User()
                target.id = int(value)
                target.first_name = value

            # يوزر
            elif value.startswith("@"):

                try:

                    target = await context.bot.get_chat(
                        value
                    )

                except Exception:

                    target = None

        if not target:

            await update.message.reply_text(
                "❌ استخدم رفع الحظر بالرد أو اليوزر أو الآيدي."
            )
            return

    # ==========================================
    # المطور الأساسي
    # ==========================================

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكن رفع أو تعديل حظر المطور الأساسي."
        )
        return

    # ==========================================
    # الصلاحية
    # ==========================================

    if not has_permission(
        update.effective_user.id,
        target.id
    ):

        await update.message.reply_text(
            "❌ لا تملك صلاحية رفع الحظر عن هذا الشخص."
        )
        return

    # ==========================================
    # رفع الحظر من تيليجرام
    # ==========================================

    try:

        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ لم أستطع رفع الحظر.\n\n{e}"
        )
        return

    # ==========================================
    # حذف سجل الحظر
    # ==========================================

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

    # ==========================================
    # الاسم
    # ==========================================

    name = getattr(
        target,
        "first_name",
        str(target.id)
    )

    # ==========================================
    # تم
    # ==========================================

    await update.message.reply_text(
        f"✅ تم رفع الحظر عن {name}"
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



async def unmute_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    # ==========================================
    # تحديد الشخص
    # ==========================================

    target = await get_target(
        update,
        context
    )


    if not target:

        await update.message.reply_text(
            "❌ استخدم رفع الكتم بالرد أو اليوزر أو الآيدي."
        )

        return



    # ==========================================
    # حماية المطور الأساسي
    # ==========================================

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكن تعديل المطور الأساسي."
        )

        return



    # ==========================================
    # منع الشخص من رفع كتم نفسه
    # ==========================================

    if target.id == update.effective_user.id:

        await update.message.reply_text(
            "❌ لا يمكنك رفع الكتم عن نفسك."
        )

        return



    # ==========================================
    # الصلاحية
    # ==========================================

    if not has_permission(
        update.effective_user.id,
        target.id
    ):

        await update.message.reply_text(
            "❌ لا تملك صلاحية رفع الكتم عن هذا الشخص."
        )

        return



    # ==========================================
    # رفع الكتم من تيليجرام
    # ==========================================

    from telegram import ChatPermissions


    try:

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,

            permissions=ChatPermissions.all_permissions()
        )


    except Exception as e:

        await update.message.reply_text(
            f"❌ لم أستطع رفع الكتم.\n\n{e}"
        )

        return



    # ==========================================
    # حذف سجل الكتم
    # ==========================================

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



    # ==========================================
    # الرد
    # ==========================================

    name = getattr(
        target,
        "first_name",
        str(target.id)
    )


    await update.message.reply_text(
        f"🔊 تم رفع الكتم عن {name}"
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