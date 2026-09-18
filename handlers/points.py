import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from database import connect

from handlers.cache import (
    get_cached_user,
    get_user_data,
    get_user_data_sync,
    set_cached_points,
    increment_cached_messages,
)

POINT_FLUSH_DELAY = 0.5

OWNER_ID = 8453977662

POINTS_PER_MESSAGE = 10

_pending_point_deltas = {}

_point_flush_task = None
_point_flush_lock = None


def _get_point_flush_lock():
    global _point_flush_lock

    if _point_flush_lock is None:
        _point_flush_lock = asyncio.Lock()

    return _point_flush_lock


def _queue_point_delta(user_id, amount):
    _pending_point_deltas[user_id] = (
        _pending_point_deltas.get(user_id, 0)
        + amount
    )


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
        await asyncio.sleep(POINT_FLUSH_DELAY)
        await flush_pending_points()

    except asyncio.CancelledError:
        raise

    except Exception as e:
        print(
            f"⚠️ خطأ في حفظ النقاط بالخلفية: {e}"
        )


async def flush_pending_points():

    if not _pending_point_deltas:
        return

    lock = _get_point_flush_lock()

    async with lock:

        if not _pending_point_deltas:
            return

        pending = dict(
            _pending_point_deltas
        )

        _pending_point_deltas.clear()

        try:

            await asyncio.to_thread(
                _save_point_deltas_sync,
                pending
            )

        except Exception as e:

            for user_id, amount in pending.items():

                _pending_point_deltas[user_id] = (
                    _pending_point_deltas.get(user_id, 0)
                    + amount
                )

            print(
                f"⚠️ فشل حفظ النقاط، تمت إعادتها للطابور: {e}"
            )

            raise


def _save_point_deltas_sync(pending):

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


def add_points(user_id, amount):

    cached = get_cached_user(user_id)

    if cached is not None:

        current_points = (
            cached.get("points", 0) or 0
        )

    else:

        data = get_user_data_sync(user_id)

        if data is not None:

            current_points = (
                data.get("points", 0) or 0
            )

        else:

            current_points = 0

    new_points = current_points + amount

    set_cached_points(
        user_id,
        new_points
    )

    _queue_point_delta(
        user_id,
        amount
    )

    _schedule_point_flush()

    return new_points


def get_points(user_id):

    cached = get_cached_user(user_id)

    if cached is not None:

        return (
            cached.get("points", 0) or 0
        )

    data = get_user_data_sync(user_id)

    if data is not None:

        points = (
            data.get("points", 0) or 0
        )

        set_cached_points(
            user_id,
            points
        )

        return points

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


def _get_user_id_from_update(update):

    if not update.message:
        return None

    if update.message.reply_to_message:

        replied_user = (
            update.message.reply_to_message.from_user
        )

        if replied_user:
            return replied_user.id

    return update.effective_user.id


async def add_points_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    if user.id != OWNER_ID:

        await update.message.reply_text(
            "❌ هذا الأمر مخصص للمالك فقط."
        )

        return

    text = update.message.text or ""

    parts = text.strip().split()

    if len(parts) != 2:

        await update.message.reply_text(
            "❌ الاستخدام الصحيح:\n\n"
            "اضف 500\n\n"
            "ويُفضل استخدام الأمر بالرد على الشخص."
        )

        return

    try:

        amount = int(parts[1])

    except ValueError:

        await update.message.reply_text(
            "❌ عدد النقاط غير صحيح."
        )

        return

    if amount <= 0:

        await update.message.reply_text(
            "❌ يجب أن يكون عدد النقاط أكبر من صفر."
        )

        return

    target_id = _get_user_id_from_update(
        update
    )

    if target_id is None:
        return

    new_points = add_points(
        target_id,
        amount
    )

    if (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
    ):

        target_name = (
            update.message.reply_to_message.from_user.first_name
            or "المستخدم"
        )

        await update.message.reply_text(
            f"✅ تمت إضافة {amount} نقطة إلى {target_name}.\n\n"
            f"🏆 نقاطه الآن: {new_points}"
        )

    else:

        await update.message.reply_text(
            f"✅ تمت إضافة {amount} نقطة لك.\n\n"
            f"🏆 نقاطك الآن: {new_points}"
        )



