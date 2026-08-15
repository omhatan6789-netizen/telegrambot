import random
import asyncio
from collections import Counter

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes

from handlers.roles import get_rank_level



# ==================================================
# إعدادات اللعبة
# ==================================================

HIDE_TIME = 60
SEARCH_TIME = 30

MIN_PLAYERS = 2


# ==================================================
# الألعاب النشطة
#
# chat_id:
# {
#     "players": {},
#     "order": [],
#     "board_size": 16,
#     "available": [],
#     "contents": {},
#     "phase": "registration",
#     "current_index": 0,
#     "search_message_id": None,
#     "hide_tasks": {},
#     "search_task": None,
# }
# ==================================================

active_hide_games = {}


# ==================================================
# هل يستطيع إدارة اللعبة؟
#
# أي شخص معه رتبة أعلى من عضو
# ==================================================

def can_manage_hide_game(user_id):

    return get_rank_level(user_id) > 0


# ==================================================
# اسم اللاعب
# ==================================================

def get_player_name(user):

    if not user:
        return "مستخدم"

    if user.username:
        return f"@{user.username}"

    return user.first_name or "مستخدم"


# ==================================================
# حجم اللوحة
# ==================================================

def get_board_size(player_count):

    if player_count <= 2:
        return 16

    if player_count <= 5:
        return 20

    return 24


# ==================================================
# إنشاء محتويات المربعات
# ==================================================

def create_contents(board_size):

    contents = []

    # ----------------------------------------------
    # عدد المحتويات حسب حجم اللوحة
    # ----------------------------------------------

    if board_size <= 16:

        items = [
            "bomb",
            "bomb",
            "bomb",

            "extra",
            "extra",

            "plus5",
            "plus5",

            "plus10",

            "minus3",
            "minus3",

            "minus5",
            "minus5",
        ]

    elif board_size <= 20:

        items = [
            "bomb",
            "bomb",
            "bomb",
            "bomb",

            "extra",
            "extra",
            "extra",

            "plus5",
            "plus5",
            "plus5",

            "plus10",
            "plus10",

            "minus3",
            "minus3",
            "minus3",

            "minus5",
            "minus5",
            "minus5",
        ]

    else:

        items = [
            "bomb",
            "bomb",
            "bomb",
            "bomb",
            "bomb",

            "extra",
            "extra",
            "extra",

            "plus5",
            "plus5",
            "plus5",

            "plus10",
            "plus10",

            "minus3",
            "minus3",
            "minus3",

            "minus5",
            "minus5",
            "minus5",
        ]

    # ----------------------------------------------
    # الباقي فارغ
    # ----------------------------------------------

    while len(items) < board_size:
        items.append("empty")

    random.shuffle(items)

    return {
        number: items[number - 1]
        for number in range(1, board_size + 1)
    }


# ==================================================
# لوحة الأرقام
# ==================================================

def build_board(numbers, callback_prefix):

    buttons = []

    row = []

    for number in numbers:

        row.append(
            InlineKeyboardButton(
                str(number),
                callback_data=f"{callback_prefix}:{number}"
            )
        )

        if len(row) == 4:

            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


# ==================================================
# بدء التسجيل
# ==================================================

async def start_hide_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":

        await update.message.reply_text(
            "❌ لعبة الغميضة تبدأ من القروب."
        )

        return

    # ----------------------------------------------
    # الرتبة
    # ----------------------------------------------

    if not can_manage_hide_game(user.id):

        await update.message.reply_text(
            "❌ هذا الأمر للرتب فقط."
        )

        return

    # ----------------------------------------------
    # يوجد قيم شغال
    # ----------------------------------------------

    if chat.id in active_hide_games:

        await update.message.reply_text(
            "❌ توجد لعبة غميضة شغالة بالفعل."
        )

        return

    # ----------------------------------------------
    # إنشاء اللعبة
    # ----------------------------------------------

    active_hide_games[chat.id] = {

        "players": {},

        "order": [],

        "board_size": 16,

        "available": [],

        "contents": {},

        "phase": "registration",

        "current_index": 0,

        "search_message_id": None,

        "hide_tasks": {},

        "search_task": None,

        "discoveries": Counter(),

        "bomb_hits": Counter(),

        "scores": {},

        "hidden": {},

        "searching": False,
    }

    await update.message.reply_text(
        "🚪 تم فتح التسجيل في لعبة الغميضة!\n\n"
        "• نوع اللوحة المختار: الأرقام 🔢\n"
        "• اكتب دخول للانضمام إلى اللعبة.\n"
        "• عندما يكتمل اللاعبون، يكتب الأدمن ابدا لبدء اللعبة.\n"
        "• الحد الأدنى لبدء اللعبة: 2 لاعبين."
    )


