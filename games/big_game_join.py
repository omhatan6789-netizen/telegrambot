from games.liar import (
    active_liar_games,
    join_liar_game
)

from games.penalties import (
    active_penalty_games,
    join_penalty_game
)

from games.hide_and_seek import (
    active_hide_games,
    join_hide_game
)


async def join_big_game_router(update, context):

    chat = update.effective_chat

    if not chat:
        return

    chat_id = chat.id

    # ==================================================
    # الكذاب
    # ==================================================

    if chat_id in active_liar_games:

        await join_liar_game(
            update,
            context
        )

        return

    # ==================================================
    # البلنتيات
    # ==================================================

    if chat_id in active_penalty_games:

        await join_penalty_game(
            update,
            context
        )

        return

    # ==================================================
    # غميضة
    # ==================================================

    if chat_id in active_hide_games:

        await join_hide_game(
            update,
            context
        )

        return

    # لا توجد لعبة تحتاج دخول
    return