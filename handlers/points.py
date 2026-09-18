import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from database import connect

from handlers.cache import (
    get_cached_user,
    get_user_data,
    set_cached_points,
)


# =========================================================
# إضافة نقاط
# =========================================================

def add_points(user_id, amount):

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO points
            (
                user_id,
                points
            )
            VALUES
            (
                ?,
                ?
            )
            ON CONFLICT (user_id)
            DO UPDATE SET
                points =
                    points.points
                    + EXCLUDED.points
            RETURNING points
            """,
            (
                user_id,
                amount
            )
        )

        result = cur.fetchone()

        conn.commit()

        if result:
            new_points = result[0]

            set_cached_points(
                user_id,
                new_points
            )

            return new_points

        return None

    except Exception:

        conn.rollback()
        raise

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# جلب النقاط
# =========================================================

def get_points(user_id):

    cached = get_cached_user(user_id)

    if cached is not None:
        return cached.get("points", 0)

    conn = connect()

    try:

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

        points = (
            result[0]
            if result
            else 0
        )

        set_cached_points(
            user_id,
            points
        )

        return points

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# نقاطي
# =========================================================

async def my_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    data = await get_user_data(user_id)

    points = (
        data.get("points", 0)
        if data
        else 0
    )

    await update.message.reply_text(
        f"🏆 نقاطك الحالية: {points}"
    )


# =========================================================
# الترتيب
# =========================================================

async def top_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user

    # =====================================================
    # تنفيذ DB خارج event loop
    # =====================================================

    rows = await asyncio.to_thread(
        _get_top_points_sync,
        user.id,
        user.first_name,
        user.username
    )

    if not rows:

        await update.message.reply_text(
            "❌ لا يوجد ترتيب حتى الآن"
        )

        return

    text = "🏆 ترتيب اللاعبين\n\n"

    for place, row in enumerate(
        rows,
        1
    ):

        name = row[0] or "مستخدم"
        points = row[1] or 0

        text += (
            f"{place} - {name} : "
            f"{points} نقطة\n"
        )

    await update.message.reply_text(
        text
    )


# =========================================================
# جلب الترتيب من DB
# =========================================================

def _get_top_points_sync(
    user_id,
    first_name,
    username
):

    conn = connect()

    try:

        cur = conn.cursor()

        # تحديث بيانات المستخدم
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
                first_name = EXCLUDED.first_name,
                username = EXCLUDED.username
            """,
            (
                user_id,
                first_name,
                username
            )
        )

        conn.commit()

        # جلب الترتيب
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

        return rows

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()
