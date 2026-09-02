import asyncio
import random

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

TURN_TIME = 30
WIN_POINTS = 50


# ==================================================
# صور الاستعداد
# ==================================================

READY_IMAGES = {
    "red": "AgACAgQAAxkBAAICx2qXXRF_tg0mysuxrFyg-TzQFOFWAAJvEmsbkuPAUDW0ZFs8Jpp0AQADAgADeQADPQQ",
    "blue": "AgACAgQAAxkBAAICzWqXXSelWf1kB8pPZa_v_tT75xNZAAJwEmsbkuPAUAaqxmTbcl6BAQADAgADeQADPQQ",
}


# ==================================================
# صور النتائج
#
# المفتاح:
# (فريق الحارس, اتجاه الحارس, اتجاه المسدد)
# ==================================================

RESULT_IMAGES = {

    # ==============================================
    # الحارس الأحمر
    # ==============================================

    (
        "red",
        "يسار",
        "يسار"
    ):
        "AgACAgQAAxkBAAIC2mqXXi2MCyP1bavd0hR1Z7qzHoCAAAJ0EmsbkuPAUKVIWnY0MYkOAQADAgADeQADPQQ",

    (
        "red",
        "يسار",
        "وسط"
    ):
        "AgACAgQAAxkBAAIC5GqXXw7IjhzegXCjpRcxZwqjVS6WAAJ5EmsbkuPAUFp8zcXUDTg5AQADAgADeQADPQQ",

    (
        "red",
        "يسار",
        "يمين"
    ):
        "AgACAgQAAxkBAAIC2GqXXd6JOsmKg6XY4QmjioYpY6JBAAJzEmsbkuPAUN2RFOQM76ZjAQADAgADeQADPQQ",

    (
        "red",
        "وسط",
        "يسار"
    ):
        "AgACAgQAAxkBAAIC4GqXXq47KtcOgOu_X2FaUbKinv5bAAJ3EmsbkuPAUM6TlGij3IEHAQADAgADeQADPQQ",

    (
        "red",
        "وسط",
        "وسط"
    ):
        "AgACAgQAAxkBAAIC1mqXXaAJP0tj2fHk37IEYyLojq8-AAJyEmsbkuPAUMnwQohZeWMRAQADAgADeQADPQQ",

    (
        "red",
        "وسط",
        "يمين"
    ):
        "AgACAgQAAxkBAAIC3GqXXk_YkocGUIQQLrUjVUsT6WFJAAJ1EmsbkuPAUKlvrIEsTFKiAQADAgADeQADPQQ",

    (
        "red",
        "يمين",
        "يسار"
    ):
        "AgACAgQAAxkBAAIC4mqXXuc962m3PinFC3de9Cnd0yn9AAJ4EmsbkuPAUPPtWgmjylC3AQADAgADeQADPQQ",

    (
        "red",
        "يمين",
        "وسط"
    ):
        "AgACAgQAAxkBAAIC3mqXXm9DsfMF7RKuGnjX0DZZCDElAAJ2EmsbkuPAUGcJXuHpNXeRAQADAgADeQADPQQ",

    (
        "red",
        "يمين",
        "يمين"
    ):
        "AgACAgQAAyEFAATwGwEUAAJP-2qXQ8T5AtOCk6Tgh_lxF3uj8CLbAAIhE2sbtou5UESSt8Vei3-fAQADAgADeQADPQQ",


    # ==============================================
    # الحارس الأزرق
    # ==============================================

    (
        "blue",
        "يسار",
        "يسار"
    ):
        "AgACAgQAAxkBAAIC5mqXX1YLbKkPxyFAuXt4GIyWpwr0AAJ6EmsbkuPAUJauXBMfrdsmAQADAgADeQADPQQ",

    (
        "blue",
        "يسار",
        "وسط"
    ):
        "AgACAgQAAxkBAAIC-2qXY5T0b_X374-vZzZGl0HLQEEYAAKIEmsbkuPAUFT-iD8IXTJ6AQADAgADeQADPQQ",

    (
        "blue",
        "يسار",
        "يمين"
    ):
        "AgACAgQAAxkBAAIC6mqXX5umjMZgl8QvHQ9cWVE7OBkrAAJ8EmsbkuPAUETvi9lxwAABoAEAAwIAA3kAAz0E",

    (
        "blue",
        "وسط",
        "يسار"
    ):
        "AgACAgQAAxkBAAIC8mqXYJiHXfglNwRGoIhIfxfC8bjdAAKCEmsbkuPAUGkJ2VH7L0tAAQADAgADeQADPQQ",

    (
        "blue",
        "وسط",
        "وسط"
    ):
        "AgACAgQAAxkBAAIC8GqXYHN9_lRYWV7MQ-2ViZNxESDxAAKAEmsbkuPAUBIAAa6Cdmoz2AEAAwIAA3kAAz0E",

    (
        "blue",
        "وسط",
        "يمين"
    ):
        "AgACAgQAAxkBAAIC9GqXYNPEKxVz0lKOSKIvI8jMwlTPAAKFEmsbkuPAUMilU52EcjlsAQADAgADeQADPQQ",

    (
        "blue",
        "يمين",
        "يسار"
    ):
        "AgACAgQAAxkBAAIC6GqXX3Rokn49gwNhssRA_Jr5Mim6AAJ7EmsbkuPAUBloAjhQo03mAQADAgADeQADPQQ",

    (
        "blue",
        "يمين",
        "وسط"
    ):
        "AgACAgQAAxkBAAIC7GqXX81g1Ntcm7CbDJFBr4XBTj0nAAJ9EmsbkuPAUC1szPgbscpJAQADAgADeQADPQQ",

    (
        "blue",
        "يمين",
        "يمين"
    ):
        "AgACAgQAAxkBAAIC7mqXX_UXpeFNif4tcrDWx1_KUoeSAAJ_EmsbkuPAUIc2qNsrW-HMAQADAgADeQADPQQ",
}