# ==================================================
# دخول لاعب
# ==================================================

async def join_hide_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if chat.id not in active_hide_games:
        return

    game = active_hide_games[chat.id]

    if game["phase"] != "registration":
        return

    user = update.effective_user

    # ----------------------------------------------
    # موجود مسبقًا
    # ----------------------------------------------

    if user.id in game["players"]:

        await update.message.reply_text(
            f"❌ أنت داخل اللعبة بالفعل يا {get_player_name(user)}."
        )

        return

    # ----------------------------------------------
    # إضافة اللاعب
    # ----------------------------------------------

    game["players"][user.id] = user

    game["order"].append(user.id)

    game["scores"][user.id] = 0

    # ----------------------------------------------
    # تحديث حجم اللوحة
    # ----------------------------------------------

    game["board_size"] = get_board_size(
        len(game["players"])
    )

    names = []

    for player_id in game["order"]:

        player = game["players"][player_id]

        names.append(
            f"{len(names) + 1}. {get_player_name(player)}"
        )

    await update.message.reply_text(
        f"✅ تم تسجيل {get_player_name(user)} في لعبة الغميضة!\n\n"
        f"👥 عدد اللاعبين: {len(game['players'])}\n"
        f"🔢 عدد المربعات: {game['board_size']}\n\n"
        + "\n".join(names)
    )


# ==================================================
# بدء اللعبة
# ==================================================

async def begin_hide_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if chat.id not in active_hide_games:
        return

    game = active_hide_games[chat.id]

    if not can_manage_hide_game(user.id):

        return

    if game["phase"] != "registration":

        await update.message.reply_text(
            "❌ اللعبة بدأت بالفعل."
        )

        return

    player_count = len(game["players"])

    if player_count < MIN_PLAYERS:

        await update.message.reply_text(
            "❌ لا يمكن بدء اللعبة.\n"
            f"الحد الأدنى: {MIN_PLAYERS} لاعبين."
        )

        return

    # ----------------------------------------------
    # إنشاء اللوحة
    # ----------------------------------------------

    game["board_size"] = get_board_size(
        player_count
    )

    game["available"] = list(
        range(
            1,
            game["board_size"] + 1
        )
    )

    game["contents"] = create_contents(
        game["board_size"]
    )

    game["phase"] = "hiding"

    await update.message.reply_text(
        "😶‍🌫️ بدأت لعبة الغميضة!\n\n"
        "📩 أرسلت الآن لكل لاعب رسالة خاصة لاختيار مكان اختبائه.\n"
        "⏱ أمام كل لاعب 60 ثانية.\n\n"
        "إذا لم يختر اللاعب خلال الوقت، سأختار له رقمًا عشوائيًا."
    )

    # ----------------------------------------------
    # إرسال رسالة الخاص لكل لاعب
    # ----------------------------------------------

    for player_id in game["order"]:

        await send_hide_choice(
            context,
            chat.id,
            player_id
        )

    # ----------------------------------------------
    # مؤقت عام للاختباء
    # ----------------------------------------------

    asyncio.create_task(
        hide_phase_timeout(
            context,
            chat.id
        )
    )


# ==================================================
# إرسال اختيار الاختباء
# ==================================================

async def send_hide_choice(
    context,
    chat_id,
    player_id
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    player = game["players"].get(player_id)

    if not player:
        return

    numbers = list(
        range(
            1,
            game["board_size"] + 1
        )
    )

    keyboard = build_board(
        numbers,
        f"hide:{chat_id}:{player_id}"
    )

    try:

        message = await context.bot.send_message(
            chat_id=player_id,
            text=(
                "😶‍🌫️ اختر الرقم الذي تريد الاختباء فيه.\n\n"
                "⏱ لديك 60 ثانية.\n"
                "يمكن لأكثر من لاعب الاختباء في نفس الرقم."
            ),
            reply_markup=keyboard
        )

        game["hide_tasks"][player_id] = message.message_id

    except Exception:

        # المستخدم لم يبدأ محادثة مع البوت
        try:

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ لم أستطع إرسال رسالة خاصة إلى "
                    f"{get_player_name(player)}.\n"
                    "يجب عليه فتح محادثة البوت والضغط على Start."
                )
            )

        except Exception:
            pass


