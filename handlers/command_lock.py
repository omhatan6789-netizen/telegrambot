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
    "المالك": 5
}


# حفظ عمليات القفل المؤقتة
lock_sessions = {}



def can_lock(user_id):

    if user_id == OWNER_ID:
        return True

    rank = get_rank(user_id)

    return RANKS.get(rank, 0) >= RANKS["نائب المالك"]



async def lock_command_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    if not can_lock(user_id):

        await update.message.reply_text(
            "❌ هذا الأمر للمالك ونائب المالك فقط"
        )

        return



    text = update.message.text.split(maxsplit=2)


    if len(text) < 3:

        await update.message.reply_text(
            "❌ مثال:\nقفل امر ايدي"
        )

        return



    command = text[2]


    lock_sessions[user_id] = command



    await update.message.reply_text(
        f"""
• حسنًا اختر الرتبة التي تريدها :

1- `المالك`
2- `نائب المالك`
3- `ادمن اساسي`
4- `ادمن`
5- `مميز`


- سيتم وضع امر ↤︎ `{command}` له فقط
""",
        parse_mode="Markdown"
    )





async def choose_lock_rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    if user_id not in lock_sessions:
        return



    rank = update.message.text.strip()



    if rank not in [
        "المالك",
        "نائب المالك",
        "ادمن اساسي",
        "ادمن",
        "مميز"
    ]:
        return



    command = lock_sessions[user_id]



    conn = connect()
    cur = conn.cursor()



    cur.execute(
        """
        INSERT OR REPLACE INTO command_locks
        (
            command,
            min_rank
        )
        VALUES (?,?)
        """,
        (
            command,
            rank
        )
    )



    conn.commit()
    conn.close()



    del lock_sessions[user_id]



    await update.message.reply_text(
        f"""
🔒 تم قفل الأمر:

`{command}`

الرتبة المطلوبة:
`{rank}`
""",
        parse_mode="Markdown"
    )