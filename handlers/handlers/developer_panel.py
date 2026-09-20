import asyncio
import re
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import connect

from handlers.moderation import (
    get_list_rows,
    LIST_TABLES,
    _clear_list_table,
)

from handlers.start_editor import (
    start_editor_command,
)


OWNER_ID = 8453977662


# =========================================================
# الجلسات
# =========================================================

dev_sessions = {}


# =========================================================
# إنشاء الجداول
# =========================================================

def create_developer_panel_tables():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            CREATE TABLE IF NOT EXISTS developer_panel_access (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by BIGINT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS developer_private_starts (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_start_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS developer_bot_chats (
                chat_id BIGINT PRIMARY KEY,
                chat_type TEXT NOT NULL,
                title TEXT,
                username TEXT,
                active INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS developer_broadcasts (
                id SERIAL PRIMARY KEY,
                sender_id BIGINT NOT NULL,
                sender_name TEXT,
                source_chat_id BIGINT NOT NULL,
                source_message_id BIGINT NOT NULL,
                broadcast_type TEXT NOT NULL,
                pin_enabled INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS developer_broadcast_targets (
                id SERIAL PRIMARY KEY,
                broadcast_id INTEGER NOT NULL,
                chat_id BIGINT NOT NULL,
                chat_type TEXT NOT NULL,
                title TEXT,
                username TEXT,
                sent_message_id BIGINT,
                success INTEGER DEFAULT 0,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# =========================================================
# الصلاحية
# =========================================================

def is_developer_allowed(user_id):

    if not user_id:
        return False

    if user_id == OWNER_ID:
        return True

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT 1
            FROM developer_panel_access
            WHERE user_id = ?
            LIMIT 1
        """, (user_id,))

        return cur.fetchone() is not None

    finally:

        cur.close()
        conn.close()


def is_developer_allowed_sync(user_id):

    try:
        return is_developer_allowed(user_id)
    except Exception:
        return False


async def check_access(user_id):

    return await asyncio.to_thread(
        is_developer_allowed_sync,
        user_id
    )


# =========================================================
# تسجيل /start الخاص
# =========================================================

def register_private_start(user):

    if not user:
        return

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO developer_private_starts
            (
                user_id,
                username,
                first_name
            )
            VALUES (?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_start_at=CURRENT_TIMESTAMP
        """, (
            user.id,
            user.username or "",
            user.first_name or ""
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()


async def track_private_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.effective_chat:
        return

    if update.effective_chat.type != "private":
        return

    if not update.message.text:
        return

    if not update.message.text.startswith("/start"):
        return

    user = update.effective_user

    if not user:
        return

    await asyncio.to_thread(
        register_private_start,
        user
    )


# =========================================================
# تسجيل القروبات والقنوات
# =========================================================

def save_bot_chat(
    chat_id,
    chat_type,
    title=None,
    username=None,
    active=True
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO developer_bot_chats
            (
                chat_id,
                chat_type,
                title,
                username,
                active
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(chat_id)
            DO UPDATE SET
                chat_type=excluded.chat_type,
                title=excluded.title,
                username=excluded.username,
                active=excluded.active,
                updated_at=CURRENT_TIMESTAMP
        """, (
            chat_id,
            chat_type,
            title or "",
            username or "",
            1 if active else 0
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()


async def track_bot_chat_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    member_update = update.my_chat_member

    if not member_update:
        return

    chat = member_update.chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup",
        "channel"
    ):
        return

    new_status = member_update.new_chat_member.status

    active = new_status not in (
        "left",
        "kicked"
    )

    await asyncio.to_thread(
        save_bot_chat,
        chat.id,
        chat.type,
        chat.title,
        chat.username,
        active
    )


# =========================================================
# جلب القروبات والقنوات
# =========================================================

def get_registered_chats(chat_type=None):

    conn = connect()
    cur = conn.cursor()

    try:

        if chat_type:

            cur.execute("""
                SELECT
                    chat_id,
                    chat_type,
                    title,
                    username
                FROM developer_bot_chats
                WHERE active=1
                AND chat_type=?
                ORDER BY title ASC, chat_id ASC
            """, (chat_type,))

        else:

            cur.execute("""
                SELECT
                    chat_id,
                    chat_type,
                    title,
                    username
                FROM developer_bot_chats
                WHERE active=1
                ORDER BY chat_type, title ASC, chat_id ASC
            """)

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


# =========================================================
# المشتركين الخاص
# =========================================================

def get_private_subscribers():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                user_id,
                username,
                first_name
            FROM developer_private_starts
            ORDER BY user_id
        """)

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


# =========================================================
# اسم المستخدم كمنشن
# =========================================================

def mention_html(user):

    if not user:
        return ""

    name = (
        getattr(user, "first_name", None)
        or getattr(user, "username", None)
        or str(user.id)
    )

    name = (
        str(name)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    return (
        f'<a href="tg://user?id={user.id}">'
        f'{name}'
        f'</a>'
    )


# =========================================================
# القائمة الرئيسية
# =========================================================

def developer_main_keyboard(user_id):

    rows = [
        [
            InlineKeyboardButton(
                "الإحصائيات",
                callback_data="devpanel:stats"
            ),
            InlineKeyboardButton(
                "الإذاعة",
                callback_data="devpanel:broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "المكتومين",
                callback_data="devpanel:list:mute"
            ),
            InlineKeyboardButton(
                "المحظورين",
                callback_data="devpanel:list:ban"
            )
        ],
        [
            InlineKeyboardButton(
                "تعديل ستارت",
                callback_data="devpanel:startedit"
            ),
            InlineKeyboardButton(
                "المسموحين بالوصول",
                callback_data="devpanel:access"
            )
        ],
        [
            InlineKeyboardButton(
                "سجل الإذاعة",
                callback_data="devpanel:logs"
            ),
            InlineKeyboardButton(
                "المقيدين",
                callback_data="devpanel:list:restrict"
            )
        ]
    ]

    return InlineKeyboardMarkup(rows)


async def show_developer_main(query):

    user = query.from_user

    text = (
        f"id=\"8ng9pi\"\n"
        f"أهلًا يـ {mention_html(user)} 👋"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=developer_main_keyboard(user.id)
    )


# =========================================================
# زر الرجوع
# =========================================================

def back_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "↩️ رجوع للقائمة",
                callback_data="devpanel:menu"
            )
        ]
    ])


# =========================================================
# أمر لوحة المطور
# =========================================================

async def developer_panel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.effective_chat.type != "private":
        return

    user = update.effective_user

    if not user:
        return

    allowed = await check_access(user.id)

    if not allowed:
        return

    dev_sessions.pop(user.id, None)

    await update.message.reply_text(
        (
            f"id=\"8ng9pi\"\n"
            f"أهلًا يـ {mention_html(user)} 👋"
        ),
        parse_mode="HTML",
        reply_markup=developer_main_keyboard(user.id)
    )

    raise ApplicationHandlerStop


# =========================================================
# الإحصائيات
# =========================================================

def get_statistics():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT COUNT(*)
            FROM developer_private_starts
        """)

        subscribers = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT COUNT(*)
            FROM developer_bot_chats
            WHERE active=1
            AND chat_type IN ('group', 'supergroup')
        """)

        groups = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT COUNT(*)
            FROM developer_bot_chats
            WHERE active=1
            AND chat_type='channel'
        """)

        channels = cur.fetchone()[0] or 0

        return subscribers, groups, channels

    finally:

        cur.close()
        conn.close()


async def show_statistics(query):

    subscribers, groups, channels = await asyncio.to_thread(
        get_statistics
    )

    text = (
        "📊 الإحصائيات\n"
        "━━━━━━━━━━━━\n\n"
        f"👤 عدد المشتركين: {subscribers}\n"
        f"👥 عدد المجموعات: {groups}\n"
        f"📢 عدد القنوات: {channels}"
    )

    await query.edit_message_text(
        text,
        reply_markup=back_keyboard()
    )


# =========================================================
# قائمة الإذاعة
# =========================================================

def broadcast_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "الخاص",
                callback_data="devpanel:broadcast:private"
            ),
            InlineKeyboardButton(
                "المجموعات",
                callback_data="devpanel:broadcast:groups"
            )
        ],
        [
            InlineKeyboardButton(
                "القنوات",
                callback_data="devpanel:broadcast:channels"
            ),
            InlineKeyboardButton(
                "الكل",
                callback_data="devpanel:broadcast:all"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ رجوع للقائمة",
                callback_data="devpanel:menu"
            )
        ]
    ])


async def show_broadcast_menu(query):

    await query.edit_message_text(
        'id="1vuh7p"',
        reply_markup=broadcast_keyboard()
    )


# =========================================================
# قائمة الخاص
# =========================================================

def private_broadcast_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "للـكل",
                callback_data="devpanel:private:all"
            )
        ],
        [
            InlineKeyboardButton(
                "لشخص محدد",
                callback_data="devpanel:private:specific"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ رجوع للقائمة",
                callback_data="devpanel:broadcast"
            )
        ]
    ])


async def show_private_broadcast_menu(query):

    await query.edit_message_text(
        'id="rx11ze"',
        reply_markup=private_broadcast_keyboard()
    )


# =========================================================
# طلب رسالة إذاعة
# =========================================================

async def ask_broadcast_message(
    query,
    user_id,
    broadcast_type,
    target_user_id=None,
    pin_enabled=False
):

    dev_sessions[user_id] = {
        "action": "broadcast_message",
        "broadcast_type": broadcast_type,
        "target_user_id": target_user_id,
        "pin_enabled": pin_enabled,
    }

    text = (
        "حسنًا، ارسل الآن الرسالة التي تريد إذاعتها.\n\n"
        "تقدر ترسل نص، صورة، فيديو، GIF، ملصق، "
        "أو أي نوع رسالة يدعمه البوت."
    )

    await query.edit_message_text(
        text,
        reply_markup=back_keyboard()
    )


# =========================================================
# التثبيت
# =========================================================

def all_broadcast_keyboard(pin_enabled):

    status = "✅" if pin_enabled else "❌"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"تثبيت الرسالة {status}",
                callback_data="devpanel:all:togglepin"
            )
        ],
        [
            InlineKeyboardButton(
                "إرسال",
                callback_data="devpanel:all:send"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ رجوع للقائمة",
                callback_data="devpanel:broadcast"
            )
        ]
    ])


# =========================================================
# معالجة callbacks
# =========================================================

async def developer_panel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    user = query.from_user

    if not user:
        return

    allowed = await check_access(user.id)

    if not allowed:
        await query.answer()
        return

    data = query.data or ""

    # -----------------------------------------------------
    # القائمة
    # -----------------------------------------------------

    if data == "devpanel:menu":

        await query.answer()

        dev_sessions.pop(user.id, None)

        await show_developer_main(query)

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # الإحصائيات
    # -----------------------------------------------------

    if data == "devpanel:stats":

        await query.answer()

        await show_statistics(query)

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # الإذاعة
    # -----------------------------------------------------

    if data == "devpanel:broadcast":

        await query.answer()

        dev_sessions.pop(user.id, None)

        await show_broadcast_menu(query)

        raise ApplicationHandlerStop

    if data == "devpanel:broadcast:private":

        await query.answer()

        await show_private_broadcast_menu(query)

        raise ApplicationHandlerStop

    if data == "devpanel:broadcast:groups":

        await query.answer()

        await ask_broadcast_message(
            query,
            user.id,
            "groups"
        )

        raise ApplicationHandlerStop

    if data == "devpanel:broadcast:channels":

        await query.answer()

        await ask_broadcast_message(
            query,
            user.id,
            "channels"
        )

        raise ApplicationHandlerStop

    if data == "devpanel:broadcast:all":

        await query.answer()

        dev_sessions[user.id] = {
            "action": "broadcast_all_options",
            "pin_enabled": False,
        }

        await query.edit_message_text(
            "إعدادات الإذاعة للكل:",
            reply_markup=all_broadcast_keyboard(False)
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # الخاص للكل
    # -----------------------------------------------------

    if data == "devpanel:private:all":

        await query.answer()

        await ask_broadcast_message(
            query,
            user.id,
            "private"
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # الخاص لشخص
    # -----------------------------------------------------

    if data == "devpanel:private:specific":

        await query.answer()

        dev_sessions[user.id] = {
            "action": "private_specific_target"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره.\n\n"
            "مثال:\n"
            "8453977662\n"
            "@username",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # تبديل التثبيت
    # -----------------------------------------------------

    if data == "devpanel:all:togglepin":

        await query.answer()

        session = dev_sessions.get(user.id)

        if not session:
            return

        session["pin_enabled"] = not session.get(
            "pin_enabled",
            False
        )

        await query.edit_message_reply_markup(
            reply_markup=all_broadcast_keyboard(
                session["pin_enabled"]
            )
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # إرسال الكل
    # -----------------------------------------------------

    if data == "devpanel:all:send":

        await query.answer()

        session = dev_sessions.get(user.id)

        if not session:
            return

        session["action"] = "broadcast_message"
        session["broadcast_type"] = "all"

        await query.edit_message_text(
            "حسنًا، ارسل الآن الرسالة التي تريد إذاعتها.\n\n"
            "تقدر ترسل نص، صورة، فيديو، GIF، ملصق، "
            "أو أي نوع رسالة يدعمه البوت.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # المسموحين
    # -----------------------------------------------------

    if data == "devpanel:access":

        await query.answer()

        if user.id != OWNER_ID:

            await query.answer(
                "هذا الزر للمالك فقط 🚨",
                show_alert=True
            )

            raise ApplicationHandlerStop

        await show_access_panel(
            query
        )

        raise ApplicationHandlerStop

    if data == "devpanel:access:add":

        await query.answer()

        if user.id != OWNER_ID:
            raise ApplicationHandlerStop

        dev_sessions[user.id] = {
            "action": "developer_access_add"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره لإضافته.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    if data == "devpanel:access:delete":

        await query.answer()

        if user.id != OWNER_ID:
            raise ApplicationHandlerStop

        dev_sessions[user.id] = {
            "action": "developer_access_delete"
        }

        await query.edit_message_text(
            "ارسل أيدي الشخص أو يوزره لحذفه.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # تعديل ستارت
    # -----------------------------------------------------

    if data == "devpanel:startedit":

        await query.answer()

        # نفس نظام start_editor الحالي
        dev_sessions.pop(user.id, None)

        await start_editor_command(
            Update(
                update.update_id,
                message=query.message
            ),
            context
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # القوائم
    # -----------------------------------------------------

    if data.startswith("devpanel:list:"):

        await query.answer()

        kind = data.split(":")[-1]

        if kind not in LIST_TABLES:
            return

        await show_moderation_list(
            query,
            kind
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # تأكيد المسح
    # -----------------------------------------------------

    if data.startswith("devpanel:clear:confirm:"):

        await query.answer()

        kind = data.split(":")[-1]

        if kind not in LIST_TABLES:
            return

        await confirm_clear_list(
            query,
            kind
        )

        raise ApplicationHandlerStop

    if data.startswith("devpanel:clear:execute:"):

        await query.answer()

        kind = data.split(":")[-1]

        if kind not in LIST_TABLES:
            return

        await execute_clear_all_groups(
            query,
            context,
            kind
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # سجل الإذاعة
    # -----------------------------------------------------

    if data == "devpanel:logs":

        await query.answer()

        await show_broadcast_logs(
            query
        )

        raise ApplicationHandlerStop

    if data.startswith("devpanel:log:view:"):

        await query.answer()

        broadcast_id = int(
            data.split(":")[-1]
        )

        await view_broadcast(
            query,
            context,
            broadcast_id
        )

        raise ApplicationHandlerStop

    if data.startswith("devpanel:log:links:"):

        await query.answer()

        broadcast_id = int(
            data.split(":")[-1]
        )

        await show_broadcast_links(
            query,
            broadcast_id
        )

        raise ApplicationHandlerStop


# =========================================================
# المسموحين
# =========================================================

def get_developer_access():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT user_id, username, first_name
            FROM developer_panel_access
            ORDER BY id ASC
        """)

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


async def show_access_panel(query):

    rows = await asyncio.to_thread(
        get_developer_access
    )

    text = "المسموحين بالوصول:\n\n"

    if not rows:

        text += "لا يوجد أشخاص مضافين."

    else:

        for index, row in enumerate(rows, 1):

            user_id, username, first_name = row

            if username:

                text += f"{index}. @{username.lstrip('@')}\n"

            else:

                text += f"{index}. {first_name or user_id}\n"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "إضافة شخص",
                callback_data="devpanel:access:add"
            ),
            InlineKeyboardButton(
                "حذف شخص",
                callback_data="devpanel:access:delete"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ رجوع للقائمة",
                callback_data="devpanel:menu"
            )
        ]
    ])

    await query.edit_message_text(
        text,
        reply_markup=keyboard
    )


