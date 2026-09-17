from datetime import datetime
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import connect
from handlers.roles import get_rank
from handlers.users import get_id_target_user


OWNER_ID = 8453977662


# =========================================================
# الحالات المؤقتة
# =========================================================

DEVELOPER_USERNAME_WAIT = "profile_developer_username"
OWNER_USERNAME_WAIT = "profile_owner_username"
ADMIN_REPLY_NAME_WAIT = "profile_admin_reply_name"


# =========================================================
# إنشاء جداول النظام
# =========================================================

def create_profile_reply_tables():

    conn = connect()
    cur = conn.cursor()

    try:

        # =================================================
        # بيانات المطور - عالمية لكل القروبات
        # =================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_profile_settings
            (
                profile_type TEXT PRIMARY KEY,
                user_id BIGINT,
                username TEXT
            )
        """)

        # =================================================
        # إعدادات الملف الشخصي لكل قروب
        # =================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS group_profile_settings
            (
                chat_id BIGINT PRIMARY KEY,
                owner_user_id BIGINT,
                owner_username TEXT,
                admin_replies_enabled INTEGER DEFAULT 0
            )
        """)

        # =================================================
        # ردود الأدمن
        # كل أدمن له رد واحد فقط في كل قروب
        # =================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_replies
            (
                chat_id BIGINT,
                admin_user_id BIGINT,
                reply_name TEXT NOT NULL,
                created_date TEXT,
                PRIMARY KEY (chat_id, admin_user_id),
                UNIQUE (chat_id, reply_name)
            )
        """)

        # =================================================
        # المطور الأساسي الافتراضي
        # =================================================

        cur.execute("""
            INSERT INTO bot_profile_settings
            (
                profile_type,
                user_id,
                username
            )
            VALUES (?, ?, NULL)

            ON CONFLICT (profile_type)
            DO NOTHING
        """, (
            "developer",
            OWNER_ID
        ))

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
# جلب المطور المحفوظ
# =========================================================

def get_saved_developer():

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                user_id,
                username
            FROM bot_profile_settings
            WHERE profile_type=?
        """, (
            "developer",
        ))

        return cur.fetchone()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# حفظ المطور
# =========================================================

def save_developer(
    user_id,
    username
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO bot_profile_settings
            (
                profile_type,
                user_id,
                username
            )
            VALUES (?, ?, ?)

            ON CONFLICT (profile_type)
            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                username = EXCLUDED.username
        """, (
            "developer",
            user_id,
            username
        ))

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
# جلب إعدادات القروب
# =========================================================

def get_group_settings(chat_id):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                owner_user_id,
                owner_username,
                admin_replies_enabled
            FROM group_profile_settings
            WHERE chat_id=?
        """, (
            chat_id,
        ))

        return cur.fetchone()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# إنشاء إعدادات القروب إذا لم تكن موجودة
# =========================================================

def ensure_group_settings(chat_id):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO group_profile_settings
            (
                chat_id,
                owner_user_id,
                owner_username,
                admin_replies_enabled
            )
            VALUES (?, NULL, NULL, 0)

            ON CONFLICT (chat_id)
            DO NOTHING
        """, (
            chat_id,
        ))

        conn.commit()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# حفظ مالك القروب
# =========================================================

def save_group_owner(
    chat_id,
    user_id,
    username
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO group_profile_settings
            (
                chat_id,
                owner_user_id,
                owner_username,
                admin_replies_enabled
            )
            VALUES (?, ?, ?, 0)

            ON CONFLICT (chat_id)
            DO UPDATE SET
                owner_user_id = EXCLUDED.owner_user_id,
                owner_username = EXCLUDED.owner_username
        """, (
            chat_id,
            user_id,
            username
        ))

        conn.commit()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# تفعيل / تعطيل ردود الأدمن
# =========================================================