# ==================================================
# الاتجاهات
# ==================================================

DIRECTIONS = {
    "يسار": "👈🏻",
    "وسط": "🎯",
    "يمين": "👉🏻",
}


# ==================================================
# الألعاب النشطة
# ==================================================

active_penalty_games = {}


# ==================================================
# الصلاحية
# نفس نظام غميضة
# ==================================================

def can_manage_penalties(user_id):

    return get_rank_level(user_id) > 0


# ==================================================
# اسم اللاعب
# ==================================================

def get_player_name(user):

    if not user:
        return "مستخدم"

    # اسم الحساب الظاهر في تيليجرام، وليس اليوزر
    return user.full_name or user.first_name or "مستخدم"


# ==================================================
# لوحة الاتجاهات
# ==================================================

def direction_keyboard(chat_id):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "يسار 👈🏻",
                callback_data=f"penalty:direction:{chat_id}:يسار"
            ),
            InlineKeyboardButton(
                "وسط 🎯",
                callback_data=f"penalty:direction:{chat_id}:وسط"
            ),
            InlineKeyboardButton(
                "يمين 👉🏻",
                callback_data=f"penalty:direction:{chat_id}:يمين"
            )
        ]
    ])


# ==================================================
# بدء التسجيل
# ==================================================

async def start_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":

        await update.message.reply_text(
            "❌ لعبة البلنتيات تبدأ من القروب."
        )

        return

    if not can_manage_penalties(user.id):

        await update.message.reply_text(
            "❌ هذا الأمر للرتب فقط."
        )

        return

    if chat.id in active_penalty_games:

        await update.message.reply_text(
            "❌ توجد مباراة بلنتيات شغالة بالفعل."
        )

        return

    active_penalty_games[chat.id] = {
        "players": {},
        "order": [],

        "phase": "registration",

        "red": {
            "shooters": [],
            "goalies": []
        },

        "blue": {
            "shooters": [],
            "goalies": []
        },

        "shoot_index": {
            "red": 0,
            "blue": 0
        },

        "goalie_index": {
            "red": 0,
            "blue": 0
        },

        "score": {
            "red": 0,
            "blue": 0
        },

        "kick_number": 1,

        "current_team": "red",

        "current_shooter": None,
        "current_goalie": None,

        "shooter_choice": None,
        "goalie_choice": None,

        "shooter_ready": False,
        "goalie_ready": False,

        "ready_message_id": None,
        
        "shooter_task": None,
        "goalie_task": None,

        "resolving": False,

        "manual_message_id": None,

        "used_players": set(),
    }

    await update.message.reply_text(
        "⚽️ تم بدء لعبة البلنتيات 🥅\n\n"
        "• للانضمام اكتب: دخول\n"
        "• للبدء اكتب: ابدا"
    )


# ==================================================
# دخول اللاعب
# ==================================================

async def join_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id

    game = active_penalty_games.get(chat_id)

    if not game:
        return

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

    await update.message.reply_text(
        f"انضم {get_player_name(user)} ⚽ "
        f"(العدد: {len(game['players'])})"
    )


# ==================================================
# بدء التوزيع
# ==================================================

async def distribute_penalties(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] != "registration":
        return

    if len(game["players"]) < 2:

        await update.message.reply_text(
            "❌ يجب أن يكون هناك لاعبان على الأقل."
        )

        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔘 يدوي",
                callback_data=f"penalty:distribution:{chat_id}:manual"
            ),
            InlineKeyboardButton(
                "🔘 عشوائي",
                callback_data=f"penalty:distribution:{chat_id}:random"
            )
        ]
    ])

    await update.message.reply_text(
        "🛡️ توزيع فرق مباراة البلنتيات "
        "(أحمر ضد أزرق)\n"
        f"يا {get_player_name(user)}، كيف تبي نوزّع اللاعبين؟",
        reply_markup=keyboard
    )


# ==================================================
# callback التوزيع
# ==================================================


async def distribution_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    try:

        parts = query.data.split(":")

        if len(parts) != 4:
            await query.answer()
            return

        _, action, chat_id_text, mode = parts

        chat_id = int(chat_id_text)

    except Exception:

        await query.answer()
        return

    game = active_penalty_games.get(chat_id)

    if not game:

        await query.answer(
            "❌ انتهت المباراة.",
            show_alert=True
        )

        return

    if not can_manage_penalties(
        query.from_user.id
    ):

        await query.answer(
            "❌ ما عندك صلاحية.",
            show_alert=True
        )

        return

    if game["phase"] != "registration":

        await query.answer(
            "❌ انتهى وقت التوزيع.",
            show_alert=True
        )

        return

    await query.answer()

    # ==================================================
    # احذف رسالة:
    # 🛡️ توزيع فرق مباراة البلنتيات...
    # ==================================================

    try:
        await query.message.delete()
    except Exception:
        pass

    # ==================================================
    # عشوائي
    # ==================================================

    if mode == "random":

        await random_distribution(
            context,
            chat_id
        )

        return

    # ==================================================
    # يدوي
    # ==================================================

    if mode == "manual":

        await show_manual_distribution(
            context,
            chat_id
        )

        return


# ==================================================
# التوزيع العشوائي
# ==================================================

