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
}


# ==================================================
# المطور
# ==================================================

DEV_PRIMARY = "primary"
DEV_SECONDARY = "secondary"


def is_developer(user_id):
    """
    يرجع نوع المطور:
    primary   = المطور الأساسي
    secondary = مطور مرفوع
    None      = ليس مطورًا
    """

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

    # المطور الأساسي
    if user_id == OWNER_ID:
        return "Dev"

    developer_type = is_developer(user_id)

    if developer_type in (
        DEV_PRIMARY,
        DEV_SECONDARY
    ):
        return "Dev"

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rank
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    data = cur.fetchone()

    conn.close()

    if data and data[0]:
        return data[0]

    return "عضو"


# ==================================================
# مستوى الشخص
# ==================================================

def get_rank_level(user_id):

    developer_type = is_developer(user_id)

    if developer_type == DEV_PRIMARY:
        return 7

    if developer_type == DEV_SECONDARY:
        return 6

    rank = get_rank(user_id)

    return RANK_LEVELS.get(rank, 0)


# ==================================================
# التحقق من قفل الأمر
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

    required_rank = data[0]

    user_level = get_rank_level(user_id)

    required_level = RANK_LEVELS.get(
        required_rank,
        0
    )

    # المطور أعلى من كل الرتب
    if is_developer(user_id):
        return True, None

    if user_level >= required_level:
        return True, None

    return False, required_rank


# ==================================================
# استخراج الشخص المستهدف
# ==================================================

async def get_target_user(update, context):

    if not update.message:
        return None

    message = update.message
    text = (message.text or "").strip()

    # ==========================================
    # 1 - بالرد
    # ==========================================

    if message.reply_to_message:
        return message.reply_to_message.from_user

    # ==========================================
    # 2 - استخراج الكلمات
    # ==========================================

    parts = text.split()

    if len(parts) < 2:
        return None

    target = parts[-1].strip()

    # ==========================================
    # 3 - الآيدي
    # ==========================================

    if target.isdigit():

        try:
            user = await context.bot.get_chat(
                int(target)
            )

            return user

        except Exception:
            return None

    # ==========================================
    # 4 - اليوزر
    # ==========================================

    if target.startswith("@"):

        username = target[1:].strip()

        if not username:
            return None

        try:
            user = await context.bot.get_chat(
                f"@{username}"
            )

            return user

        except Exception:
            return None

    return None


# ==================================================
# تحديد الرتبة المطلوبة
# ==================================================

def get_rank_from_command(text):

    text = text.strip()

    commands = {

        "رفع Dev": "Dev",
        "رفع المالك": "المالك",
        "رفع نائب المالك": "نائب المالك",
        "رفع ادمن اساسي": "ادمن اساسي",
        "رفع ادمن": "ادمن",
        "رفع مميز": "مميز",

        "تنزيل Dev": "عضو",
        "تنزيل المالك": "عضو",
        "تنزيل نائب المالك": "عضو",
        "تنزيل ادمن اساسي": "عضو",
        "تنزيل ادمن": "عضو",
        "تنزيل مميز": "عضو",
    }

    # نحاول مطابقة بداية الأمر
    for command, rank in commands.items():

        if text.startswith(command):

            if command.startswith("رفع"):
                return command, rank, True

            return command, rank, False

    return None, None, None


# ==================================================
# صلاحية تعديل الرتبة
# ==================================================

def can_change_rank(actor_id, target_id, new_rank, promoting):

    actor_dev = is_developer(actor_id)
    target_dev = is_developer(target_id)

    actor_level = get_rank_level(actor_id)
    target_level = get_rank_level(target_id)

    # ------------------------------------------
    # لا أحد يعدل المطور الأساسي
    # إلا نفسه/النظام الداخلي
    # ------------------------------------------

    if target_id == OWNER_ID:

        return False, "❌ لا يمكن تعديل المطور الأساسي."

    # ------------------------------------------
    # المطور الأساسي
    # ------------------------------------------

    if actor_dev == DEV_PRIMARY:

        return True, None

    # ------------------------------------------
    # المطور المساعد
    # ------------------------------------------

    if actor_dev == DEV_SECONDARY:

        # لا يستطيع تعديل المطور الأساسي
        if target_id == OWNER_ID:
            return False, "❌ لا يمكنك تعديل المطور الأساسي."

        # ولا يستطيع تعديل مطور مساعد آخر
        if target_dev == DEV_SECONDARY:
            return False, "❌ لا يمكنك تعديل مطور من نفس رتبتك."

        # المطور المساعد يستطيع إدارة الرتب الأقل منه
        if target_level >= actor_level:
            return False, "❌ لا يمكنك تعديل رتبة مساوية أو أعلى منك."

        # يستطيع رفع/تنزيل المالك
        if new_rank == "المالك":
            return True, None

        return True, None

    # ------------------------------------------
    # الرتب العادية
    # ------------------------------------------

    # لا يستطيع تعديل شخص أعلى أو مساوي
    if target_level >= actor_level:
        return False, "❌ لا يمكنك تعديل رتبة مساوية أو أعلى منك."

    # لا يستطيع رفع شخص إلى رتبته أو أعلى
    if promoting:

        new_level = (
            5
            if new_rank == "المالك"
            else RANK_LEVELS.get(
                new_rank,
                0
            )
        )

        if new_level >= actor_level:
            return False, "❌ لا يمكنك رفع شخص إلى رتبة مساوية أو أعلى منك."

    return True, None


