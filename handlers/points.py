from telegram import Update
from telegram.ext import ContextTypes

from database import connect


# =====================
# إضافة نقاط
# =====================

def add_points(user_id, amount):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO points
        (
            user_id,
            points
        )
        VALUES
        (
            ?,
            0
        )
        """,
        (user_id,)
    )

    cur.execute(
        """
        UPDATE points
        SET points = points + ?
        WHERE user_id = ?
        """,
        (
            amount,
            user_id
        )
    )

    conn.commit()
    conn.close()


# =====================
# جلب النقاط
# =====================

def get_points(user_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT points
        FROM points
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return 0

    return result[0]


# =====================
# نقاطي
# =====================

async def my_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    points = get_points(
        update.effective_user.id
    )

    await update.message.reply_text(
        f"🏆 نقاطك الحالية: {points}"
    )


# =====================
# الترتيب
# =====================

async def top_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    # تحديث اسم المستخدم الحالي
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users
        (
            user_id,
            first_name,
            username
        )
        VALUES
        (
            ?,
            ?,
            ?
        )
        ON CONFLICT(user_id)
        DO UPDATE SET
            first_name = excluded.first_name,
            username = excluded.username
        """,
        (
            update.effective_user.id,
            update.effective_user.first_name,
            update.effective_user.username
        )
    )

    conn.commit()
    conn.close()



    # جلب الترتيب
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            users.first_name,
            points.points
        FROM points

        LEFT JOIN users
        ON users.user_id = points.user_id

        ORDER BY points.points DESC

        LIMIT 10
        """
    )

    rows = cur.fetchall()

    conn.close()



    if not rows:

        await update.message.reply_text(
            "❌ لا يوجد ترتيب حتى الآن"
        )

        return



    text = "🏆 ترتيب اللاعبين\n\n"


    place = 1

    for row in rows:

        name = row[0] or "مستخدم"

        pts = row[1] or 0


        text += (
            f"{place} - {name} : "
            f"{pts} نقطة\n"
        )


        place += 1



    await update.message.reply_text(
        text
    )