def make_random_teams(game):

    player_ids = list(game["players"].keys())

    random.shuffle(player_ids)

    count = len(player_ids)

    if count == 2:

        red_id = player_ids[0]
        blue_id = player_ids[1]

        game["red"]["shooters"] = [red_id]
        game["red"]["goalies"] = [red_id]

        game["blue"]["shooters"] = [blue_id]
        game["blue"]["goalies"] = [blue_id]

        return

    red_count = (count + 1) // 2
    blue_count = count - red_count

    red_players = player_ids[:red_count]
    blue_players = player_ids[red_count:]

    def assign_team(team_players, team):

        shuffled = list(team_players)

        random.shuffle(shuffled)

        if len(shuffled) == 1:

            game[team]["shooters"] = [shuffled[0]]
            game[team]["goalies"] = [shuffled[0]]

            return

        # المسددون أكثر من الحراس
        goalie_count = max(1, len(shuffled) // 3)

        if goalie_count >= len(shuffled):
            goalie_count = 1

        goalie_ids = shuffled[:goalie_count]
        shooter_ids = shuffled[goalie_count:]

        game[team]["shooters"] = shooter_ids
        game[team]["goalies"] = goalie_ids

    assign_team(red_players, "red")
    assign_team(blue_players, "blue")


async def random_distribution(
    context,
    chat_id
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    make_random_teams(game)

    game["phase"] = "distributed"

    await send_distribution_result(
        context,
        chat_id,
        random_mode=True
    )


# ==================================================
# عرض التوزيع اليدوي
# ==================================================

async def show_manual_distribution(
    context,
    chat_id
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    game["phase"] = "manual"

    lines = []

    for index, player_id in enumerate(
        game["order"],
        start=1
    ):

        player = game["players"][player_id]

        lines.append(
            f"{index}. {get_player_name(player)}"
        )

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🎯 التوزيع اليدوي لمباراة البلنتيات\n\n"
            + "\n".join(lines)
            + "\n\n"
            "استخدم:\n"
            ".احمر رقم رقم*\n"
            ".ازرق رقم رقم*\n\n"
            "ضع * بجانب الرقم لجعل اللاعب حارسًا.\n"
            "مثال:\n"
            ".احمر 1 2*\n\n"
            "يعني:\n"
            "1 = مسدد\n"
            "2 = حارس"
        )
    )

    game["manual_message_id"] = message.message_id


# ==================================================
# تحويل رقم اللاعب
# ==================================================

def get_player_by_number(game, number):

    if number < 1 or number > len(game["order"]):
        return None

    player_id = game["order"][number - 1]

    return player_id


# ==================================================
# الأمر اليدوي
# ==================================================

async def manual_team_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "manual":
        return

    user = update.effective_user

    if not can_manage_penalties(user.id):
        return

    text = update.message.text.strip()

    parts = text.split()

    if len(parts) < 2:
        return

    command = parts[0]

    if command not in (".احمر", ".ازرق"):
        return

    team = "red" if command == ".احمر" else "blue"

    selected = []

    for raw in parts[1:]:

        is_goalie = raw.endswith("*")

        clean = raw[:-1] if is_goalie else raw

        try:
            number = int(clean)
        except ValueError:
            await update.message.reply_text(
                f"❌ الرقم {clean} غير صحيح."
            )
            return

        player_id = get_player_by_number(
            game,
            number
        )

        if player_id is None:

            await update.message.reply_text(
                f"❌ لا يوجد لاعب بالرقم {number}."
            )

            return

        selected.append(
            (player_id, is_goalie)
        )

    # لا يسمح بتكرار اللاعب
    for player_id, _ in selected:

        if player_id in game["used_players"]:

            player = game["players"].get(player_id)

            await update.message.reply_text(
                f"❌ اللاعب {get_player_name(player)} "
                "تم توزيعه بالفعل."
            )

            return

    # ==================================================
    # إذا يوجد أكثر من لاعب:
    # يجب أن يكون كل لاعب دورًا واحدًا
    # ==================================================

    unassigned_before = (
        len(game["players"])
        - len(game["used_players"])
    )

    if unassigned_before > len(selected):

        # لا يسمح بأن يكون اللاعب حارس + مسدد
        # إلا إذا كان هذا اللاعب هو الوحيد المتبقي
        pass

    for player_id, is_goalie in selected:

        if is_goalie:

            game[team]["goalies"].append(
                player_id
            )

        else:

            game[team]["shooters"].append(
                player_id
            )

        game["used_players"].add(
            player_id
        )

    await show_manual_status(
        update,
        game,
        team
    )

    await check_manual_completion(
        context,
        chat_id
    )


# ==================================================
# حالة التوزيع اليدوي
# ==================================================

async def show_manual_status(
    update,
    game,
    team
):

    red_shooters = [
        get_player_name(game["players"].get(pid))
        for pid in game["red"]["shooters"]
    ]

    red_goalies = [
        get_player_name(game["players"].get(pid))
        for pid in game["red"]["goalies"]
    ]

    blue_shooters = [
        get_player_name(game["players"].get(pid))
        for pid in game["blue"]["shooters"]
    ]

    blue_goalies = [
        get_player_name(game["players"].get(pid))
        for pid in game["blue"]["goalies"]
    ]

    remaining = [
        index + 1
        for index, player_id in enumerate(game["order"])
        if player_id not in game["used_players"]
    ]

    text = (
        "📋 حالة التوزيع:\n\n"
        "🔴 الفريق الأحمر:\n"
        f"🎯 المسددين: "
        f"{', '.join(red_shooters) if red_shooters else '—'}\n"
        f"🛡️ الحراس: "
        f"{', '.join(red_goalies) if red_goalies else '—'}\n\n"
        "🔵 الفريق الأزرق:\n"
        f"🎯 المسددين: "
        f"{', '.join(blue_shooters) if blue_shooters else '—'}\n"
        f"🛡️ الحراس: "
        f"{', '.join(blue_goalies) if blue_goalies else '—'}"
    )

    if remaining:

        text += (
            "\n\n👥 اللاعبون المتبقون:\n"
            + "\n".join(
                str(number)
                for number in remaining
            )
        )

    await update.message.reply_text(text)


# ==================================================
# إكمال التوزيع اليدوي
# ==================================================

async def check_manual_completion(
    context,
    chat_id
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    remaining = [
        player_id
        for player_id in game["order"]
        if player_id not in game["used_players"]
    ]

    if remaining:
        return

    # ==================================================
    # كل اللاعبين تم توزيعهم
    # ==================================================

    for team in ("red", "blue"):

        total_players = set(
            game[team]["shooters"]
            + game[team]["goalies"]
        )

        # فريق فيه لاعب واحد فقط:
        # يكون مسدد + حارس
        if len(total_players) == 1:

            player_id = next(
                iter(total_players)
            )

            game[team]["shooters"] = [player_id]
            game[team]["goalies"] = [player_id]

    # ==================================================
    # كل فريق لازم عنده مسدد وحارس
    # ==================================================

    for team in ("red", "blue"):

        if not game[team]["shooters"]:

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ لا يمكن إكمال التوزيع.\n"
                    f"الفريق "
                    f"{'الأحمر 🔴' if team == 'red' else 'الأزرق 🔵'} "
                    "ليس لديه مسدد."
                )
            )

            return

        if not game[team]["goalies"]:

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ لا يمكن إكمال التوزيع.\n"
                    f"الفريق "
                    f"{'الأحمر 🔴' if team == 'red' else 'الأزرق 🔵'} "
                    "ليس لديه حارس."
                )
            )

            return

    game["phase"] = "distributed"

    await send_distribution_result(
        context,
        chat_id,
        random_mode=False
    )