def find_user_for_access(value):

    value = value.strip()

    conn = connect()
    cur = conn.cursor()

    try:

        if value.startswith("@"):

            username = value[1:].strip().lower()

            cur.execute("""
                SELECT user_id, username, first_name
                FROM users
                WHERE LOWER(username)=?
                LIMIT 1
            """, (username,))

        elif value.isdigit():

            cur.execute("""
                SELECT user_id, username, first_name
                FROM users
                WHERE user_id=?
                LIMIT 1
            """, (int(value),))

        else:

            return None

        return cur.fetchone()

    finally:

        cur.close()
        conn.close()


def add_developer_access(
    user_id,
    username=None,
    first_name=None,
    added_by=None
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO developer_panel_access
            (
                user_id,
                username,
                first_name,
                added_by
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (
            user_id,
            username or "",
            first_name or "",
            added_by
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()


def delete_developer_access(value):

    conn = connect()
    cur = conn.cursor()

    try:

        if value.startswith("@"):

            cur.execute("""
                DELETE FROM developer_panel_access
                WHERE LOWER(username)=?
            """, (
                value[1:].lower(),
            ))

        elif value.isdigit():

            cur.execute("""
                DELETE FROM developer_panel_access
                WHERE user_id=?
            """, (
                int(value),
            ))

        conn.commit()

    finally:

        cur.close()
        conn.close()


# =========================================================
# قوائم الحماية
# =========================================================

async def show_moderation_list(
    query,
    kind
):

    table = LIST_TABLES[kind][0]
    title = LIST_TABLES[kind][1]

    chats = await asyncio.to_thread(
        get_registered_chats,
        None
    )

    text = f"• {title}\n━━━━━━━━━━━━\n\n"

    total = 0

    for chat in chats:

        chat_id = chat[0]
        chat_title = chat[2] or str(chat_id)

        rows = await asyncio.to_thread(
            get_list_rows,
            chat_id,
            table
        )

        if not rows:
            continue

        text += (
            f"📍 {chat_title}\n"
            f"ID: <code>{chat_id}</code>\n"
        )

        for index, row in enumerate(rows, 1):

            user_id = row[0]
            username = row[1]
            first_name = row[2]

            if username:

                display = f"@{username.lstrip('@')}"

            else:

                display = (
                    first_name
                    or str(user_id)
                )

            text += (
                f"{index}. {display} "
                f"(<code>{user_id}</code>)\n"
            )

            total += 1

        text += "\n"

    if total == 0:
        text += "لا يوجد."

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"مسح {LIST_TABLES[kind][2].replace('مسح ', '')}",
                callback_data=f"devpanel:clear:confirm:{kind}"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ الرجوع للقائمة",
                callback_data="devpanel:menu"
            )
        ]
    ])

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def confirm_clear_list(
    query,
    kind
):

    name = LIST_TABLES[kind][2]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "نعم، تأكيد المسح",
                callback_data=f"devpanel:clear:execute:{kind}"
            )
        ],
        [
            InlineKeyboardButton(
                "إلغاء",
                callback_data=f"devpanel:list:{kind}"
            )
        ]
    ])

    await query.edit_message_text(
        f"⚠️ هل أنت متأكد من {name} من جميع المجموعات؟\n\n"
        "سيتم فك القيد/الحظر ثم حذف السجلات.",
        reply_markup=keyboard
    )


# =========================================================
# مسح الحماية من جميع المجموعات
# =========================================================

async def execute_clear_all_groups(
    query,
    context,
    kind
):

    table = LIST_TABLES[kind][0]

    chats = await asyncio.to_thread(
        get_registered_chats,
        None
    )

    total = 0

    for chat in chats:

        chat_id = chat[0]

        rows = await asyncio.to_thread(
            get_list_rows,
            chat_id,
            table
        )

        for row in rows:

            user_id = row[0]

            try:

                if kind == "restrict":

                    from telegram import ChatPermissions

                    permissions = ChatPermissions(
                        can_send_messages=True,
                        can_send_audios=True,
                        can_send_documents=True,
                        can_send_photos=True,
                        can_send_videos=True,
                        can_send_video_notes=True,
                        can_send_voice_notes=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True,
                        can_manage_topics=True,
                    )

                    await context.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        permissions=permissions
                    )

                elif kind == "ban":

                    await context.bot.unban_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        only_if_banned=False
                    )

            except Exception:
                pass

            total += 1

        await asyncio.to_thread(
            _clear_list_table,
            table,
            chat_id
        )

    await query.edit_message_text(
        f"تم مسح {LIST_TABLES[kind][2].replace('مسح ', '')} "
        f"من جميع المجموعات ✅\n\n"
        f"عدد السجلات: {total}",
        reply_markup=back_keyboard()
    )


# =========================================================
# تحديد شخص للخاص
# =========================================================

async def resolve_private_target(
    value,
    context
):

    value = value.strip()

    if value.isdigit():

        user_id = int(value)

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute("""
                SELECT user_id
                FROM developer_private_starts
                WHERE user_id=?
                LIMIT 1
            """, (user_id,))

            row = cur.fetchone()

        finally:

            cur.close()
            conn.close()

        if row:
            return user_id

        return None

    if value.startswith("@"):

        username = value[1:].lower()

        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute("""
                SELECT user_id
                FROM developer_private_starts
                WHERE LOWER(username)=?
                LIMIT 1
            """, (username,))

            row = cur.fetchone()

        finally:

            cur.close()
            conn.close()

        if row:
            return row[0]

    return None


# =========================================================
# استقبال رسائل لوحة المطور
# =========================================================

async def developer_panel_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.effective_chat:
        return

    if update.effective_chat.type != "private":
        return

    user = update.effective_user

    if not user:
        return

    session = dev_sessions.get(user.id)

    if not session:
        return

    allowed = await check_access(user.id)

    if not allowed:

        dev_sessions.pop(user.id, None)

        return

    action = session.get("action")

    # =====================================================
    # إضافة مطور
    # =====================================================

    if action == "developer_access_add":

        if user.id != OWNER_ID:
            dev_sessions.pop(user.id, None)
            return

        value = (
            update.message.text or ""
        ).strip()

        if not value:

            await update.message.reply_text(
                "ارسل أيدي أو يوزر صحيح.",
                reply_markup=back_keyboard()
            )

            raise ApplicationHandlerStop

        row = await asyncio.to_thread(
            find_user_for_access,
            value
        )

        if not row:

            await update.message.reply_text(
                "ما لقيت هذا المستخدم في قاعدة البيانات.\n"
                "استخدم ID أو username لشخص مسجل عند البوت.",
                reply_markup=back_keyboard()
            )

            raise ApplicationHandlerStop

        await asyncio.to_thread(
            add_developer_access,
            row[0],
            row[1],
            row[2],
            user.id
        )

        dev_sessions.pop(user.id, None)

        await update.message.reply_text(
            "تمت إضافته للمسموحين بالوصول للوحة المطور ✅",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # حذف مطور
    # =====================================================

    if action == "developer_access_delete":

        if user.id != OWNER_ID:
            dev_sessions.pop(user.id, None)
            return

        value = (
            update.message.text or ""
        ).strip()

        if not value:

            await update.message.reply_text(
                "ارسل أيدي أو يوزر صحيح.",
                reply_markup=back_keyboard()
            )

            raise ApplicationHandlerStop

        await asyncio.to_thread(
            delete_developer_access,
            value
        )

        dev_sessions.pop(user.id, None)

        await update.message.reply_text(
            "تم حذف الشخص من المسموحين بالوصول ✅",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تحديد شخص للإذاعة الخاصة
    # =====================================================

    if action == "private_specific_target":

        value = (
            update.message.text or ""
        ).strip()

        if not value:

            await update.message.reply_text(
                "ارسل ID أو username.",
                reply_markup=back_keyboard()
            )

            raise ApplicationHandlerStop

        target_id = await resolve_private_target(
            value,
            context
        )

        if not target_id:

            await update.message.reply_text(
                "ما لقيت هذا الشخص ضمن مستخدمي البوت الذين بدأوا الخاص.",
                reply_markup=back_keyboard()
            )

            raise ApplicationHandlerStop

        await ask_broadcast_message_from_message(
            update,
            user.id,
            "private_specific",
            target_id
        )

        raise ApplicationHandlerStop

    # =====================================================
    # استقبال رسالة الإذاعة
    # =====================================================

    if action == "broadcast_message":

        source = update.message

        broadcast_type = session.get(
            "broadcast_type"
        )

        target_user_id = session.get(
            "target_user_id"
        )

        pin_enabled = session.get(
            "pin_enabled",
            False
        )

        result = await execute_broadcast(
            update,
            context,
            source,
            broadcast_type,
            target_user_id,
            pin_enabled
        )

        dev_sessions.pop(user.id, None)

        await send_broadcast_result(
            update,
            result
        )

        raise ApplicationHandlerStop


# =========================================================
# تحويل جلسة الرسالة
# =========================================================

async def ask_broadcast_message_from_message(
    update,
    user_id,
    broadcast_type,
    target_user_id
):

    dev_sessions[user_id] = {
        "action": "broadcast_message",
        "broadcast_type": broadcast_type,
        "target_user_id": target_user_id,
        "pin_enabled": False
    }

    await update.message.reply_text(
        "تمام، ارسل الآن الرسالة التي تريد إرسالها للشخص.",
        reply_markup=back_keyboard()
    )


# =========================================================
# إنشاء سجل إذاعة
# =========================================================

def create_broadcast_log(
    sender,
    source,
    broadcast_type,
    pin_enabled
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO developer_broadcasts
            (
                sender_id,
                sender_name,
                source_chat_id,
                source_message_id,
                broadcast_type,
                pin_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (
            sender.id,
            sender.first_name or "",
            source.chat.id,
            source.message_id,
            broadcast_type,
            1 if pin_enabled else 0
        ))

        row = cur.fetchone()

        conn.commit()

        return row[0]

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


# =========================================================
# حفظ نتيجة هدف
# =========================================================

def save_broadcast_target(
    broadcast_id,
    chat_id,
    chat_type,
    title,
    username,
    sent_message_id=None,
    success=False,
    error=None
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO developer_broadcast_targets
            (
                broadcast_id,
                chat_id,
                chat_type,
                title,
                username,
                sent_message_id,
                success,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            broadcast_id,
            chat_id,
            chat_type,
            title or "",
            username or "",
            sent_message_id,
            1 if success else 0,
            error or ""
        ))

        conn.commit()

    finally:

        cur.close()
        conn.close()


# =========================================================
# تنفيذ الإذاعة
# =========================================================

async def execute_broadcast(
    update,
    context,
    source,
    broadcast_type,
    target_user_id=None,
    pin_enabled=False
):

    sender = update.effective_user

    broadcast_id = await asyncio.to_thread(
        create_broadcast_log,
        sender,
        source,
        broadcast_type,
        pin_enabled
    )

    targets = []

    if broadcast_type == "private":

        targets = [
            (
                row[0],
                "private",
                row[2] or str(row[0]),
                row[1] or ""
            )
            for row in await asyncio.to_thread(
                get_private_subscribers
            )
        ]

    elif broadcast_type == "private_specific":

        targets = [
            (
                target_user_id,
                "private",
                str(target_user_id),
                ""
            )
        ]

    elif broadcast_type == "groups":

        rows = await asyncio.to_thread(
            get_registered_chats
        )

        targets = [
            (
                row[0],
                row[1],
                row[2],
                row[3]
            )
            for row in rows
            if row[1] in ("group", "supergroup")
        ]

    elif broadcast_type == "channels":

        rows = await asyncio.to_thread(
            get_registered_chats,
            "channel"
        )

        targets = [
            (
                row[0],
                row[1],
                row[2],
                row[3]
            )
            for row in rows
        ]

    elif broadcast_type == "all":

        private_rows = await asyncio.to_thread(
            get_private_subscribers
        )

        targets.extend([
            (
                row[0],
                "private",
                row[2] or str(row[0]),
                row[1] or ""
            )
            for row in private_rows
        ])

        chat_rows = await asyncio.to_thread(
            get_registered_chats
        )

        targets.extend([
            (
                row[0],
                row[1],
                row[2],
                row[3]
            )
            for row in chat_rows
        ])

    success = 0
    failed = 0
    failures = []

    for (
        chat_id,
        chat_type,
        title,
        username
    ) in targets:

        try:

            copied = await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source.chat.id,
                message_id=source.message_id
            )

            sent_message_id = copied.message_id

            # ---------------------------------------------
            # تثبيت
            # ---------------------------------------------

            if (
                pin_enabled
                and chat_type in (
                    "group",
                    "supergroup",
                    "channel"
                )
            ):

                try:

                    await context.bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=sent_message_id,
                        disable_notification=True
                    )

                except Exception:
                    pass

            await asyncio.to_thread(
                save_broadcast_target,
                broadcast_id,
                chat_id,
                chat_type,
                title,
                username,
                sent_message_id,
                True,
                None
            )

            success += 1

        except Exception as e:

            error_text = str(e)

            await asyncio.to_thread(
                save_broadcast_target,
                broadcast_id,
                chat_id,
                chat_type,
                title,
                username,
                None,
                False,
                error_text
            )

            failed += 1

            if chat_type in (
                "group",
                "supergroup",
                "channel"
            ):

                link = await get_chat_link(
                    context,
                    chat_id,
                    username
                )

                failures.append({
                    "title": title or str(chat_id),
                    "chat_id": chat_id,
                    "link": link
                })

    return {
        "broadcast_id": broadcast_id,
        "success": success,
        "failed": failed,
        "failures": failures
    }


# =========================================================
# رابط القروب / القناة
# =========================================================

async def get_chat_link(
    context,
    chat_id,
    username=None
):

    if username:

        return f"https://t.me/{username.lstrip('@')}"

    try:

        invite = await context.bot.create_chat_invite_link(
            chat_id=chat_id
        )

        return invite.invite_link

    except Exception:

        return None


# =========================================================
# نتيجة الإذاعة
# =========================================================

async def send_broadcast_result(
    update,
    result
):

    text = (
        "تمت الإذاعة ✅\n\n"
        f"نجح الإرسال: {result['success']}\n"
        f"فشل الإرسال: {result['failed']}"
    )

    await update.message.reply_text(
        text,
        reply_markup=back_keyboard()
    )

    if not result["failures"]:
        return

    failure_text = "⚠️ تعذر الإرسال إلى:\n\n"

    for item in result["failures"]:

        failure_text += (
            f"• {item['title']}\n"
            f"  ID: <code>{item['chat_id']}</code>\n"
        )

        if item["link"]:
            failure_text += (
                f"  {item['link']}\n"
            )

        else:
            failure_text += (
                "  الرابط: غير متوفر\n"
            )

        failure_text += "\n"

    await update.message.reply_text(
        failure_text,
        parse_mode="HTML"
    )


# =========================================================
# سجل الإذاعة
# =========================================================

def get_broadcast_logs():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                id,
                sender_id,
                sender_name,
                broadcast_type,
                created_at
            FROM developer_broadcasts
            ORDER BY id DESC
            LIMIT 20
        """)

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


def broadcast_type_name(value):

    return {
        "all": "الكل",
        "private": "الخاص",
        "private_specific": "الخاص - شخص محدد",
        "groups": "المجموعات",
        "channels": "القنوات",
    }.get(value, value)


async def show_broadcast_logs(query):

    rows = await asyncio.to_thread(
        get_broadcast_logs
    )

    if not rows:

        await query.edit_message_text(
            "لا توجد إذاعات مسجلة.",
            reply_markup=back_keyboard()
        )

        return

    text = ""
    keyboard_rows = []

    for row in rows:

        (
            broadcast_id,
            sender_id,
            sender_name,
            broadcast_type,
            created_at
        ) = row

        if isinstance(created_at, datetime):

            date_text = created_at.strftime(
                "%Y/%m/%d"
            )

        else:

            date_text = str(created_at)

        text += (
            f'الاذاعة {broadcast_id} .\n\n'
            f"• النوع: {broadcast_type_name(broadcast_type)}\n"
            f"• مُرسل الاذاعة: "
            f'<a href="tg://user?id={sender_id}">'
            f'{sender_name or sender_id}'
            f"</a>\n"
            f"• التاريخ: {date_text}\n\n"
        )

        keyboard_rows.append([
            InlineKeyboardButton(
                "رؤية الرسالة",
                callback_data=f"devpanel:log:view:{broadcast_id}"
            ),
            InlineKeyboardButton(
                "روابط القروبات",
                callback_data=f"devpanel:log:links:{broadcast_id}"
            )
        ])

    keyboard_rows.append([
        InlineKeyboardButton(
            "↩️ رجوع للقائمة",
            callback_data="devpanel:menu"
        )
    ])

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard_rows
        )
    )


# =========================================================
# جلب سجل إذاعة
# =========================================================

def get_broadcast(
    broadcast_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                source_chat_id,
                source_message_id
            FROM developer_broadcasts
            WHERE id=?
            LIMIT 1
        """, (broadcast_id,))

        return cur.fetchone()

    finally:

        cur.close()
        conn.close()


