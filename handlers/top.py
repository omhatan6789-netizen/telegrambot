import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import connect


# =========================================================
# الإعدادات
# =========================================================

TOP_PREFIX = "top"

# أنواع التوب
TOP_POINTS = "points"
TOP_ACTIVITY = "activity"
TOP_ROBBERY = "robbery"
TOP_LUCK = "luck"
TOP_GLOBAL_POINTS = "global_points"


# =========================================================
# أدوات قاعدة البيانات
# =========================================================

def _ensure_top_tables_sync():
    conn = connect()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_points (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                points BIGINT DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_activity (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                messages BIGINT DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_robbery_stats (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                stolen BIGINT DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_luck_stats (
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                wins BIGINT DEFAULT 0,
                losses BIGINT DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        conn.commit()

    finally:
        conn.close()


def create_top_tables():
    _ensure_top_tables_sync()


# =========================================================
# تحديث تفاعل المستخدم
# =========================================================

def increment_group_activity_sync(
    chat_id: int,
    user_id: int,
    amount: int = 1
):
    conn = connect()

    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO group_activity (
                chat_id,
                user_id,
                messages
            )
            VALUES (?, ?, ?)
            ON CONFLICT (chat_id, user_id)
            DO UPDATE SET
                messages = group_activity.messages + excluded.messages
        """, (
            chat_id,
            user_id,
            amount
        ))

        conn.commit()

    finally:
        conn.close()


async def increment_group_activity(
    chat_id: int,
    user_id: int,
    amount: int = 1
):
    import asyncio

    await asyncio.to_thread(
        increment_group_activity_sync,
        chat_id,
        user_id,
        amount
    )


# =========================================================
# تحديث نقاط القروب
# =========================================================

def add_group_points_sync(
    chat_id: int,
    user_id: int,
    amount: int
):
    if not chat_id or not user_id or not amount:
        return

    conn = connect()

    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO group_points (
                chat_id,
                user_id,
                points
            )
            VALUES (?, ?, ?)
            ON CONFLICT (chat_id, user_id)
            DO UPDATE SET
                points = group_points.points + excluded.points
        """, (
            chat_id,
            user_id,
            amount
        ))

        conn.commit()

    finally:
        conn.close()


async def add_group_points(
    chat_id: int,
    user_id: int,
    amount: int
):
    import asyncio

    await asyncio.to_thread(
        add_group_points_sync,
        chat_id,
        user_id,
        amount
    )


# =========================================================
# تحديث الزرف
# =========================================================

def add_group_robbery_sync(
    chat_id: int,
    user_id: int,
    amount: int
):
    if not chat_id or not user_id or amount <= 0:
        return

    conn = connect()

    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO group_robbery_stats (
                chat_id,
                user_id,
                stolen
            )
            VALUES (?, ?, ?)
            ON CONFLICT (chat_id, user_id)
            DO UPDATE SET
                stolen = group_robbery_stats.stolen + excluded.stolen
        """, (
            chat_id,
            user_id,
            amount
        ))

        conn.commit()

    finally:
        conn.close()


async def add_group_robbery(
    chat_id: int,
    user_id: int,
    amount: int
):
    import asyncio

    await asyncio.to_thread(
        add_group_robbery_sync,
        chat_id,
        user_id,
        amount
    )


def reset_group_robbery_sync(
    chat_id: int,
    user_id: int
):
    conn = connect()

    try:
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM group_robbery_stats
            WHERE chat_id = ?
              AND user_id = ?
        """, (
            chat_id,
            user_id
        ))

        conn.commit()

    finally:
        conn.close()


async def reset_group_robbery(
    chat_id: int,
    user_id: int
):
    import asyncio

    await asyncio.to_thread(
        reset_group_robbery_sync,
        chat_id,
        user_id
    )


# =========================================================
# تحديث الحظ
# =========================================================

def add_luck_result_sync(
    chat_id: int,
    user_id: int,
    won: bool
):
    conn = connect()

    try:
        cur = conn.cursor()

        if won:
            cur.execute("""
                INSERT INTO group_luck_stats (
                    chat_id,
                    user_id,
                    wins,
                    losses
                )
                VALUES (?, ?, 1, 0)
                ON CONFLICT (chat_id, user_id)
                DO UPDATE SET
                    wins = group_luck_stats.wins + 1
            """, (
                chat_id,
                user_id
            ))
        else:
            cur.execute("""
                INSERT INTO group_luck_stats (
                    chat_id,
                    user_id,
                    wins,
                    losses
                )
                VALUES (?, ?, 0, 1)
                ON CONFLICT (chat_id, user_id)
                DO UPDATE SET
                    losses = group_luck_stats.losses + 1
            """, (
                chat_id,
                user_id
            ))

        conn.commit()

    finally:
        conn.close()


async def add_luck_result(
    chat_id: int,
    user_id: int,
    won: bool
):
    import asyncio

    await asyncio.to_thread(
        add_luck_result_sync,
        chat_id,
        user_id,
        won
    )


# =========================================================
# اسم المستخدم
# =========================================================

def _display_name(row):
    first_name = row.get("first_name") if isinstance(row, dict) else None
    username = row.get("username") if isinstance(row, dict) else None
    user_id = row.get("user_id") if isinstance(row, dict) else None

    name = first_name or username or str(user_id)

    return html.escape(str(name))


# =========================================================
# جلب المستخدمين
# =========================================================

def _get_user_rows_sync(user_ids):
    if not user_ids:
        return {}

    conn = connect()

    try:
        cur = conn.cursor()

        placeholders = ",".join(["?"] * len(user_ids))

        cur.execute(
            f"""
            SELECT
                user_id,
                first_name,
                username
            FROM users
            WHERE user_id IN ({placeholders})
            """,
            tuple(user_ids)
        )

        rows = cur.fetchall()

        result = {}

        for row in rows:
            if hasattr(row, "keys"):
                result[int(row["user_id"])] = {
                    "user_id": int(row["user_id"]),
                    "first_name": row["first_name"],
                    "username": row["username"]
                }
            else:
                result[int(row[0])] = {
                    "user_id": int(row[0]),
                    "first_name": row[1],
                    "username": row[2]
                }

        return result

    finally:
        conn.close()


# =========================================================
# جلب التوب
# =========================================================

def _get_local_top_sync(
    chat_id: int,
    top_type: str
):
    conn = connect()

    try:
        cur = conn.cursor()

        if top_type == TOP_POINTS:

            cur.execute("""
                SELECT
                    user_id,
                    points
                FROM group_points
                WHERE chat_id = ?
                  AND points > 0
                ORDER BY points DESC
                LIMIT 10
            """, (chat_id,))

            rows = cur.fetchall()

            return [
                {
                    "user_id": int(row[0]),
                    "value": int(row[1])
                }
                for row in rows
            ]

        if top_type == TOP_ACTIVITY:

            cur.execute("""
                SELECT
                    user_id,
                    messages
                FROM group_activity
                WHERE chat_id = ?
                  AND messages > 0
                ORDER BY messages DESC
                LIMIT 10
            """, (chat_id,))

            rows = cur.fetchall()

            return [
                {
                    "user_id": int(row[0]),
                    "value": int(row[1])
                }
                for row in rows
            ]

        if top_type == TOP_ROBBERY:

            cur.execute("""
                SELECT
                    user_id,
                    stolen
                FROM group_robbery_stats
                WHERE chat_id = ?
                  AND stolen > 0
                ORDER BY stolen DESC
                LIMIT 10
            """, (chat_id,))

            rows = cur.fetchall()

            return [
                {
                    "user_id": int(row[0]),
                    "value": int(row[1])
                }
                for row in rows
            ]

        if top_type == TOP_LUCK:

            cur.execute("""
                SELECT
                    user_id,
                    wins,
                    losses
                FROM group_luck_stats
                WHERE chat_id = ?
                  AND wins > 0
                ORDER BY
                    wins DESC,
                    losses ASC,
                    user_id ASC
                LIMIT 10
            """, (chat_id,))

            rows = cur.fetchall()

            return [
                {
                    "user_id": int(row[0]),
                    "wins": int(row[1]),
                    "losses": int(row[2])
                }
                for row in rows
            ]

        return []

    finally:
        conn.close()


def _get_global_top_sync():

    conn = connect()

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT
                points.user_id,
                points.points
            FROM points
            WHERE points.points > 0
            ORDER BY points.points DESC
            LIMIT 10
        """)

        rows = cur.fetchall()

        return [
            {
                "user_id": int(row[0]),
                "value": int(row[1])
            }
            for row in rows
        ]

    finally:
        conn.close()


# =========================================================
# القائمة الرئيسية
# =========================================================

def top_main_keyboard(owner_id: int, message_id: int):

    prefix = f"{TOP_PREFIX}:{owner_id}:{message_id}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "توب النقاط🎖️",
                callback_data=f"{prefix}:{TOP_POINTS}"
            ),
            InlineKeyboardButton(
                "توب المتفاعلين 💬",
                callback_data=f"{prefix}:{TOP_ACTIVITY}"
            )
        ],
        [
            InlineKeyboardButton(
                "توب الحرامية 😈",
                callback_data=f"{prefix}:{TOP_ROBBERY}"
            ),
            InlineKeyboardButton(
                "توب افضل حظ 🎲",
                callback_data=f"{prefix}:{TOP_LUCK}"
            )
        ],
        [
            InlineKeyboardButton(
                "توب النقاط عام 🏅",
                callback_data=f"{prefix}:{TOP_GLOBAL_POINTS}"
            )
        ]
    ])


def top_result_keyboard(
    owner_id: int,
    message_id: int
):

    prefix = f"{TOP_PREFIX}:{owner_id}:{message_id}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "↪️ رجوع",
                callback_data=f"{prefix}:back"
            ),
            InlineKeyboardButton(
                "• اخفاء التوب",
                callback_data=f"{prefix}:hide"
            )
        ]
    ])


# =========================================================
# أمر توب
# =========================================================

async def top_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    text = (
        "<b>— اهلاً بك عزيزي في قائمة الاوامر :</b>\n"
        "<b>• اختر نوع التوب من الازرار الي تحت .</b>\n"
        "—————————————————"
    )

    sent = await message.reply_text(
        text,
        parse_mode="HTML"
    )

    # Telegram يعطي message_id بعد الإرسال
    await sent.edit_reply_markup(
        reply_markup=top_main_keyboard(
            user.id,
            sent.message_id
        )
    )


# =========================================================
# إنشاء نص التوب
# =========================================================

async def _build_top_text(
    query,
    top_type: str
):

    message = query.message
    chat = message.chat

    chat_id = chat.id

    if top_type == TOP_POINTS:

        rows = await __import__("asyncio").to_thread(
            _get_local_top_sync,
            chat_id,
            TOP_POINTS
        )

        title = (
            f"<b>توب أغنى ناس بـ قروب —— "
            f"{html.escape(chat.title or 'القروب')} :</b>"
        )

        if not rows:
            return title + "\n\n• ما فيه بيانات حاليًا ."

        user_ids = [x["user_id"] for x in rows]

        users = await __import__("asyncio").to_thread(
            _get_user_rows_sync,
            user_ids
        )

        lines = []

        for index, item in enumerate(rows, 1):
            uid = item["user_id"]
            name = users.get(
                uid,
                {
                    "first_name": str(uid),
                    "username": None,
                    "user_id": uid
                }
            )

            display = _display_name(name)

            lines.append(
                f"{index}- "
                f'<a href="tg://user?id={uid}">{display}</a>'
                f" ↤︎ {item['value']:,}"
            )

        return title + "\n\n" + "\n".join(lines)

    if top_type == TOP_ACTIVITY:

        rows = await __import__("asyncio").to_thread(
            _get_local_top_sync,
            chat_id,
            TOP_ACTIVITY
        )

        title = "<b>توب اكثر ناس يسولفون بالقروب 🗣️:</b>"

        if not rows:
            return title + "\n\n• ما فيه بيانات حاليًا ."

        user_ids = [x["user_id"] for x in rows]

        users = await __import__("asyncio").to_thread(
            _get_user_rows_sync,
            user_ids
        )

        lines = []

        for index, item in enumerate(rows, 1):
            uid = item["user_id"]

            name = users.get(
                uid,
                {
                    "first_name": str(uid),
                    "username": None,
                    "user_id": uid
                }
            )

            display = _display_name(name)

            lines.append(
                f"{index}- "
                f'<a href="tg://user?id={uid}">{display}</a>'
                f" ↤︎ {item['value']:,}"
            )

        return title + "\n\n" + "\n".join(lines)

    if top_type == TOP_ROBBERY:

        rows = await __import__("asyncio").to_thread(
            _get_local_top_sync,
            chat_id,
            TOP_ROBBERY
        )

        title = "<b>توب اكثر 10 يزرفون نقاط من الناس:</b>"

        if not rows:
            return title + "\n\n• ما فيه بيانات حاليًا ."

        user_ids = [x["user_id"] for x in rows]

        users = await __import__("asyncio").to_thread(
            _get_user_rows_sync,
            user_ids
        )

        lines = []

        for index, item in enumerate(rows, 1):
            uid = item["user_id"]

            name = users.get(
                uid,
                {
                    "first_name": str(uid),
                    "username": None,
                    "user_id": uid
                }
            )

            display = _display_name(name)

            lines.append(
                f"{index}- "
                f'<a href="tg://user?id={uid}">{display}</a>'
                f" ↤︎ {item['value']:,}"
            )

        return title + "\n\n" + "\n".join(lines)

    if top_type == TOP_LUCK:

        rows = await __import__("asyncio").to_thread(
            _get_local_top_sync,
            chat_id,
            TOP_LUCK
        )

        title = "<b>توب اكثر 10 حظهم فنان:</b>"

        if not rows:
            return title + "\n\n• ما فيه بيانات حاليًا ."

        user_ids = [x["user_id"] for x in rows]

        users = await __import__("asyncio").to_thread(
            _get_user_rows_sync,
            user_ids
        )

        lines = []

        for index, item in enumerate(rows, 1):
            uid = item["user_id"]

            name = users.get(
                uid,
                {
                    "first_name": str(uid),
                    "username": None,
                    "user_id": uid
                }
            )

            display = _display_name(name)

            lines.append(
                f"{index}- "
                f'<a href="tg://user?id={uid}">{display}</a>'
                f" ↤︎ {item['wins']:,} فوز"
                f" | {item['losses']:,} خسارة"
            )

        return title + "\n\n" + "\n".join(lines)

    if top_type == TOP_GLOBAL_POINTS:

        rows = await __import__("asyncio").to_thread(
            _get_global_top_sync
        )

        title = "<b>توب أغنى ناس بالبوت 🎖️ :</b>"

        if not rows:
            return title + "\n\n• ما فيه بيانات حاليًا ."

        user_ids = [x["user_id"] for x in rows]

        users = await __import__("asyncio").to_thread(
            _get_user_rows_sync,
            user_ids
        )

        lines = []

        for index, item in enumerate(rows, 1):
            uid = item["user_id"]

            name = users.get(
                uid,
                {
                    "first_name": str(uid),
                    "username": None,
                    "user_id": uid
                }
            )

            display = _display_name(name)

            lines.append(
                f"{index}- "
                f'<a href="tg://user?id={uid}">{display}</a>'
                f" ↤︎ {item['value']:,}"
            )

        return title + "\n\n" + "\n".join(lines)

    return "• حدث خطأ."


# =========================================================
# Callback التوب
# =========================================================

async def top_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query or not query.message:
        return

    data = query.data or ""

    parts = data.split(":")

    if len(parts) != 4:
        await query.answer()
        return

    if parts[0] != TOP_PREFIX:
        await query.answer()
        return

    try:
        owner_id = int(parts[1])
        message_id = int(parts[2])
    except ValueError:
        await query.answer()
        return

    action = parts[3]

    # =====================================================
    # حماية التوب
    # =====================================================

    if query.from_user.id != owner_id:
        await query.answer(
            "انت ماكتبت توب.",
            show_alert=True
        )
        return

    if query.message.message_id != message_id:
        await query.answer()
        return

    # =====================================================
    # رجوع
    # =====================================================

    if action == "back":

        text = (
            "<b>— اهلاً بك عزيزي في قائمة الاوامر :</b>\n"
            "<b>• اختر نوع التوب من الازرار الي تحت .</b>\n"
            "—————————————————"
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=top_main_keyboard(
                owner_id,
                message_id
            )
        )

        await query.answer()
        return

    # =====================================================
    # إخفاء
    # =====================================================

    if action == "hide":

        await query.edit_message_text(
            "• تم اخفاء التوب بنجاح ."
        )

        await query.answer()
        return

    # =====================================================
    # عرض التوب
    # =====================================================

    if action not in (
        TOP_POINTS,
        TOP_ACTIVITY,
        TOP_ROBBERY,
        TOP_LUCK,
        TOP_GLOBAL_POINTS
    ):
        await query.answer()
        return

    try:
        text = await _build_top_text(
            query,
            action
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=top_result_keyboard(
                owner_id,
                message_id
            )
        )

        await query.answer()

    except Exception as e:
        print(
            f"⚠️ خطأ في عرض التوب: {e}"
        )

        await query.answer(
            "حدث خطأ أثناء عرض التوب.",
            show_alert=True
        )
