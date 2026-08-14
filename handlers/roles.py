from telegram import Update
from telegram.ext import ContextTypes

from database import connect


# ==================================================
# الإعدادات
# ==================================================

OWNER_ID = 8453977662


# ==================================================
# مستويات الرتب
# ==================================================

RANK_LEVELS = {
    "عضو": 0,
    "مميز": 1,
    "ادمن": 2,
    "ادمن اساسي": 3,
    "نائب المالك": 4,
    "المالك": 5,
    "Dev": 6
}


# ==================================================
# أنواع المطور
# ==================================================

DEV_PRIMARY = "primary"
DEV_SECONDARY = "secondary"


# ==================================================
# توحيد الرتبة
# ==================================================

def normalize_rank(rank):

    if not rank:
        return "عضو"

    rank = str(rank).strip()

    if rank in RANK_LEVELS:
        return rank

    return "عضو"


# ==================================================
# نوع المطور
# ==================================================

def is_developer(user_id):

    # المالك الأساسي ثابت دائمًا
    if user_id == OWNER_ID:
        return DEV_PRIMARY

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT developer_type
        FROM developers
        WHERE user_id=?
        """,
        (user_id,)
    )

    result = cur.fetchone()

    conn.close()

    if not result:
        return None

    return result[0]


def is_primary_developer(user_id):
    return is_developer(user_id) == DEV_PRIMARY


def is_secondary_developer(user_id):
    return is_developer(user_id) == DEV_SECONDARY


# ==================================================
# الحصول على الرتبة
# ==================================================

def get_rank(user_id):

    # ==================================================
    # المالك الأساسي
    # ==================================================

    if user_id == OWNER_ID:
        return "Dev"

    conn = connect()
    cur = conn.cursor()

    # ==================================================
    # أولاً: المطور المساعد
    # ==================================================

    cur.execute(
        """
        SELECT developer_type
        FROM developers
        WHERE user_id=?
        """,
        (user_id,)
    )

    developer = cur.fetchone()

    if developer:
        if developer[0] in (
            DEV_PRIMARY,
            DEV_SECONDARY
        ):
            conn.close()
            return "Dev"

    # ==================================================
    # قراءة الرتبة من users
    # ==================================================

    cur.execute(
        """
        SELECT rank
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    user_data = cur.fetchone()

    user_rank = None

    if user_data:
        user_rank = normalize_rank(user_data[0])

    # ==================================================
    # قراءة النسخة الاحتياطية من ranks
    # ==================================================

    cur.execute(
        """
        SELECT rank
        FROM ranks
        WHERE user_id=?
        """,
        (user_id,)
    )

    rank_data = cur.fetchone()

    saved_rank = None

    if rank_data:
        saved_rank = normalize_rank(rank_data[0])

    # ==================================================
    # إذا ranks فيها رتبة أعلى من users
    # نستخدم الرتبة المحفوظة
    # ==================================================

    if saved_rank:

        user_level = RANK_LEVELS.get(
            user_rank,
            0
        )

        saved_level = RANK_LEVELS.get(
            saved_rank,
            0
        )

        if saved_level > user_level:

            # إصلاح users أيضًا حتى تصير النسختان متطابقتين
            cur.execute(
                """
                UPDATE users
                SET rank=?
                WHERE user_id=?
                """,
                (
                    saved_rank,
                    user_id
                )
            )

            conn.commit()
            conn.close()

            return saved_rank

    conn.close()

    return user_rank or saved_rank or "عضو"


# ==================================================
# مستوى الرتبة
# ==================================================

def get_rank_level(user_id):

    # المالك الأساسي
    if user_id == OWNER_ID:
        return 7

    # أي Dev مساعد
    if is_secondary_developer(user_id):
        return 6

    rank = get_rank(user_id)

    return RANK_LEVELS.get(
        rank,
        0
    )


# ==================================================
# فحص صلاحية الأمر المقفول
# ==================================================