# ==================================================
# نتيجة التوزيع
# ==================================================

async def send_distribution_result(
    context,
    chat_id,
    random_mode=False
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    def names(team, role):

        return ", ".join(
            get_player_name(
                game["players"].get(player_id)
            )
            for player_id in game[team][role]
        )

    text = (
        "🎯 اكتمل توزيع مباراة البلنتيات!\n\n"
        "🔴 الفريق الأحمر:\n"
        f"🎯 المسددين: {names('red', 'shooters')}\n"
        f"🛡️ الحراس: {names('red', 'goalies')}\n\n"
        "🔵 الفريق الأزرق:\n"
        f"🎯 المسددين: {names('blue', 'shooters')}\n"
        f"🛡️ الحراس: {names('blue', 'goalies')}\n\n"
        "الأدمن يكتب .ابدا لبدء ركلات الترجيح! 🚀"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )


# ==================================================
# بدء ركلات الترجيح
# ==================================================

async def begin_penalties(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] != "distributed":

        await update.message.reply_text(
            "❌ لم يكتمل توزيع اللاعبين بعد."
        )

        return

    game["phase"] = "shootout"
    game["kick_number"] = 1
    game["current_team"] = "red"

    await start_kick(
        context,
        chat_id
    )


# ==================================================
# جلب المسدد التالي
# ==================================================

def next_shooter(game, team):

    players = game[team]["shooters"]

    index = game["shoot_index"][team] % len(players)

    player_id = players[index]

    game["shoot_index"][team] += 1

    return player_id


# ==================================================
# جلب الحارس التالي
# ==================================================

def next_goalie(game, team):

    players = game[team]["goalies"]

    index = game["goalie_index"][team] % len(players)

    player_id = players[index]

    game["goalie_index"][team] += 1

    return player_id



def get_kick_warning(game):

    red = game["score"]["red"]
    blue = game["score"]["blue"]

    team = game["current_team"]

    shooter = game["players"].get(
        game["current_shooter"]
    )

    goalie = game["players"].get(
        game["current_goalie"]
    )

    if not shooter or not goalie:
        return None

    shooter_name = get_player_name(shooter)
    goalie_name = get_player_name(goalie)

    # ==================================================
    # الركلة الخامسة للأحمر
    # ==================================================

    if game["kick_number"] == 9 and team == "red":

        # الأحمر متأخر بفارق يجعل هذه ركلة بقاء
        if red < blue:

            return (
                "⚠️ *ضغوط هائلة!* "
                f"يجب على *{shooter_name}* التسجيل للاستمرار، "
                f"إذا ضاعت أو صدها الحارس *{goalie_name}* "
                "يفوز *🔵 الفريق الأزرق* باللقب! 🏆"
            )

        # الأحمر متقدم، ويمكن أن يحسم إذا كان الفارق
        # أكبر من إمكانية تعويض الأزرق في ركلته الخامسة
        if red > blue:

            return (
                "⚠️ *ركلة حاسمة للبطولة!* "
                f"إذا سجلها *{shooter_name}*، "
                "يفوز *🔴 الفريق الأحمر* باللقب! 🏆"
            )

    # ==================================================
    # الركلة الخامسة للأزرق
    # ==================================================

    if game["kick_number"] == 10 and team == "blue":

        # الأزرق متأخر
        if blue < red:

            return (
                "⚠️ *ضغوط هائلة!* "
                f"يجب على *{shooter_name}* التسجيل للاستمرار، "
                f"إذا ضاعت أو صدها الحارس *{goalie_name}* "
                "يفوز *🔴 الفريق الأحمر* باللقب! 🏆"
            )

        # الأزرق متقدم
        if blue > red:

            return (
                "⚠️ *ركلة حاسمة للبطولة!* "
                f"إذا سجلها *{shooter_name}*، "
                "يفوز *🔵 الفريق الأزرق* باللقب! 🏆"
            )

    # ==================================================
    # الركلات الحاسمة بعد التعادل
    # ==================================================

    if game["kick_number"] > 10:

        if team == "red":

            if red < blue:

                return (
                    "⚠️ *ضغوط هائلة!* "
                    f"يجب على *{shooter_name}* التسجيل للاستمرار، "
                    f"إذا ضاعت أو صدها الحارس *{goalie_name}* "
                    "يفوز *🔵 الفريق الأزرق* باللقب! 🏆"
                )

            if red > blue:

                return (
                    "⚠️ *ركلة حاسمة للبطولة!* "
                    f"إذا سجلها *{shooter_name}*، "
                    "يفوز *🔴 الفريق الأحمر* باللقب! 🏆"
                )

        else:

            if blue < red:

                return (
                    "⚠️ *ضغوط هائلة!* "
                    f"يجب على *{shooter_name}* التسجيل للاستمرار، "
                    f"إذا ضاعت أو صدها الحارس *{goalie_name}* "
                    "يفوز *🔴 الفريق الأحمر* باللقب! 🏆"
                )

            if blue > red:

                return (
                    "⚠️ *ركلة حاسمة للبطولة!* "
                    f"إذا سجلها *{shooter_name}*، "
                    "يفوز *🔵 الفريق الأزرق* باللقب! 🏆"
                )

    return None
    
# ==================================================
# بدء الركلة
# ==================================================

async def start_kick(
    context,
    chat_id
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "shootout":
        return

    team = game["current_team"]

    goalie_team = (
        "blue"
        if team == "red"
        else "red"
    )

    shooter_id = next_shooter(
        game,
        team
    )

    goalie_id = next_goalie(
        game,
        goalie_team
    )

    game["current_shooter"] = shooter_id
    game["current_goalie"] = goalie_id

    game["shooter_choice"] = None
    game["goalie_choice"] = None

    game["shooter_ready"] = False
    game["goalie_ready"] = False

    game["resolving"] = False
    game["ready_message_id"] = None

    shooter_task = asyncio.create_task(
        choice_timeout(
            context,
            chat_id,
            "shooter"
        )
    )

    goalie_task = asyncio.create_task(
        choice_timeout(
            context,
            chat_id,
            "goalie"
        )
    )

    game["shooter_task"] = shooter_task
    game["goalie_task"] = goalie_task

    await send_ready_image(
        context,
        chat_id,
        goalie_team
    )

    # تحذير الركلة الحاسمة يظهر مع بداية الركلة
    warning = get_kick_warning(game)

    if warning:

        try:

            await context.bot.send_message(
                chat_id=chat_id,
                text=warning
            )

        except Exception:
            pass


# ==================================================
# صورة استعداد الحارس
# ==================================================

async def send_ready_image(
    context,
    chat_id,
    goalie_team
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    file_id = READY_IMAGES.get(goalie_team)

    if not file_id:
        return

    team = game["current_team"]

    shooter = game["players"].get(
        game["current_shooter"]
    )

    goalie = game["players"].get(
        game["current_goalie"]
    )

    shooter_status = (
        "✅ جاهز"
        if game["shooter_ready"]
        else
        "⏳ ينتظر الاختيار"
    )

    goalie_status = (
        "✅ جاهز"
        if game["goalie_ready"]
        else
        "⏳ ينتظر الاختيار"
    )

    # ==================================================
    # اسم الجولة
    # ==================================================

    if game["kick_number"] <= 2:
        round_number = 1
    elif game["kick_number"] <= 4:
        round_number = 2
    elif game["kick_number"] <= 6:
        round_number = 3
    elif game["kick_number"] <= 8:
        round_number = 4
    elif game["kick_number"] <= 10:
        round_number = 5
    else:
        round_number = (
            (game["kick_number"] - 1) // 2
        )

    # ==================================================
    # أول / ثاني ركلة في الجولة
    # ==================================================

    if game["kick_number"] % 2 == 1:
        kick_name = "الركلة الأولى"
    else:
        kick_name = "الركلة الثانية"

    caption = (
        f"🎮 *الجولة {round_number} — {kick_name} "
        f"{'🔴' if team == 'red' else '🔵'}*\n\n"
        f"🎯 المسدد: *{get_player_name(shooter)}* "
        f"{'🔴' if team == 'red' else '🔵'} "
        f"({shooter_status})\n"
        f"🛡️ الحارس: *{get_player_name(goalie)}* "
        f"{'🔵' if goalie_team == 'blue' else '🔴'} "
        f"({goalie_status})\n\n"
    )

    # ==================================================
    # التحذير
    # ==================================================

    warning = get_kick_warning(game)

    if warning:
        caption += warning + "\n\n"

    caption += (
        "اختر الزاوية من الأزرار بالأسفل:"
    )

    message = await context.bot.send_photo(
        chat_id=chat_id,
        photo=file_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=direction_keyboard(chat_id)
    )

    game["ready_message_id"] = message.message_id


async def update_ready_message(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    message_id = game.get("ready_message_id")

    if not message_id:
        return

    team = game["current_team"]

    shooter = game["players"].get(
        game["current_shooter"]
    )

    goalie = game["players"].get(
        game["current_goalie"]
    )

    if not shooter or not goalie:
        return

    shooter_status = (
        "✅ جاهز"
        if game["shooter_ready"]
        else "⏳ ينتظر الاختيار"
    )

    goalie_status = (
        "✅ جاهز"
        if game["goalie_ready"]
        else "⏳ ينتظر الاختيار"
    )

    round_number = (
        (game["kick_number"] + 1) // 2
    )

    if game["kick_number"] % 2 == 1:
        kick_name = "الركلة الأولى"
    else:
        kick_name = "الركلة الثانية"

    shooter_color = (
        "🔴"
        if team == "red"
        else "🔵"
    )

    goalie_color = (
        "🔵"
        if team == "red"
        else "🔴"
    )

    caption = (
        f"🎮 *الجولة {round_number} — {kick_name} "
        f"{shooter_color}*\n\n"

        f"🎯 المسدد: *{get_player_name(shooter)}* "
        f"{shooter_color} "
        f"({shooter_status})\n"

        f"🛡️ الحارس: *{get_player_name(goalie)}* "
        f"{goalie_color} "
        f"({goalie_status})\n\n"
    )

    # رسالة الضغط / الركلة الحاسمة
    warning = get_kick_warning(game)

    if warning:
        caption += warning + "\n\n"

    caption += (
        "اختر الزاوية من الأزرار بالأسفل:"
    )

    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=direction_keyboard(chat_id)
        )

    except Exception:
        pass

# ==================================================
# ضغط اتجاه
# ==================================================

async def penalty_direction_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    try:

        _, _, chat_id_text, direction = query.data.split(":")

        chat_id = int(chat_id_text)

    except Exception:

        await query.answer()

        return

    game = active_penalty_games.get(chat_id)

    if not game:

        await query.answer(
            "❌ انتهت المباراة.",
            show_alert=True
        )

        return

    if game["phase"] != "shootout":

        await query.answer(
            "❌ لا توجد ركلة حالية.",
            show_alert=True
        )

        return

    user_id = query.from_user.id

    shooter_id = game["current_shooter"]
    goalie_id = game["current_goalie"]

    if user_id not in game["players"]:

        await query.answer(
            "❌ انت مو بالقيم اصلا!",
            show_alert=True
        )

        return

    if user_id != shooter_id and user_id != goalie_id:

        await query.answer(
            "❌ انتظر، ليس دورك!",
            show_alert=True
        )

        return

    if user_id == shooter_id:

        if game["shooter_choice"] is not None:

            await query.answer(
                "❌ اخترت اتجاهك بالفعل.",
                show_alert=True
            )

            return

        game["shooter_choice"] = direction
        game["shooter_ready"] = True

        await update_ready_message(
    
            context,
            chat_id
        )
        task = game.get("shooter_task")

        if task:
            task.cancel()

        game["shooter_task"] = None

        await query.answer(
            "✅ تم تسجيل اختيارك."
        )

    elif user_id == goalie_id:

        if game["goalie_choice"] is not None:

            await query.answer(
                "❌ اخترت اتجاهك بالفعل.",
                show_alert=True
            )

            return

        game["goalie_choice"] = direction
        game["goalie_ready"] = True

        await update_ready_message(
    
            context,
            chat_id
        )
        task = game.get("goalie_task")

        if task:
            task.cancel()

        game["goalie_task"] = None

        await query.answer(
            "✅ تم تسجيل اختيارك."
        )

    if (
        game["shooter_choice"] is not None
        and game["goalie_choice"] is not None
    ):

        if game["resolving"]:
            return

        game["resolving"] = True

        await resolve_kick(
            context,
            chat_id
        )


# ==================================================
# تحديث حالة الاختيار
# ==================================================

async def update_kick_status(
    context,
    chat_id
):

    # الحالة تعرض في رسالة جديدة عند بدء الركلة.
    # النتائج نفسها تعتمد على الاختيارات المخزنة.
    return


# ==================================================
# مؤقت الاختيار
# ==================================================

async def choice_timeout(
    context,
    chat_id,
    role
):

    try:
        await asyncio.sleep(TURN_TIME)

    except asyncio.CancelledError:
        return

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "shootout":
        return

    # ==================================================
    # إذا انتهى وقت المسدد ولم يختر
    # ==================================================

    if role == "shooter":

        if game["shooter_choice"] is None:

            game["shooter_choice"] = "وسط"
            game["shooter_ready"] = True

    # ==================================================
    # إذا انتهى وقت الحارس ولم يختر
    # ==================================================

    elif role == "goalie":

        if game["goalie_choice"] is None:

            game["goalie_choice"] = "وسط"
            game["goalie_ready"] = True

    # ==================================================
    # تحديث الكابشن
    # ==================================================

    await update_ready_message(
        context,
        chat_id
    )

    # ==================================================
    # إذا الاثنين اختاروا / انتهى وقتهم
    # يتم حسم الركلة
    # ==================================================

    if (
        game["shooter_choice"] is not None
        and game["goalie_choice"] is not None
    ):

        if game.get("resolving"):
            return

        game["resolving"] = True

        await resolve_kick(
            context,
            chat_id
        )
    


# ==================================================
# إلغاء المؤقتات
# ==================================================

def cancel_kick_tasks(game):

    for key in (
        "shooter_task",
        "goalie_task"
    ):

        task = game.get(key)

        if task:

            task.cancel()

        game[key] = None


# ==================================================
# نتيجة الركلة
# ==================================================


async def penalty_direction_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    try:
        _, _, chat_id_text, direction = query.data.split(":")
        chat_id = int(chat_id_text)
    except Exception:
        await query.answer()
        return
    game = active_penalty_games.get(chat_id)
    if not game:
        await query.answer(
            "❌ انتهت المباراة.",
            show_alert=True
        )
        return
    if game["phase"] != "shootout":
        await query.answer(
            "❌ لا توجد ركلة حالية.",
            show_alert=True
        )
        return
    user_id = query.from_user.id
    shooter_id = game["current_shooter"]
    goalie_id = game["current_goalie"]
    if user_id not in game["players"]:
        await query.answer(
            "❌ انت مو بالقيم اصلا!",
            show_alert=True
        )
        return
    if user_id != shooter_id and user_id != goalie_id:
        await query.answer(
            "❌ انتظر، ليس دورك!",
            show_alert=True
        )
        return
    # ==========================================
    # اختيار المسدد
    # ==========================================
    if user_id == shooter_id:
        if game["shooter_choice"] is not None:
            await query.answer(
                "❌ اخترت اتجاهك بالفعل.",
                show_alert=True
            )
            return
        game["shooter_choice"] = direction
        game["shooter_ready"] = True
        task = game.get("shooter_task")
        if task:
            task.cancel()
        game["shooter_task"] = None
        await update_ready_message(
            context,
            chat_id
        )
        await query.answer(
            "✅ تم تسجيل اختيارك."
        )
    # ==========================================
    # اختيار الحارس
    # ==========================================
    elif user_id == goalie_id:
        if game["goalie_choice"] is not None:
            await query.answer(
                "❌ اخترت اتجاهك بالفعل.",
                show_alert=True
            )
            return
        game["goalie_choice"] = direction
        game["goalie_ready"] = True
        task = game.get("goalie_task")
        if task:
            task.cancel()
        game["goalie_task"] = None
        await update_ready_message(
            context,
            chat_id
        )
        await query.answer(
            "✅ تم تسجيل اختيارك."
        )
    # ==========================================
    # الاثنين اختاروا
    # ==========================================
    if (
        game["shooter_choice"] is not None
        and game["goalie_choice"] is not None
    ):
        if game["resolving"]:
            return
        game["resolving"] = True
        await resolve_kick(
            context,
            chat_id
        )


async def resolve_kick(
    context,
    chat_id
):
    game = active_penalty_games.get(chat_id)
    if not game:
        return
    if game["phase"] != "shootout":
        return
    # ==========================================
    # أي شخص ما اختار = وسط
    # ==========================================
    if game.get("shooter_choice") is None:
        game["shooter_choice"] = "وسط"
    if game.get("goalie_choice") is None:
        game["goalie_choice"] = "وسط"
    game["shooter_ready"] = True
    game["goalie_ready"] = True
    shooter_choice = game["shooter_choice"]
    goalie_choice = game["goalie_choice"]
    # ==========================================
    # منع التكرار
    # ==========================================
    if game.get("resolving") is False:
        game["resolving"] = True
    cancel_kick_tasks(game)
    shooter_id = game["current_shooter"]
    goalie_id = game["current_goalie"]
    shooter = game["players"].get(shooter_id)
    goalie = game["players"].get(goalie_id)
    if not shooter or not goalie:
        game["resolving"] = False
        return
    shooting_team = game["current_team"]
    goalie_team = (
        "blue"
        if shooting_team == "red"
        else "red"
    )
    # ==========================================
    # تحديد الهدف
    # ==========================================
    goal = shooter_choice != goalie_choice
    if goal:
        game["score"][shooting_team] += 1
    # ==========================================
    # رسالة التشويق
    # ==========================================
    teaser = await context.bot.send_message(
        chat_id=chat_id,
        text="هل يسجلها المسدد؟ ام يصدها الحارس…🧤🔥"
    )
    await asyncio.sleep(5)
    try:
        await teaser.delete()
    except Exception:
        pass
    # ==========================================
    # صورة النتيجة
    # ==========================================
    image_id = RESULT_IMAGES.get(
        (
            goalie_team,
            goalie_choice,
            shooter_choice
        )
    )
    # ==========================================
    # كابشن الهدف
    # ==========================================
    if goal:
        team_name = (
            "الأحمر 🔴"
            if shooting_team == "red"
            else
            "الأزرق 🔵"
        )
        text = (
            f"⚽ قوووول!! هدف لصالح "
            f"{get_player_name(shooter)} "
            f"(فريق {team_name}) 🔥\n\n"
            f"🎯 المسدد سدد في "
            f"{shooter_choice} "
            f"{DIRECTIONS[shooter_choice]} "
            f"والحارس ارتمى إلى "
            f"{goalie_choice} "
            f"{DIRECTIONS[goalie_choice]}!\n\n"
            f"📊 النتيجة: "
            f"🔴 الأحمر {game['score']['red']} "
            f"- {game['score']['blue']} الأزرق 🔵"
        )
    # ==========================================
    # كابشن التصدي
    # ==========================================
    else:
        goalie_team_name = (
            "الأحمر 🔴"
            if goalie_team == "red"
            else
            "الأزرق 🔵"
        )
        text = (
            "🧤 ياساتر صدها الحارس! مستحييل! 💥\n\n"
            f"🛡️ الحارس {get_player_name(goalie)} "
            f"(فريق {goalie_team_name}) "
            f"تصدى للكرة في "
            f"{goalie_choice} "
            f"{DIRECTIONS[goalie_choice]}!\n\n"
            f"📊 النتيجة: "
            f"🔴 الأحمر {game['score']['red']} "
            f"- {game['score']['blue']} الأزرق 🔵"
        )
    # ==========================================
    # إرسال صورة النتيجة
    # ==========================================
    if image_id:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image_id,
                caption=text
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text
        )
    # ==========================================
    # فحص نهاية المباراة
    # ==========================================
    winner = get_winner_if_finished(game)
    if winner:
        await finish_penalty_game(
            context,
            chat_id,
            winner
        )
        return
    # ==========================================
    # الركلة انتهت
    # ==========================================
    game["resolving"] = False
    await context.bot.send_message(
        chat_id=chat_id,
        text="⏸️ اكتب .كمل للركلة التالية."
    )


# ==================================================
# تحديد الفائز حسب نظام الركلات الحقيقي
# ==================================================

def get_winner_if_finished(game):

    red = game["score"]["red"]
    blue = game["score"]["blue"]

    kick_number = game["kick_number"]

    # ==================================================
    # تحديد عدد الركلات المكتملة
    #
    # 1 = الأحمر 1
    # 2 = الأزرق 1
    # 3 = الأحمر 2
    # 4 = الأزرق 2
    # 5 = الأحمر 3
    # 6 = الأزرق 3
    # 7 = الأحمر 4
    # 8 = الأزرق 4
    # 9 = الأحمر 5
    # 10 = الأزرق 5
    # ==================================================

    if kick_number % 2 == 1:

        # الركلة الحالية للأحمر
        red_kicks = (kick_number - 1) // 2
        blue_kicks = (kick_number - 1) // 2

    else:

        # الركلة الحالية للأزرق
        red_kicks = kick_number // 2
        blue_kicks = (kick_number // 2) - 1

    # ==================================================
    # بعد الركلة الخامسة للأحمر
    # لا نحسم المباراة لأن الأزرق لم يسدد الخامسة بعد
    # ==================================================

    if red_kicks < 5 or blue_kicks < 5:
        return None

    # ==================================================
    # كل فريق سدد 5 ركلات
    # ==================================================

    if red != blue:

        return (
            "red"
            if red > blue
            else "blue"
        )

    # ==================================================
    # تعادل بعد 5 ركلات
    # → ركلات حاسمة Sudden Death
    # ==================================================

    return None


# ==================================================
# .كمل
# ==================================================

async def continue_penalties(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] != "shootout":
        return

    if game["resolving"]:

        await update.message.reply_text(
            "⏳ انتظر حتى تنتهي الركلة الحالية."
        )

        return

    # يجب أن تكون الركلة السابقة منتهية
    if (
        game["shooter_choice"] is None
        or game["goalie_choice"] is None
    ):

        await update.message.reply_text(
            "❌ الركلة الحالية لم تنتهِ بعد."
        )

        return

    # الفائز لو كانت المباراة انتهت
    winner = get_winner_if_finished(game)

    if winner:

        await finish_penalty_game(
            context,
            chat_id,
            winner
        )

        return

    # الجولة التالية
    game["kick_number"] += 1

    # أحمر ثم أزرق دائمًا
    game["current_team"] = (
        "blue"
        if game["current_team"] == "red"
        else "red"
    )

    await start_kick(
        context,
        chat_id
    )


# ==================================================
# إنهاء المباراة يدويًا
# ==================================================

async def end_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    cancel_kick_tasks(game)

    active_penalty_games.pop(
        chat_id,
        None
    )

    await update.message.reply_text(
        "🛑 تم إنهاء مباراة البلنتيات."
    )


# ==================================================
# إنهاء المباراة + الجوائز
# ==================================================

async def finish_penalty_game(
    context,
    chat_id,
    winner
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] == "finished":
        return

    game["phase"] = "finished"

    cancel_kick_tasks(game)

    loser = (
        "blue"
        if winner == "red"
        else "red"
    )

    winner_name = (
        "🔴 الفريق الأحمر"
        if winner == "red"
        else
        "🔵 الفريق الأزرق"
    )

    text = (
        "🏆 انتهت مباراة البلنتيات! 🏆\n\n"
        f"🎉 الفائز: {winner_name}!\n\n"
        f"النتيجة النهائية: "
        f"🔴 الأحمر {game['score']['red']} "
        f"- {game['score']['blue']} الأزرق 🔵"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )

    # ==================================================
    # الجوائز - رسالة واحدة لكل الفريق الفائز
    # ==================================================

        winners = list(dict.fromkeys(
            game[winner]["shooters"]
            + game[winner]["goalies"]
        ))

        reward_lines = [
          "✨ جوائز الفريق الفائز: ✨"
        ]

        for player_id in winners:

            player = game["players"].get(player_id)

            if not player:
                continue

            try:
                add_points(
                    player_id,
                    WIN_POINTS
                )

                reward_lines.append(
                    f"• {get_player_name(player)} — "
                    f"حصل على {WIN_POINTS} نقطة! 🎖️"
                )

            except Exception as e:

                print(
                    f"❌ خطأ في إضافة النقاط للاعب "
                    f"{player_id}: {e}"
                )

                # حتى لو فشلت إضافة النقاط
                # لا نوقف رسالة النهاية
                reward_lines.append(
                    f"• {get_player_name(player)} — "
                    f"حصل على {WIN_POINTS} نقطة! 🎖️"
                )

        # ==================================================
        # إرسال جوائز الفريق الفائز
        # ==================================================

        try:

            await context.bot.send_message(
                chat_id=chat_id,
                text="\n".join(reward_lines)
            )

        except Exception as e:

            print(
                f"❌ خطأ في إرسال رسالة الجوائز: {e}"
            )

        # ==================================================
        # حذف اللعبة
        # ==================================================

        active_penalty_games.pop(
            chat_id,
            None
        )
