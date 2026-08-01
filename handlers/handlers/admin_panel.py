from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from permission import is_admin, is_owner


# =====================
# لوحة الادمن
# =====================

async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    if not await is_admin(user_id):

        await update.message.reply_text(
            "❌ هذه اللوحة للأدمن فقط"
        )
        return



    keyboard = [

        [
            InlineKeyboardButton(
                "👤 كشف مستخدم",
                callback_data="admin_check"
            )
        ],

        [
            InlineKeyboardButton(
                "🔇 كتم",
                callback_data="admin_mute"
            ),

            InlineKeyboardButton(
                "🔊 فك الكتم",
                callback_data="admin_unmute"
            )
        ],

        [
            InlineKeyboardButton(
                "🚫 حظر",
                callback_data="admin_ban"
            ),

            InlineKeyboardButton(
                "✅ رفع الحظر",
                callback_data="admin_unban"
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
                "📋 الرتب",
                callback_data="admin_roles"
            )
        ],

        [
            InlineKeyboardButton(
                "💬 الردود",
                callback_data="admin_replies"
            )
        ]

    ]


    await update.message.reply_text(
        "🛡 لوحة الادمن\n\n"
        "اختر الأمر الذي تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )




# =====================
# لوحة المطور
# =====================

async def developer_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    user_id = update.effective_user.id


    owner = await is_owner(user_id)


    # نائب المالك مسموح
    from permission import is_admin

    admin = await is_admin(user_id)


    if not owner:

        if not admin:

            await update.message.reply_text(
                "❌ هذه اللوحة للمطور ونائب المالك فقط"
            )

            return



    keyboard = [

        [
            InlineKeyboardButton(
                "👑 إدارة الرتب",
                callback_data="dev_ranks"
            )
        ],

        [
            InlineKeyboardButton(
                "👮 إدارة الأدمنية",
                callback_data="dev_admins"
            )
        ],

        [
            InlineKeyboardButton(
                "🚫 إدارة الحظر",
                callback_data="dev_bans"
            )
        ],

        [
            InlineKeyboardButton(
                "🎮 إدارة الألعاب",
                callback_data="dev_games"
            )
        ],

        [
            InlineKeyboardButton(
                "⚙️ إعدادات البوت",
                callback_data="dev_settings"
            )
        ]

    ]


    await update.message.reply_text(
        "👑 لوحة المطور\n\n"
        "كل أدوات التحكم هنا:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )





# =====================
# ضغط الأزرار
# =====================

async def admin_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return


    await query.answer()


    data = query.data



    texts = {

        "admin_check":
        "👤 كشف المستخدم\n\n"
        "استخدم الأمر:\n"
        "كشف بالرد على المستخدم أو باليوزر أو الايدي",


        "admin_mute":
        "🔇 الكتم\n\n"
        "استخدم:\n"
        "كتم بالرد على الشخص",


        "admin_unmute":
        "🔊 فك الكتم\n\n"
        "استخدم:\n"
        "فك كتم بالرد",


        "admin_ban":
        "🚫 الحظر\n\n"
        "استخدم:\n"
        "حظر بالرد",


        "admin_unban":
        "✅ رفع الحظر\n\n"
        "استخدم:\n"
        "رفع حظر بالرد",


        "admin_games":
        "🎮 إدارة الألعاب\n\n"
        "اضف لعبة\n"
        "حذف لعبة\n"
        "تفعيل لعبة\n"
        "تعطيل لعبة",


        "admin_roles":
        "📋 الرتب\n\n"
        "رفع ادمن\n"
        "رفع ادمن اساسي\n"
        "رفع نائب المالك",


        "admin_replies":
        "💬 الردود\n\n"
        "اضف رد\n"
        "تعديل رد\n"
        "مسح رد",


        "dev_ranks":
        "👑 إدارة جميع الرتب",


        "dev_admins":
        "👮 إدارة الأدمنية",


        "dev_bans":
        "🚫 التحكم الكامل بالحظر",


        "dev_games":
        "🎮 جميع إعدادات الألعاب",


        "dev_settings":
        "⚙️ إعدادات البوت"
    }



    if data in texts:

        await query.edit_message_text(
            texts[data]
        )