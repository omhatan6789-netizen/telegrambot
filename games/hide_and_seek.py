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
from handlers.points import add_points


# ==================================================
# إعدادات اللعبة
# ==================================================

HIDE_TIME = 60
SEARCH_TIME = 30

MIN_PLAYERS = 2

WIN_POINTS = 30


# ==================================================
# الألعاب النشطة
# ==================================================

active_hide_games = {}


# ==================================================
# هل يستطيع إدارة اللعبة؟
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

    if not can_manage_hide_game(user.id):

        await update.message.reply_text(
            "❌ هذا الأمر للرتب فقط."
        )

        return

    if chat.id in active_hide_games:

        await update.message.reply_text(
            "❌ ت��جد لعبة غميضة شغالة بالفعل."
        )

        return

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

        "hide_timeout_task": None,

        "discoveries": Counter(),

        "bomb_hits": Counter(),

        "scores": {},

        "hidden": {},

        "searching": False,

        "search_player": None,

        # حماية من الضغط المتكرر
        "processing": False,
    }

    await update.message.reply_text(
        "🚪 تم فتح التسجيل في لعبة الغميضة!\n\n"
        "• نوع اللوحة المختار: الأرقام 🔢\n"
        "• اكتب دخول للانضمام إلى اللعبة.\n"
        "• عندما يكتمل اللاعبون، يكتب الأدمن ابدا لبدء اللعبة.\n"
        f"• الحد الأدنى لبدء اللعبة: {MIN_PLAYERS} لاعبين."
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

    if user.id in game["players"]:

        await update.message.reply_text(
            f"❌ أنت داخل اللعبة بالفعل يا "
            f"{get_player_name(user)}."
        )

        return

    game["players"][user.id] = user

    game["order"].append(user.id)

    game["scores"][user.id] = 0

    game["board_size"] = get_board_size(
        len(game["players"])
    )

    names = []

    for player_id in game["order"]:

        player = game["players"][player_id]

        names.append(
            f"{len(names) + 1}. "
            f"{get_player_name(player)}"
        )

    await update.message.reply_text(
        f"✅ تم تسجيل {get_player_name(user)} "
        "في لعبة الغميضة!\n\n"
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
        "📩 أرسلت الآن لكل لاعب رسالة خاصة "
        "لاختيار مكان اختبائه.\n"
        f"⏱ أمام كل لاعب {HIDE_TIME} ثانية.\n\n"
        "إذا لم يختر اللاعب خلال الوقت، "
        "سأختار له رقمًا عشوائيًا."
    )

    # إرسال لوحة الاختباء لكل لاعب
    for player_id in game["order"]:

        await send_hide_choice(
            context,
            chat.id,
            player_id
        )

    # مؤقت الاختباء
    task = asyncio.create_task(
        hide_phase_timeout(
            context,
            chat.id
        )
    )

    game["hide_timeout_task"] = task


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
                f"😶‍🌫️ اختر الرقم الذي تريد "
                "الاختباء فيه.\n\n"
                f"⏱ لديك {HIDE_TIME} ثانية.\n"
                "يمكن لأكثر من لاعب الاختباء "
                "في نفس الرقم."
            ),
            reply_markup=keyboard
        )

        game["hide_tasks"][player_id] = message.message_id

    except Exception:

        try:

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ لم أستطع إرسال رسالة خاصة إلى "
                    f"{get_player_name(player)}.\n"
                    "يجب عليه فتح محادثة البوت "
                    "والضغط على Start."
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

    data = query.data or ""

    parts = data.split(":")

    if len(parts) != 3:
        await query.answer()
        return

    try:

        _, chat_id_text, player_id_text = parts

        chat_id = int(chat_id_text)
        player_id = int(player_id_text)

        number = int(parts[2])

    except Exception:

        await query.answer()
        return

    game = active_hide_games.get(chat_id)

    if not game:

        await query.answer(
            "❌ اللعبة انتهت.",
            show_alert=True
        )

        return

    if game["phase"] != "hiding":

        await query.answer(
            "❌ انتهى وقت الاختباء.",
            show_alert=True
        )

        return

    if query.from_user.id != player_id:

        await query.answer(
            "❌ هذه اللوحة ليست لك.",
            show_alert=True
        )

        return

    if player_id in game["hidden"]:

        await query.answer(
            "❌ أنت اخترت رقمك بالفعل.",
            show_alert=True
        )

        return

    if number < 1 or number > game["board_size"]:

        await query.answer(
            "❌ رقم غير صحيح.",
            show_alert=True
        )

        return

    # حفظ الرقم
    game["hidden"][player_id] = number

    await query.answer(
        "✅ تم اختيار الرقم."
    )

    # تعديل نفس رسالة الخاص
    try:

        await query.edit_message_text(
            text=(
                "😶‍🌫️ تم اختيار مكان اختبائك!\n\n"
                f"🔢 رقمك: {number}\n\n"
                "انتظر حتى يختار باقي اللاعبين."
            )
        )

    except Exception:
        pass

    # الجميع اختار
    if len(game["hidden"]) >= len(game["players"]):

        timeout_task = game.get(
            "hide_timeout_task"
        )

        if timeout_task:
            timeout_task.cancel()

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

    try:

        await asyncio.sleep(HIDE_TIME)

    except asyncio.CancelledError:

        return

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "hiding":
        return

    # أرقام الاختباء لا تُحذف من أي لوحة
    # ويمكن لأكثر من لاعب اختيار نفس الرقم

    for player_id in game["order"]:

        if player_id in game["hidden"]:
            continue

        if player_id not in game["players"]:
            continue

        number = random.randint(
            1,
            game["board_size"]
        )

        game["hidden"][player_id] = number

        try:

            await context.bot.send_message(
                chat_id=player_id,
                text=(
                    "⏰ انتهى وقت الاختباء!\n\n"
                    f"🎲 اخترت لك المربع "
                    f"({number}) عشوائيًا."
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

    game["current_index"] = 0

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "😶‍🌫️ لقد اختبأ جميع اللاعبين بنجاح!\n\n"
            "🔎 تبدأ الآن أدوار البحث.\n"
            "كل لاعب يختار مربعًا واحدًا للبحث فيه.\n\n"
            "💥 إذا وجد لاعبًا في المربع يت�� استبعاده.\n"
            "🎁 توجد هدايا وقنابل خلف بعض المربعات.\n\n"
            f"🏆 آخر لاعب يبقى يحصل على +{WIN_POINTS} نقطة.\n"
            f"🏆 وإذا بقي اللاعبون في نفس المربع "
            f"يفوزون جميعًا ويحصل كل واحد على +{WIN_POINTS}."
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

    # لا أحد أو لاعب واحد
    if len(alive) <= 1:
        return True

    # إذا جميع اللاعبين المتبقين في نفس الرقم
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

    # فحص نهاية اللعبة
    if check_game_finished(game):

        await finish_hide_game(
            context,
            chat_id
        )

        return

    order = game["order"]

    if not order:

        await finish_hide_game(
            context,
            chat_id
        )

        return

    checked = 0

    while checked < len(order):

        index = game["current_index"] % len(order)

        player_id = order[index]

        game["current_index"] += 1

        checked += 1

        # اللاعب مطرود
        if player_id not in game["players"]:
            continue

        player = game["players"].get(player_id)

        if not player:
            continue

        # الأرقام المتاحة للبحث
        #
        # مهم:
        # الرقم لا يختفي إلا بعد البحث فيه.
        available = list(game["available"])

        # اللاعب لا يستطيع البحث في مكان اختبائه
        hidden_number = game["hidden"].get(
            player_id
        )

        if hidden_number in available:

            available.remove(hidden_number)

        # لا يوجد مكان يمكن البحث فيه
        if not available:

            await finish_hide_game(
                context,
                chat_id
            )

            return

        game["searching"] = True

        game["search_player"] = player_id

        keyboard = build_board(
            available,
            f"search:{chat_id}:{player_id}"
        )

        message = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🫣 تفضل يا {get_player_name(player)} "
                "اختر مربعًا للبحث فيه.\n\n"
                f"⏱ أمامك {SEARCH_TIME} ثانية."
            ),
            reply_markup=keyboard
        )

        game["search_message_id"] = message.message_id

        # مؤقت الدور
        old_task = game.get("search_task")

        if old_task:

            old_task.cancel()

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

    data = query.data or ""

    try:

        _, chat_id_text, player_id_text, number_text = (
            data.split(":")
        )

        chat_id = int(chat_id_text)
        player_id = int(player_id_text)
        number = int(number_text)

    except Exception:

        await query.answer()
        return

    game = active_hide_games.get(chat_id)

    if not game:

        await query.answer(
            "❌ اللعبة انتهت.",
            show_alert=True
        )

        return

    if game["phase"] != "searching":

        await query.answer(
            "❌ البحث غير متاح الآن.",
            show_alert=True
        )

        return

    # ----------------------------------------------
    # أهم نقطة:
    # الشخص الذي ضغط الزر يجب أن يكون اللاعب الحالي
    # ----------------------------------------------

    if game.get("search_player") != query.from_user.id:

        await query.answer(
            "⏳ انتظر، ليس دورك!",
            show_alert=True
        )

        return

    # حماية من الضغط المكرر
    if game.get("processing"):

        await query.answer(
            "⏳ لحظة...",
            show_alert=True
        )

        return

    # نتأكد أن الرقم ما زال موجودًا
    if number not in game["available"]:

        await query.answer(
            "❌ هذا الرقم تم البحث فيه بالفعل.",
            show_alert=True
        )

        return

    # اللاعب نفسه يجب أن يطابق الـ callback
    if player_id != query.from_user.id:

        await query.answer(
            "❌ ليس دورك!",
            show_alert=True
        )

        return

    # لا يستطيع البحث في مكان اختبائه
    if number == game["hidden"].get(player_id):

        await query.answer(
            "❌ لا يمكنك البحث في مكان اختبائك!",
            show_alert=True
        )

        return

    game["processing"] = True

    # إيقاف المؤقت
    task = game.get("search_task")

    if task:

        task.cancel()

        game["search_task"] = None

    await query.answer(
        "🔎 يتم البحث..."
    )

    try:

        await resolve_search(
            context,
            chat_id,
            player_id,
            number,
            query.message
        )

    finally:

        game["processing"] = False