# ==================================================
# اختيار مكان الاختباء
# ==================================================

async def hide_number_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    parts = data.split(":")

    if len(parts) != 3:
        return

    _, chat_id_text, player_id_text = parts

    try:

        chat_id = int(chat_id_text)
        player_id = int(player_id_text)
        number = int(data.split(":")[-1])

    except Exception:
        return

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "hiding":
        return

    if query.from_user.id != player_id:

        await query.answer(
            "❌ هذه اللوحة ليست لك.",
            show_alert=True
        )

        return

    if number < 1 or number > game["board_size"]:
        return

    # ----------------------------------------------
    # حفظ المكان
    # ----------------------------------------------

    game["hidden"][player_id] = number

    # ----------------------------------------------
    # تعديل الرسالة
    # ----------------------------------------------

    try:

        await query.edit_message_text(
            f"😶‍🌫️ تم اختيارك للمربع ({number})."
        )

    except Exception:
        pass

    # ----------------------------------------------
    # هل الجميع اختار؟
    # ----------------------------------------------

    if len(game["hidden"]) == len(game["players"]):

        await finish_hiding(
            context,
            chat_id
        )


# ==================================================
# انتهاء وقت الاختباء
# ==================================================

async def hide_phase_timeout(
    context,
    chat_id
):

    await asyncio.sleep(HIDE_TIME)

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "hiding":
        return

    # ----------------------------------------------
    # اختيار عشوائي لمن لم يختر
    # ----------------------------------------------

    numbers = list(
        range(
            1,
            game["board_size"] + 1
        )
    )

    for player_id in game["order"]:

        if player_id in game["hidden"]:
            continue

        game["hidden"][player_id] = random.choice(
            numbers
        )

        player = game["players"][player_id]

        try:

            await context.bot.send_message(
                chat_id=player_id,
                text=(
                    "⏰ انتهى وقت الاختباء!\n\n"
                    f"😶‍🌫️ اخترت لك المربع "
                    f"({game['hidden'][player_id]}) عشوائيًا."
                )
            )

        except Exception:
            pass

    await finish_hiding(
        context,
        chat_id
    )


# ==================================================
# إنهاء الاختباء وبدء البحث
# ==================================================

async def finish_hiding(
    context,
    chat_id
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "hiding":
        return

    game["phase"] = "searching"

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "😶‍🌫️ لقد اختبأ جميع اللاعبين بنجاح.\n\n"
            "تبدأ الآن أدوار البحث! في كل دور، يختار اللاعب "
            "أحد المربعات المتاحة للبحث فيه.\n"
            "💥 إذا تم العثور على لاعبين في المربع المختار، "
            "يتم استبعادهم فورًا!\n\n"
            "🎁 تم توزيع الهدايا العشوائية في المربعات!\n"
            "الهدايا المتوفرة خلف المربعات:\n"
            "• 🔄 فرصة اختيار أخرى\n"
            "• 💣 قنبلة (تكشف تلميحًا عن الرقم السري)\n"
            "• 🎁 +5 نقاط، +10 نقاط\n"
            "• 💥 -3 نقاط، -5 نقاط\n\n"
            "🏆 تستمر الأدوار حتى يتبقى فائز واحد "
            "(أو يفوز آخر اللاعبين معًا إذا اختبأوا في نفس المربع)."
        )
    )

    await start_next_search_turn(
        context,
        chat_id
    )


# ==================================================
# إيجاد اللاعبين الموجودين في مربع
# ==================================================

def players_in_box(game, number):

    found = []

    for player_id, hidden_number in game["hidden"].items():

        if hidden_number != number:
            continue

        # اللاعب لا يزال داخل اللعبة
        if player_id not in game["players"]:
            continue

        found.append(player_id)

    return found


# ==================================================
# اللاعبين المتبقين
# ==================================================

def alive_players(game):

    return [
        player_id
        for player_id in game["order"]
        if player_id in game["players"]
    ]


# ==================================================
# هل انتهت اللعبة؟
# ==================================================

