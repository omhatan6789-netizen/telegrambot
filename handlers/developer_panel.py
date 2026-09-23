# =========================================================
# handlers/developer_panel.py
# =========================================================

import asyncio
import re

from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    ChatPermissions,
)

from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop,
)

from database import (
    connect,
    acquire_schema_lock,
)

from handlers.cache import get_user_data

from handlers.moderation import (
    get_list_rows,
    LIST_TABLES,
)

from handlers.start_editor import (
    open_start_editor_from_panel,
)


OWNER_ID = 8453977662


# =========================================================
# جلسات لوحة المطور
# =========================================================

dev_sessions = {}


# =========================================================
# أدوات عامة
# =========================================================

def _now():
    return datetime.now()


def _escape_html(text):
    if text is None:
        return ""

    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def mention_html(user_id, name):
    return (
        f'<a href="tg://user?id={user_id}">'
        f'{_escape_html(name or "مستخدم")}'
        f'</a>'
    )


def _utf16_length(text):
    return len((text or "").encode("utf-16-le")) // 2


# =========================================================
# إنشاء جداول لوحة المطور
# =========================================================

def create_developer_panel_tables():

    conn = connect()
    cur = conn.cursor()
    acquire_schema_lock(conn)

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
# صلاحية لوحة المطور
# =========================================================

def is_developer_allowed_sync(user_id):

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
            WHERE user_id=?
            LIMIT 1
        """, (user_id,))

        return cur.fetchone() is not None

    finally:

        cur.close()
        conn.close()


async def check_access(user_id):

    return await asyncio.to_thread(
        is_developer_allowed_sync,
        user_id
    )


# =========================================================
# تسجيل مستخدمي /start في الخاص
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

    if not re.match(
        r"^/start(?:\s.*)?$",
        update.message.text
    ):
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
    title,
    username,
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

    status = member_update.new_chat_member.status

    active = status not in (
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
                ORDER BY chat_type ASC, title ASC
            """)

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


