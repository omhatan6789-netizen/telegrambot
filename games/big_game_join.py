from games.liar import (
    active_liar_games,
    join_liar_game,
    leave_liar_game,
    begin_liar_game,
    end_liar_game,
)
from games.penalties import (
    active_penalty_games,
    join_penalty_game,
    begin_penalties,
    continue_penalties,
    end_penalty_game,
)
from games.hide_and_seek import (
    active_hide_games,
    join_hide_game,
    begin_hide_game,
    end_hide_game,
)
from games.liars_table import (
    active_liars_tables,
    join_liars_table,
    leave_liars_table,
    begin_liars_table,
    end_liars_table,
)
from games.word_race import (
    RACES,
    join_word_race,
    leave_word_race,
    begin_word_race,
    continue_word_race,
    end_word_race,
)
from games.image_quiz.image_quiz import (
    IMAGE_QUIZZES,
    join_image_quiz,
    leave_image_quiz,
    begin_image_quiz,
    continue_image_quiz,
    end_image_quiz,
)
def get_active_game(chat_id):
    if chat_id in IMAGE_QUIZZES:
        return "image"
    if chat_id in active_liars_tables:
        return "liars_table"
    if chat_id in active_liar_games:
        return "liar"
    if chat_id in active_penalty_games:
        return "penalty"
    if chat_id in active_hide_games:
        return "hide"
    if chat_id in RACES:
        return "word_race"
    return None
async def join_big_game_router(update, context):
    chat = update.effective_chat
    if not chat:
        return
    game = get_active_game(chat.id)
    if game == "image":
        await join_image_quiz(update, context)
        return
    if game == "liars_table":
        await join_liars_table(update, context)
        return
    if game == "liar":
        await join_liar_game(update, context)
        return
    if game == "penalty":
        await join_penalty_game(update, context)
        return
    if game == "hide":
        await join_hide_game(update, context)
        return
    if game == "word_race":
        await join_word_race(update, context)
        return
async def leave_big_game_router(update, context):
    chat = update.effective_chat
    if not chat:
        return
    game = get_active_game(chat.id)
    if game == "image":
        await leave_image_quiz(update, context)
        return
    if game == "liars_table":
        await leave_liars_table(update, context)
        return
    if game == "liar":
        await leave_liar_game(update, context)
        return
    if game == "word_race":
        await leave_word_race(update, context)
        return
async def begin_big_game_router(update, context):
    chat = update.effective_chat
    if not chat:
        return
    game = get_active_game(chat.id)
    if game == "image":
        await begin_image_quiz(update, context)
        return
    if game == "liars_table":
        await begin_liars_table(update, context)
        return
    if game == "liar":
        await begin_liar_game(update, context)
        return
    if game == "penalty":
        await begin_penalties(update, context)
        return
    if game == "hide":
        await begin_hide_game(update, context)
        return
    if game == "word_race":
        await begin_word_race(update, context)
        return
async def continue_big_game_router(update, context):
    chat = update.effective_chat
    if not chat:
        return
    game = get_active_game(chat.id)
    if game == "image":
        await continue_image_quiz(update, context)
        return
    if game == "penalty":
        await continue_penalties(update, context)
        return
    if game == "word_race":
        await continue_word_race(update, context)
        return
async def end_big_game_router(update, context):
    chat = update.effective_chat
    if not chat:
        return
    game = get_active_game(chat.id)
    if game == "image":
        await end_image_quiz(update, context)
        return
    if game == "liars_table":
        await end_liars_table(update, context)
        return
    if game == "liar":
        await end_liar_game(update, context)
        return
    if game == "penalty":
        await end_penalty_game(update, context)
        return
    if game == "hide":
        await end_hide_game(update, context)
        return
    if game == "word_race":
        await end_word_race(update, context)
        return