def check_game_finished(game):

    alive = alive_players(game)

    if len(alive) <= 1:
        return True

    # إذا كل اللاعبين الباقين بنفس المربع
    hidden_numbers = {
        game["hidden"].get(player_id)
        for player_id in alive
    }

    if len(hidden_numbers) == 1:
        return True

    return False


# ==================================================
# بدء دور جديد
# ==================================================

async def start_next_search_turn(
    context,
    chat_id
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "searching":
        return

    # ----------------------------------------------
    # نهاية اللعبة
    # ----------------------------------------------

    if check_game_finished(game):

        await finish_hide_game(
            context,
            chat_id
        )

        return

    # ----------------------------------------------
    # البحث عن اللاعب التالي
    # ----------------------------------------------

    order = game["order"]

    checked = 0

    while checked < len(order):

        index = game["current_index"] % len(order)

        player_id = order[index]

        game["current_index"] += 1

        checked += 1

        if player_id not in game["players"]:
            continue

        # ------------------------------------------
        # اللاعب حي
        # ------------------------------------------

        game["searching"] = True

        player = game["players"][player_id]

        # ------------------------------------------
        # منع البحث في مكانه
        # ------------------------------------------

        available = [
            number
            for number in game["available"]
            if number != game["hidden"].get(player_id)
        ]

        if not available:

            await finish_hide_game(
                context,
                chat_id
            )

            return

        keyboard = build_board(
            available,
            f"search:{chat_id}:{player_id}"
        )

        message = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🫣 تفضل يا {get_player_name(player)} "
                "اختر مربع لكشف ما بداخله.\n\n"
                f"⏱ أمامك {SEARCH_TIME} ثانية."
            ),
            reply_markup=keyboard
        )

        game["search_message_id"] = message.message_id
        game["search_player"] = player_id

        # ------------------------------------------
        # مؤقت الدور
        # ------------------------------------------

        game["search_task"] = asyncio.create_task(
            search_timeout(
                context,
                chat_id,
                player_id
            )
        )

        return

    await finish_hide_game(
        context,
        chat_id
    )


# ==================================================
# اختيار مربع للبحث
# ==================================================

async def search_number_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    try:

        _, chat_id_text, player_id_text, number_text = (
            query.data.split(":")
        )

        chat_id = int(chat_id_text)
        player_id = int(player_id_text)
        number = int(number_text)

    except Exception:

        return

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "searching":
        return

    if game.get("search_player") != player_id:

        await query.answer(
            "❌ ليس دورك الآن.",
            show_alert=True
        )

        return

    if number not in game["available"]:

        await query.answer(
            "❌ هذا المربع لم يعد متاحًا.",
            show_alert=True
        )

        return

    task = game.get("search_task")

    if task:
        task.cancel()
        game["search_task"] = None

    await resolve_search(
        context,
        chat_id,
        player_id,
        number
    )


# ==================================================
# حل البحث
# ==================================================

