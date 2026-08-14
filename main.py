from telegram import Update
from telegram.ext import ApplicationHandlerStop

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)

from config import BOT_TOKEN
from permissions import permission_command
from database import create_tables


# ==================================================
# الأنمي
# ==================================================

from games.anime_game import (
    start_anime_quiz,
    check_anime_answer
)


# ==================================================
# البداية
# ==================================================

from handlers.start import start


# ==================================================
# لوحة الإدارة
# ==================================================

from handlers.admin_panel import (
    admin_panel,
    developer_panel,
    admin_buttons
)


# ==================================================
# قفل الأوامر
# ==================================================

from handlers.command_lock import (
    lock_command,
    save_lock_rank,
    open_command
)


# ==================================================
# حارس الأوامر
# ==================================================

from handlers.command_guard import command_guard


# ==================================================
# الأوامر المضافة
# ==================================================

from custom_commands import (
    add_command_start,
    receive_old_command,
    receive_new_command,
    custom_commands_list,
    delete_command_start,
    delete_command,
    delete_all_commands,
    check_custom_commands,
    WAIT_OLD,
    WAIT_NEW
)


# ==================================================
# الحظر والكتم
# ==================================================

from handlers.moderation import (
    check_user,
    ban_user,
    unban_user,
    global_ban,
    mute_user,
    unmute_user,
    global_mute
)


# ==================================================
# النقاط
# ==================================================

from handlers.points import (
    my_points,
    top_points
)


# ==================================================
# المستخدمين
# ==================================================

from handlers.users import (
    user_id_command,
    save_join_date,
    save_user_message
)


# ==================================================
# الرتب
# ==================================================

from handlers.roles import (
    roles_command,
    change_rank
)


# ==================================================
# الردود
# ==================================================

from handlers.replies import (
    add_reply_start,
    add_reply_handler,
    check_replies,
    replies_list,

    add_special_reply_start,
    add_special_reply_handler,
    special_replies_list,

    edit_special_reply_start,
    edit_special_reply_handler,

    edit_reply_start,
    edit_reply_handler,

    delete_special_reply_start,
    delete_special_reply_handler,

    delete_reply_start,
    delete_reply_handler,

    delete_all_replies,
    delete_all_special_replies
)


# ==================================================
# أسرع كلمة
# ==================================================

from games.speed_words import (
    start_speed_words,
    check_speed_words
)


# ==================================================
# الألعاب
# ==================================================

from games.games_manager import (
    add_game_start,
    add_game_handler,

    games_list,
    delete_game,
    enable_game,
    disable_game,
    enable_all_games,
    disable_all_games,

    add_question_start,
    add_question_handler,

    questions_list,
    delete_question,

    play_game,
    check_game_answer
)


# ==================================================
# MAIN
# ==================================================

