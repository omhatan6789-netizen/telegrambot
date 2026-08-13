from telegram import Update
from telegram.ext import ApplicationHandlerStop
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
    filters
)

from config import BOT_TOKEN
from permissions import permission_command
from database import create_tables
from games.anime_game import (
    start_anime_quiz,
    check_anime_answer
)

from handlers.start import start
from handlers.admin_panel import (
    admin_panel,
    developer_panel,
    admin_buttons
)

from handlers.command_lock import (
    lock_command,
    save_lock_rank,
    open_command
)

from handlers.command_guard import command_guard

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

from telegram.ext import ConversationHandler
from handlers.moderation import (
    check_user,
    ban_user,
    unban_user,
    global_ban,
    mute_user,
    unmute_user,
    global_mute
)
from handlers.points import (
    my_points,
    top_points
)


from handlers.users import (
    user_id_command,
    save_join_date,
    save_user_message
)


from handlers.roles import (
    roles_command,
    change_rank
)


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


from games.speed_words import (
    start_speed_words,
    check_speed_words
)


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



def main():

    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    # =====================
    # الأوامر المضافة
    # =====================

    add_command_conv = ConversationHandler(

        entry_points=[
            MessageHandler(
                filters.Regex("^اضف امر$"),
                add_command_start
            )
        ],

        states={

            WAIT_OLD: [
                MessageHandler(
                    filters.TEXT,
                    receive_old_command
                )
            ],

            WAIT_NEW: [
                MessageHandler(
                    filters.TEXT,
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

    app.add_handler(
        MessageHandler(
            filters.Regex("^الاوامر المضافة$"),
            custom_commands_list
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^مسح امر$"),
            delete_command_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_command
        ),
        group=-2
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^مسح الاوامر المضافة$"),
            delete_all_commands
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_custom_commands
        ),
        group=-3
    )

    # =====================
    # منع / سماح الصلاحيات
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(منع|سماح)\s+.+"
            ),
            permission_command
        ),
        group=-2
    )

    # =====================
    # حراسة الأوامر
    # =====================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            command_guard
        ),
        group=-1
    )

    # =====================
    # قفل وفتح الأوامر
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^قفل امر "),
            lock_command
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^فتح امر "),
            open_command
        )
    )

    # =====================
    # start
    # =====================

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # =====================
    # المستخدم
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^ايدي$"),
            user_id_command
        )
    )

   
    # رتبتي / رتبته
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(رتبتي|رتبته(?:\s+@[A-Za-z0-9_]+|\s+\d+)?)$"
            ),
            roles_command
        )
    )

    # كشف المجموعة
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كشف المجموعة$"
            ),
            roles_command
        )
    )

    # كشف شخص
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^كشف(?:\s+.*)?$"
            ),
            check_user
        )
    )

    # =====================
    # الحظر والكتم
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حظر عام($|\s)"),
            global_ban
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^كتم عام($|\s)"),
            global_mute
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^رفع الحظر($|\s)"),
            unban_user
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^رفع الكتم($|\s)"),
            unmute_user
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^حظر($|\s)"),
            ban_user
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^كتم($|\s)"),
            mute_user
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(رفع|تنزيل) (Dev|المالك|نائب المالك|ادمن اساسي|ادمن|مميز)(\s+(@[A-Za-z0-9_]+|\d+))?$"
            ),
            change_rank
        )
    )


    # =====================
    # الردود المميزة
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^اضف رد مميز$"),
            add_special_reply_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_special_reply_handler
        ),
        group=1
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^تعديل رد مميز$"),
            edit_special_reply_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            edit_special_reply_handler
        ),
        group=2
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^مسح رد مميز$"),
            delete_special_reply_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            delete_special_reply_handler
        ),
        group=3
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^الردود المميزة$"),
            special_replies_list
        )
    )

    # =====================
    # الردود العادية
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^اضف رد$"),
            add_reply_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            add_reply_handler
        ),
        group=4
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^تعديل رد$"),
            edit_reply_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            edit_reply_handler
        ),
        group=5
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^مسح رد$"),
            delete_reply_start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            delete_reply_handler
        ),
        group=6
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^الردود$"),
            replies_list
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^مسح الردود$"),
            delete_all_replies
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^مسح الردود المميزة$"),
            delete_all_special_replies
        )
    )

    # =====================
    # النقاط
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^نقاطي$"),
            my_points
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^توب$"),
            top_points
        )
    )

    # =====================
    # أسرع كلمة
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^كلمات$"),
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



    # =====================
    # الألعاب
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^اضف لعبة$"),
            add_game_start
        ),
        group=20
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            add_game_handler
        ),
        group=21
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^الالعاب$"),
            games_list
        )
    )

    # =====================
    # إضافة الأسئلة
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^اضف سؤال"),
            add_question_start
        ),
        group=22
    )

    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            add_question_handler
        ),
        group=23
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^اسئلة"),
            questions_list
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^حذف سؤال"),
            delete_question
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^حذف لعبة"),
            delete_game
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^تفعيل لعبة"),
            enable_game
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^تعطيل لعبة"),
            disable_game
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^تفعيل الالعاب$"),
            enable_all_games
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^تعطيل الالعاب$"),
            disable_all_games
        )
    )

    # =====================
    # لعبة الأنمي
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^انمي$"),
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

    # =====================
    # الألعاب المخصصة
    # =====================

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

       
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_custom_commands
        ),
        group=35
    )

    
    # =====================
    # تشغيل الردود
    # =====================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_replies
        ),
        group=40
    )

    # =====================
    # المستخدمين
    # =====================

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

    # =====================
    # لوحة الإدارة
    # =====================

    app.add_handler(
        MessageHandler(
            filters.Regex("^اوامر الادمن$"),
            admin_panel
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^اوامر المطور$"),
            developer_panel
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_buttons
        )
    )

    # =====================
    # حفظ رتب قفل الأوامر
    # =====================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_lock_rank
        ),
        group=60
    )

    # =====================
    # إيقاف المعالجات بعد الفوز
    # (اختياري لكن يمنع تعارض الألعاب والردود)
    # =====================

    async def stop_after_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from games.games_manager import active_games

        if update.effective_chat and update.effective_chat.id not in active_games:
            return

        raise ApplicationHandlerStop()

    app.add_handler(
        MessageHandler(
            filters.ALL,
            stop_after_game
        ),
        group=100
    )

    print("🤖 Bot Started...")

    app.run_polling()


if __name__ == "__main__":
    main()