async def resolve_search(
    context,
    chat_id,
    player_id,
    number
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if number not in game["available"]:
        return

    player = game["players"].get(player_id)

    if not player:
        return

    # ----------------------------------------------
    # إزالة المربع
    # ----------------------------------------------

    game["available"].remove(number)

    # ----------------------------------------------
    # اللاعبين المختبئين
    # ----------------------------------------------

    found_players = players_in_box(
        game,
        number
    )

    content = game["contents"].get(
        number,
        "empty"
    )

    # ----------------------------------------------
    # الرسالة الأساسية
    # ----------------------------------------------

    text = (
        f"🎯 قام اللاعب {get_player_name(player)} "
        f"بالبحث في المربع ({number}):\n\n"
    )

    # ----------------------------------------------
    # كشف اللاعبين
    # ----------------------------------------------

    if found_players:

        names = []

        for found_id in found_players:

            found_user = game["players"].get(found_id)

            if found_user:
                names.append(
                    get_player_name(found_user)
                )

        text += (
            "💥 تم كشف المخبأ!\n"
            "تم العثور على اللاعبين: "
            + " و ".join(names)
            + " ❌\n"
            "(تم استبعادهم من اللعبة)."
        )

        for found_id in found_players:

            del game["players"][found_id]

        game["discoveries"][player_id] += len(
            found_players
        )

        # المربع الذي كان فيه اللاعبون أصبح فارغًا
        # ولا نكشف أي هدية إضافية معه.

    else:

        text += (
            "💨 كان المربع فارغًا! "
            "لم يتم العثور على أحد."
        )

        # ------------------------------------------
        # محتوى المربع
        # ------------------------------------------

        if content == "bomb":

            game["bomb_hits"][player_id] += 1

            # نختار لاعبًا حيًا عشوائيًا للتلميح
            alive = alive_players(game)

            if alive:

                target_id = random.choice(alive)

                target = game["players"].get(target_id)

                if target:

                    secret_number = game["hidden"].get(
                        target_id
                    )

                    if secret_number % 2 == 0:
                        parity = "زوجي"
                    else:
                        parity = "فردي"

                    text += (
                        "\n\n💣 انفجرت قنبلة!\n"
                        f"تم كشف تلميح للمجموعة عن موقع اللاعب "
                        f"{get_player_name(target)}:\n"
                        f"الرقم السري الذي يختبئ فيه هو رقم {parity}."
                    )

        elif content == "extra":

            text += (
                "\n\n🔄 حصل اللاعب "
                f"{get_player_name(player)} "
                "على هدية فرصة إضافية!\n"
                "يمكنه الاختيار واللعب مرة أخرى في هذا الدور."
            )

            game["scores"][player_id] += 0

        elif content == "plus5":

            game["scores"][player_id] += 5

            add_points(
                player_id,
                5
            )

            text += (
                "\n\n🎁 حصل اللاعب "
                f"{get_player_name(player)} "
                "على +5 نقاط!"
            )

        elif content == "plus10":

            game["scores"][player_id] += 10

            add_points(
                player_id,
                10
            )

            text += (
                "\n\n🎁 حصل اللاعب "
                f"{get_player_name(player)} "
                "على +10 نقاط!"
            )

        elif content == "minus3":

            game["scores"][player_id] -= 3

            add_points(
                player_id,
                -3
            )

            text += (
                "\n\n💥 أوبس! مربع خصم نقاط.\n"
                "تم خصم 3 نقاط من اللاعب "
                f"{get_player_name(player)}."
            )

        elif content == "minus5":

            game["scores"][player_id] -= 5

            add_points(
                player_id,
                -5
            )

            text += (
                "\n\n💥 أوبس! مربع خصم نقاط.\n"
                "تم خصم 5 نقاط من اللاعب "
                f"{get_player_name(player)}."
            )

    # ----------------------------------------------
    # إرسال النتيجة
    # ----------------------------------------------

    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )

    # ----------------------------------------------
    # فحص نهاية اللعبة
    # ----------------------------------------------

    if check_game_finished(game):

        await finish_hide_game(
            context,
            chat_id
        )

        return

    # ----------------------------------------------
    # فرصة إضافية
    # ----------------------------------------------

    if (
        not found_players
        and content == "extra"
        and player_id in game["players"]
    ):

        await start_specific_search_turn(
            context,
            chat_id,
            player_id
        )

        return

    # ----------------------------------------------
    # الدور التالي
    # ----------------------------------------------

    game["searching"] = False

    await start_next_search_turn(
        context,
        chat_id
    )


# ==================================================
# دور محدد
# ==================================================

async def start_specific_search_turn(
    context,
    chat_id,
    player_id
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if player_id not in game["players"]:
        return

    available = [
        number
        for number in game["available"]
        if number != game["hidden"].get(player_id)
    ]

    if not available:

        await finish_hide_game(
            context,
            chat_id
        )

        return

    player = game["players"][player_id]

    keyboard = build_board(
        available,
        f"search:{chat_id}:{player_id}"
    )

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🔄 فرصة إضافية!\n\n"
            f"تفضل يا {get_player_name(player)} "
            "اختر مربعًا آخر."
            f"\n\n⏱ أمامك {SEARCH_TIME} ثانية."
        ),
        reply_markup=keyboard
    )

    game["search_player"] = player_id

    game["search_message_id"] = message.message_id

    game["search_task"] = asyncio.create_task(
        search_timeout(
            context,
            chat_id,
            player_id
        )
    )


# ==================================================
# انتهاء وقت البحث
# ==================================================

async def search_timeout(
    context,
    chat_id,
    player_id
):

    try:

        await asyncio.sleep(
            SEARCH_TIME
        )

    except asyncio.CancelledError:

        return

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "searching":
        return

    if game.get("search_player") != player_id:
        return

    available = [
        number
        for number in game["available"]
        if number != game["hidden"].get(player_id)
    ]

    if not available:

        await finish_hide_game(
            context,
            chat_id
        )

        return

    number = random.choice(
        available
    )

    player = game["players"].get(player_id)

    if player:

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⏰ انتهى وقت {get_player_name(player)}!\n"
                f"🎲 تم اختيار المربع ({number}) عشوائيًا."
            )
        )

    await resolve_search(
        context,
        chat_id,
        player_id,
        number
    )


