from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ApplicationHandlerStop

from database import connect


# ==================================================
# الإعدادات
# ==================================================

OWNER_ID = 8453977662


# ==================================================
# أدوات عامة
# ==================================================

def is_group(update: Update):
    chat = update.effective_chat

    if not chat:
        return False

    return chat.type in ("group", "supergroup")


def html_mention(user):
    if not user:
        return ""

    name = getattr(user, "first_name", None) or "المستخدم"

    return f'<a href="tg://user?id={user.id}">{name}</a>'


async def send_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user,
    caption: str,
):
    """
    إرسال صورة الحساب إن وجدت.
    وإذا لم توجد صورة يرسل النص فقط.
    """

    if not user:
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    user.first_name or "الحساب",
                    url=f"tg://user?id={user.id}",
                )
            ]
        ]
    )

    photo_file_id = None

    try:
        photos = await context.bot.get_user_profile_photos(
            user.id,
            limit=1
        )

        if photos.total_count > 0:
            photo_file_id = photos.photos[0][-1].file_id

    except Exception as e:
        print(f"⚠️ تعذر جلب صورة المستخدم: {e}")

    if photo_file_id:

        await update.effective_message.reply_photo(
            photo=photo_file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    else:

        await update.effective_message.reply_text(
            caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def get_user_info(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
):
    """
    جلب أحدث معلومات الحساب من Telegram.
    """

    try:
        return await context.bot.get_chat(user_id)
    except Exception:
        return None


# ==================================================
# إنشاء الجداول
# ==================================================

def create_profile_reply_tables():

    conn = connect()
    cur = conn.cursor()

    try:

        # --------------------------------------------------
        # إعدادات المطور العامة
        # --------------------------------------------------

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_profile_settings (
                profile_type TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT
            )
            """
        )

        # --------------------------------------------------
        # إعدادات المجموعة
        # --------------------------------------------------

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS group_profile_settings (
                chat_id BIGINT PRIMARY KEY,
                owner_user_id BIGINT,
                owner_username TEXT,
                admin_replies_enabled BOOLEAN DEFAULT FALSE
            )
            """
        )

        # --------------------------------------------------
        # ردود الادمن
        # --------------------------------------------------

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_replies (
                chat_id BIGINT NOT NULL,
                admin_user_id BIGINT NOT NULL,
                reply_name TEXT NOT NULL,
                created_date TEXT NOT NULL,
                PRIMARY KEY (chat_id, admin_user_id),
                UNIQUE (chat_id, reply_name)
            )
            """
        )

        # --------------------------------------------------
        # المطور الأساسي
        # --------------------------------------------------

        cur.execute(
            """
            INSERT INTO bot_profile_settings (
                profile_type,
                user_id,
                username
            )
            VALUES (?, ?, ?)
            ON CONFLICT (profile_type) DO NOTHING
            """,
            (
                "developer",
                OWNER_ID,
                None,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


# ==================================================
# المطور
# ==================================================

def get_saved_developer():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT user_id, username
            FROM bot_profile_settings
            WHERE profile_type = ?
            """,
            ("developer",)
        )

        row = cur.fetchone()

        if not row:
            return OWNER_ID, None

        return row[0], row[1]

    finally:

        cur.close()
        conn.close()


def save_developer(
    user_id: int,
    username: str | None,
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            INSERT INTO bot_profile_settings (
                profile_type,
                user_id,
                username
            )
            VALUES (?, ?, ?)
            ON CONFLICT (profile_type)
            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                username = EXCLUDED.username
            """,
            (
                "developer",
                user_id,
                username,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


# ==================================================
# إعدادات المجموعة
# ==================================================

def get_group_settings(chat_id):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT
                owner_user_id,
                owner_username,
                admin_replies_enabled
            FROM group_profile_settings
            WHERE chat_id = ?
            """,
            (chat_id,)
        )

        row = cur.fetchone()

        return row

    finally:

        cur.close()
        conn.close()