def main():

    # ==================================================
    # إنشاء الجداول
    # ==================================================

    create_tables()


    # ==================================================
    # إنشاء التطبيق
    # ==================================================

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )


    # ==================================================
    # الأوامر المضافة
    # ==================================================

    add_command_conv = ConversationHandler(

        entry_points=[
            MessageHandler(
                filters.Regex(r"^اضف امر$"),
                add_command_start
            )
        ],

        states={

            WAIT_OLD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_old_command
                )
            ],

            WAIT_NEW: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_new_command
                )
            ]

        },

        fallbacks=[]
    )


    app.add_handler(
        add_command_conv,
        group=-2
    )


    # قائمة الأوامر المضافة

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الاوامر المضافة$"),
            custom_commands_list
        )
    )


    # بدء حذف أمر

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح امر$"),
            delete_command_start
        )
    )


    # استقبال اسم الأمر المراد حذفه

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_command
        ),
        group=-2
    )


    # حذف جميع الأوامر

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح الاوامر المضافة$"),
            delete_all_commands
        )
    )


    # ==================================================
    # منع / سماح
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(منع|سماح)(?:\s+.+)?$"
            ),
            permission_command
        ),
        group=-10
    )


    # ==================================================
    # حارس الأوامر
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            command_guard
        ),
        group=-5
    )


    # ==================================================
    # قفل وفتح الأوامر
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^قفل امر .+$"),
            lock_command
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^فتح امر .+$"),
            open_command
        ),
        group=0
    )


    # --------------------------------------------------
    # حفظ الرتبة التي اختارها المستخدم لقفل الأمر
    #
    # هذا كان ناقصًا عندك
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_lock_rank
        ),
        group=1
    )


    # ==================================================
    # START
    # ==================================================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    # ==================================================
    # المستخدم
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^ايدي$"),
            user_id_command
        )
    )


    # ==================================================
    # رتبتي / رتبته
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(رتبتي|رتبته(?:\s+@[A-Za-z0-9_]+|\s+\d+)?)$"
            ),
            roles_command
        )
    )


    # ==================================================
    # كشف المجموعة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كشف المجموعة$"
            ),
            roles_command
        )
    )


    # ==================================================
    # كشف شخص
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كشف(?:\s+.*)?$"
            ),
            check_user
        )
    )


    # ==================================================
    # الحظر والكتم
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^حظر عام(?:\s|$)"
            ),
            global_ban
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كتم عام(?:\s|$)"
            ),
            global_mute
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^رفع الحظر(?:\s|$)"
            ),
            unban_user
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^رفع الكتم(?:\s|$)"
            ),
            unmute_user
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^حظر(?:\s|$)"
            ),
            ban_user
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كتم(?:\s|$)"
            ),
            mute_user
        )
    )


    # ==================================================
    # رفع / تنزيل الرتب
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(رفع|تنزيل) "
                r"(Dev|المالك|نائب المالك|ادمن اساسي|ادمن|مميز)"
                r"(?:\s+(@[A-Za-z0-9_]+|\d+))?$"
            ),
            change_rank
        )
    )


    # ==================================================
    # الردود المميزة
    # ==================================================

    # بدء إضافة رد مميز

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف رد مميز$"),
            add_special_reply_start
        ),
        group=0
    )


    # استقبال خطوات إضافة الرد المميز

    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_special_reply_handler
        ),
        group=2
    )


    # --------------------------------------------------
    # تعديل رد مميز
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعديل رد مميز$"),
            edit_special_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            edit_special_reply_handler
        ),
        group=3
    )


    # --------------------------------------------------
    # حذف رد مميز
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح رد مميز$"),
            delete_special_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            delete_special_reply_handler
        ),
        group=4
    )


    # --------------------------------------------------
    # قائمة الردود المميزة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الردود المميزة$"),
            special_replies_list
        )
    )


    # ==================================================
    # الردود العادية
    # ==================================================

    # --------------------------------------------------
    # إضافة رد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف رد$"),
            add_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_reply_handler
        ),
        group=5
    )


    # --------------------------------------------------
    # تعديل رد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعديل رد$"),
            edit_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            edit_reply_handler
        ),
        group=6
    )


    # --------------------------------------------------
    # حذف رد
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح رد$"),
            delete_reply_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            delete_reply_handler
        ),
        group=7
    )


    # --------------------------------------------------
    # قائمة الردود
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الردود$"),
            replies_list
        )
    )


    # --------------------------------------------------
    # حذف جميع الردود
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح الردود$"),
            delete_all_replies
        )
    )


    # --------------------------------------------------
    # حذف جميع الردود المميزة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^مسح الردود المميزة$"),
            delete_all_special_replies
        )
    )


    # ==================================================
    # النقاط
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^نقاطي$"),
            my_points
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^توب$"),
            top_points
        )
    )


    # ==================================================
    # أسرع كلمة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^كلمات$"),
            start_speed_words
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_speed_words
        ),
        group=10
    )


    # ==================================================
    # الألعاب
    # ==================================================

    # --------------------------------------------------
    # إضافة لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف لعبة$"),
            add_game_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_game_handler
        ),
        group=21
    )


    # --------------------------------------------------
    # قائمة الألعاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^الالعاب$"),
            games_list
        )
    )


    # ==================================================
    # الأسئلة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اضف سؤال(?:\s|$)"),
            add_question_start
        ),
        group=0
    )


    app.add_handler(
        MessageHandler(
            (
                filters.TEXT |
                filters.PHOTO
            ) & ~filters.COMMAND,
            add_question_handler
        ),
        group=23
    )


    # --------------------------------------------------
    # قائمة الأسئلة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اسئلة"),
            questions_list
        )
    )


    # --------------------------------------------------
    # حذف سؤال
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف سؤال"),
            delete_question
        )
    )


    # --------------------------------------------------
    # حذف لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حذف لعبة"),
            delete_game
        )
    )


    # --------------------------------------------------
    # تفعيل لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تفعيل لعبة"),
            enable_game
        )
    )


    # --------------------------------------------------
    # تعطيل لعبة
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعطيل لعبة"),
            disable_game
        )
    )


    # --------------------------------------------------
    # تفعيل جميع الألعاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تفعيل الالعاب$"),
            enable_all_games
        )
    )


    # --------------------------------------------------
    # تعطيل جميع الألعاب
    # --------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^تعطيل الالعاب$"),
            disable_all_games
        )
    )


    # ==================================================
    # لعبة الأنمي
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^انمي$"),
            start_anime_quiz
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_anime_answer
        ),
        group=32
    )


    # ==================================================
    # الألعاب المخصصة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            play_game
        ),
        group=30
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_game_answer
        ),
        group=31
    )


    # ==================================================
    # الأوامر المضافة وتشغيلها
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_custom_commands
        ),
        group=35
    )


    # ==================================================
    # تشغيل الردود
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_replies
        ),
        group=40
    )


    # ==================================================
    # المستخدمين
    # ==================================================

    app.add_handler(
        ChatMemberHandler(
            save_join_date,
            ChatMemberHandler.CHAT_MEMBER
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_user_message
        ),
        group=50
    )


    # ==================================================
    # لوحة الإدارة
    # ==================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اوامر الادمن$"),
            admin_panel
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex(r"^اوامر المطور$"),
            developer_panel
        )
    )


    app.add_handler(
        CallbackQueryHandler(
            admin_buttons
        )
    )


    # ==================================================
    # إيقاف المعالجات بعد الفوز في الألعاب
    # ==================================================

    async def stop_after_game(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        from games.games_manager import active_games


        if not update.effective_chat:
            return


        chat_id = update.effective_chat.id


        if chat_id not in active_games:
            return


        raise ApplicationHandlerStop()


    app.add_handler(
        MessageHandler(
            filters.ALL,
            stop_after_game
        ),
        group=100
    )


    # ==================================================
    # تشغيل البوت
    # ==================================================

    print("🤖 Bot Started...")


    app.run_polling()


# ==================================================
# التشغيل
# ==================================================

if __name__ == "__main__":
    main()