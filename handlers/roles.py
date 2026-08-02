from telegram import Update
from telegram.ext import ContextTypes

from database import connect


OWNER_ID = 8453977662


RANK_LEVELS = {
    "عضو": 0,
    "مميز": 1,
    "ادمن": 2,
    "ادمن اساسي": 3,
    "نائب المالك": 4,
    "المالك": 5
}


def get_rank(user_id):

    if user_id == OWNER_ID:
        return "المالك"

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
            f"رتبتك: {get_rank(user.id)}"
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
            SELECT rank, user_id
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


        async def get_name(user_id):

            try:
                info = await context.bot.get_chat(user_id)

                if info.username:
                    return f"@{info.username}"

                return str(user_id)

            except:
                return str(user_id)



        # المالك
        owner.append(
            await get_name(OWNER_ID)
        )


        for rank, user_id in users:

            if user_id == OWNER_ID:
                continue


            name = await get_name(user_id)


            if rank == "نائب المالك":
                deputy.append(name)


            elif rank == "ادمن اساسي":
                basic.append(name)


            elif rank == "ادمن":
                admins.append(name)


            elif rank == "مميز":
                vip.append(name)



        msg = """
• قائمة المالك الوحيد
━━━━━━━━━━━━
"""


        for i, x in enumerate(owner, 1):
            msg += f"{i} - {x}\n"



        msg += """

• قائمة نُوَّاب المالك
━━━━━━━━━━━━
"""

        if deputy:
            for i, x in enumerate(deputy, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"



        msg += """

• قائمة الادمنية الاساسيين
━━━━━━━━━━━━
"""

        if basic:
            for i, x in enumerate(basic, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"



        msg += """

• قائمة الادمنية
━━━━━━━━━━━━
"""

        if admins:
            for i, x in enumerate(admins, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"



        msg += """

• قائمة المميزين
━━━━━━━━━━━━
"""

        if vip:
            for i, x in enumerate(vip, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"



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
        new_rank = "نائب المالك"

    elif text.startswith("رفع ادمن اساسي"):
        new_rank = "ادمن اساسي"

    elif text.startswith("رفع ادمن"):
        new_rank = "ادمن"

    elif text.startswith("رفع مميز"):
        new_rank = "مميز"

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
        f"تم تعديل رتبة {target.first_name}\n"
        f"الرتبةالجديدة: {new_rank}"
    )  