# ==================================================
# حل البحث
# ==================================================

async def resolve_search(
    context,
    chat_id,
    player_id,
    number,
    original_message=None
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    # حماية مهمة جدًا
    # إذا الرقم غير موجود لا نلمسه
    if number not in game["available"]:
        return

    player = game["players"].get(player_id)

    if not player:
        return

    # ----------------------------------------------
    # حذف الرقم فقط هنا
    #
    # يعني الرقم لا يختفي إلا بعد اختيار فعلي
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
    # الرسالة
    # ----------------------------------------------

    text = (
        f"🔎 {get_player_name(player)} "
        f"اختار المربع ({number})\n\n"
    )

    # ----------------------------------------------
    # وجد لاعبين
    # ----------------------------------------------

    if found_players:

        names = []

        for found_id in found_players:

            found_user = game["players"].get(
                found_id
            )

            if found_user:

                names.append(
                    get_player_name(found_user)
                )

        text += (
            "💥 تم كشف المخبأ!\n\n"
            "👀 تم العثور على:\n"
            + "\n".join(
                f"• {name}"
                for name in names
            )
            + "\n\n"
            "❌ تم استبعادهم من اللعبة."
        )

        for found_id in found_players:

            if found_id in game["players"]:

                del game["players"][found_id]

        game["discoveries"][player_id] += len(
            found_players
        )

    # ----------------------------------------------
    # لم يجد أحد
    # ----------------------------------------------

    else:

        text += (
            "💨 لم يجد أحدًا في هذا المربع."
        )

        # ------------------------------------------
        # القنبلة
        # ------------------------------------------

        if content == "bomb":

            game["bomb_hits"][player_id] += 1

            alive = alive_players(game)

            if alive:

                target_id = random.choice(alive)

                target = game["players"].get(
                    target_id
                )

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
                        f"💡 تلميح عن "
                        f"{get_player_name(target)}:\n"
                        f"رقم اختبائه {parity}."
                    )

        # ------------------------------------------
        # فرصة إضافية
        # ------------------------------------------

        elif content == "extra":

            text += (
                "\n\n🔄 حصل على فرصة إضافية!"
            )

        # ------------------------------------------
        # +5
        # ------------------------------------------

        elif content == "plus5":

            game["scores"][player_id] += 5

            add_points(
                player_id,
                5
            )

            text += (
                "\n\n🎁 حصل على +5 نقاط!"
            )

        # ------------------------------------------
        # +10
        # ------------------------------------------

        elif content == "plus10":

            game["scores"][player_id] += 10

            add_points(
                player_id,
                10
            )

            text += (
                "\n\n🎁 حصل على +10 نقاط!"
            )

        # ------------------------------------------
        # -3
        # ------------------------------------------

        elif content == "minus3":

            game["scores"][player_id] -= 3

            add_points(
                player_id,
                -3
            )

            text += (
                "\n\n💥 مربع خصم!\n"
                "تم خصم 3 نقاط."
            )

        # ------------------------------------------
        # -5
        # ------------------------------------------

        elif content == "minus5":

            game["scores"][player_id] -= 5

            add_points(
                player_id,
                -5
            )

            text += (
                "\n\n💥 مربع خصم!\n"
                "تم خصم 5 نقاط."
            )

    # ----------------------------------------------
    # تعديل نفس رسالة اللاعب
    # ----------------------------------------------

    if original_message:

        try:

            await original_message.edit_text(
                text=text,
                reply_markup=None
            )

        except Exception:

            # احتياط إذا فشل التعديل
            try:

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text
                )

            except Exception:
                pass

    else:

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

    game["search_player"] = None

    await start_next_search_turn(
        context,
        chat_id
    )


