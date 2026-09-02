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
# الإعدادات
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
# ==================================================

RESULT_IMAGES = {

    # =========================
    # الحارس الأحمر
    # =========================

    ("red", "يسار", "يسار"):
        "AgACAgQAAxkBAAIC2mqXXi2MCyP1bavd0hR1Z7qzHoCAAAJ0EmsbkuPAUKVIWnY0MYkOAQADAgADeQADPQQ",

    ("red", "يسار", "وسط"):
        "AgACAgQAAxkBAAIC5GqXXw7IjhzegXCjpRcxZwqjVS6WAAJ5EmsbkuPAUFp8zcXUDTg5AQADAgADeQADPQQ",

    ("red", "يسار", "يمين"):
        "AgACAgQAAxkBAAIC2GqXXd6JOsmKg6XY4QmjioYpY6JBAAJzEmsbkuPAUN2RFOQM76ZjAQADAgADeQADPQQ",

    ("red", "وسط", "يسار"):
        "AgACAgQAAxkBAAIC4GqXXq47KtcOgOu_X2FaUbKinv5bAAJ3EmsbkuPAUM6TlGij3IEHAQADAgADeQADPQQ",

    ("red", "وسط", "وسط"):
        "AgACAgQAAxkBAAIC1mqXXaAJP0tj2fHk37IEYyLojq8-AAJyEmsbkuPAUMnwQohZeWMRAQADAgADeQADPQQ",

    ("red", "وسط", "يمين"):
        "AgACAgQAAxkBAAIC3GqXXk_YkocGUIQQLrUjVUsT6WFJAAJ1EmsbkuPAUKlvrIEsTFKiAQADAgADeQADPQQ",

    ("red", "يمين", "يسار"):
        "AgACAgQAAxkBAAIC4mqXXuc962m3PinFC3de9Cnd0yn9AAJ4EmsbkuPAUPPtWgmjylC3AQADAgADeQADPQQ",

    ("red", "يمين", "وسط"):
        "AgACAgQAAxkBAAIC3mqXXm9DsfMF7RKuGnjX0DZZCDElAAJ2EmsbkuPAUGcJXuHpNXeRAQADAgADeQADPQQ",

    ("red", "يمين", "يمين"):
        "AgACAgQAAyEFAATwGwEUAAJP-2qXQ8T5AtOCk6Tgh_lxF3uj8CLbAAIhE2sbtou5UESSt8Vei3-fAQADAgADeQADPQQ",


    # =========================
    # الحارس الأزرق
    # =========================

    ("blue", "يسار", "يسار"):
        "AgACAgQAAxkBAAIC5mqXX1YLbKkPxyFAuXt4GIyWpwr0AAJ6EmsbkuPAUJauXBMfrdsmAQADAgADeQADPQQ",

    ("blue", "يسار", "وسط"):
        "AgACAgQAAxkBAAIC-2qXY5T0b_X374-vZzZGl0HLQEEYAAKIEmsbkuPAUFT-iD8IXTJ6AQADAgADeQADPQQ",

    ("blue", "يسار", "يمين"):
        "AgACAgQAAxkBAAIC6mqXX5umjMZgl8QvHQ9cWVE7OBkrAAJ8EmsbkuPAUETvi9lxwAABoAEAAwIAA3kAAz0E",

    ("blue", "وسط", "يسار"):
        "AgACAgQAAxkBAAIC8mqXYJiHXfglNwRGoIhIfxfC8bjdAAKCEmsbkuPAUGkJ2VH7L0tAAQADAgADeQADPQQ",

    ("blue", "وسط", "وسط"):
        "AgACAgQAAxkBAAIC8GqXYHN9_lRYWV7MQ-2ViZNxESDxAAKAEmsbkuPAUBIAAa6Cdmoz2AEAAwIAA3kAAz0E",

    ("blue", "وسط", "يمين"):
        "AgACAgQAAxkBAAIC9GqXYNPEKxVz0lKOSKIvI8jMwlTPAAKFEmsbkuPAUMilU52EcjlsAQADAgADeQADPQQ",

    ("blue", "يمين", "يسار"):
        "AgACAgQAAxkBAAIC6GqXX3Rokn49gwNhssRA_Jr5Mim6AAJ7EmsbkuPAUBloAjhQo03mAQADAgADeQADPQQ",

    ("blue", "يمين", "وسط"):
        "AgACAgQAAxkBAAIC7GqXX81g1Ntcm7CbDJFBr4XBTj0nAAJ9EmsbkuPAUC1szPgbscpJAQADAgADeQADPQQ",

    ("blue", "يمين", "يمين"):
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
# اسم اللاعب
# ==================================================

def get_player_name(user):
    if not user:
        return "مستخدم"

    return user.full_name or user.first_name or "مستخدم"


# ==================================================
# الصلاحيات
# ==================================================

def can_manage_penalties(user_id):
    return get_rank_level(user_id) > 0


# ==================================================
# لوحة الاتجاهات
# ==================================================

def direction_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"يسار {DIRECTIONS['يسار']}",
                callback_data=f"penalty:{chat_id}:يسار"
            ),
            InlineKeyboardButton(
                f"وسط {DIRECTIONS['وسط']}",
                callback_data=f"penalty:{chat_id}:وسط"
            ),
            InlineKeyboardButton(
                f"يمين {DIRECTIONS['يمين']}",
                callback_data=f"penalty:{chat_id}:يمين"
            ),
        ]
    ])


