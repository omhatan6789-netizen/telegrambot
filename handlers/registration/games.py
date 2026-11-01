
from telegram.ext import (
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

from games.demon_nawaf import (
    start_demon_nawaf,
    demon_nawaf_callback,
    demon_nawaf_private_start,
)

from handlers.games_menu import (
    games_menu_command,
    games_menu_callback,
)

from games.big_game_join import (
    join_big_game_router,
    leave_big_game_router,
    begin_big_game_router,
    continue_big_game_router,
    end_big_game_router,
)

from games.xo import (
    start_xo_game,
    xo_callback,
)

from games.rock_paper_scissors import (
    start_rock_paper_scissors,
    rock_paper_scissors_callback,
)

from games.word_race import (
    start_word_race,
    word_race_mode,
    word_race_distribution,
    word_race_manual_team,
    word_race_callback,
    check_word_race_message,
    WordRaceActiveFilter,
)

from games.engine import game_message_handler

from games.image_quiz.image_quiz import (
    start_image_quiz,
    add_image_quiz_player,
    image_quiz_settings,
    add_manual_image_command,
    receive_manual_image,
    cancel_manual_image,
    delete_manual_image_command,
    receive_delete_manual_image,
    cancel_delete_manual_image,
    image_quiz_callback,
    check_image_quiz_message,
)

from games.liars_table import (
    start_liars_table,
    liars_table_callback,
    liars_table_private_start,
)

from games.liar import (
    start_liar_game_lobby,
    force_voting,
    liar_lobby_callback,
    liar_vote_callback,
    liar_guess_callback,
    check_liar_message,
)

from games.penalties import (
    start_penalty_game,
    distribute_penalties,
    manual_team_command,
    distribution_callback,
    penalty_direction_callback,
)

from games.hide_and_seek import (
    start_hide_game,
    hide_number_callback,
    search_number_callback,
)

from handlers.games_help import games_help


def build_games_handlers(app):
    handlers = [

        # ==========================================
        # ديمون نواف
        # ==========================================

        (
            122,
            -4,
            MessageHandler(
                (
                    filters.ChatType.GROUPS
                    | filters.ChatType.PRIVATE
                )
                & filters.Regex(
                    r"^(?:ديمون نواف|Demon Nawaf)$"
                ),
                start_demon_nawaf,
            ),
        ),

        (
            123,
            -4,
            CallbackQueryHandler(
                demon_nawaf_callback,
                pattern=r"^dn:",
            ),
        ),

        (
            124,
            -5,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(
                    r"^/start(?:@\w+)?\s+demon_nawaf$"
                ),
                demon_nawaf_private_start,
            ),
        ),

        # ==========================================
        # قائمة الألعاب
        # ==========================================

        (
            145,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.لعبة$"),
                games_menu_command,
            ),
        ),

        # ==========================================
        # الألعاب الموحدة
        # ==========================================

        (
            146,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^دخول$"),
                join_big_game_router,
            ),
        ),

        (
            147,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.خروج$"),
                leave_big_game_router,
            ),
        ),

        (
            148,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.ابدا$"),
                begin_big_game_router,
            ),
        ),

        (
            149,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.كمل$"),
                continue_big_game_router,
            ),
        ),

        (
            150,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.انهاء$"),
                end_big_game_router,
            ),
        ),

        # ==========================================
        # اكس او
        # ==========================================

        (
            151,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^اكس او(?:\s+\d+)?$"),
                start_xo_game,
            ),
        ),

        (
            152,
            -4,
            CallbackQueryHandler(
                xo_callback,
                pattern=r"^xo:",
            ),
        ),

        # ==========================================
        # حجرة ورقة مقص
        # ==========================================

        (
            153,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(
                    r"^(?:حجرة(?: ورقة مقص)?|ورقة|مقص)(?:\s+\d+)?$"
                ),
                start_rock_paper_scissors,
            ),
        ),

        (
            154,
            -4,
            CallbackQueryHandler(
                rock_paper_scissors_callback,
                pattern=r"^rps:",
            ),
        ),

        # ==========================================
        # سباق الكلمات
        # ==========================================

        (
            155,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^سباق الكلمات$"),
                start_word_race,
            ),
        ),

        (
            156,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & WordRaceActiveFilter([r"^\.الطور$"]),
                word_race_mode,
            ),
        ),

        (
            157,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & WordRaceActiveFilter([r"^\.وزع$"]),
                word_race_distribution,
            ),
        ),

        (
            158,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & WordRaceActiveFilter(
                    [r"^\.اضافة (احمر|ازرق|اخضر|اصفر)$"]
                ),
                word_race_manual_team,
            ),
        ),

        (
            159,
            -4,
            CallbackQueryHandler(
                word_race_callback,
                pattern=r"^wr:",
            ),
        ),

        (
            160,
            9,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                check_word_race_message,
            ),
        ),

        (
            161,
            9,
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.TEXT
                & ~filters.COMMAND,
                check_word_race_message,
            ),
        ),

        # ==========================================
        # محرك الألعاب
        # ==========================================

        (
            164,
            30,
            MessageHandler(
                filters.ChatType.GROUPS
                & (
                    filters.TEXT
                    | filters.PHOTO
                ),
                game_message_handler,
            ),
        ),

        # ==========================================
        # توقع الصورة
        # ==========================================

        (
            168,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^توقع الصورة$"),
                start_image_quiz,
            ),
        ),

        (
            169,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.اضافة$"),
                add_image_quiz_player,
            ),
        ),

        (
            170,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^\.اعدادات$"),
                image_quiz_settings,
            ),
        ),

        (
            171,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^اضف صور توقع$"),
                add_manual_image_command,
            ),
        ),

        (
            172,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.PHOTO,
                receive_manual_image,
            ),
        ),

        (
            173,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^الغاء اضافة صورة$"),
                cancel_manual_image,
            ),
        ),

        (
            174,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^حذف صور توقع$"),
                delete_manual_image_command,
            ),
        ),

        (
            175,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.PHOTO,
                receive_delete_manual_image,
            ),
        ),

        (
            176,
            -6,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^الغاء حذف صورة$"),
                cancel_delete_manual_image,
            ),
        ),

        (
            177,
            -6,
            CallbackQueryHandler(
                image_quiz_callback,
                pattern=r"^iq:",
            ),
        ),

        (
            178,
            8,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.TEXT
                & ~filters.COMMAND,
                check_image_quiz_message,
            ),
        ),

        # ==========================================
        # طاولة الكذب
        # ==========================================

        (
            179,
            -4,
            MessageHandler(
                filters.ChatType.GROUPS
                & filters.Regex(r"^طاولة الكذب$"),
                start_liars_table,
            ),
        ),

        (
            180,
            -4,
            CallbackQueryHandler(
                liars_table_callback,
                pattern=r"^lt:",
            ),
        ),

        (
            181,
            -4,
            CommandHandler(
                "start",
                liars_table_private_start,
            ),
        ),

        # ==========================================
        # لعبة الكذاب
        # ==========================================

        (
            182,
            0,
            MessageHandler(
                filters.Regex(r"^الكذاب$"),
                start_liar_game_lobby,
            ),
        ),

        (
            183,
            -3,
            MessageHandler(
                filters.Regex(r"^\.التصويت$"),
                force_voting,
            ),
        ),

        (
            184,
            -3,
            CallbackQueryHandler(
                liar_lobby_callback,
                pattern=r"^liar_lobby:",
            ),
        ),

        (
            185,
            -3,
            CallbackQueryHandler(
                liar_vote_callback,
                pattern=r"^liar_vote:",
            ),
        ),

        (
            186,
            -3,
            CallbackQueryHandler(
                liar_guess_callback,
                pattern=r"^liar_guess:",
            ),
        ),

        (
            187,
            9,
            MessageHandler(
                filters.TEXT
                & ~filters.COMMAND,
                check_liar_message,
            ),
        ),

        # ==========================================
        # لعبة البلنتيات
        # ==========================================

        (
            188,
            0,
            MessageHandler(
                filters.Regex(r"^بلنتيات$"),
                start_penalty_game,
            ),
        ),

        (
            189,
            0,
            MessageHandler(
                filters.Regex(r"^\.وزع$"),
                distribute_penalties,
            ),
        ),

        (
            190,
            0,
            MessageHandler(
                filters.Regex(
                    r"^\.(?:احمر|ازرق)(?:\s+\d+)+$"
                ),
                manual_team_command,
            ),
        ),

        (
            191,
            -3,
            CallbackQueryHandler(
                distribution_callback,
                pattern=r"^penalty:distribution:",
            ),
        ),

        (
            192,
            -3,
            CallbackQueryHandler(
                penalty_direction_callback,
                pattern=r"^penalty:direction:",
            ),
        ),

        # ==========================================
        # لعبة الغميضة
        # ==========================================

        (
            193,
            0,
            MessageHandler(
                filters.Regex(r"^غميضة$"),
                start_hide_game,
            ),
        ),

        (
            194,
            -3,
            CallbackQueryHandler(
                hide_number_callback,
                pattern=r"^hide:",
            ),
        ),

        (
            195,
            -3,
            CallbackQueryHandler(
                search_number_callback,
                pattern=r"^search:",
            ),
        ),

        # ==========================================
        # شرح الألعاب
        # ==========================================

        (
            197,
            0,
            MessageHandler(
                filters.Regex(r"^شرح الالعاب$"),
                games_help,
            ),
        ),

        # ==========================================
        # Callback قائمة الألعاب
        # ==========================================

        (
            199,
            0,
            CallbackQueryHandler(
                games_menu_callback,
                pattern=r"^game_menu:",
            ),
        ),
    ]

    return handlers