# ==================================================
# دور إضافي
# ==================================================

async def start_specific_search_turn(
    context,
    chat_id,
    player_id
):

    game = active_hide_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "searching":
        return

    if player_id not in game["players"]:
        return

    available = list(game["available"])

    hidden_number = game["hidden"].get(
        player_id
    )

    if hidden_number in available:

        available.remove(hidden_number)

    if not available:

        await finish_hide_game(
            context,
            chat_id
        )

        return

    player = game["players"][player_id]

    game["search_player"] = player_id

    keyboard = build_board(
        available,
        f"search:{chat_id}:{player_id}"
    )

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🔄 فرصة إضافية!\n\n"
            f"تفضل يا {get_player_name(player)} "
            "اختر مربعًا آخر.\n\n"
            f"⏱ أمامك {SEARCH_TIME} ثانية."
        ),
        reply_markup=keyboard
    )

    game["search_message_id"] = message.message_id

    old_task = game.get("search_task")

    if old_task:
        old_task.cancel()

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

    player = game["players"].get(player_id)

    # ----------------------------------------------
    # اللاعب لم يختر
    # يتم طرده من اللعبة
    # ----------------------------------------------

    if player:

        try:

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["search_message_id"],
                text=(
                    f"⏰ انتهى وقت {get_player_name(player)}!\n\n"
                    "❌ لم يختر أي مربع.\n"
                    "تم استبعاده من اللعبة."
                )
            )

        except Exception:
            pass

    # حذف اللاعب
    if player_id in game["players"]:

        del game["players"][player_id]

    game["search_task"] = None

    game["search_player"] = None

    game["searching"] = False

    # ----------------------------------------------
    # إذا بقي لاعب واحد
    # ----------------------------------------------

    if check_game_finished(game):

        await finish_hide_game(
            context,
            chat_id
        )

        return

    # ----------------------------------------------
    # تكملة الدور تلقائيًا
    # ----------------------------------------------

    await start_next_search_turn(
        context,
        chat_id
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

    # إلغاء مؤقت البحث
    task = game.get("search_task")

    if task:

        task.cancel()

    # إلغاء مؤقت الاختباء
    task = game.get(
        "hide_timeout_task"
    )

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

    # حماية من استدعاء النهاية مرتين
    if game["phase"] == "finished":
        return

    game["phase"] = "finished"

    # ----------------------------------------------
    # إلغاء المؤقتات
    # ----------------------------------------------

    task = game.get("search_task")

    if task:

        task.cancel()

    task = game.get(
        "hide_timeout_task"
    )

    if task:

        task.cancel()

    game["search_task"] = None
    game["hide_timeout_task"] = None

    # ----------------------------------------------
    # الفائزون
    # ----------------------------------------------

    alive = alive_players(game)

    winners = list(alive)

    # ----------------------------------------------
    # إعطاء +30 لكل فائز
    # ----------------------------------------------

    for winner_id in winners:

        add_points(
            winner_id,
            WIN_POINTS
        )

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
    # رسالة النهاية
    # ----------------------------------------------

    text = (
        "🏆 انتهت لعبة الغميضة!\n\n"
    )

    if len(winners) == 1:

        winner = game["players"].get(
            winners[0]
        )

        if winner:

            text += (
                f"🥇 {get_player_name(winner)}\n"
                f"🎁 الفائز وحصل على +{WIN_POINTS} نقطة!\n"
            )

    elif len(winners) > 1:

        text += (
            f"🥇 الفائزون جميعًا!\n\n"
        )

        for winner_id in winners:

            winner = game["players"].get(
                winner_id
            )

            if winner:

                text += (
                    f"• {get_player_name(winner)} "
                    f"+{WIN_POINTS} نقطة\n"
                )

    else:

        text += (
            "❌ انتهت اللعبة ولم يتبقَّ لاعبون.\n"
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
                f"({game['discoveries'][most_discoveries]} اكتشاف)\n"
                "🎁 حصل على +5 نقاط."
            )

    if most_bombs:

        user = game["players"].get(
            most_bombs
        )

        if user:

            text += (
                "\n\n💣 أكثر لاعب أصابته القنابل: "
                f"{get_player_name(user)} "
                f"({game['bomb_hits'][most_bombs]} قنابل)\n"
                "💥 تم خصم 5 نقاط منه."
            )

    # ----------------------------------------------
    # نقاط الجولة
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

            # اللاعب قد يكون انطرد
            # لذلك نستخدم players ثم order
            player = game["players"].get(
                player_id
            )

            if not player:

                # نبحث عنه من ترتيب اللاعبين
                # حتى تظهر نقاطه لو كان انطرد
                for original_id in game["order"]:

                    if original_id == player_id:

                        # لا يوجد User object منفصل
                        # إذا حُذف من players
                        # نتجاهله
                        break

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