# ==================================================
# رسالة حالة الركلة
# ==================================================

def build_kick_status(game):
    team = game["current_team"]
    goalie_team = "blue" if team == "red" else "red"

    shooter = game["players"].get(game["current_shooter"])
    goalie = game["players"].get(game["current_goalie"])

    shooter_emoji = "🔴" if team == "red" else "🔵"
    goalie_emoji = "🔵" if goalie_team == "blue" else "🔴"

    kick_word = (
        "الأولى"
        if game["kick_number"] == 1
        else "التالية"
    )

    shooter_status = (
        "✅ جاهز"
        if game["shooter_choice"] is not None
        else "⏳ ينتظر الاختيار"
    )

    goalie_status = (
        "✅ جاهز"
        if game["goalie_choice"] is not None
        else "⏳ ينتظر الاختيار"
    )

    return (
        f"🎮 الجولة {game['kick_number']} — الركلة {kick_word} {shooter_emoji}\n\n"
        f"🎯 المسدد: {get_player_name(shooter)} {shooter_emoji} ({shooter_status})\n"
        f"🛡️ الحارس: {get_player_name(goalie)} {goalie_emoji} ({goalie_status})\n\n"
        "اختر الزاوية من الأزرار بالأسفل:"
    )


# ==================================================
# تحديث رسالة الركلة نفسها
# ==================================================

async def update_kick_status(context, chat_id):
    game = active_penalty_games.get(chat_id)

    if not game:
        return

    message_id = game.get("kick_message_id")

    if not message_id:
        return

    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=build_kick_status(game),
            reply_markup=direction_keyboard(chat_id)
        )
    except Exception:
        pass


# ==================================================
# صورة الاستعداد
# ==================================================

async def send_ready_image(
    context,
    chat_id,
    goalie_team,
    caption=None,
    reply_markup=None
):
    file_id = READY_IMAGES.get(goalie_team)

    if not file_id:
        return None

    try:
        return await context.bot.send_photo(
            chat_id=chat_id,
            photo=file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    except Exception:
        return None


# ==================================================
# بداية المباراة
# ==================================================

async def start_penalty_game(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id in active_penalty_games:
        await update.message.reply_text(
            "• فيه مباراة بلنتيات شغالة بالفعل."
        )
        return

    active_penalty_games[chat_id] = {
        "players": {},
        "order": [],

        "phase": "registration",

        "red_shooters": [],
        "blue_shooters": [],

        "red_goalies": [],
        "blue_goalies": [],

        "red_shooter_index": 0,
        "blue_shooter_index": 0,

        "red_goalie_index": 0,
        "blue_goalie_index": 0,

        "red_score": 0,
        "blue_score": 0,

        "kick_number": 1,
        "current_team": "red",

        "current_shooter": None,
        "current_goalie": None,

        "shooter_choice": None,
        "goalie_choice": None,

        "shooter_ready": False,
        "goalie_ready": False,

        "shooter_task": None,
        "goalie_task": None,

        "kick_message_id": None,

        "resolving": False,

        "manual_message_id": None,

        "used_players": set(),
    }

    await update.message.reply_text(
        "⚽ *مباراة البلنتيات بدأت!*\n\n"
        "اكتب *دخول* للانضمام إلى المباراة.",
        parse_mode="Markdown"
    )


# ==================================================
# دخول لاعب
# ==================================================

async def join_penalty_game(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "registration":
        return

    if user.id in game["players"]:
        return

    game["players"][user.id] = user
    game["order"].append(user.id)

    await update.message.reply_text(
        f"انضم {get_player_name(user)} ⚽ "
        f"(العدد: {len(game['players'])})"
    )


# ==================================================
# توزيع الفرق
# ==================================================

async def distribute_penalties(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
            "• لازم يدخل لاعبين على الأقل."
        )
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "يدوي",
                callback_data=f"penalty_dist:{chat_id}:manual"
            ),
            InlineKeyboardButton(
                "عشوائي",
                callback_data=f"penalty_dist:{chat_id}:random"
            ),
        ]
    ])

    await update.message.reply_text(
        "🛡️ توزيع فرق مباراة البلنتيات (أحمر ضد أزرق)\n"
        f"يا {get_player_name(user)}، كيف تبي نوزّع اللاعبين؟",
        reply_markup=keyboard
    )