# ==================================================
# تحديث رتبة المستخدم
# ==================================================

def update_user_rank(user_id, rank):

    conn = connect()
    cur = conn.cursor()

    # ------------------------------------------
    # Dev
    # ------------------------------------------

    if rank == "Dev":

        cur.execute(
            """
            INSERT OR REPLACE INTO developers
            (
                user_id,
                developer_type,
                added_by
            )
            VALUES
            (
                ?,
                'secondary',
                ?
            )
            """,
            (
                user_id,
                OWNER_ID
            )
        )

        conn.commit()
        conn.close()

        return

    # ------------------------------------------
    # إذا كان سابقًا Dev
    # ------------------------------------------

    cur.execute(
        """
        DELETE FROM developers
        WHERE user_id=?
        AND developer_type='secondary'
        """,
        (user_id,)
    )

    # ------------------------------------------
    # الرتبة العادية
    # ------------------------------------------

    cur.execute(
        """
        INSERT INTO users
        (
            user_id,
            rank
        )
        VALUES
        (
            ?,
            ?
        )
        ON CONFLICT(user_id)
        DO UPDATE SET rank=excluded.rank
        """,
        (
            user_id,
            rank
        )
    )

    conn.commit()
    conn.close()


# ==================================================
# عرض رتبتي / رتبته
# ==================================================

async def roles_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text.strip()

    # ==============================================
    # رتبتي
    # ==============================================

    if text == "رتبتي":

        user = update.effective_user

        await update.message.reply_text(
            f"• رتبتك
             هي ↤︎ {get_rank(user.id)}"
        )

        return

    # ==============================================
    # رتبته
    # ==============================================

    if text == "رتبته" or text.startswith("رتبته "):

    target = await get_target_user(
        update,
        context
    )

    if not target:

        await update.message.reply_text(
            "❌ حدد الشخص بالرد أو اليوزر أو الآيدي."
        )

        return

    rank = get_rank(target.id)

    await update.message.reply_text(
        f"• رتبته هي ↤︎ {rank}"
    )

    return
    
    # ==============================================
    # كشف المجموعة
    # ==============================================

    if text.startswith("كشف المجموعة"):

        allowed, required = check_command_permission(
            update.effective_user.id,
            "كشف المجموعة"
        )

        if not allowed:

            await update.message.reply_text(
                f"❌ هذا الأمر لـ `{required}` وفوق فقط",
                parse_mode="Markdown"
            )

            return

        conn = connect()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT rank, user_id
            FROM users
            """
        )

        users = cur.fetchall()

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

                return str(user_id)

            except Exception:

                return str(user_id)

        owner.append(
            await get_name(OWNER_ID)
        )

        for rank, user_id in users:

            if user_id == OWNER_ID:
                continue

            name = await get_name(user_id)

            if rank == "نائب المالك":
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

        for i, x in enumerate(owner, 1):
            msg += f"{i} - {x}\n"

        msg += """

• قائمة نواب المالك
━━━━━━━━━━━━
"""

        if deputy:
            for i, x in enumerate(deputy, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"

        msg += """

• قائمة الادمنية الاساسيين
━━━━━━━━━━━━
"""

        if basic:
            for i, x in enumerate(basic, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"

        msg += """

• قائمة الادمنية
━━━━━━━━━━━━
"""

        if admins:
            for i, x in enumerate(admins, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"

        msg += """

• قائمة المميزين
━━━━━━━━━━━━
"""

        if vip:
            for i, x in enumerate(vip, 1):
                msg += f"{i} - {x}\n"
        else:
            msg += "لا يوجد\n"

        await update.message.reply_text(msg)

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

    # ==============================================
    # الهدف
    # ==============================================

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

    # ==============================================
    # لا تعدل نفسك
    # ==============================================

    if target.id == actor.id:

        await update.message.reply_text(
            "❌ لا يمكنك تعديل رتبتك بنفسك."
        )

        return

    # ==============================================
    # فحص الصلاحيات
    # ==============================================

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

    # ==============================================
    # تنزيل Dev
    # ==============================================

    if command == "تنزيل Dev":

        if not is_secondary_developer(target.id):

            await update.message.reply_text(
                "❌ هذا الشخص ليس Dev."
            )

            return

        update_user_rank(
            target.id,
            "عضو"
        )

        await update.message.reply_text(
            f"✅ تم تنزيل {target.first_name} من Dev إلى عضو."
        )

        return

    # ==============================================
    # رفع Dev
    # ==============================================

    if command == "رفع Dev":

        if is_developer(target.id):

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

    # ==============================================
    # تحديث الرتبة
    # ==============================================

    old_rank = get_rank(target.id)

    update_user_rank(
        target.id,
        new_rank
    )

    await update.message.reply_text(
        f"✅ تم تعديل رتبة {target.first_name}\n"
        f"• الرتبة السابقة ↤︎ {old_rank}\n"
        f"• الرتبة الجديدة ↤︎ {new_rank}"
    )