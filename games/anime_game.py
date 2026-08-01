from telegram import Update
from telegram.ext import ContextTypes

from games.anime_questions import get_random_anime_question
from handlers.points import add_points


active_anime_games = {}


async def start_anime_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    question = get_random_anime_question()


    chat_id = update.effective_chat.id


    active_anime_games[chat_id] = {

        "answers": [
            x.lower()
            for x in question["answers"]
        ],

        "winner": False

    }


    await update.message.reply_text(
   
        f"❓ {question['question']}\n\n"
        " أول واحد يجاوب صح ياخذ 5 نقاط🌟"
    )



async def check_anime_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return


    chat_id = update.effective_chat.id


    if chat_id not in active_anime_games:
        return


    answer = update.message.text.strip().lower()


    game = active_anime_games[chat_id]


    if answer in game["answers"]:


        add_points(
            update.effective_user.id,
            5
        )


        await update.message.reply_text(
            f" !يا فناااان {update.effective_user.first_name}\n"
            "✅ إجابة صحيحة\n"
            "⭐ +5 نقاط"
        )


        del active_anime_games[chat_id]