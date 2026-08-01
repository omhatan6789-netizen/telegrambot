from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.roles import get_rank


OWNER_ID = 8453977662


RANKS = {
    "عضو": 0,
    "💎 مميز": 1,
    "🛡 ادمن": 2,
    "🟣 ادمن أساسي": 3,
    "🤍 نائب المالك": 4,
    "👑 المالك": 5
}


def can_open_admin(user_id):

    if user_id == OWNER_ID:
        return True

    rank = get_rank(user_id)

    return RANKS.get(rank, 0) >= 2



async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    if not can_open_admin(user_id):

        await update.message.reply_text(
            "❌ هذه اللوحة للأدمن وفوق فقط"
        )

        return



    keyboard = [

        [
            InlineKeyboardButton(
                "🛡 الرتب",
                callback_data="admin_ranks"
            )
        ],

        [
            InlineKeyboardButton(
                "🚫 الحظر والكتم",
                callback_data="admin_ban_mute"
            )
        ],

        [
            InlineKeyboardButton(
                "🎮 الألعاب",
                callback_data="admin_games"
            )
        ],

        [
            InlineKeyboardButton(
                "💬 الردود",
                callback_data="admin_replies"
            )
        ],

        [
            InlineKeyboardButton(
                "🔎 الكشف",
                callback_data="admin_check"
            )
        ]

    ]


    await update.message.reply_text(
        "🛡 اوامر الأدمن\n\nاختر القسم:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )




async def admin_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()


    if query.data == "admin_ranks":

        text = """
    🛡 أوامر الرتب:

    📌 رفع الرتب:
    رفع مميز
    رفع ادمن
    رفع ادمن اساسي
    رفع نائب المالك


    📌 تنزيل الرتب:
    تنزيل مميز
    تنزيل ادمن
    تنزيل ادمن اساسي
    تنزيل نائب المالك


    طريقة الاستخدام:
    ↩️ رد على رسالة الشخص ثم اكتب الأمر

    مثال:
    رفع ادمن
    """


    elif query.data == "admin_ban_mute":

        text = """
    🚫 أوامر الحماية:

    📌 الحظر:
    حظر (بالرد أو الآيدي)
    رفع الحظر (بالرد أو الآيدي)

    🌍 الحظر العام:
    حظر عام (بالرد أو الآيدي)

    📌 الكتم:
    كتم (بالرد أو الآيدي)
    رفع الكتم (بالرد أو الآيدي)

    🌍 الكتم العام:
    كتم عام (بالرد أو الآيدي)

    🔎 الكشف:
    كشف (بالرد أو الآيدي أو اليوزر)

    ⏱ المدة:
    مثال:
    كتم 10د
    كتم 1س
    كتم 30ث
    كتم 1ي
    """


    elif query.data == "admin_games":

        text = """
    🎮 أوامر الألعاب:

    📌 إضافة لعبة:
    اضف لعبة

    📌 حذف لعبة:
    حذف لعبة اسم اللعبة

    📌 عرض الألعاب:
    الالعاب

    📌 إضافة سؤال:
    اضف سؤال اسم اللعبة

    📌 عرض أسئلة لعبة:
    اسئلة اسم اللعبة

    📌 حذف سؤال:
    حذف سؤال اسم اللعبة رقم السؤال

    📌 تفعيل لعبة:
    تفعيل لعبة اسم اللعبة

    📌 تعطيل لعبة:
    تعطيل لعبة اسم اللعبة

    📌 تفعيل جميع الألعاب:
    تفعيل الالعاب

    📌 تعطيل جميع الألعاب:
    تعطيل الالعاب
    """



    elif query.data == "admin_replies":

        text = """
    💬 أوامر الردود:

    📌 الردود العادية:

    اضف رد
    تعديل رد
    مسح رد
    الردود


    ⭐ الردود المميزة:

    اضف رد مميز
    تعديل رد مميز
    مسح رد مميز
    الردود المميزة


    🗑 حذف الكل:

    مسح الردود
    مسح الردودالمميزة
    """


    elif query.data == "admin_check":

        text = """
    🔎 أمر الكشف:

    كشف بالرد
    كشف بالآيدي
    كشف باليوزر
    """


    else:
        text = "❌ لا يوجد"


    await query.edit_message_text(
        text
    )