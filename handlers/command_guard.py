from telegram import Update
from telegram.ext import (
    ContextTypes,
    ApplicationHandlerStop
)

from handlers.roles import check_command_permission
from permissions import check_user_permission


# ==================================================
# تحديد اسم الأمر الحقيقي
# ==================================================

def get_command_name(text):

    text = " ".join(
        text.strip().split()
    )

    if not text:
        return ""

    # الأوامر متعددة الكلمات
    multi_word_commands = (
        "كشف المجموعة",
        "رفع الحظر",
        "رفع الكتم",
        "حظر عام",
        "كتم عام",
        "قفل امر",
        "فتح امر",

        # أوامر الردود
        "اضف رد",
        "حذف رد",
        "مسح رد",
        "تعديل رد",
        "قائمة الردود",

        "اضف رد مميز",
        "حذف رد مميز",
        "مسح رد مميز",
        "تعديل رد مميز",
        "قائمة الردود المميزة",
    )

    for command in multi_word_commands:

        if (
            text == command
            or text.startswith(command + " ")
        ):
            return command

    # الأمر العادي = أول كلمة
    return text.split()[0]


# ==================================================
# حارس الأوامر
# ==================================================

async def command_guard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (update.message.text or "").strip()

    if not text:
        return

    # ==================================================
    # أوامر منع / سماح نفسها لا تدخل في الحارس
    # ==================================================

    if text.startswith("منع ") or text.startswith("سماح "):
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ==================================================
    # تحديد اسم الأمر تلقائيًا
    # ==================================================
    #
    # بدل ما نكتب قائمة ثابتة مثل:
    #
    # كشف المجموعة
    # رفع الحظر
    # حظر عام
    #
    # نبحث في قاعدة البيانات عن جميع الأوامر التي
    # عليها صلاحيات خاصة أو قفل رتبة.
    #
    # هذا يسمح للأوامر الجديدة بالعمل تلقائيًا.
    #
    # ==================================================

    conn = connect()
    cur = conn.cursor()

    commands = set()

    # ------------------------------
    # أوامر مقفولة حسب الرتبة
    # ------------------------------

    try:

        cur.execute(
            """
            SELECT command
            FROM command_locks
            """
        )

        rows = cur.fetchall()

        for row in rows:

            if row and row[0]:
                commands.add(row[0].strip())

    except Exception:
        pass

    # ------------------------------
    # أوامر عليها منع / سماح خاص
    # ------------------------------

    try:

        cur.execute(
            """
            SELECT permission
            FROM group_user_permissions
            WHERE chat_id=?
            """,
            (chat_id,)
        )

        rows = cur.fetchall()

        for row in rows:

            if row and row[0]:
                commands.add(row[0].strip())

    except Exception:
        pass

    conn.close()

    # ==================================================
    # الأوامر المعروفة الأساسية
    # ==================================================
    #
    # هذه فقط احتياط للأوامر التي لم يتم قفلها
    # ولم يتم وضع صلاحية خاصة لها.
    #
    # ==================================================

    base_commands = {

        "كشف المجموعة",

        "رفع الحظر",
        "رفع الكتم",

        "حظر عام",
        "كتم عام",

        "قفل امر",
        "فتح امر",

        "مسح امر",

        "مسح الاوامر المضافة",

        "الاوامر المضافة",

        "اضف امر",

        "اضف لعبة",
        "الالعاب",

        "اضف سؤال",
        "اسئلة",
        "حذف سؤال",
        "حذف لعبة",

        "تفعيل لعبة",
        "تعطيل لعبة",

        "تفعيل الالعاب",
        "تعطيل الالعاب",

        "اوامر الادمن",
        "اوامر المطور",

        "رتبتي",
        "رتبته",

        "نقاطي",
        "توب",

        "كلمات",
        "انمي",
    }

    commands.update(base_commands)

    # ==================================================
    # البحث عن أطول أمر مطابق
    # ==================================================
    #
    # مثال:
    #
    # النص:
    # رفع الحظر @user
    #
    # لدينا:
    # رفع
    # رفع الحظر
    #
    # نختار:
    # رفع الحظر
    #
    # ==================================================

    matched_command = None

    for command in sorted(
        commands,
        key=len,
        reverse=True
    ):

        if text == command or text.startswith(
            command + " "
        ):

            matched_command = command
            break

    # ==================================================
    # إذا لم يكن أمرًا معروفًا
    # ==================================================

    if not matched_command:
        return

    command = matched_command

    # ==================================================
    # منع / سماح خاص للشخص
    # ==================================================

    special_permission = check_user_permission(
        chat_id,
        user_id,
        command
    )

    # ==================================================
    # منع خاص
    # ==================================================

    if special_permission is False:

        await update.message.reply_text(
            "🚫 ليس لديك صلاحية استخدام هذا الأمر."
        )

        raise ApplicationHandlerStop()

    # ==================================================
    # سماح خاص
    # ==================================================
    #
    # إذا أعطي الشخص سماح خاص:
    # نتجاوز قفل الرتبة.
    #
    # ==================================================

    if special_permission is True:
        return

    # ==================================================
    # قفل الأمر حسب الرتبة
    # ==================================================

    allowed, required = check_command_permission(
        user_id,
        command
    )

    if not allowed:

        await update.message.reply_text(
            f"❌ هذا الأمر مخصص لرتبة {required} وفوق."
        )

        raise ApplicationHandlerStop()