def ensure_group_settings(chat_id):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            INSERT INTO group_profile_settings (
                chat_id,
                owner_user_id,
                owner_username,
                admin_replies_enabled
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT (chat_id) DO NOTHING
            """,
            (
                chat_id,
                None,
                None,
                False,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


def save_group_owner(
    chat_id: int,
    user_id: int,
    username: str | None,
):

    ensure_group_settings(chat_id)

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            UPDATE group_profile_settings
            SET
                owner_user_id = ?,
                owner_username = ?
            WHERE chat_id = ?
            """,
            (
                user_id,
                username,
                chat_id,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


def set_admin_replies_status(
    chat_id: int,
    enabled: bool,
):

    ensure_group_settings(chat_id)

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            UPDATE group_profile_settings
            SET admin_replies_enabled = ?
            WHERE chat_id = ?
            """,
            (
                enabled,
                chat_id,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


# ==================================================
# ردود الادمن - قاعدة البيانات
# ==================================================

def save_admin_reply(
    chat_id: int,
    admin_user_id: int,
    reply_name: str,
):

    conn = connect()
    cur = conn.cursor()

    try:

        created_date = datetime.now().strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        cur.execute(
            """
            INSERT INTO admin_replies (
                chat_id,
                admin_user_id,
                reply_name,
                created_date
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                chat_id,
                admin_user_id,
                reply_name,
                created_date,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


def get_admin_reply_by_user(
    chat_id: int,
    admin_user_id: int,
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT reply_name
            FROM admin_replies
            WHERE chat_id = ?
              AND admin_user_id = ?
            """,
            (
                chat_id,
                admin_user_id,
            )
        )

        row = cur.fetchone()

        return row[0] if row else None

    finally:

        cur.close()
        conn.close()


def get_admin_reply_by_name(
    chat_id: int,
    reply_name: str,
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT admin_user_id, reply_name
            FROM admin_replies
            WHERE chat_id = ?
              AND reply_name = ?
            """,
            (
                chat_id,
                reply_name,
            )
        )

        return cur.fetchone()

    finally:

        cur.close()
        conn.close()


def delete_admin_reply(
    chat_id: int,
    admin_user_id: int,
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM admin_replies
            WHERE chat_id = ?
              AND admin_user_id = ?
            """,
            (
                chat_id,
                admin_user_id,
            )
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


def delete_all_admin_replies(chat_id: int):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM admin_replies
            WHERE chat_id = ?
            """,
            (chat_id,)
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        cur.close()
        conn.close()


def get_all_admin_replies(chat_id: int):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT admin_user_id, reply_name
            FROM admin_replies
            WHERE chat_id = ?
            ORDER BY created_date ASC, admin_user_id ASC
            """,
            (chat_id,)
        )

        return cur.fetchall()

    finally:

        cur.close()
        conn.close()


# ==================================================
# الصلاحيات
# ==================================================

def get_user_rank(user_id: int):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT rank
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = cur.fetchone()

        return row[0] if row else "عضو"

    finally:

        cur.close()
        conn.close()


def get_rank_level(rank):

    levels = {
        "عضو": 0,
        "مميز": 1,
        "ادمن": 2,
        "ادمن اساسي": 3,
        "نائب المالك": 4,
        "المالك": 5,
        "Dev": 6,
    }

    return levels.get(rank, 0)


async def is_group_admin_or_above(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if user.id == OWNER_ID:
        return True

    try:

        rank = get_user_rank(user.id)

        if get_rank_level(rank) >= 2:
            return True

    except Exception:
        pass

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        if member.status in (
            "administrator",
            "creator",
        ):
            return True

    except Exception:
        pass

    return False


async def is_owner_or_above(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if user.id == OWNER_ID:
        return True

    try:

        rank = get_user_rank(user.id)

        if get_rank_level(rank) >= 5:
            return True

    except Exception:
        pass

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        if member.status == "creator":
            return True

    except Exception:
        pass

    return False


# ==================================================
# البحث عن مستخدم باليوزر
# ==================================================

async def get_group_user_from_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    username: str,
):
    chat = update.effective_chat

    if not chat:
        return None

    username = (username or "").strip()

    if not username.startswith("@"):
        return None

    username_clean = username[1:].strip().lower()

    if not username_clean:
        return None

    # ==================================================
    # البحث عن المستخدم في قاعدة بيانات البوت
    # ==================================================

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute(
            """
            SELECT user_id
            FROM users
            WHERE LOWER(username) = ?
            LIMIT 1
            """,
            (username_clean,)
        )

        row = cur.fetchone()

    finally:

        cur.close()
        conn.close()

    if not row:
        return None

    user_id = row[0]

    # ==================================================
    # التأكد أن المستخدم موجود حاليًا في المجموعة
    # ==================================================

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user_id
        )

    except Exception as e:

        print(
            f"⚠️ تعذر التحقق من عضوية {username}: {e}"
        )

        return None

    if member.status in (
        "left",
        "kicked",
    ):
        return None

    # ==================================================
    # المستخدم موجود
    # ==================================================

    return member.user


# ==================================================
# تنظيف حالات الانتظار
# ==================================================

PENDING_KEYS = (
    "profile_waiting",
    "profile_waiting_type",
)


def clear_profile_pending(context):

    for key in PENDING_KEYS:

        context.user_data.pop(
            key,
            None
        )


def set_profile_pending(
    context,
    pending_type: str,
):

    clear_profile_pending(context)

    context.user_data["profile_waiting"] = True
    context.user_data["profile_waiting_type"] = pending_type


def get_profile_pending(context):

    if not context.user_data.get(
        "profile_waiting"
    ):
        return None

    return context.user_data.get(
        "profile_waiting_type"
    )


# ==================================================
# المطور
# ==================================================

async def developer_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    developer_id, developer_username = get_saved_developer()

    developer = await get_user_info(
        context,
        developer_id
    )

    if not developer:
        developer = update.effective_user

    bot = await context.bot.get_me()

    bot_name = bot.first_name or "البوت"

    developer_name = (
        developer.first_name
        or "المطور"
    )

    bio = getattr(
        developer,
        "bio",
        None
    ) or "لا يوجد بايو."

    caption = (
        f"Dev Bot ↦ {bot_name}\n"
        f"━━━━━━━━━━━━━━\n"
        f"Dev ↦ {html_mention(developer)}\n"
        f"Bio ↦ {bio}"
    )

    await send_profile(
        update,
        context,
        developer,
        caption
    )

    raise ApplicationHandlerStop()


# ==================================================
# تغيير يوزر المطور
# ==================================================

async def change_developer_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    if user.id != OWNER_ID:

        await update.message.reply_text(
            "• هذا الأمر للمطور الأساسي فقط."
        )

        raise ApplicationHandlerStop()

    if not is_group(update):

        await update.message.reply_text(
            "• هذا الأمر يستخدم داخل المجموعة."
        )

        raise ApplicationHandlerStop()

    set_profile_pending(
        context,
        "developer_username"
    )

    await update.message.reply_text(
        "حسنًا، ارسل يوزر المطور الجديد."
    )

    raise ApplicationHandlerStop()


# ==================================================
# تغيير يوزر المالك
# ==================================================

async def change_owner_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        await update.message.reply_text(
            "• هذا الأمر يستخدم داخل المجموعة."
        )

        raise ApplicationHandlerStop()

    allowed = await is_owner_or_above(
        update,
        context
    )

    if not allowed:

        await update.message.reply_text(
            "• هذا الأمر للمالك ومن فوق."
        )

        raise ApplicationHandlerStop()

    set_profile_pending(
        context,
        "owner_username"
    )

    await update.message.reply_text(
        "حسنًا، ارسل يوزر المالك الجديد."
    )

    raise ApplicationHandlerStop()


# ==================================================
# استقبال اليوزر الجديد
# ==================================================

async def receive_developer_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        clear_profile_pending(context)
        return

    text = (
        update.message.text or ""
    ).strip()

    # العملية تنتهي مهما كانت النتيجة
    clear_profile_pending(context)

    if not text.startswith("@"):

        await update.message.reply_text(
            "• اليوزر غير صحيح، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    if " " in text:

        await update.message.reply_text(
            "• اليوزر غير صحيح، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    target = await get_group_user_from_username(
        update,
        context,
        text
    )

    if not target:

        await update.message.reply_text(
            "• اليوزر غير موجود في المجموعة، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    save_developer(
        target.id,
        text
    )

    await update.message.reply_text(
        "• تم تغيير يوزر المطور بنجاح."
    )

    raise ApplicationHandlerStop()


async def receive_owner_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        clear_profile_pending(context)
        return

    text = (
        update.message.text or ""
    ).strip()

    # العملية تنتهي مهما كانت النتيجة
    clear_profile_pending(context)

    if not text.startswith("@"):

        await update.message.reply_text(
            "• اليوزر غير صحيح، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    if " " in text:

        await update.message.reply_text(
            "• اليوزر غير صحيح، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    target = await get_group_user_from_username(
        update,
        context,
        text
    )

    if not target:

        await update.message.reply_text(
            "• اليوزر غير موجود في المجموعة، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    chat_id = update.effective_chat.id

    save_group_owner(
        chat_id,
        target.id,
        text
    )

    await update.message.reply_text(
        "• تم تغيير يوزر المالك بنجاح."
    )

    raise ApplicationHandlerStop()


# ==================================================
# المالك
# ==================================================

async def get_default_group_owner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat = update.effective_chat

    if not chat:
        return None

    try:

        administrators = await context.bot.get_chat_administrators(
            chat.id
        )

    except Exception:
        return None

    for member in administrators:

        if member.status == "creator":
            return member.user

    return None


async def owner_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    print("🟢 OWNER COMMAND RECEIVED")

    if not update.message:
        print("🔴 لا توجد message")
        return

    if not is_group(update):

        print("🔴 الأمر ليس داخل مجموعة")

        await update.message.reply_text(
            "• هذا الأمر يستخدم داخل المجموعة."
        )

        raise ApplicationHandlerStop()

    chat = update.effective_chat

    print(f"🟢 GROUP ID: {chat.id}")
    print(f"🟢 GROUP NAME: {chat.title}")

    try:

        ensure_group_settings(chat.id)

        print("🟢 ensure_group_settings OK")

        settings = get_group_settings(chat.id)

        print(f"🟢 SETTINGS: {settings}")

    except Exception as e:

        print(f"🔴 خطأ في إعدادات المالك: {e}")

        await update.message.reply_text(
            f"• حدث خطأ أثناء جلب بيانات المالك.\n\n{e}"
        )

        raise ApplicationHandlerStop()

    owner = None

    if settings:

        owner_id = settings[0]

        print(f"🟢 SAVED OWNER ID: {owner_id}")

        if owner_id:

            try:

                owner = await get_user_info(
                    context,
                    owner_id
                )

                print(f"🟢 SAVED OWNER: {owner}")

            except Exception as e:

                print(f"🔴 خطأ في جلب المالك المحفوظ: {e}")

    # إذا لا يوجد مالك مخصص
    if not owner:

        print("🟡 لا يوجد مالك مخصص، البحث عن منشئ المجموعة")

        try:

            owner = await get_default_group_owner(
                update,
                context
            )

            print(f"🟢 DEFAULT OWNER: {owner}")

        except Exception as e:

            print(f"🔴 خطأ في جلب منشئ المجموعة: {e}")

    if not owner:

        print("🔴 لم يتم العثور على مالك المجموعة")

        await update.message.reply_text(
            "• تعذر العثور على مالك المجموعة."
        )

        raise ApplicationHandlerStop()

    group_name = chat.title or "المجموعة"

    owner_name = (
        owner.first_name
        or "المالك"
    )

    bio = getattr(
        owner,
        "bio",
        None
    ) or "لا يوجد بايو."

    caption = (
        f"Owner group ↦ {group_name}\n"
        f"━━━━━━━━━━━━━━\n"
        f"USE ↤ {html_mention(owner)}\n"
        f"bio ↤ {bio}"
    )

    print("🟢 سيتم إرسال بروفايل المالك")

    try:

        await send_profile(
            update,
            context,
            owner,
            caption
        )

        print("🟢 تم إرسال بروفايل المالك")

    except Exception as e:

        print(f"🔴 خطأ أثناء إرسال بروفايل المالك: {e}")

        await update.message.reply_text(
            f"• حدث خطأ أثناء إرسال بروفايل المالك.\n\n{e}"
        )

    raise ApplicationHandlerStop()


# ==================================================
# إضافة ردي
# ==================================================

async def add_my_admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        await update.message.reply_text(
            "• هذا الأمر يستخدم داخل المجموعة."
        )

        raise ApplicationHandlerStop()

    allowed = await is_group_admin_or_above(
        update,
        context
    )

    if not allowed:

        await update.message.reply_text(
            "• هذا الأمر للادمن ومن فوق."
        )

        raise ApplicationHandlerStop()

    settings = get_group_settings(
        update.effective_chat.id
    )

    enabled = (
        settings[2]
        if settings
        else False
    )

    if not enabled:

        await update.message.reply_text(
            "• ردود الادمن غير مفعلة في هذه المجموعة."
        )

        raise ApplicationHandlerStop()

    old_reply = get_admin_reply_by_user(
        update.effective_chat.id,
        update.effective_user.id
    )

    if old_reply:

        await update.message.reply_text(
            f"عندك رد قديم اسمه ({old_reply}) "
            "اكتب حذف ردي لحذفه وإضافة رد جديد!"
        )

        raise ApplicationHandlerStop()

    set_profile_pending(
        context,
        "admin_reply_name"
    )

    await update.message.reply_text(
        "حسنًا، ارسل كلمة الرد"
    )

    raise ApplicationHandlerStop()


# ==================================================
# استقبال اسم رد الادمن
# ==================================================

async def receive_my_admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        clear_profile_pending(context)
        return

    text = (
        update.message.text or ""
    ).strip()

    # العملية تنتهي دائمًا بعد الرسالة
    clear_profile_pending(context)

    if not text:

        await update.message.reply_text(
            "• اسم الرد غير صحيح، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    if "\n" in text:

        await update.message.reply_text(
            "• اسم الرد غير صحيح، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    old_reply = get_admin_reply_by_user(
        chat_id,
        user_id
    )

    if old_reply:

        await update.message.reply_text(
            f"عندك رد قديم اسمه ({old_reply}) "
            "اكتب حذف ردي لحذفه وإضافة رد جديد!"
        )

        raise ApplicationHandlerStop()

    existing = get_admin_reply_by_name(
        chat_id,
        text
    )

    if existing:

        await update.message.reply_text(
            "• اسم الرد مستخدم بالفعل، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    try:

        save_admin_reply(
            chat_id,
            user_id,
            text
        )

    except Exception as e:

        print(
            f"⚠️ خطأ في حفظ رد الادمن: {e}"
        )

        await update.message.reply_text(
            "• حدث خطأ أثناء إضافة الرد، تم إلغاء العملية."
        )

        raise ApplicationHandlerStop()

    await update.message.reply_text(
        "تم إضافة ردك الجديد!\n"
        "اكتب اسم الرد في المجموعة لتجربته."
    )

    raise ApplicationHandlerStop()


# ==================================================
# حذف ردي
# ==================================================

async def delete_my_admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        raise ApplicationHandlerStop()

    allowed = await is_group_admin_or_above(
        update,
        context
    )

    if not allowed:

        raise ApplicationHandlerStop()

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    old_reply = get_admin_reply_by_user(
        chat_id,
        user_id
    )

    if not old_reply:

        await update.message.reply_text(
            "• ما عندك رد ادمن."
        )

        raise ApplicationHandlerStop()

    delete_admin_reply(
        chat_id,
        user_id
    )

    await update.message.reply_text(
        "• تم حذف ردك."
    )

    raise ApplicationHandlerStop()


# ==================================================
# حذف رده
# ==================================================

async def delete_other_admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):
        return

    allowed = await is_owner_or_above(
        update,
        context
    )

    if not allowed:

        raise ApplicationHandlerStop()

    reply = update.message.reply_to_message

    # إذا لم يكن Reply، تجاهل بصمت
    if not reply:

        raise ApplicationHandlerStop()

    target = reply.from_user

    if not target:

        raise ApplicationHandlerStop()

    delete_admin_reply(
        update.effective_chat.id,
        target.id
    )

    await update.message.reply_text(
        "تم حذف رده."
    )

    raise ApplicationHandlerStop()


# ==================================================
# قائمة ردود الادمن
# ==================================================

async def admin_replies_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        raise ApplicationHandlerStop()

    rows = get_all_admin_replies(
        update.effective_chat.id
    )

    text = "• ردود الاعضاء في المجموعة :\n\n"

    if not rows:

        text += "لا يوجد ردود ادمن."

        await update.message.reply_text(
            text,
            parse_mode="HTML"
        )

        raise ApplicationHandlerStop()

    number = 1

    for admin_id, reply_name in rows:

        admin = await get_user_info(
            context,
            admin_id
        )

        if admin:

            mention = html_mention(admin)

        else:

            mention = f'<a href="tg://user?id={admin_id}">عضو</a>'

        text += (
            f"{number} - 〖 {reply_name} 〗- "
            f"{mention}\n"
        )

        number += 1

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )

    raise ApplicationHandlerStop()


# ==================================================
# تفعيل ردود الادمن
# ==================================================

async def enable_admin_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        raise ApplicationHandlerStop()

    allowed = await is_owner_or_above(
        update,
        context
    )

    if not allowed:

        await update.message.reply_text(
            "• هذا الأمر للمالك ومن فوق."
        )

        raise ApplicationHandlerStop()

    set_admin_replies_status(
        update.effective_chat.id,
        True
    )

    await update.message.reply_text(
        "• تم تفعيل ردود الادمن."
    )

    raise ApplicationHandlerStop()


# ==================================================
# تعطيل ردود الادمن
# ==================================================

async def disable_admin_replies(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        raise ApplicationHandlerStop()

    allowed = await is_owner_or_above(
        update,
        context
    )

    if not allowed:

        await update.message.reply_text(
            "• هذا الأمر للمالك ومن فوق."
        )

        raise ApplicationHandlerStop()

    set_admin_replies_status(
        update.effective_chat.id,
        False
    )

    await update.message.reply_text(
        "• تم تعطيل ردود الادمن."
    )

    raise ApplicationHandlerStop()


# ==================================================
# حذف جميع ردود الادمن
# ==================================================

async def delete_all_admin_replies_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not is_group(update):

        raise ApplicationHandlerStop()

    allowed = await is_owner_or_above(
        update,
        context
    )

    if not allowed:

        await update.message.reply_text(
            "• هذا الأمر للمالك ومن فوق."
        )

        raise ApplicationHandlerStop()

    delete_all_admin_replies(
        update.effective_chat.id
    )

    await update.message.reply_text(
        "• تم حذف جميع ردود الادمن."
    )

    raise ApplicationHandlerStop()


# ==================================================
# عرض رد الادمن
# ==================================================

async def check_admin_profile_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.message.text:
        return

    if not is_group(update):
        return

    reply_name = update.message.text.strip()

    if not reply_name:
        return

    row = get_admin_reply_by_name(
        update.effective_chat.id,
        reply_name
    )

    if not row:
        return

    admin_id = row[0]

    admin = await get_user_info(
        context,
        admin_id
    )

    if not admin:
        return

    bio = getattr(
        admin,
        "bio",
        None
    ) or "لا يوجد بايو."

    caption = (
        f"USE ↤ {html_mention(admin)}\n"
        f"Bio ↤ {bio}"
    )

    await send_profile(
        update,
        context,
        admin,
        caption
    )

    # مهم جدًا:
    # يمنع check_replies وباقي المعالجات من تكرار الرد.
    raise ApplicationHandlerStop()


# ==================================================
# استقبال العمليات المعلقة
# ==================================================
async def profile_reply_pending_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    print(
        f"🔥 RECEIVED: "
        f"text={update.effective_message.text if update.effective_message else None} "
        f"pending={context.user_data.get('profile_waiting_type')}"
    )
    if not update.message:
        return

    pending_type = get_profile_pending(context)

    if not pending_type:
        return

    print(
        f"🔵 Profile pending: "
        f"user={update.effective_user.id if update.effective_user else None} "
        f"type={pending_type} "
        f"text={update.message.text!r}"
    )

    # تغيير يوزر المطور
    if pending_type == "developer_username":

        await receive_developer_username(
            update,
            context
        )

        raise ApplicationHandlerStop()

    # تغيير يوزر المالك
    if pending_type == "owner_username":

        await receive_owner_username(
            update,
            context
        )

        raise ApplicationHandlerStop()

    # إضافة رد الادمن
    if pending_type == "admin_reply_name":

        await receive_my_admin_reply(
            update,
            context
        )

        raise ApplicationHandlerStop()

    clear_profile_pending(context)

    raise ApplicationHandlerStop()