async def view_broadcast(
    query,
    context,
    broadcast_id
):

    row = await asyncio.to_thread(
        get_broadcast,
        broadcast_id
    )

    if not row:

        await query.edit_message_text(
            "الإذاعة غير موجودة.",
            reply_markup=back_keyboard()
        )

        return

    try:

        await context.bot.copy_message(
            chat_id=query.message.chat.id,
            from_chat_id=row[0],
            message_id=row[1]
        )

        await query.message.reply_text(
            "↩️",
            reply_markup=back_keyboard()
        )

    except Exception:

        await query.edit_message_text(
            "تعذر إظهار الرسالة الأصلية.",
            reply_markup=back_keyboard()
        )


# =========================================================
# روابط الإذاعة
# =========================================================

def get_broadcast_targets(
    broadcast_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                chat_id,
                chat_type,
                title,
                username,
                success
            FROM developer_broadcast_targets
            WHERE broadcast_id=?
            AND chat_type IN ('group', 'supergroup', 'channel')
            ORDER BY id ASC
        """, (broadcast_id,))

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


async def show_broadcast_links(
    query,
    broadcast_id
):

    rows = await asyncio.to_thread(
        get_broadcast_targets,
        broadcast_id
    )

    if not rows:

        await query.edit_message_text(
            "لا توجد مجموعات أو قنوات مرتبطة بهذه الإذاعة.",
            reply_markup=back_keyboard()
        )

        return

    text = ""

    for row in rows:

        (
            chat_id,
            chat_type,
            title,
            username,
            success
        ) = row

        if not success:
            continue

        if username:

            link = (
                f"https://t.me/"
                f"{username.lstrip('@')}"
            )

        else:

            link = "الرابط غير متوفر"

        text += (
            f"• {title or chat_id} - "
            f"{link}\n"
        )

    if not text:
        text = "لا توجد روابط متاحة."

    await query.edit_message_text(
        text,
        reply_markup=back_keyboard()
    )