async def remove_points_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    if user.id != OWNER_ID:

        await update.message.reply_text(
            "❌ هذا الأمر مخصص للمالك فقط."
        )

        return

    text = update.message.text or ""

    parts = text.strip().split()

    if len(parts) != 2:

        await update.message.reply_text(
            "❌ الاستخدام الصحيح:\n\n"
            "خصم 500\n\n"
            "ويجب استخدام الأمر بالرد على الشخص."
        )

        return

    try:

        amount = int(parts[1])

    except ValueError:

        await update.message.reply_text(
            "❌ عدد النقاط غير صحيح."
        )

        return

    if amount <= 0:

        await update.message.reply_text(
            "❌ يجب أن يكون عدد النقاط أكبر من صفر."
        )

        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "❌ يجب استخدام الأمر بالرد على الشخص."
        )

        return

    target_user = (
        update.message.reply_to_message.from_user
    )

    if not target_user:

        return

    target_id = target_user.id

    current_points = get_points(
        target_id
    )

    if current_points < amount:

        await update.message.reply_text(
            "❌ لا يمكن الخصم.\n\n"
            f"🏆 نقاطه الحالية: {current_points}\n"
            f"💰 المطلوب خصمه: {amount}"
        )

        return

    remaining_points = add_points(
        target_id,
        -amount
    )

    target_name = (
        target_user.first_name
        or "المستخدم"
    )

    await update.message.reply_text(
        f"✅ تم خصم {amount} نقطة من {target_name}.\n\n"
        f"🏆 نقاطه المتبقية: {remaining_points}"
    )

def _add_messages_sync(user_id, amount):

    conn = connect()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users
            (
                user_id,
                messages
            )
            VALUES
            (
                ?,
                ?
            )
            ON CONFLICT(user_id)
            DO UPDATE SET
                messages =
                    COALESCE(users.messages, 0)
                    + EXCLUDED.messages
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


async def sell_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    text = update.message.text or ""

    parts = text.strip().split()

    if len(parts) != 3:

        await update.message.reply_text(
            "❌ الاستخدام الصحيح:\n\n"
            "بيع نقاطي 200"
        )

        return

    try:

        amount = int(parts[2])

    except ValueError:

        await update.message.reply_text(
            "❌ عدد النقاط غير صحيح."
        )

        return

    if amount <= 0:

        await update.message.reply_text(
            "❌ يجب أن يكون عدد النقاط أكبر من صفر."
        )

        return

    user_id = user.id

    current_points = get_points(
        user_id
    )

    if current_points < amount:

        await update.message.reply_text(
            "❌ ما عندك نقاط كافية.\n\n"
            f"🏆 نقاطك الحالية: {current_points}\n"
            f"💰 المطلوب: {amount}"
        )

        return

    messages_to_add = (
        amount * POINTS_PER_MESSAGE
    )

    remaining_points = add_points(
        user_id,
        -amount
    )

    try:

        await asyncio.to_thread(
            _add_messages_sync,
            user_id,
            messages_to_add
        )

        increment_cached_messages(
            user_id,
            messages_to_add
        )

    except Exception as e:

        add_points(
            user_id,
            amount
        )

        await update.message.reply_text(
            "❌ حدث خطأ أثناء إضافة الرسائل، "
            "وتمت إعادة النقاط.\n\n"
            f"الخطأ: {e}"
        )

        return

    await update.message.reply_text(
        f"✅ تم بيع {amount} نقطة.\n\n"
        f"💬 حصلت على {messages_to_add} رسالة.\n"
        f"🏆 نقاطك المتبقية: {remaining_points}"
    )


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


async def top_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    try:

        await flush_pending_points()

    except Exception:
        pass

    user = update.effective_user

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


def _get_top_points_sync(
    user_id,
    first_name,
    username
):

    conn = connect()

    try:

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