# ==================================================
# إنهاء اللعبة يدويًا
# ==================================================

async def end_hide_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in active_hide_games:
        return

    if not can_manage_hide_game(user.id):

        return

    await update.message.reply_text(
        "🛑 تم إنهاء لعبة الغميضة."
    )

    game = active_hide_games.pop(
        chat_id,
        None
    )

    if not game:
        return

    # إلغاء المؤقتات
    task = game.get("search_task")

    if task:
        task.cancel()


# ==================================================
# نهاية اللعبة
# ==================================================

async def finish_hide_game(
    context,
    chat_id
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    game["phase"] = "finished"

    # ----------------------------------------------
    # إلغاء المؤقت
    # ----------------------------------------------

    task = game.get("search_task")

    if task:

        task.cancel()

    alive = alive_players(game)

    # ----------------------------------------------
    # ترتيب الفائزين
    # ----------------------------------------------

    winners = []

    if alive:

        winners = alive

    # ----------------------------------------------
    # أكثر اكتشافات
    # ----------------------------------------------

    most_discoveries = None

    if game["discoveries"]:

        most_discoveries = max(
            game["discoveries"],
            key=game["discoveries"].get
        )

        discovery_count = game["discoveries"][
            most_discoveries
        ]

        if discovery_count > 0:

            add_points(
                most_discoveries,
                5
            )

    # ----------------------------------------------
    # أكثر قنابل
    # ----------------------------------------------

    most_bombs = None

    if game["bomb_hits"]:

        most_bombs = max(
            game["bomb_hits"],
            key=game["bomb_hits"].get
        )

        bomb_count = game["bomb_hits"][
            most_bombs
        ]

        if bomb_count > 0:

            add_points(
                most_bombs,
                -5
            )

    # ----------------------------------------------
    # الرسالة
    # ----------------------------------------------

    text = "🏆 انتهت لعبة الغميضة!\n\n"

    if len(winners) == 1:

        winner = game["players"].get(
            winners[0]
        )

        if winner:

            text += (
                f"🥇 {get_player_name(winner)} — الفائز\n"
            )

    elif len(winners) > 1:

        names = []

        for winner_id in winners:

            winner = game["players"].get(
                winner_id
            )

            if winner:

                names.append(
                    get_player_name(winner)
                )

        text += (
            "🥇 الفائزون:\n"
            + "\n".join(
                f"• {name}"
                for name in names
            )
            + "\n"
        )

    # ----------------------------------------------
    # الإحصائيات
    # ----------------------------------------------

    if most_discoveries:

        user = game["players"].get(
            most_discoveries
        )

        if user:

            text += (
                "\n🔎 أكثر لاعب اكتشف مخابئ: "
                f"{get_player_name(user)} "
                f"({game['discoveries'][most_discoveries]} اكتشاف)"
                "\n🎁 حصل على +5 نقاط."
            )

    if most_bombs:

        user = game["players"].get(
            most_bombs
        )

        if user:

            text += (
                "\n\n💣 أكثر لاعب أصابته القنابل: "
                f"{get_player_name(user)} "
                f"({game['bomb_hits'][most_bombs]} قنابل)"
                "\n💥 تم خصم 5 نقاط منه."
            )

    # ----------------------------------------------
    # النقاط التي حصل عليها اللاعبون أثناء اللعبة
    # ----------------------------------------------

    scored = [
        (player_id, points)
        for player_id, points in game["scores"].items()
        if points != 0
    ]

    if scored:

        text += "\n\n📊 نقاط الجولة:\n"

        scored.sort(
            key=lambda x: x[1],
            reverse=True
        )

        for player_id, points in scored:

            player = game["players"].get(
                player_id
            )

            if not player:
                continue

            sign = "+" if points > 0 else ""

            text += (
                f"• {get_player_name(player)}: "
                f"{sign}{points}\n"
            )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )

    # ----------------------------------------------
    # حذف اللعبة
    # ----------------------------------------------

    active_hide_games.pop(
        chat_id,
        None
    )