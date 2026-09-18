import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from database import connect

from handlers.cache import (
    get_cached_user,
    get_user_data,
    get_user_data_sync,
    set_cached_points,
)


# =========================================================
# إعدادات
# =========================================================

POINT_FLUSH_DELAY = 0.5


# =========================================================
# طابور حفظ النقاط
# =========================================================

_pending_point_deltas = {}

_point_flush_task = None
_point_flush_lock = None


def _get_point_flush_lock():
    global _point_flush_lock

    if _point_flush_lock is None:
        _point_flush_lock = asyncio.Lock()

    return _point_flush_lock


# =========================================================
# إضافة تغيير نقاط إلى الطابور
# =========================================================

def _queue_point_delta(user_id, amount):

    _pending_point_deltas[user_id] = (
        _pending_point_deltas.get(user_id, 0)
        + amount
    )


# =========================================================
# تشغيل الحفظ بالخلفية
# =========================================================

def _schedule_point_flush():

    global _point_flush_task

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if (
        _point_flush_task is None
        or _point_flush_task.done()
    ):
        _point_flush_task = loop.create_task(
            _delayed_point_flush()
        )


async def _delayed_point_flush():

    try:

        await asyncio.sleep(
            POINT_FLUSH_DELAY
        )

        await flush_pending_points()

    except asyncio.CancelledError:
        raise

    except Exception as e:
        print(
            f"⚠️ خطأ في حفظ النقاط بالخلفية: {e}"
        )


# =========================================================
# حفظ النقاط المعلقة
# =========================================================

async def flush_pending_points():

    if not _pending_point_deltas:
        return

    lock = _get_point_flush_lock()

    async with lock:

        if not _pending_point_deltas:
            return

        # -------------------------------------------------
        # أخذ نسخة من التغييرات الحالية
        # -------------------------------------------------

        pending = dict(
            _pending_point_deltas
        )

        _pending_point_deltas.clear()

        # -------------------------------------------------
        # الحفظ خارج event loop
        # -------------------------------------------------

        try:

            await asyncio.to_thread(
                _save_point_deltas_sync,
                pending
            )

        except Exception as e:

            # -------------------------------------------------
            # إذا فشل الحفظ نرجع النقاط للطابور
            # -------------------------------------------------

            for user_id, amount in pending.items():

                _pending_point_deltas[user_id] = (
                    _pending_point_deltas.get(
                        user_id,
                        0
                    )
                    + amount
                )

            print(
                f"⚠️ فشل حفظ النقاط، تمت إعادتها للطابور: {e}"
            )

            raise


# =========================================================
# الحفظ الفعلي في قاعدة البيانات
# =========================================================

def _save_point_deltas_sync(
    pending
):

    if not pending:
        return

    conn = connect()

    try:

        cur = conn.cursor()

        for user_id, amount in pending.items():

            if amount == 0:
                continue

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
                """,
                (
                    user_id,
                    amount
                )
            )

        conn.commit()

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
# إضافة نقاط
# =========================================================

def add_points(
    user_id,
    amount
):

    # -----------------------------------------------------
    # محاولة الحصول على النقاط الحالية من الكاش
    # -----------------------------------------------------

    cached = get_cached_user(
        user_id
    )

    if cached is not None:

        current_points = (
            cached.get(
                "points",
                0
            )
            or 0
        )

    else:

        # -------------------------------------------------
        # أول مرة فقط:
        # نحاول تحميل المستخدم من قاعدة البيانات
        # -------------------------------------------------

        data = get_user_data_sync(
            user_id
        )

        if data is not None:

            current_points = (
                data.get(
                    "points",
                    0
                )
                or 0
            )

        else:

            current_points = 0

    # -----------------------------------------------------
    # حساب الرصيد الجديد
    # -----------------------------------------------------

    new_points = (
        current_points
        + amount
    )

    # -----------------------------------------------------
    # تحديث الكاش فورًا
    # -----------------------------------------------------

    set_cached_points(
        user_id,
        new_points
    )

    # -----------------------------------------------------
    # إضافة التغيير لطابور DB
    # -----------------------------------------------------

    _queue_point_delta(
        user_id,
        amount
    )

    # -----------------------------------------------------
    # تشغيل الحفظ بالخلفية
    # -----------------------------------------------------

    _schedule_point_flush()

    # -----------------------------------------------------
    # نفس القيمة التي كانت ترجعها الدالة القديمة
    # -----------------------------------------------------

    return new_points


# =========================================================
# جلب النقاط
# =========================================================

def get_points(
    user_id
):

    # -----------------------------------------------------
    # الكاش أولًا
    # -----------------------------------------------------

    cached = get_cached_user(
        user_id
    )

    if cached is not None:

        return (
            cached.get(
                "points",
                0
            )
            or 0
        )

    # -----------------------------------------------------
    # تحميل المستخدم من الكاش / DB
    # -----------------------------------------------------

    data = get_user_data_sync(
        user_id
    )

    if data is not None:

        points = (
            data.get(
                "points",
                0
            )
            or 0
        )

        set_cached_points(
            user_id,
            points
        )

        return points

    # -----------------------------------------------------
    # احتياط:
    # إذا لم يوجد المستخدم في users
    # نقرأ points مباشرة
    # -----------------------------------------------------

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT points
            FROM points
            WHERE user_id = ?
            """,
            (
                user_id,
            )
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

    # -----------------------------------------------------
    # الكاش / تحميل مرة واحدة عند الحاجة
    # -----------------------------------------------------

    data = await get_user_data(
        user_id
    )

    points = (
        data.get(
            "points",
            0
        )
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

    # -----------------------------------------------------
    # نتأكد أن جميع النقاط المعلقة محفوظة
    # قبل جلب الترتيب
    # -----------------------------------------------------

    try:

        await flush_pending_points()

    except Exception:
        pass

    user = update.effective_user

    # -----------------------------------------------------
    # DB خارج event loop
    # -----------------------------------------------------

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

    text = (
        "🏆 ترتيب اللاعبين\n\n"
    )

    for place, row in enumerate(
        rows,
        1
    ):

        name = (
            row[0]
            or "مستخدم"
        )

        points = (
            row[1]
            or 0
        )

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

        # -------------------------------------------------
        # تحديث بيانات المستخدم
        # -------------------------------------------------

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

        # -------------------------------------------------
        # جلب الترتيب
        # -------------------------------------------------

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