# ==================================================
# Callback التوزيع
# ==================================================

async def distribution_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data.split(":")

    if len(data) < 3:
        return

    chat_id = int(data[1])
    mode = data[2]

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    await query.edit_message_reply_markup(reply_markup=None)

    if mode == "manual":
        await show_manual_distribution(context, chat_id)

    elif mode == "random":
        await make_random_teams(context, chat_id)


# ==================================================
# التوزيع العشوائي
# ==================================================

async def make_random_teams(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    ids = list(game["order"])
    random.shuffle(ids)

    count = len(ids)

    game["red_shooters"] = []
    game["blue_shooters"] = []
    game["red_goalies"] = []
    game["blue_goalies"] = []

    if count == 2:

        game["red_shooters"] = [ids[0]]
        game["blue_shooters"] = [ids[1]]

        game["red_goalies"] = [ids[0]]
        game["blue_goalies"] = [ids[1]]

    else:

        red_count = (count + 1) // 2

        red_players = ids[:red_count]
        blue_players = ids[red_count:]

        game["red_shooters"] = red_players.copy()
        game["blue_shooters"] = blue_players.copy()

        game["red_goalies"] = red_players[:max(1, len(red_players) // 3)]
        game["blue_goalies"] = blue_players[:max(1, len(blue_players) // 3)]

        if not game["red_goalies"]:
            game["red_goalies"] = [red_players[0]]

        if not game["blue_goalies"]:
            game["blue_goalies"] = [blue_players[0]]

    await send_distribution_result(context, chat_id)


# ==================================================
# التوزيع اليدوي
# ==================================================

async def show_manual_distribution(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    game["phase"] = "manual"

    text = (
        "🛡️ *التوزيع اليدوي*\n\n"
        "استخدم الأوامر التالية:\n\n"
        "`.أحمر رقم`\n"
        "`.أزرق رقم`\n"
        "`.حارس أحمر رقم`\n"
        "`.حارس أزرق رقم`\n\n"
        "مثال:\n"
        "`.أحمر 1`"
    )

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown"
    )

    game["manual_message_id"] = message.message_id


# ==================================================
# الحصول على اللاعب بالرقم
# ==================================================

def get_player_by_number(game, number):

    try:
        number = int(number)
    except Exception:
        return None

    if number < 1 or number > len(game["order"]):
        return None

    player_id = game["order"][number - 1]

    return player_id


# ==================================================
# الأمر اليدوي
# ==================================================

async def manual_team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] != "manual":
        return

    text = update.message.text.strip()

    parts = text.split()

    if len(parts) < 2:
        return

    command = parts[0]
    number = parts[-1]

    player_id = get_player_by_number(game, number)

    if not player_id:
        await update.message.reply_text(
            "• رقم اللاعب غير صحيح."
        )
        return

    if command == ".أحمر":
        if player_id not in game["red_shooters"]:
            game["red_shooters"].append(player_id)

    elif command == ".أزرق":
        if player_id not in game["blue_shooters"]:
            game["blue_shooters"].append(player_id)

    elif command == ".حارس":
        return

    elif command == ".حارس_أحمر":
        if player_id not in game["red_goalies"]:
            game["red_goalies"].append(player_id)

    elif command == ".حارس_أزرق":
        if player_id not in game["blue_goalies"]:
            game["blue_goalies"].append(player_id)

    else:
        return

    await show_manual_status(context, chat_id)
    await check_manual_completion(context, chat_id)


# ==================================================
# حالة التوزيع اليدوي
# ==================================================

async def show_manual_status(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    def names(ids):
        return ", ".join(
            get_player_name(game["players"].get(pid))
            for pid in ids
        ) or "لا يوجد"

    text = (
        "🛡️ *التوزيع الحالي*\n\n"
        f"🔴 لاعبو الأحمر:\n{names(game['red_shooters'])}\n\n"
        f"🔵 لاعبو الأزرق:\n{names(game['blue_shooters'])}\n\n"
        f"🧤 حراس الأحمر:\n{names(game['red_goalies'])}\n\n"
        f"🧤 حراس الأزرق:\n{names(game['blue_goalies'])}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown"
    )


# ==================================================
# فحص اكتمال التوزيع
# ==================================================

async def check_manual_completion(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not game["red_shooters"]:
        return

    if not game["blue_shooters"]:
        return

    if not game["red_goalies"]:
        return

    if not game["blue_goalies"]:
        return

    await send_distribution_result(context, chat_id)


# ==================================================
# إرسال نتيجة التوزيع
# ==================================================

async def send_distribution_result(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    game["phase"] = "shootout"

    def names(ids):
        return ", ".join(
            get_player_name(game["players"].get(pid))
            for pid in ids
        ) or "لا يوجد"

    text = (
        "🛡️ *تم توزيع الفرق!*\n\n"
        f"🔴 *الفريق الأحمر*\n"
        f"🎯 المسددون: {names(game['red_shooters'])}\n"
        f"🧤 الحراس: {names(game['red_goalies'])}\n\n"
        f"🔵 *الفريق الأزرق*\n"
        f"🎯 المسددون: {names(game['blue_shooters'])}\n"
        f"🧤 الحراس: {names(game['blue_goalies'])}\n\n"
        "⚽ تبدأ المباراة الآن!"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown"
    )

    await begin_penalties(context, chat_id)


# ==================================================
# بداية البلنتيات
# ==================================================

async def begin_penalties(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    game["phase"] = "shootout"
    game["kick_number"] = 1
    game["current_team"] = "red"

    await next_shooter(context, chat_id)


# ==================================================
# الحصول على المسدد
# ==================================================

def next_shooter(game, team):

    if team == "red":
        shooters = game["red_shooters"]
        index = game["red_shooter_index"]

        if not shooters:
            return None

        player_id = shooters[index % len(shooters)]
        game["red_shooter_index"] += 1

        return player_id

    shooters = game["blue_shooters"]
    index = game["blue_shooter_index"]

    if not shooters:
        return None

    player_id = shooters[index % len(shooters)]
    game["blue_shooter_index"] += 1

    return player_id


# ==================================================
# الحصول على الحارس
# ==================================================

def next_goalie(game, team):

    if team == "red":
        goalies = game["red_goalies"]
        index = game["red_goalie_index"]

        if not goalies:
            return None

        player_id = goalies[index % len(goalies)]
        game["red_goalie_index"] += 1

        return player_id

    goalies = game["blue_goalies"]
    index = game["blue_goalie_index"]

    if not goalies:
        return None

    player_id = goalies[index % len(goalies)]
    game["blue_goalie_index"] += 1

    return player_id


# ==================================================
# بدء الركلة
# ==================================================

async def start_kick(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "shootout":
        return

    team = game["current_team"]
    goalie_team = "blue" if team == "red" else "red"

    shooter_id = next_shooter(game, team)
    goalie_id = next_goalie(game, goalie_team)

    game["current_shooter"] = shooter_id
    game["current_goalie"] = goalie_id

    game["shooter_choice"] = None
    game["goalie_choice"] = None

    game["shooter_ready"] = False
    game["goalie_ready"] = False

    game["resolving"] = False
    game["kick_message_id"] = None

    caption = build_kick_status(game)

    message = await send_ready_image(
        context,
        chat_id,
        goalie_team,
        caption=caption,
        reply_markup=direction_keyboard(chat_id)
    )

    if message:
        game["kick_message_id"] = message.message_id

    game["shooter_task"] = asyncio.create_task(
        choice_timeout(context, chat_id, "shooter")
    )

    game["goalie_task"] = asyncio.create_task(
        choice_timeout(context, chat_id, "goalie")
    )


# ==================================================
# تحذير الركلة
# ==================================================

def get_kick_warning(game):

    red_score = game["red_score"]
    blue_score = game["blue_score"]

    team = game["current_team"]
    kick_number = game["kick_number"]

    # ==============================================
    # الركلات الخمس الأولى
    # ==============================================

    if kick_number <= 10:

        if team == "red":

            red_kicks = (kick_number + 1) // 2
            blue_kicks = kick_number // 2

            blue_remaining = max(0, 5 - blue_kicks)
            red_remaining_after = max(0, 5 - red_kicks)

            # إذا سجل الأحمر الآن يصبح غير قابل للحاق
            if red_score + 1 > blue_score + blue_remaining:
                shooter = game["players"].get(game["current_shooter"])

                return (
                    "⚠️ ركلة حاسمة للبطولة!\n"
                    f"إذا سجلها {get_player_name(shooter)}، "
                    "يفوز 🔴 الفريق الأحمر باللقب! 🏆"
                )

            # إذا كان الأحمر متأخرًا ومضيعة هذه الركلة تنهي المباراة
            if (
                red_score < blue_score
                and red_score + red_remaining_after < blue_score
            ):
                shooter = game["players"].get(game["current_shooter"])
                goalie = game["players"].get(game["current_goalie"])

                return (
                    "⚠️ ضغوط هائلة!\n"
                    f"يجب على {get_player_name(shooter)} التسجيل للاستمرار، "
                    f"إذا ضاعت أو صدها الحارس {get_player_name(goalie)} "
                    "يفوز 🔵 الفريق الأزرق باللقب! 🏆"
                )

        else:

            blue_kicks = (kick_number + 1) // 2
            red_kicks = kick_number // 2

            red_remaining = max(0, 5 - red_kicks)
            blue_remaining_after = max(0, 5 - blue_kicks)

            # إذا سجل الأزرق الآن يصبح غير قابل للحاق
            if blue_score + 1 > red_score + red_remaining:
                shooter = game["players"].get(game["current_shooter"])

                return (
                    "⚠️ ركلة حاسمة للبطولة!\n"
                    f"إذا سجلها {get_player_name(shooter)}، "
                    "يفوز 🔵 الفريق الأزرق باللقب! 🏆"
                )

            # إذا كان الأزرق متأخرًا ومضيعة هذه الركلة تنهي المباراة
            if (
                blue_score < red_score
                and blue_score + blue_remaining_after < red_score
            ):
                shooter = game["players"].get(game["current_shooter"])
                goalie = game["players"].get(game["current_goalie"])

                return (
                    "⚠️ ضغوط هائلة!\n"
                    f"يجب على {get_player_name(shooter)} التسجيل للاستمرار، "
                    f"إذا ضاعت أو صدها الحارس {get_player_name(goalie)} "
                    "يفوز 🔴 الفريق الأحمر باللقب! 🏆"
                )

    # ==============================================
    # الموت المفاجئ
    # ==============================================

    elif kick_number > 10 and kick_number % 2 == 0:

        # الأزرق هو المسدد الثاني في الجولة المفاجئة
        shooter = game["players"].get(game["current_shooter"])
        goalie = game["players"].get(game["current_goalie"])

        if blue_score < red_score:

            return (
                "⚠️ ضغوط هائلة!\n"
                f"يجب على {get_player_name(shooter)} التسجيل للاستمرار، "
                f"إذا ضاعت أو صدها الحارس {get_player_name(goalie)} "
                "يفوز 🔴 الفريق الأحمر باللقب! 🏆"
            )

        if blue_score == red_score:

            return (
                "⚠️ ركلة حاسمة للبطولة!\n"
                f"إذا سجلها {get_player_name(shooter)}، "
                "يفوز 🔵 الفريق الأزرق باللقب! 🏆"
            )

    return None


# ==================================================
# مؤقت الاختيار
# ==================================================

async def choice_timeout(context, chat_id, role):

    try:
        await asyncio.sleep(TURN_TIME)

        game = active_penalty_games.get(chat_id)

        if not game:
            return

        if game["phase"] != "shootout":
            return

        if game["resolving"]:
            return

        if role == "shooter":

            if game["shooter_choice"] is None:
                game["shooter_choice"] = "وسط"
                game["shooter_ready"] = True

                await update_kick_status(context, chat_id)

        elif role == "goalie":

            if game["goalie_choice"] is None:
                game["goalie_choice"] = "وسط"
                game["goalie_ready"] = True

                await update_kick_status(context, chat_id)

        if (
            game["shooter_choice"] is not None
            and game["goalie_choice"] is not None
            and not game["resolving"]
        ):
            game["resolving"] = True

            await resolve_kick(context, chat_id)

    except asyncio.CancelledError:
        pass


# ==================================================
# اختيار الاتجاه
# ==================================================

async def penalty_direction_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data.split(":")

    if len(data) < 3:
        return

    chat_id = int(data[1])
    direction = data[2]

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "shootout":
        return

    if game["resolving"]:
        return

    user_id = query.from_user.id

    shooter_id = game["current_shooter"]
    goalie_id = game["current_goalie"]

    if user_id == shooter_id:

        if game["shooter_choice"] is not None:
            await query.answer(
                "اخترت اتجاهك بالفعل.",
                show_alert=True
            )
            return

        game["shooter_choice"] = direction
        game["shooter_ready"] = True

    elif user_id == goalie_id:

        if game["goalie_choice"] is not None:
            await query.answer(
                "اخترت اتجاهك بالفعل.",
                show_alert=True
            )
            return

        game["goalie_choice"] = direction
        game["goalie_ready"] = True

    else:

        await query.answer(
            "• هذي الركلة مو لك.",
            show_alert=True
        )
        return

    await update_kick_status(context, chat_id)

    if (
        game["shooter_choice"] is not None
        and game["goalie_choice"] is not None
        and not game["resolving"]
    ):

        game["resolving"] = True

        if game.get("shooter_task"):
            game["shooter_task"].cancel()

        if game.get("goalie_task"):
            game["goalie_task"].cancel()

        await resolve_kick(context, chat_id)


# ==================================================
# تحديد الفائز
# ==================================================

def get_winner_if_finished(game):

    red_score = game["red_score"]
    blue_score = game["blue_score"]

    kick_number = game["kick_number"]

    # ==============================================
    # الركلات الخمس الأولى
    # ==============================================

    if kick_number <= 10:

        red_kicks = (kick_number + 1) // 2
        blue_kicks = kick_number // 2

        red_remaining = max(0, 5 - red_kicks)
        blue_remaining = max(0, 5 - blue_kicks)

        if red_score > blue_score + blue_remaining:
            return "red"

        if blue_score > red_score + red_remaining:
            return "blue"

        if red_kicks == 5 and blue_kicks == 5:

            if red_score > blue_score:
                return "red"

            if blue_score > red_score:
                return "blue"

            return None

    # ==============================================
    # الموت المفاجئ
    # ==============================================

    else:

        # بعد ركلة الأزرق الثانية في كل زوج
        if kick_number % 2 == 0:

            if red_score > blue_score:
                return "red"

            if blue_score > red_score:
                return "blue"

    return None


# ==================================================
# حل الركلة
# ==================================================

async def resolve_kick(context, chat_id):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    team = game["current_team"]
    goalie_team = "blue" if team == "red" else "red"

    shooter_choice = game["shooter_choice"]
    goalie_choice = game["goalie_choice"]

    shooter = game["players"].get(game["current_shooter"])
    goalie = game["players"].get(game["current_goalie"])

    # ==============================================
    # التحذير
    # ==============================================

    warning = get_kick_warning(game)

    if warning:

        await context.bot.send_message(
            chat_id=chat_id,
            text=warning
        )

    # ==============================================
    # التشويق
    # ==============================================

    teaser = await context.bot.send_message(
        chat_id=chat_id,
        text="هل يسجلها المسدد؟ ام يصدها الحارس…🧤🔥"
    )

    await asyncio.sleep(5)

    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=teaser.message_id
        )
    except Exception:
        pass

    # ==============================================
    # تحديد النتيجة
    # ==============================================

    goal = shooter_choice != goalie_choice

    if goal:

        if team == "red":
            game["red_score"] += 1
        else:
            game["blue_score"] += 1

    image_id = RESULT_IMAGES.get(
        (
            goalie_team,
            shooter_choice,
            goalie_choice
        )
    )

    red_score = game["red_score"]
    blue_score = game["blue_score"]

    shooter_emoji = "🔴" if team == "red" else "🔵"
    goalie_emoji = "🔵" if goalie_team == "blue" else "🔴"

    if goal:

        result_text = (
            f"⚽ هدف!\n\n"
            f"🎯 المسدد: {get_player_name(shooter)} {shooter_emoji}\n"
            f"🛡️ الحارس: {get_player_name(goalie)} {goalie_emoji}\n\n"
            f"🎯 اختيار المسدد: {DIRECTIONS[shooter_choice]}\n"
            f"🛡️ اختيار الحارس: {DIRECTIONS[goalie_choice]}\n\n"
            f"📊 النتيجة: 🔴 {red_score} - {blue_score} 🔵"
        )

    else:

        result_text = (
            f"🧤 تصدي!\n\n"
            f"🎯 المسدد: {get_player_name(shooter)} {shooter_emoji}\n"
            f"🛡️ الحارس: {get_player_name(goalie)} {goalie_emoji}\n\n"
            f"🎯 اختيار المسدد: {DIRECTIONS[shooter_choice]}\n"
            f"🛡️ اختيار الحارس: {DIRECTIONS[goalie_choice]}\n\n"
            f"📊 النتيجة: 🔴 {red_score} - {blue_score} 🔵"
        )

    if image_id:

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=image_id,
            caption=result_text
        )

    else:

        await context.bot.send_message(
            chat_id=chat_id,
            text=result_text
        )

    # ==============================================
    # فحص الفائز
    # ==============================================

    winner = get_winner_if_finished(game)

    if winner:

        await finish_penalty_game(
            context,
            chat_id,
            winner
        )

        return

    # ==============================================
    # انتظار .كمل
    # ==============================================

    await context.bot.send_message(
        chat_id=chat_id,
        text="⏸️ اكتب .كمل للركلة التالية."
    )


# ==================================================
# الركلة التالية
# ==================================================

async def continue_penalties(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "shootout":
        return

    if not can_manage_penalties(user.id):
        return

    game["kick_number"] += 1

    game["current_team"] = (
        "blue"
        if game["current_team"] == "red"
        else "red"
    )

    await start_kick(context, chat_id)


# ==================================================
# إنهاء المباراة
# ==================================================

async def finish_penalty_game(
    context,
    chat_id,
    winner
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    game["phase"] = "finished"

    if game.get("shooter_task"):
        game["shooter_task"].cancel()

    if game.get("goalie_task"):
        game["goalie_task"].cancel()

    red_score = game["red_score"]
    blue_score = game["blue_score"]

    if winner == "red":

        winner_ids = (
            game["red_shooters"]
            + game["red_goalies"]
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🏆 فاز 🔴 الفريق الأحمر!\n\n"
                f"📊 النتيجة النهائية: "
                f"🔴 {red_score} - {blue_score} 🔵"
            )
        )

    else:

        winner_ids = (
            game["blue_shooters"]
            + game["blue_goalies"]
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🏆 فاز 🔵 الفريق الأزرق!\n\n"
                f"📊 النتيجة النهائية: "
                f"🔴 {red_score} - {blue_score} 🔵"
            )
        )

    # ==============================================
    # الجوائز
    # ==============================================

    reward_lines = [
        "✨ جوائز الفريق الفائز: ✨"
    ]

    rewarded = set()

    for player_id in winner_ids:

        if player_id in rewarded:
            continue

        rewarded.add(player_id)

        player = game["players"].get(player_id)

        if not player:
            continue

        add_points(player_id, WIN_POINTS)

        reward_lines.append(
            f"• {get_player_name(player)} — "
            f"حصل على {WIN_POINTS} نقطة! 🎖️"
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(reward_lines)
    )

    del active_penalty_games[chat_id]