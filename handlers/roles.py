from telegram import Update
from telegram.ext import ContextTypes

from database import connect


OWNER_ID = 8453977662


RANK_LEVELS = {
    "عضو": 0,
    "💎 مميز": 1,
    "🛡 ادمن": 2,
    "🟣 ادمن أساسي": 3,
    "🤍 نائب المالك": 4,
    "👑 المالك": 5
}


def get_rank(user_id):

    if user_id == OWNER_ID:
        return "👑 المالك"

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

    data = cur.fetchone()

    conn.close()

    if data and data[0]:
        return data[0]

    return "عضو"



async def roles_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text
    user = update.effective_user


    # =================
    # رتبتي
    # =================
    if text == "رتبتي":

        await update.message.reply_text(
            f"🛡 رتبتك: {get_rank(user.id)}"
        )

        return



    # =================
    # كشف المجموعة
    # =================
    if text == "كشف المجموعة":

        conn = connect()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT first_name, rank, user_id
            FROM users
            """
        )

        users = cur.fetchall()

        conn.close()


        owner = []
        deputy = []
        basic = []
        admins = []
        vip = []
        members = []


        # المالك الحقيقي
        try:
            owner_info = await context.bot.get_chat(OWNER_ID)

            owner.append(
                f"• {owner_info.first_name}"
            )

        except:

            owner.append(
                "• المالك"
            )



        for name, rank, user_id in users:


            # تجاهل المالك لأنه انضاف فوق
            if user_id == OWNER_ID:
                continue


            item = f"• {name}"


            if rank == "🤍 نائب المالك":

                deputy.append(item)


            elif rank == "🟣 ادمن أساسي":

                basic.append(item)


            elif rank == "🛡 ادمن":

                admins.append(item)


            elif rank == "💎 مميز":

                vip.append(item)


            else:

                members.append(item)



        msg = f"""
📋 كشف رتب المجموعة

👑 المالك:
{chr(10).join(owner)}


🤍 نائب المالك:
{chr(10).join(deputy) if deputy else "لا يوجد"}


🟣 الادمن الأساسي:
{chr(10).join(basic) if basic else "لا يوجد"}


🛡 الادمن:
{chr(10).join(admins) if admins else "لا يوجد"}


💎 المميزين:
{chr(10).join(vip) if vip else "لا يوجد"}


👤 الأعضاء:
{chr(10).join(members) if members else "لا يوجد"}
"""

        await update.message.reply_text(msg)

        return


async def change_rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user
    text = update.message.text


    if text.startswith("رفع نائب المالك"):
        new_rank = "🤍 نائب المالك"

    elif text.startswith("رفع ادمن اساسي"):
        new_rank = "🟣 ادمن أساسي"

    elif text.startswith("رفع ادمن"):
        new_rank = "🛡 ادمن"

    elif text.startswith("رفع مميز"):
        new_rank = "💎 مميز"

    elif text.startswith("تنزيل نائب المالك"):
        new_rank = "عضو"

    elif text.startswith("تنزيل ادمن اساسي"):
        new_rank = "عضو"

    elif text.startswith("تنزيل ادمن"):
        new_rank = "عضو"

    elif text.startswith("تنزيل مميز"):
        new_rank = "عضو"

    else:
        return


    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ لازم ترد على رسالة الشخص"
        )
        return


    target = update.message.reply_to_message.from_user


    if target.id == OWNER_ID:
        await update.message.reply_text(
            "❌ لا يمكن تعديل رتبة المالك"
        )
        return


    actor_rank = get_rank(actor.id)


    if RANK_LEVELS.get(actor_rank, 0) <= RANK_LEVELS.get(new_rank, 0):
        await update.message.reply_text(
            "❌ لا تملك صلاحية هذه الرتبة"
        )
        return


    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET rank=?
        WHERE user_id=?
        """,
        (
            new_rank,
            target.id
        )
    )

    conn.commit()
    conn.close()


    await update.message.reply_text(
        f"✅ تم تعديل رتبة {target.first_name}\n"
        f"🛡 الرتبة: {new_rank}"
    )  