# =========================================================
# مشتركو الخاص
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
            ORDER BY user_id ASC
        """)

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


# =========================================================
# لوحة المطور الرئيسية
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

    if user_id == OWNER_ID:

        rows[2].append(
            InlineKeyboardButton(
                "المسموحين بالوصول",
                callback_data="devpanel:access"
            )
        )

    return InlineKeyboardMarkup(rows)


async def show_developer_main(query):

    user = query.from_user

    dev_sessions.pop(user.id, None)

    await query.edit_message_text(
        (
            f'أهلًا يـ '
            f'{mention_html(user.id, user.first_name)} 👋'
        ),
        parse_mode="HTML",
        reply_markup=developer_main_keyboard(
            user.id
        )
    )


# =========================================================
# الرجوع
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

    if not update.effective_chat:
        return

    if update.effective_chat.type != "private":
        return

    user = update.effective_user

    if not user:
        return

    allowed = await check_access(user.id)

    if not allowed:

        # مهم:
        # نوقف الهاندلرات التالية حتى لا يرد
        # custom command أو أي نظام آخر على الأمر.
        raise ApplicationHandlerStop

    dev_sessions.pop(user.id, None)

    await update.message.reply_text(
        (
            f'أهلًا يـ '
            f'{mention_html(user.id, user.first_name)} 👋'
        ),
        parse_mode="HTML",
        reply_markup=developer_main_keyboard(
            user.id
        )
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

    subscribers, groups, channels = (
        await asyncio.to_thread(
            get_statistics
        )
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
        'id="wbbk55"',
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
        'id="3xkdt3"',
        reply_markup=private_broadcast_keyboard()
    )


# =========================================================
# خيارات الكل + التثبيت
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
        "pin_enabled": pin_enabled
    }

    await query.edit_message_text(
        "ارسل الآن رسالة الإذاعة.",
        reply_markup=back_keyboard()
    )


# =========================================================
# CALLBACK الرئيسي
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

    # =====================================================
    # القائمة الرئيسية
    # =====================================================

    if data == "devpanel:menu":

        await query.answer()

        await show_developer_main(
            query
        )

        raise ApplicationHandlerStop

    # =====================================================
    # الإحصائيات
    # =====================================================

    if data == "devpanel:stats":

        await query.answer()

        await show_statistics(
            query
        )

        raise ApplicationHandlerStop

    # =====================================================
    # الإذاعة
    # =====================================================

    if data == "devpanel:broadcast":

        await query.answer()

        dev_sessions.pop(
            user.id,
            None
        )

        await show_broadcast_menu(
            query
        )

        raise ApplicationHandlerStop

    # =====================================================
    # الخاص
    # =====================================================

    if data == "devpanel:broadcast:private":

        await query.answer()

        await show_private_broadcast_menu(
            query
        )

        raise ApplicationHandlerStop

    # =====================================================
    # المجموعات
    # =====================================================

    if data == "devpanel:broadcast:groups":

        await query.answer()

        await ask_broadcast_message(
            query,
            user.id,
            "groups"
        )

        raise ApplicationHandlerStop

    # =====================================================
    # القنوات
    # =====================================================

    if data == "devpanel:broadcast:channels":

        await query.answer()

        await ask_broadcast_message(
            query,
            user.id,
            "channels"
        )

        raise ApplicationHandlerStop

    # =====================================================
    # الكل
    # =====================================================

    if data == "devpanel:broadcast:all":

        await query.answer()

        dev_sessions[user.id] = {
            "action": "broadcast_all_options",
            "pin_enabled": False
        }

        await query.edit_message_text(
            "إعدادات الإذاعة للكل:",
            reply_markup=all_broadcast_keyboard(
                False
            )
        )

        raise ApplicationHandlerStop

    # =====================================================
    # الخاص للكل
    # =====================================================

    if data == "devpanel:private:all":

        await query.answer()

        await ask_broadcast_message(
            query,
            user.id,
            "private"
        )

        raise ApplicationHandlerStop

    # =====================================================
    # الخاص لشخص محدد
    # =====================================================

    if data == "devpanel:private:specific":

        await query.answer()

        dev_sessions[user.id] = {
            "action": "private_specific_target"
        }

        await query.edit_message_text(
            "ارسل ID الشخص أو يوزره.\n\n"
            "مثال:\n"
            "8453977662\n"
            "@username",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تبديل التثبيت
    # =====================================================

    if data == "devpanel:all:togglepin":

        await query.answer()

        session = dev_sessions.get(
            user.id
        )

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

    # =====================================================
    # إرسال الكل
    # =====================================================

    if data == "devpanel:all:send":

        await query.answer()

        session = dev_sessions.get(
            user.id
        )

        if not session:
            return

        session["action"] = "broadcast_message"
        session["broadcast_type"] = "all"

        await query.edit_message_text(
            "ارسل الآن رسالة الإذاعة.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تعديل ستارت
    # =====================================================

    if data == "devpanel:startedit":

        await query.answer()

        dev_sessions.pop(
            user.id,
            None
        )

        # يسمح لنظام start_editor بمعرفة أن الدخول
        # جاء من لوحة المطور.
        context.user_data[
            "developer_panel_start_editor"
        ] = True

        await open_start_editor_from_panel(
            query,
            context
        )

        raise ApplicationHandlerStop

    # =====================================================
    # المسموحين بالوصول
    # =====================================================

    if data == "devpanel:access":

        await query.answer()

        if user.id != OWNER_ID:

            return

        await show_access_panel(
            query
        )

        raise ApplicationHandlerStop

    if data == "devpanel:access:add":

        await query.answer()

        if user.id != OWNER_ID:
            return

        dev_sessions[user.id] = {
            "action": "developer_access_add"
        }

        await query.edit_message_text(
            "ارسل ID الشخص أو يوزره لإضافته.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    if data == "devpanel:access:delete":

        await query.answer()

        if user.id != OWNER_ID:
            return

        dev_sessions[user.id] = {
            "action": "developer_access_delete"
        }

        await query.edit_message_text(
            "ارسل ID الشخص أو يوزره لحذفه.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # قوائم الحماية
    # =====================================================

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

    # =====================================================
    # تأكيد المسح
    # =====================================================

    if data.startswith(
        "devpanel:clear:confirm:"
    ):

        await query.answer()

        kind = data.split(":")[-1]

        if kind not in LIST_TABLES:
            return

        await confirm_clear_list(
            query,
            kind
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تنفيذ المسح
    # =====================================================

    if data.startswith(
        "devpanel:clear:execute:"
    ):

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

    # =====================================================
    # سجل الإذاعة
    # =====================================================

    if data == "devpanel:logs":

        await query.answer()

        await show_broadcast_logs(
            query
        )

        raise ApplicationHandlerStop

    # =====================================================
    # رؤية الرسالة
    # =====================================================

    if data.startswith(
        "devpanel:log:view:"
    ):

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

    # =====================================================
    # روابط القروبات
    # =====================================================

    if data.startswith(
        "devpanel:log:links:"
    ):

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
            SELECT
                user_id,
                username,
                first_name
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

        for index, row in enumerate(
            rows,
            1
        ):

            user_id = row[0]
            username = row[1]
            first_name = row[2]

            if username:

                text += (
                    f"{index}. "
                    f"@{username.lstrip('@')}\n"
                )

            else:

                text += (
                    f"{index}. "
                    f"{first_name or user_id}\n"
                )

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

            username = value[
                1:
            ].strip().lower()

            cur.execute("""
                SELECT
                    user_id,
                    username,
                    first_name
                FROM users
                WHERE LOWER(username)=?
                LIMIT 1
            """, (
                username,
            ))

        elif value.isdigit():

            cur.execute("""
                SELECT
                    user_id,
                    username,
                    first_name
                FROM users
                WHERE user_id=?
                LIMIT 1
            """, (
                int(value),
            ))

        else:

            return None

        return cur.fetchone()

    finally:

        cur.close()
        conn.close()


def add_developer_access(
    user_id,
    username,
    first_name,
    added_by
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
        get_registered_chats
    )

    text = (
        f"• {title}\n"
        "━━━━━━━━━━━━\n\n"
    )

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
            f"📍 {_escape_html(chat_title)}\n"
            f"ID: <code>{chat_id}</code>\n"
        )

        for index, row in enumerate(
            rows,
            1
        ):

            user_id = row[0]
            username = row[1]
            first_name = row[2]

            display = (
                f"@{username.lstrip('@')}"
                if username
                else first_name or str(user_id)
            )

            text += (
                f"{index}. "
                f"{_escape_html(display)} "
                f"(<code>{user_id}</code>)\n"
            )

            total += 1

        text += "\n"

    if total == 0:

        text += "لا يوجد."

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                LIST_TABLES[kind][2],
                callback_data=(
                    f"devpanel:clear:confirm:{kind}"
                )
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
                callback_data=(
                    f"devpanel:clear:execute:{kind}"
                )
            )
        ],
        [
            InlineKeyboardButton(
                "إلغاء",
                callback_data=(
                    f"devpanel:list:{kind}"
                )
            )
        ]
    ])

    await query.edit_message_text(
        (
            f"⚠️ هل أنت متأكد من {name} "
            "من جميع المجموعات؟\n\n"
            "سيتم تنفيذ المسح على جميع السجلات."
        ),
        reply_markup=keyboard
    )


# =========================================================
# مسح قوائم الحماية من جميع المجموعات
# =========================================================

async def execute_clear_all_groups(
    query,
    context,
    kind
):

    table = LIST_TABLES[kind][0]

    chats = await asyncio.to_thread(
        get_registered_chats
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

        # حذف سجل نفس نظام الحماية
        conn = connect()
        cur = conn.cursor()

        try:

            cur.execute(
                f"""
                DELETE FROM {table}
                WHERE chat_id=?
                """,
                (chat_id,)
            )

            conn.commit()

        finally:

            cur.close()
            conn.close()

    await query.edit_message_text(
        (
            f"تم مسح {LIST_TABLES[kind][2].replace('مسح ', '')} "
            "من جميع المجموعات ✅\n\n"
            f"عدد السجلات: {total}"
        ),
        reply_markup=back_keyboard()
    )


# =========================================================
# البحث عن مستخدم خاص
# =========================================================

def resolve_private_target_sync(value):

    value = value.strip()

    conn = connect()
    cur = conn.cursor()

    try:

        if value.isdigit():

            cur.execute("""
                SELECT user_id
                FROM developer_private_starts
                WHERE user_id=?
                LIMIT 1
            """, (
                int(value),
            ))

        elif value.startswith("@"):

            cur.execute("""
                SELECT user_id
                FROM developer_private_starts
                WHERE LOWER(username)=?
                LIMIT 1
            """, (
                value[1:].lower(),
            ))

        else:

            return None

        row = cur.fetchone()

        return row[0] if row else None

    finally:

        cur.close()
        conn.close()


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

    session = dev_sessions.get(
        user.id
    )

    if not session:
        return

    allowed = await check_access(
        user.id
    )

    if not allowed:

        dev_sessions.pop(
            user.id,
            None
        )

        raise ApplicationHandlerStop

    action = session.get(
        "action"
    )

    # =====================================================
    # إضافة شخص
    # =====================================================

    if action == "developer_access_add":

        if user.id != OWNER_ID:

            dev_sessions.pop(
                user.id,
                None
            )

            raise ApplicationHandlerStop

        value = (
            update.message.text or ""
        ).strip()

        row = await asyncio.to_thread(
            find_user_for_access,
            value
        )

        if not row:

            await update.message.reply_text(
                "ما لقيت المستخدم.\n"
                "تأكد أن الـ ID أو اليوزر صحيح.",
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

        dev_sessions.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            "تمت إضافته للمسموحين بالوصول ✅",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # حذف شخص
    # =====================================================

    if action == "developer_access_delete":

        if user.id != OWNER_ID:

            dev_sessions.pop(
                user.id,
                None
            )

            raise ApplicationHandlerStop

        value = (
            update.message.text or ""
        ).strip()

        await asyncio.to_thread(
            delete_developer_access,
            value
        )

        dev_sessions.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            "تم حذف الشخص من المسموحين بالوصول ✅",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # تحديد شخص للإذاعة
    # =====================================================

    if action == "private_specific_target":

        value = (
            update.message.text or ""
        ).strip()

        target_user_id = await asyncio.to_thread(
            resolve_private_target_sync,
            value
        )

        if not target_user_id:

            await update.message.reply_text(
                "ما لقيت هذا الشخص ضمن المشتركين "
                "الذين بدأوا البوت في الخاص.",
                reply_markup=back_keyboard()
            )

            raise ApplicationHandlerStop

        dev_sessions[user.id] = {
            "action": "broadcast_message",
            "broadcast_type": "private_specific",
            "target_user_id": target_user_id,
            "pin_enabled": False
        }

        await update.message.reply_text(
            "تمام، ارسل الآن الرسالة التي تريد إرسالها للشخص.",
            reply_markup=back_keyboard()
        )

        raise ApplicationHandlerStop

    # =====================================================
    # رسالة الإذاعة
    # =====================================================

    if action == "broadcast_message":

        result = await execute_broadcast(
            update,
            context,
            update.message,
            session.get("broadcast_type"),
            session.get("target_user_id"),
            session.get("pin_enabled", False)
        )

        dev_sessions.pop(
            user.id,
            None
        )

        await send_broadcast_result(
            update,
            result
        )

        raise ApplicationHandlerStop


# =========================================================
# متغيرات الرسالة
# =========================================================

PRIVATE_VARIABLES = {
    "#الاسم",
    "#منشن",
    "#يوزره",
    "#اليوزر",
    "#الرسائل",
    "#الايدي",
    "#الرتبه",
    "#النقاط",
}

CHAT_VARIABLES = {
    "#الاسم",
    "#منشن",
}


def _build_replacements(
    target,
    user_data,
    target_user
):

    # =====================================================
    # الخاص
    # =====================================================

    if target["chat_type"] == "private":

        if target_user:

            first_name = (
                target_user.first_name
                or target["title"]
                or "مستخدم"
            )

            username = (
                f"@{target_user.username}"
                if target_user.username
                else "لا يوجد"
            )

        else:

            first_name = (
                target["title"]
                or "مستخدم"
            )

            username = (
                f"@{target['username'].lstrip('@')}"
                if target["username"]
                else "لا يوجد"
            )

        messages = 0
        rank = "عضو"
        points = 0

        if user_data:

            messages = (
                user_data.get(
                    "messages",
                    0
                ) or 0
            )

            rank = (
                user_data.get(
                    "rank",
                    "عضو"
                )
                or "عضو"
            )

            points = (
                user_data.get(
                    "points",
                    0
                ) or 0
            )

        return {
            "#الاسم": first_name,
            "#منشن": first_name,
            "#يوزره": username,
            "#اليوزر": username,
            "#الرسائل": str(messages),
            "#الايدي": str(target["user_id"]),
            "#الرتبه": rank,
            "#النقاط": str(points),
        }

    # =====================================================
    # القروب / القناة
    # =====================================================

    return {
        "#الاسم": target["title"] or "المجموعة",
        "#منشن": target["title"] or "المجموعة",
    }


# =========================================================
# استبدال المتغيرات + إعادة بناء الـ Entities
# =========================================================

def _replace_variables_with_entities(
    text,
    entities,
    replacements,
    mention_user=None
):

    if not text:

        return text, entities or []

    entities = entities or []

    # -----------------------------------------------------
    # جمع أماكن المتغيرات
    # -----------------------------------------------------

    replacements_positions = []

    for key, value in replacements.items():

        start_search = 0

        while True:

            position = text.find(
                key,
                start_search
            )

            if position == -1:
                break

            old_start = _utf16_length(
                text[:position]
            )

            old_length = _utf16_length(
                key
            )

            new_length = _utf16_length(
                value
            )

            replacements_positions.append({
                "key": key,
                "start": old_start,
                "end": old_start + old_length,
                "old_length": old_length,
                "new_length": new_length,
                "position": position,
            })

            start_search = (
                position + len(key)
            )

    replacements_positions.sort(
        key=lambda x: x["start"]
    )

    # -----------------------------------------------------
    # النص النهائي
    # -----------------------------------------------------

    final_text = text

    for key, value in replacements.items():

        final_text = final_text.replace(
            key,
            value
        )

    # -----------------------------------------------------
    # تحويل Offset من النص القديم للجديد
    # -----------------------------------------------------

    def transform_position(
        old_position
    ):

        new_position = old_position

        for replacement in replacements_positions:

            if replacement["end"] <= old_position:

                new_position += (
                    replacement["new_length"]
                    -
                    replacement["old_length"]
                )

        return new_position

    # -----------------------------------------------------
    # إعادة بناء الـ entities
    # -----------------------------------------------------

    final_entities = []

    for old_entity in entities:

        old_offset = (
            old_entity.offset
            or 0
        )

        old_length = (
            old_entity.length
            or 0
        )

        old_end = (
            old_offset
            +
            old_length
        )

        new_offset = transform_position(
            old_offset
        )

        new_length = old_length

        # -------------------------------------------------
        # تعديل طول entity إذا كان المتغير داخله
        # -------------------------------------------------

        for replacement in replacements_positions:

            start = replacement["start"]
            end = replacement["end"]

            difference = (
                replacement["new_length"]
                -
                replacement["old_length"]
            )

            if (
                start >= old_offset
                and end <= old_end
            ):

                new_length += difference

        try:

            entity = MessageEntity(
                type=old_entity.type,
                offset=new_offset,
                length=new_length,
                url=old_entity.url,
                user=old_entity.user,
                language=old_entity.language,
                custom_emoji_id=(
                    old_entity.custom_emoji_id
                )
            )

            final_entities.append(
                entity
            )

        except Exception:

            final_entities.append(
                old_entity
            )

    # -----------------------------------------------------
    # #منشن حقيقي
    # -----------------------------------------------------

    if (
        mention_user
        and "#منشن" in replacements
    ):

        for replacement in replacements_positions:

            if replacement["key"] != "#منشن":
                continue

            new_offset = transform_position(
                replacement["start"]
            )

            mention_text = replacements[
                "#منشن"
            ]

            try:

                final_entities.append(
                    MessageEntity(
                        type="text_mention",
                        offset=new_offset,
                        length=_utf16_length(
                            mention_text
                        ),
                        user=mention_user
                    )
                )

            except Exception:
                pass

    # -----------------------------------------------------
    # ترتيب entities
    # -----------------------------------------------------

    final_entities.sort(
        key=lambda entity: (
            entity.offset or 0,
            -(entity.length or 0)
        )
    )

    return (
        final_text,
        final_entities
    )


# =========================================================
# تجهيز الرسالة حسب المستلم
# =========================================================

async def prepare_broadcast_message(
    context,
    source,
    target
):

    target_user = None
    user_data = None

    # =====================================================
    # إذا كان المستلم شخص
    # =====================================================

    if target["chat_type"] == "private":

        user_id = target["user_id"]

        try:

            target_user = await context.bot.get_chat(
                user_id
            )

        except Exception:

            target_user = None

        try:

            user_data = await get_user_data(
                user_id
            )

        except Exception:

            user_data = None

    replacements = _build_replacements(
        target,
        user_data,
        target_user
    )

    # =====================================================
    # النص
    # =====================================================

    final_text = None
    final_entities = []

    if source.text is not None:

        final_text, final_entities = (
            _replace_variables_with_entities(
                source.text,
                source.entities,
                replacements,
                target_user
                if target["chat_type"] == "private"
                else None
            )
        )

    # =====================================================
    # الكابشن
    # =====================================================

    final_caption = None
    final_caption_entities = []

    if source.caption is not None:

        final_caption, final_caption_entities = (
            _replace_variables_with_entities(
                source.caption,
                source.caption_entities,
                replacements,
                target_user
                if target["chat_type"] == "private"
                else None
            )
        )

    return {
        "text": final_text,
        "entities": final_entities,
        "caption": final_caption,
        "caption_entities": final_caption_entities,
        "source": source,
        "target": target,
        "target_user": target_user,
        "user_data": user_data,
    }


# =========================================================
# إرسال الرسالة المعالجة
# =========================================================

async def send_prepared_broadcast(
    context,
    chat_id,
    prepared
):

    source = prepared["source"]

    # =====================================================
    # نص
    # =====================================================

    if source.text is not None:

        return await context.bot.send_message(
            chat_id=chat_id,
            text=prepared["text"] or "",
            entities=(
                prepared["entities"]
                or None
            ),
        )

    # =====================================================
    # صورة
    # =====================================================

    if source.photo:

        return await context.bot.send_photo(
            chat_id=chat_id,
            photo=source.photo[-1].file_id,
            caption=prepared["caption"],
            caption_entities=(
                prepared["caption_entities"]
                or None
            )
        )

    # =====================================================
    # فيديو
    # =====================================================

    if source.video:

        return await context.bot.send_video(
            chat_id=chat_id,
            video=source.video.file_id,
            caption=prepared["caption"],
            caption_entities=(
                prepared["caption_entities"]
                or None
            )
        )

    # =====================================================
    # GIF / Animation
    # =====================================================

    if source.animation:

        return await context.bot.send_animation(
            chat_id=chat_id,
            animation=source.animation.file_id,
            caption=prepared["caption"],
            caption_entities=(
                prepared["caption_entities"]
                or None
            )
        )

    # =====================================================
    # Sticker
    # =====================================================

    if source.sticker:

        return await context.bot.send_sticker(
            chat_id=chat_id,
            sticker=source.sticker.file_id
        )

    # =====================================================
    # Voice
    # =====================================================

    if source.voice:

        return await context.bot.send_voice(
            chat_id=chat_id,
            voice=source.voice.file_id,
            caption=prepared["caption"],
            caption_entities=(
                prepared["caption_entities"]
                or None
            )
        )

    # =====================================================
    # Audio
    # =====================================================

    if source.audio:

        return await context.bot.send_audio(
            chat_id=chat_id,
            audio=source.audio.file_id,
            caption=prepared["caption"],
            caption_entities=(
                prepared["caption_entities"]
                or None
            )
        )

    # =====================================================
    # Document
    # =====================================================

    if source.document:

        return await context.bot.send_document(
            chat_id=chat_id,
            document=source.document.file_id,
            caption=prepared["caption"],
            caption_entities=(
                prepared["caption_entities"]
                or None
            )
        )

    # =====================================================
    # Video Note
    # =====================================================

    if source.video_note:

        return await context.bot.send_video_note(
            chat_id=chat_id,
            video_note=source.video_note.file_id
        )

    # =====================================================
    # Location
    # =====================================================

    if source.location:

        return await context.bot.send_location(
            chat_id=chat_id,
            latitude=source.location.latitude,
            longitude=source.location.longitude
        )

    # =====================================================
    # Contact
    # =====================================================

    if source.contact:

        return await context.bot.send_contact(
            chat_id=chat_id,
            phone_number=source.contact.phone_number,
            first_name=source.contact.first_name,
            last_name=source.contact.last_name
        )

    # =====================================================
    # Poll
    # =====================================================

    if source.poll:

        options = [
            option.text
            for option in source.poll.options
        ]

        return await context.bot.send_poll(
            chat_id=chat_id,
            question=source.poll.question,
            options=options,
            is_anonymous=source.poll.is_anonymous,
            allows_multiple_answers=(
                source.poll.allows_multiple_answers
            ),
            type=source.poll.type
        )

    # =====================================================
    # fallback
    # =====================================================

    return await context.bot.copy_message(
        chat_id=chat_id,
        from_chat_id=source.chat.id,
        message_id=source.message_id
    )


# =========================================================
# إنشاء سجل الإذاعة
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
# حفظ هدف الإذاعة
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

    # =====================================================
    # الخاص
    # =====================================================

    if broadcast_type == "private":

        rows = await asyncio.to_thread(
            get_private_subscribers
        )

        targets = [
            {
                "chat_id": row[0],
                "chat_type": "private",
                "title": row[2] or str(row[0]),
                "username": row[1] or "",
                "user_id": row[0],
            }
            for row in rows
        ]

    # =====================================================
    # شخص محدد
    # =====================================================

    elif broadcast_type == "private_specific":

        targets = [
            {
                "chat_id": target_user_id,
                "chat_type": "private",
                "title": str(target_user_id),
                "username": "",
                "user_id": target_user_id,
            }
        ]

    # =====================================================
    # مجموعات
    # =====================================================

    elif broadcast_type == "groups":

        rows = await asyncio.to_thread(
            get_registered_chats
        )

        targets = [
            {
                "chat_id": row[0],
                "chat_type": row[1],
                "title": row[2] or str(row[0]),
                "username": row[3] or "",
                "user_id": None,
            }
            for row in rows
            if row[1] in (
                "group",
                "supergroup"
            )
        ]

    # =====================================================
    # قنوات
    # =====================================================

    elif broadcast_type == "channels":

        rows = await asyncio.to_thread(
            get_registered_chats,
            "channel"
        )

        targets = [
            {
                "chat_id": row[0],
                "chat_type": "channel",
                "title": row[2] or str(row[0]),
                "username": row[3] or "",
                "user_id": None,
            }
            for row in rows
        ]

    # =====================================================
    # الكل
    # =====================================================

    elif broadcast_type == "all":

        private_rows = await asyncio.to_thread(
            get_private_subscribers
        )

        targets.extend([
            {
                "chat_id": row[0],
                "chat_type": "private",
                "title": row[2] or str(row[0]),
                "username": row[1] or "",
                "user_id": row[0],
            }
            for row in private_rows
        ])

        chat_rows = await asyncio.to_thread(
            get_registered_chats
        )

        targets.extend([
            {
                "chat_id": row[0],
                "chat_type": row[1],
                "title": row[2] or str(row[0]),
                "username": row[3] or "",
                "user_id": None,
            }
            for row in chat_rows
        ])

    success = 0
    failed = 0
    failures = []

    # =====================================================
    # إرسال نسخة منفصلة لكل مستلم
    # =====================================================

    for target in targets:

        try:

            prepared = await prepare_broadcast_message(
                context,
                source,
                target
            )

            sent = await send_prepared_broadcast(
                context,
                target["chat_id"],
                prepared
            )

            sent_message_id = sent.message_id

            # -------------------------------------------------
            # تثبيت
            # -------------------------------------------------

            if (
                pin_enabled
                and target["chat_type"] in (
                    "group",
                    "supergroup",
                    "channel"
                )
            ):

                try:

                    await context.bot.pin_chat_message(
                        chat_id=target["chat_id"],
                        message_id=sent_message_id,
                        disable_notification=True
                    )

                except Exception:
                    pass

            await asyncio.to_thread(
                save_broadcast_target,
                broadcast_id,
                target["chat_id"],
                target["chat_type"],
                target["title"],
                target["username"],
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
                target["chat_id"],
                target["chat_type"],
                target["title"],
                target["username"],
                None,
                False,
                error_text
            )

            failed += 1

            if target["chat_type"] in (
                "group",
                "supergroup",
                "channel"
            ):

                link = await get_chat_link(
                    context,
                    target["chat_id"],
                    target["username"]
                )

                failures.append({
                    "title": target["title"],
                    "chat_id": target["chat_id"],
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

        return (
            f"https://t.me/"
            f"{username.lstrip('@')}"
        )

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

    await update.message.reply_text(
        (
            "تمت الإذاعة ✅\n\n"
            f"نجح الإرسال: {result['success']}\n"
            f"فشل الإرسال: {result['failed']}"
        ),
        reply_markup=back_keyboard()
    )

    if not result["failures"]:
        return

    text = "⚠️ تعذر الإرسال إلى:\n\n"

    for item in result["failures"]:

        text += (
            f"• {_escape_html(item['title'])}\n"
            f"  ID: <code>{item['chat_id']}</code>\n"
        )

        if item["link"]:

            text += (
                f"  {_escape_html(item['link'])}\n"
            )

        else:

            text += (
                "  الرابط: غير متوفر\n"
            )

        text += "\n"

    await update.message.reply_text(
        text,
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
    }.get(
        value,
        value
    )


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
    keyboard = []

    for row in rows:

        (
            broadcast_id,
            sender_id,
            sender_name,
            broadcast_type,
            created_at
        ) = row

        if isinstance(
            created_at,
            datetime
        ):

            date_text = created_at.strftime(
                "%Y/%m/%d"
            )

        else:

            date_text = str(
                created_at
            )

        sender_mention = mention_html(
            sender_id,
            sender_name or str(sender_id)
        )

        entry = (
            f"الاذاعة {broadcast_id} .\n\n"
            f"• النوع: "
            f"{broadcast_type_name(broadcast_type)}\n"
            f"• مُرسل الاذاعة: "
            f"{sender_mention}\n"
            f"• التاريخ: {date_text}\n\n"
        )

        # منع تجاوز حد رسالة تيليجرام
        if len(
            text + entry
        ) > 3600:

            break

        text += entry

        keyboard.append([
            InlineKeyboardButton(
                "رؤية الرسالة",
                callback_data=(
                    f"devpanel:log:view:{broadcast_id}"
                )
            ),
            InlineKeyboardButton(
                "روابط القروبات",
                callback_data=(
                    f"devpanel:log:links:{broadcast_id}"
                )
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "↩️ رجوع للقائمة",
            callback_data="devpanel:menu"
        )
    ])

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# جلب إذاعة
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
        """, (
            broadcast_id,
        ))

        return cur.fetchone()

    finally:

        cur.close()
        conn.close()


# =========================================================
# رؤية الرسالة الأصلية
# =========================================================

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
# روابط القروبات
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
            AND chat_type IN (
                'group',
                'supergroup',
                'channel'
            )
            ORDER BY id ASC
        """, (
            broadcast_id,
        ))

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

    successful = [
        row
        for row in rows
        if row[4]
    ]

    if not successful:

        await query.edit_message_text(
            "لا توجد مجموعات أو قنوات مرتبطة بهذه الإذاعة.",
            reply_markup=back_keyboard()
        )

        return

    text = ""

    for row in successful:

        (
            chat_id,
            chat_type,
            title,
            username,
            success
        ) = row

        if username:

            link = (
                f"https://t.me/"
                f"{username.lstrip('@')}"
            )

        else:

            link = "الرابط غير متوفر"

        text += (
            f"• {_escape_html(title or chat_id)}\n"
            f"  {_escape_html(link)}\n\n"
        )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )
