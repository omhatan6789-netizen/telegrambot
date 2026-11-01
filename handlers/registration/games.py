
from telegram.ext import (
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

# ==================================================
# الألعاب القديمة
# ==================================================

from games.hide_and_seek import (
    start_hide_game,
    hide_number_callback,
    search_number_callback,
)

from games.penalties import (
    start_penalty_game,
    distribute_penalties,
    manual_team_command,
    distribution_callback,
    penalty_direction_callback,
)

from games.big_game_join import (
    join_big_game_router,
    leave_big_game_router,
    begin_big_game_router,
    continue_big_game_router,
    end_big_game_router,
)

from games.word_race import (
    start_word_race,
    word_race_mode,
    word_race_distribution,
    word_race_manual_team,
    check_word_race_message,
    word_race_callback,
    WordRaceActiveFilter,
)

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

from games.xo import (
    start_xo_game,
    xo_callback,
)

from games.rock_paper_scissors import (
    start_rock_paper_scissors,
    rock_paper_scissors_callback,
)

from games.demon_nawaf import (
    start_demon_nawaf,
    demon_nawaf_callback,
    demon_nawaf_private_start,
)

# ==================================================
# قائمة الألعاب وشرحها
# ==================================================

from handlers.games_menu import (
    games_menu_command,
    games_menu_callback,
)

from handlers.games_help import games_help

# ==================================================
# محرك الألعاب الجديد
# ==================================================

from games.engine import game_message_handler


def build_games_handlers(app):
    handlers = []

    # --------------------------------------------------
    # ديمون نواف
    # --------------------------------------------------

    handlers.append((
        100,
        -4,
        MessageHandler(
            (filters.ChatType.GROUPS | filters.ChatType.PRIVATE)
            & filters.Regex(r"^(?:ديمون نواف|Demon Nawaf)$"),
            start_demon_nawaf,
        ),
    ))

    handlers.append((
        110,
        -4,
        CallbackQueryHandler(
            demon_nawaf_callback,
            pattern=r"^dn:",
        ),
    ))

    handlers.append((
        120,
        -5,
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.Regex(r"^/start(?:@\w+)?\s+demon_nawaf$"),
            demon_nawaf_private_start,
        ),
    ))

    # --------------------------------------------------
    # قائمة الألعاب
    # --------------------------------------------------

    handlers.append((
        200,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.لعبة$"),
            games_menu_command,
        ),
    ))

    # --------------------------------------------------
    # الألعاب الموحدة
    # --------------------------------------------------

    handlers.append((
        210,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^دخول$"),
            join_big_game_router,
        ),
    ))

    handlers.append((
        220,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.خروج$"),
            leave_big_game_router,
        ),
    ))

    handlers.append((
        230,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.ابدا$"),
            begin_big_game_router,
        ),
    ))

    handlers.append((
        240,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.كمل$"),
            continue_big_game_router,
        ),
    ))

    handlers.append((
        250,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.انهاء$"),
            end_big_game_router,
        ),
    ))

    # --------------------------------------------------
    # اكس او
    # --------------------------------------------------

    handlers.append((
        260,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^اكس او(?:\s+\d+)?$"),
            start_xo_game,
        ),
    ))

    handlers.append((
        270,
        -4,
        CallbackQueryHandler(
            xo_callback,
            pattern=r"^xo:",
        ),
    ))

    # --------------------------------------------------
    # حجرة ورقة مقص
    # --------------------------------------------------

    handlers.append((
        280,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(
                r"^(?:حجرة(?: ورقة مقص)?|ورقة|مقص)(?:\s+\d+)?$"
            ),
            start_rock_paper_scissors,
        ),
    ))

    handlers.append((
        290,
        -4,
        CallbackQueryHandler(
            rock_paper_scissors_callback,
            pattern=r"^rps:",
        ),
    ))

    # --------------------------------------------------
    # سباق الكلمات
    # --------------------------------------------------

    handlers.append((
        300,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^سباق الكلمات$"),
            start_word_race,
        ),
    ))

    handlers.append((
        310,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^\.الطور$"]),
            word_race_mode,
        ),
    ))

    handlers.append((
        320,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter([r"^\.وزع$"]),
            word_race_distribution,
        ),
    ))

    handlers.append((
        330,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & WordRaceActiveFilter(
                [r"^\.اضافة (احمر|ازرق|اخضر|اصفر)$"]
            ),
            word_race_manual_team,
        ),
    ))

    handlers.append((
        340,
        -4,
        CallbackQueryHandler(
            word_race_callback,
            pattern=r"^wr:",
        ),
    ))

    handlers.append((
        350,
        9,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            check_word_race_message,
        ),
    ))

    handlers.append((
        360,
        9,
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            check_word_race_message,
        ),
    ))

    # --------------------------------------------------
    # توقع الصورة
    # --------------------------------------------------

    handlers.append((
        370,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^توقع الصورة$"),
            start_image_quiz,
        ),
    ))

    handlers.append((
        380,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.اضافة$"),
            add_image_quiz_player,
        ),
    ))

    handlers.append((
        390,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^\.اعدادات$"),
            image_quiz_settings,
        ),
    ))

    handlers.append((
        400,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^اضف صور توقع$"),
            add_manual_image_command,
        ),
    ))

    handlers.append((
        410,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.PHOTO,
            receive_manual_image,
        ),
    ))

    handlers.append((
        420,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^الغاء اضافة صورة$"),
            cancel_manual_image,
        ),
    ))

    handlers.append((
        430,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^حذف صور توقع$"),
            delete_manual_image_command,
        ),
    ))

    handlers.append((
        440,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.PHOTO,
            receive_delete_manual_image,
        ),
    ))

    handlers.append((
        450,
        -6,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^الغاء حذف صورة$"),
            cancel_delete_manual_image,
        ),
    ))

    handlers.append((
        460,
        -6,
        CallbackQueryHandler(
            image_quiz_callback,
            pattern=r"^iq:",
        ),
    ))

    handlers.append((
        470,
        8,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            check_image_quiz_message,
        ),
    ))

    # --------------------------------------------------
    # طاولة الكذب
    # --------------------------------------------------

    handlers.append((
        480,
        -4,
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.Regex(r"^طاولة الكذب$"),
            start_liars_table,
        ),
    ))

    handlers.append((
        490,
        -4,
        CallbackQueryHandler(
            liars_table_callback,
            pattern=r"^lt:",
        ),
    ))

    handlers.append((
        500,
        -4,
        CommandHandler(
            "start",
            liars_table_private_start,
        ),
    ))

    # --------------------------------------------------
    # لعبة الكذاب
    # --------------------------------------------------

    handlers.append((
        510,
        0,
        MessageHandler(
            filters.Regex(r"^الكذاب$"),
            start_liar_game_lobby,
        ),
    ))

    handlers.append((
        520,
        -3,
        MessageHandler(
            filters.Regex(r"^\.التصويت$"),
            force_voting,
        ),
    ))

    handlers.append((
        530,
        -3,
        CallbackQueryHandler(
            liar_lobby_callback,
            pattern=r"^liar_lobby:",
        ),
    ))

    handlers.append((
        540,
        -3,
        CallbackQueryHandler(
            liar_vote_callback,
            pattern=r"^liar_vote:",
        ),
    ))

    handlers.append((
        550,
        -3,
        CallbackQueryHandler(
            liar_guess_callback,
            pattern=r"^liar_guess:",
        ),
    ))

    handlers.append((
        560,
        9,
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            check_liar_message,
        ),
    ))

    # --------------------------------------------------
    # البلنتيات
    # --------------------------------------------------

    handlers.append((
        570,
        0,
        MessageHandler(
            filters.Regex(r"^بلنتيات$"),
            start_penalty_game,
        ),
    ))

    handlers.append((
        580,
        0,
        MessageHandler(
            filters.Regex(r"^\.وزع$"),
            distribute_penalties,
        ),
    ))

    handlers.append((
        590,
        0,
        MessageHandler(
            filters.Regex(r"^\.(?:احمر|ازرق)(?:\s+\d+)+$"),
            manual_team_command,
        ),
    ))

    handlers.append((
        600,
        -3,
        CallbackQueryHandler(
            distribution_callback,
            pattern=r"^penalty:distribution:",
        ),
    ))

    handlers.append((
        610,
        -3,
        CallbackQueryHandler(
            penalty_direction_callback,
            pattern=r"^penalty:direction:",
        ),
    ))

    # --------------------------------------------------
    # الغميضة
    # --------------------------------------------------

    handlers.append((
        620,
        0,
        MessageHandler(
            filters.Regex(r"^غميضة$"),
            start_hide_game,
        ),
    ))

    handlers.append((
        630,
        -3,
        CallbackQueryHandler(
            hide_number_callback,
            pattern=r"^hide:",
        ),
    ))

    handlers.append((
        640,
        -3,
        CallbackQueryHandler(
            search_number_callback,
            pattern=r"^search:",
        ),
    ))

    # --------------------------------------------------
    # محرك الألعاب الجديد
    # --------------------------------------------------

    handlers.append((
        650,
        30,
        MessageHandler(
            filters.ChatType.GROUPS
            & (filters.TEXT | filters.PHOTO),
            game_message_handler,
        ),
    ))

    # --------------------------------------------------
    # شرح الألعاب
    # --------------------------------------------------

    handlers.append((
        660,
        0,
        MessageHandler(
            filters.Regex(r"^شرح الالعاب$"),
            games_help,
        ),
    ))

    # --------------------------------------------------
    # Callback قائمة الألعاب
    # --------------------------------------------------

    handlers.append((
        670,
        0,
        CallbackQueryHandler(
            games_menu_callback,
            pattern=r"^game_menu:",
        ),
    ))

    return handlers