def set_admin_replies_status(
    chat_id,
    enabled
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO group_profile_settings
            (
                chat_id,
                owner_user_id,
                owner_username,
                admin_replies_enabled
            )
            VALUES (?, NULL, NULL, ?)

            ON CONFLICT (chat_id)
            DO UPDATE SET
                admin_replies_enabled = EXCLUDED.admin_replies_enabled
        """, (
            chat_id,
            1 if enabled else 0
        ))

        conn.commit()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# حفظ رد الأدمن
# =========================================================

def save_admin_reply(
    chat_id,
    user_id,
    reply_name
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO admin_replies
            (
                chat_id,
                admin_user_id,
                reply_name,
                created_date
            )
            VALUES (?, ?, ?, ?)
        """, (
            chat_id,
            user_id,
            reply_name,
            datetime.now().strftime(
                "%Y/%m/%d %H:%M:%S"
            )
        ))

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
# جلب رد الأدمن الخاص بالشخص
# =========================================================

def get_admin_reply_by_user(
    chat_id,
    user_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                reply_name
            FROM admin_replies
            WHERE chat_id=?
            AND admin_user_id=?
        """, (
            chat_id,
            user_id
        ))

        return cur.fetchone()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# جلب رد باسم معين
# =========================================================

def get_admin_reply_by_name(
    chat_id,
    reply_name
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                admin_user_id,
                reply_name
            FROM admin_replies
            WHERE chat_id=?
            AND reply_name=?
        """, (
            chat_id,
            reply_name
        ))

        return cur.fetchone()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# حذف رد شخص
# =========================================================

def delete_admin_reply(
    chat_id,
    user_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM admin_replies
            WHERE chat_id=?
            AND admin_user_id=?
        """, (
            chat_id,
            user_id
        ))

        deleted = cur.rowcount

        conn.commit()

        return deleted > 0

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# حذف جميع الردود في القروب
# =========================================================

def delete_all_admin_replies(
    chat_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM admin_replies
            WHERE chat_id=?
        """, (
            chat_id,
        ))

        deleted = cur.rowcount

        conn.commit()

        return deleted

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# جلب جميع ردود الأدمن للقروب
# =========================================================