def check_command_permission(user_id, command):

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rank
        FROM command_locks
        WHERE command=?
        """,
        (command,)
    )

    data = cur.fetchone()

    conn.close()

    # الأمر غير مقفول
    if not data:
        return True, None

    required_rank = normalize_rank(data[0])

    user_level = get_rank_level(user_id)

    required_level = RANK_LEVELS.get(
        required_rank,
        0
    )

    # المطورون يتجاوزون القفل
    if is_developer(user_id):
        return True, None

    if user_level >= required_level:
        return True, None

    return False, required_rank


# ==================================================
# استخراج الشخص المستهدف
# ==================================================

async def get_target_user(
    update,
    context
):

    if not update.message:
        return None

    message = update.message

    # ==================================================
    # أول أولوية: الرد على رسالة
    # ==================================================

    if message.reply_to_message:

        replied_user = message.reply_to_message.from_user

        if replied_user:
            return replied_user

    # ==================================================
    # إذا لم يكن ردًا، نقرأ الآيدي / اليوزر
    # ==================================================

    text = (
        message.text or ""
    ).strip()

    parts = text.split()

    if len(parts) < 2:
        return None

    target = parts[-1].strip()

    # ==================================================
    # آيدي
    # ==================================================

    if target.isdigit():

        try:

            chat = await context.bot.get_chat(
                int(target)
            )

            return chat

        except Exception:
            return None

    # ==================================================
    # يوزر
    # ==================================================

    if target.startswith("@"):

        try:

            chat = await context.bot.get_chat(
                target
            )

            return chat

        except Exception:
            return None

    return None


# ==================================================
# تحديد الرتبة من الأمر
# ==================================================

def get_rank_from_command(text):

    text = (
        text or ""
    ).strip()

    commands = {

        "رفع Dev": ("Dev", True),
        "رفع المالك": ("المالك", True),
        "رفع نائب المالك": ("نائب المالك", True),
        "رفع ادمن اساسي": ("ادمن اساسي", True),
        "رفع ادمن": ("ادمن", True),
        "رفع مميز": ("مميز", True),

        "تنزيل Dev": ("عضو", False),
        "تنزيل المالك": ("عضو", False),
        "تنزيل نائب المالك": ("عضو", False),
        "تنزيل ادمن اساسي": ("عضو", False),
        "تنزيل ادمن": ("عضو", False),
        "تنزيل مميز": ("عضو", False),
    }

    for command in sorted(
        commands,
        key=len,
        reverse=True
    ):

        if (
            text == command
            or text.startswith(command + " ")
        ):

            rank, promoting = commands[command]

            return (
                command,
                rank,
                promoting
            )

    return None, None, None


# ==================================================
# صلاحية تعديل الرتبة
# ==================================================

def can_change_rank(
    actor_id,
    target_id,
    new_rank,
    promoting
):

    actor_dev = is_developer(actor_id)
    target_dev = is_developer(target_id)

    actor_level = get_rank_level(actor_id)
    target_level = get_rank_level(target_id)

    # ==================================================
    # حماية المالك الأساسي
    # ==================================================

    if target_id == OWNER_ID:

        return (
            False,
            "❌ لا يمكن تعديل المطور الأساسي."
        )

    # ==================================================
    # المطور الأساسي
    # ==================================================

    if actor_dev == DEV_PRIMARY:
        return True, None

    # ==================================================
    # المطور المساعد
    # ==================================================

    if actor_dev == DEV_SECONDARY:

        if target_dev == DEV_PRIMARY:

            return (
                False,
                "❌ لا يمكنك تعديل المطور الأساسي."
            )

        if target_dev == DEV_SECONDARY:

            return (
                False,
                "❌ لا يمكنك تعديل مطور من نفس رتبتك."
            )

        if target_level >= actor_level:

            return (
                False,
                "❌ لا يمكنك تعديل رتبة مساوية أو أعلى منك."
            )

        if promoting:

            new_level = RANK_LEVELS.get(
                new_rank,
                0
            )

            if new_level >= actor_level:

                return (
                    False,
                    "❌ لا يمكنك رفع شخص إلى رتبة مساوية أو أعلى منك."
                )

        return True, None

    # ==================================================
    # الرتب العادية
    # ==================================================

    if target_level >= actor_level:

        return (
            False,
            "❌ لا يمكنك تعديل رتبة مساوية أو أعلى منك."
        )

    if promoting:

        new_level = RANK_LEVELS.get(
            new_rank,
            0
        )

        if new_level >= actor_level:

            return (
                False,
                "❌ لا يمكنك رفع شخص إلى رتبة مساوية أو أعلى منك."
            )

    return True, None


# ==================================================
# حفظ الرتبة
# ==================================================

def update_user_rank(
    user_id,
    rank
):

    rank = normalize_rank(rank)

    conn = connect()
    cur = conn.cursor()

    # ==================================================
    # Dev مساعد
    # ==================================================

    if rank == "Dev":

        cur.execute(
            """
            INSERT INTO developers
            (
                user_id,
                developer_type,
                added_by
            )
            VALUES (?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                developer_type='secondary',
                added_by=excluded.added_by
            """,
            (
                user_id,
                DEV_SECONDARY,
                OWNER_ID
            )
        )

    else:

        cur.execute(
            """
            DELETE FROM developers
            WHERE user_id=?
            AND developer_type='secondary'
            """,
            (user_id,)
        )

    # ==================================================
    # users
    # ==================================================

    cur.execute(
        """
        INSERT INTO users
        (
            user_id,
            username,
            first_name,
            messages,
            rank
        )
        VALUES (?, '', '', 0, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            rank=excluded.rank
        """,
        (
            user_id,
            rank
        )
    )

    # ==================================================
    # ranks
    # ==================================================

    cur.execute(
        """
        INSERT INTO ranks
        (
            user_id,
            rank
        )
        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            rank=excluded.rank
        """,
        (
            user_id,
            rank
        )
    )

    conn.commit()
    conn.close()


# ==================================================
# عرض الرتبة
# ==================================================

async def roles_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (
        update.message.text or ""
    ).strip()

    # ==================================================
    # رتبتي
    # ==================================================

    if text == "رتبتي":

        user = update.effective_user

        rank = get_rank(
            user.id
        )

        await update.message.reply_text(
            f"• رتبتك هي ↤︎ {rank}"
        )

        return

    # ==================================================
    # رتبته
    # ==================================================

    if (
        text == "رتبته"
        or text.startswith("رتبته ")
    ):

        target = await get_target_user(
            update,
            context
        )

        if not target:

            await update.message.reply_text(
                "❌ حدد الشخص بالرد أو اليوزر أو الآيدي."
            )

            return

        rank = get_rank(
            target.id
        )

        await update.message.reply_text(
            f"• رتبته هي ↤︎ {rank}"
        )

        return

    # ==================================================
    # كشف المجموعة
    # ==================================================

    if text == "كشف المجموعة":

        allowed, required = check_command_permission(
            update.effective_user.id,
            "كشف المجموعة"
        )

        if not allowed:

            await update.message.reply_text(
                f"❌ هذا الأمر لـ {required} وفوق فقط"
            )

            return

        conn = connect()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id
            FROM users
            """
        )

        user_rows = cur.fetchall()

        conn.close()

        owner = []
        deputy = []
        basic = []
        admins = []
        vip = []

        async def get_name(user_id):

            try:

                info = await context.bot.get_chat(
                    user_id
                )

                if info.username:
                    return f"@{info.username}"

                return (
                    info.first_name
                    or str(user_id)
                )

            except Exception:

                return str(user_id)

        for row in user_rows:

            user_id = row[0]

            rank = get_rank(
                user_id
            )

            name = await get_name(
                user_id
            )

            if rank == "المالك":

                owner.append(name)

            elif rank == "Dev":

                continue

            elif rank == "نائب المالك":

                deputy.append(name)

            elif rank == "ادمن اساسي":

                basic.append(name)

            elif rank == "ادمن":

                admins.append(name)

            elif rank == "مميز":

                vip.append(name)

        msg = """
كشف المجموعة: 📋

• قائمة المالك
━━━━━━━━━━━━
"""

        if owner:

            for i, name in enumerate(
                owner,
                1
            ):
                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة نواب المالك
━━━━━━━━━━━━
"""

        if deputy:

            for i, name in enumerate(
                deputy,
                1
            ):
                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة الادمنية الاساسيين
━━━━━━━━━━━━
"""

        if basic:

            for i, name in enumerate(
                basic,
                1
            ):
                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة الادمنية
━━━━━━━━━━━━
"""

        if admins:

            for i, name in enumerate(
                admins,
                1
            ):
                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        msg += """
• قائمة المميزين
━━━━━━━━━━━━
"""

        if vip:

            for i, name in enumerate(
                vip,
                1
            ):
                msg += f"{i} - {name}\n"

        else:

            msg += "لا يوجد\n"

        await update.message.reply_text(
            msg
        )

        return


# ==================================================
# رفع / تنزيل الرتب
# ==================================================

async def change_rank(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    actor = update.effective_user

    text = (
        update.message.text or ""
    ).strip()

    command, new_rank, promoting = get_rank_from_command(
        text
    )

    if not command:
        return

    # ==================================================
    # الهدف
    # ==================================================

    target = await get_target_user(
        update,
        context
    )

    if not target:

        await update.message.reply_text(
            "❌ حدد الشخص بالرد أو اليوزر أو الآيدي.\n\n"
            "مثال:\n"
            "رفع ادمن\n"
            "رفع ادمن @username\n"
            "رفع ادمن 123456789"
        )

        return

    # ==================================================
    # منع تعديل النفس
    # ==================================================

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل رتبتك بنفسك."
        )

        return

    # ==================================================
    # حماية Dev الأساسي
    # ==================================================

    if target.id == OWNER_ID:

        await update.message.reply_text(
            "❌ لا يمكن تعديل رتبة الـDev الأساسي."
        )

        return

    # ==================================================
    # فحص الصلاحية
    # ==================================================

    allowed, reason = can_change_rank(
        actor.id,
        target.id,
        new_rank,
        promoting
    )

    if not allowed:

        await update.message.reply_text(
            reason
        )

        return

    # ==================================================
    # تنزيل Dev
    # ==================================================

    if command == "تنزيل Dev":

        if not is_secondary_developer(
            target.id
        ):

            await update.message.reply_text(
                "❌ هذا الشخص ليس Dev."
            )

            return

        old_rank = get_rank(
            target.id
        )

        update_user_rank(
            target.id,
            "عضو"
        )

        await update.message.reply_text(
            f"✅ تم تنزيل {target.first_name} من "
            f"{old_rank} إلى عضو."
        )

        return

    # ==================================================
    # رفع Dev
    # ==================================================

    if command == "رفع Dev":

        if is_developer(
            target.id
        ):

            await update.message.reply_text(
                "❌ هذا الشخص Dev بالفعل."
            )

            return

        update_user_rank(
            target.id,
            "Dev"
        )

        await update.message.reply_text(
            f"✅ تم رفع {target.first_name} إلى Dev."
        )

        return

    # ==================================================
    # الرتبة العادية
    # ==================================================

    old_rank = get_rank(
        target.id
    )

    update_user_rank(
        target.id,
        new_rank
    )

    await update.message.reply_text(
        f"✅ تم تعديل رتبة {target.first_name}\n"
        f"• الرتبة السابقة ↤︎ {old_rank}\n"
        f"• الرتبة الجديدة ↤︎ {new_rank}"
    )