def get_all_admin_replies(
    chat_id
):

    conn = connect()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                admin_user_id,
                reply_name
            FROM admin_replies
            WHERE chat_id=?
            ORDER BY created_date ASC,
                     admin_user_id ASC
        """, (
            chat_id,
        ))

        return cur.fetchall()

    finally:

        try:
            cur.close()
        except Exception:
            pass

        conn.close()


# =========================================================
# صلاحية الأدمن وفوق
# =========================================================

async def is_group_admin_or_above(
    update,
    context
):

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    # المطور الأساسي
    if user.id == OWNER_ID:
        return True

    # الرتبة الموجودة في نظام البوت
    try:

        rank = get_rank(user.id)

        if rank in (
            "ادمن",
            "ادمن اساسي",
            "نائب المالك",
            "المالك",
            "Dev"
        ):
            return True

    except Exception:
        pass

    # صلاحية Telegram
    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except Exception:

        return False


# =========================================================
# صلاحية المالك وفوق
# =========================================================

async def is_owner_or_above(
    update,
    context
):

    user = update.effective_user

    if not user:
        return False

    if user.id == OWNER_ID:
        return True

    try:

        rank = get_rank(user.id)

        if rank in (
            "المالك",
            "Dev"
        ):
            return True

    except Exception:
        pass

    return False


# =========================================================
# جلب يوزر بنفس طريقة أمر ايدي
# =========================================================
#
# نستخدم get_id_target_user الموجودة أصلًا عندك.
#
# بعدها نتحقق فقط أن الشخص موجود في القروب الحالي.
#
# =========================================================

async def get_group_user_from_username(
    update,
    context,
    username
):

    chat = update.effective_chat

    if not chat:
        return None

    username = (
        username or ""
    ).strip()

    if not username.startswith("@"):
        return None

    # =====================================================
    # إنشاء Update مؤقت بنفس طريقة أمر ايدي
    # =====================================================
    #
    # get_id_target_user يعتمد على:
    #
    # message.text
    #
    # لذلك نستخدم نفس الرسالة الحالية ونمررها له.
    #
    # لا نعدل users.py.
    # =====================================================

    original_text = update.message.text

    try:

        update.message.text = (
            f"ايدي {username}"
        )

        target = await get_id_target_user(
            update,
            context
        )

    finally:

        update.message.text = original_text

    if not target:
        return None

    user_id = getattr(
        target,
        "id",
        None
    )

    if not user_id:
        return None

    # =====================================================
    # التأكد أن الشخص موجود في القروب الحالي
    # =====================================================

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user_id
        )

    except Exception:

        return None

    if member.status in (
        "left",
        "kicked"
    ):
        return None

    return member.user


# =========================================================
# المطور
# =========================================================

async def developer_command(
    update,
    context
):

    if not update.message:
        return

    saved = get_saved_developer()

    if saved:

        developer_id = (
            saved[0]
            or OWNER_ID
        )

    else:

        developer_id = OWNER_ID

    # =====================================================
    # جلب معلومات المطور المحفوظ
    # =====================================================

    try:

        user = await context.bot.get_chat(
            developer_id
        )

    except Exception:

        await update.message.reply_text(
            "❌ تعذر جلب معلومات المطور."
        )

        return

    bot = await context.bot.get_me()

    bot_name = escape(
        bot.first_name or "البوت"
    )

    name = escape(
        user.first_name or "غير معروف"
    )

    bio = escape(
        user.bio or "لا يوجد"
    )

    text = (
        f"Dev Bot ↦ {bot_name}\n"
        f"━━━━━━━━━━━━━━\n"
        f"Dev ↦ "
        f'<a href="tg://user?id={developer_id}">'
        f"{name}"
        f"</a>\n"
        f"Bio ↦ {bio}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                user.first_name or "المطور",
                url=f"tg://user?id={developer_id}"
            )
        ]
    ])

    # =====================================================
    # صورة المطور
    # =====================================================

    try:

        photos = await context.bot.get_user_profile_photos(
            developer_id,
            limit=1
        )

        if photos.total_count > 0:

            photo = photos.photos[0][-1].file_id

            await update.message.reply_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            return

    except Exception:
        pass

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================================================
# تغيير يوزر المطور
# =========================================================

async def change_developer_username(
    update,
    context
):

    if not update.message:
        return

    if not update.effective_user:
        return

    if update.effective_user.id != OWNER_ID:

        await update.message.reply_text(
            "❌ هذا الأمر للمطور الأساسي فقط."
        )

        return

    context.user_data[
        DEVELOPER_USERNAME_WAIT
    ] = True

    await update.message.reply_text(
        "حسنًا، ارسل يوزر المطور الجديد."
    )


# =========================================================
# استقبال يوزر المطور
# =========================================================

async def receive_developer_username(
    update,
    context
):

    if not update.message:
        return False

    if not context.user_data.get(
        DEVELOPER_USERNAME_WAIT
    ):
        return False

    if not update.effective_user:
        return False

    if update.effective_user.id != OWNER_ID:

        context.user_data.pop(
            DEVELOPER_USERNAME_WAIT,
            None
        )

        return False

    username = (
        update.message.text or ""
    ).strip()

    if not username.startswith("@"):

        await update.message.reply_text(
            "❌ ارسل اليوزر بهذا الشكل:\n"
            "@username"
        )

        return True

    # =====================================================
    # جلب بنفس طريقة ايدي + التحقق من وجوده بالقروب
    # =====================================================

    target = await get_group_user_from_username(
        update,
        context,
        username
    )

    if not target:

        await update.message.reply_text(
            "❌ هذا اليوزر غير موجود في القروب الحالي."
        )

        return True

    save_developer(
        target.id,
        target.username
    )

    context.user_data.pop(
        DEVELOPER_USERNAME_WAIT,
        None
    )

    await update.message.reply_text(
        "✅ تم تغيير المطور بنجاح."
    )

    return True


# =========================================================
# المالك
# =========================================================

async def owner_command(
    update,
    context
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):

        await update.message.reply_text(
            "❌ هذا الأمر داخل القروبات فقط."
        )

        return

    ensure_group_settings(
        chat.id
    )

    settings = get_group_settings(
        chat.id
    )

    owner_id = None

    if settings:
        owner_id = settings[0]

    # =====================================================
    # إذا ما فيه مالك محفوظ:
    # نجيب المنشئ الحقيقي للقروب
    # =====================================================

    if not owner_id:

        try:

            admins = await context.bot.get_chat_administrators(
                chat.id
            )

            for member in admins:

                if member.status == "creator":

                    owner_id = member.user.id

                    save_group_owner(
                        chat.id,
                        owner_id,
                        member.user.username
                    )

                    break

        except Exception:
            pass

    if not owner_id:

        await update.message.reply_text(
            "❌ تعذر معرفة مالك القروب."
        )

        return

    # =====================================================
    # جلب معلومات المالك
    # =====================================================

    try:

        user = await context.bot.get_chat(
            owner_id
        )

    except Exception:

        await update.message.reply_text(
            "❌ تعذر جلب معلومات مالك القروب."
        )

        return

    group_name = escape(
        chat.title or "القروب"
    )

    name = escape(
        user.first_name or "غير معروف"
    )

    bio = escape(
        user.bio or "لا يوجد"
    )

    text = (
        f"Owner group ↦ {group_name}\n"
        f"━━━━━━━━━━━━━━\n"
        f"USE ↤ "
        f'<a href="tg://user?id={owner_id}">'
        f"{name}"
        f"</a>\n"
        f"bio ↤ {bio}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                user.first_name or "المالك",
                url=f"tg://user?id={owner_id}"
            )
        ]
    ])

    # =====================================================
    # صورة المالك
    # =====================================================

    try:

        photos = await context.bot.get_user_profile_photos(
            owner_id,
            limit=1
        )

        if photos.total_count > 0:

            photo = photos.photos[0][-1].file_id

            await update.message.reply_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            return

    except Exception:
        pass

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================================================
# تغيير يوزر المالك
# =========================================================

async def change_owner_username(
    update,
    context
):

    if not update.message:
        return

    if not await is_owner_or_above(
        update,
        context
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للمالك وفوق فقط."
        )

        return

    context.user_data[
        OWNER_USERNAME_WAIT
    ] = True

    await update.message.reply_text(
        "حسنًا، ارسل يوزر المالك الجديد."
    )


# =========================================================
# استقبال يوزر المالك
# =========================================================

async def receive_owner_username(
    update,
    context
):

    if not update.message:
        return False

    if not context.user_data.get(
        OWNER_USERNAME_WAIT
    ):
        return False

    if not await is_owner_or_above(
        update,
        context
    ):

        context.user_data.pop(
            OWNER_USERNAME_WAIT,
            None
        )

        return False

    username = (
        update.message.text or ""
    ).strip()

    if not username.startswith("@"):

        await update.message.reply_text(
            "❌ ارسل اليوزر بهذا الشكل:\n"
            "@username"
        )

        return True

    # =====================================================
    # نفس طريقة ايدي + التحقق من القروب
    # =====================================================

    target = await get_group_user_from_username(
        update,
        context,
        username
    )

    if not target:

        await update.message.reply_text(
            "❌ هذا اليوزر غير موجود في القروب الحالي."
        )

        return True

    save_group_owner(
        update.effective_chat.id,
        target.id,
        target.username
    )

    context.user_data.pop(
        OWNER_USERNAME_WAIT,
        None
    )

    await update.message.reply_text(
        "✅ تم تغيير مالك القروب بنجاح."
    )

    return True


# =========================================================
# إضافة ردي
# =========================================================

async def add_my_admin_reply(
    update,
    context
):

    if not update.message:
        return

    if not await is_group_admin_or_above(
        update,
        context
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للادمن وفوق فقط."
        )

        return

    chat_id = update.effective_chat.id

    ensure_group_settings(
        chat_id
    )

    settings = get_group_settings(
        chat_id
    )

    if not settings or not settings[2]:

        await update.message.reply_text(
            "❌ ردود الادمن غير مفعلة في هذه المجموعة."
        )

        return

    # =====================================================
    # هل عنده رد سابق؟
    # =====================================================

    old_reply = get_admin_reply_by_user(
        chat_id,
        update.effective_user.id
    )

    if old_reply:

        await update.message.reply_text(
            f"عندك رد قديم اسمه ({old_reply[0]}) "
            "اكتب حذف ردي لحذفه وإضافة رد جديد!"
        )

        return

    context.user_data[
        ADMIN_REPLY_NAME_WAIT
    ] = True

    await update.message.reply_text(
        "حسنًا، ارسل كلمة الرد"
    )


# =========================================================
# استقبال اسم رد الأدمن
# =========================================================

async def receive_my_admin_reply(
    update,
    context
):

    if not update.message:
        return False

    if not context.user_data.get(
        ADMIN_REPLY_NAME_WAIT
    ):
        return False

    if not await is_group_admin_or_above(
        update,
        context
    ):

        context.user_data.pop(
            ADMIN_REPLY_NAME_WAIT,
            None
        )

        return False

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    settings = get_group_settings(
        chat_id
    )

    if not settings or not settings[2]:

        context.user_data.pop(
            ADMIN_REPLY_NAME_WAIT,
            None
        )

        await update.message.reply_text(
            "❌ ردود الادمن غير مفعلة في هذه المجموعة."
        )

        return True

    # =====================================================
    # منع وجود ردين لنفس الأدمن
    # =====================================================

    old_reply = get_admin_reply_by_user(
        chat_id,
        user_id
    )

    if old_reply:

        context.user_data.pop(
            ADMIN_REPLY_NAME_WAIT,
            None
        )

        await update.message.reply_text(
            f"عندك رد قديم اسمه ({old_reply[0]}) "
            "اكتب حذف ردي لحذفه وإضافة رد جديد!"
        )

        return True

    reply_name = (
        update.message.text or ""
    ).strip()

    if not reply_name:

        await update.message.reply_text(
            "❌ ارسل كلمة الرد."
        )

        return True

    # =====================================================
    # التأكد أن الاسم غير مستخدم
    # =====================================================

    existing = get_admin_reply_by_name(
        chat_id,
        reply_name
    )

    if existing:

        await update.message.reply_text(
            "❌ اسم الرد هذا مستخدم من ادمن آخر."
        )

        return True

    try:

        save_admin_reply(
            chat_id,
            user_id,
            reply_name
        )

    except Exception:

        await update.message.reply_text(
            "❌ تعذر إضافة الرد، حاول مرة أخرى."
        )

        return True

    context.user_data.pop(
        ADMIN_REPLY_NAME_WAIT,
        None
    )

    await update.message.reply_text(
        "تم إضافة ردك الجديد!\n"
        f"اكتب «{reply_name}» لتجربته."
    )

    return True


# =========================================================
# حذف ردي
# =========================================================

async def delete_my_admin_reply(
    update,
    context
):

    if not update.message:
        return

    if not await is_group_admin_or_above(
        update,
        context
    ):
        return

    deleted = delete_admin_reply(
        update.effective_chat.id,
        update.effective_user.id
    )

    if deleted:

        await update.message.reply_text(
            "تم حذف ردك."
        )

    else:

        await update.message.reply_text(
            "❌ ما عندك رد."
        )


# =========================================================
# حذف رده
# =========================================================

async def delete_other_admin_reply(
    update,
    context
):

    if not update.message:
        return

    if not await is_owner_or_above(
        update,
        context
    ):
        return

    message = update.message

    # لازم يكون الأمر ردًا على رسالة الشخص
    if not message.reply_to_message:
        return

    target = message.reply_to_message.from_user

    if not target:
        return

    deleted = delete_admin_reply(
        message.chat.id,
        target.id
    )

    # إذا ما عنده رد:
    # تجاهل بدون أي رسالة
    if deleted:

        await message.reply_text(
            "تم حذف رده."
        )


# =========================================================
# قائمة ردود الأدمن
# =========================================================

async def admin_replies_list(
    update,
    context
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    rows = get_all_admin_replies(
        chat.id
    )

    text = (
        "• ردود الاعضاء في المجموعة :\n\n"
    )

    if not rows:

        text += (
            "لا توجد ردود ادمن حاليًا."
        )

        await update.message.reply_text(
            text
        )

        return

    for index, row in enumerate(
        rows,
        start=1
    ):

        admin_id = row[0]
        reply_name = row[1]

        try:

            user = await context.bot.get_chat(
                admin_id
            )

            name = (
                user.first_name
                or "غير معروف"
            )

        except Exception:

            name = "غير معروف"

        safe_name = escape(
            name
        )

        safe_reply_name = escape(
            reply_name
        )

        mention = (
            f'<a href="tg://user?id={admin_id}">'
            f"{safe_name}"
            f"</a>"
        )

        text += (
            f"{index} - 〖 {safe_reply_name} 〗- "
            f"{mention}\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# تفعيل ردود الأدمن
# =========================================================

async def enable_admin_replies(
    update,
    context
):

    if not update.message:
        return

    if not await is_owner_or_above(
        update,
        context
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للمالك وفوق فقط."
        )

        return

    set_admin_replies_status(
        update.effective_chat.id,
        True
    )

    await update.message.reply_text(
        "✅ تم تفعيل ردود الادمن."
    )


# =========================================================
# تعطيل ردود الأدمن
# =========================================================

async def disable_admin_replies(
    update,
    context
):

    if not update.message:
        return

    if not await is_owner_or_above(
        update,
        context
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للمالك وفوق فقط."
        )

        return

    set_admin_replies_status(
        update.effective_chat.id,
        False
    )

    await update.message.reply_text(
        "✅ تم تعطيل ردود الادمن.\n"
        "الردود الموجودة مسبقًا ستبقى تعمل."
    )


# =========================================================
# حذف جميع ردود الأدمن
# =========================================================

async def delete_all_admin_replies_command(
    update,
    context
):

    if not update.message:
        return

    if not await is_owner_or_above(
        update,
        context
    ):

        await update.message.reply_text(
            "❌ هذا الأمر للمالك وفوق فقط."
        )

        return

    delete_all_admin_replies(
        update.effective_chat.id
    )

    await update.message.reply_text(
        "✅ تم حذف جميع ردود الادمن."
    )


# =========================================================
# تشغيل ردود الأدمن
# =========================================================

async def check_admin_profile_reply(
    update,
    context
):

    if not update.message:
        return

    if not update.message.text:
        return

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in (
        "group",
        "supergroup"
    ):
        return

    # لا نفحص أوامر /
    if update.message.text.startswith("/"):
        return

    reply_name = (
        update.message.text.strip()
    )

    if not reply_name:
        return

    result = get_admin_reply_by_name(
        chat.id,
        reply_name
    )

    if not result:
        return

    admin_id = result[0]

    # =====================================================
    # جلب صاحب الرد الحقيقي
    # =====================================================

    try:

        user = await context.bot.get_chat(
            admin_id
        )

    except Exception:

        return

    name = escape(
        user.first_name or "غير معروف"
    )

    bio = escape(
        user.bio or "لا يوجد"
    )

    text = (
        f"USE ↤ "
        f'<a href="tg://user?id={admin_id}">'
        f"{name}"
        f"</a>\n"
        f"Bio ↤ {bio}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                user.first_name or "الادمن",
                url=f"tg://user?id={admin_id}"
            )
        ]
    ])

    # =====================================================
    # صورة صاحب الرد
    # =====================================================

    try:

        photos = await context.bot.get_user_profile_photos(
            admin_id,
            limit=1
        )

        if photos.total_count > 0:

            photo = photos.photos[0][-1].file_id

            await update.message.reply_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            return

    except Exception:
        pass

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================================================
# معالج استقبال البيانات المؤقتة
# =========================================================

async def profile_reply_pending_handler(
    update,
    context
):

    # =====================================================
    # يوزر المطور
    # =====================================================

    if context.user_data.get(
        DEVELOPER_USERNAME_WAIT
    ):

        handled = await receive_developer_username(
            update,
            context
        )

        if handled:
            return

    # =====================================================
    # يوزر المالك
    # =====================================================

    if context.user_data.get(
        OWNER_USERNAME_WAIT
    ):

        handled = await receive_owner_username(
            update,
            context
        )

        if handled:
            return

    # =====================================================
    # اسم رد الأدمن
    # =====================================================

    if context.user_data.get(
        ADMIN_REPLY_NAME_WAIT
    ):

        handled = await receive_my_admin_reply(
            update,
            context
        )

        if handled:
            return
