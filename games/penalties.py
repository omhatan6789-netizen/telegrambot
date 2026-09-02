import asyncio
import random
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from handlers.roles import get_rank_level
from handlers.points import add_points


# =========================================================
# الحالة
# =========================================================

active_penalty_games = {}


# =========================================================
# الصور
# =========================================================

START_IMAGES = {
    "red": "AgACAgQAAxkBAAICx2qXXRF_tg0mysuxrFyg-TzQFOFWAAJvEmsbkuPAUDW0ZFs8Jpp0AQADAgADeQADPQQ",
    "blue": "AgACAgQAAxkBAAICzWqXXSelWf1kB8pPZa_v_tT75xNZAAJwEmsbkuPAUAaqxmTbcl6BAQADAgADeQADPQQ",
}


RESULT_IMAGES = {
    "red": {
        "right": {
            "right": "AgACAgQAAyEFAATwGwEUAAJP-2qXQ8T5AtOCk6Tgh_lxF3uj8CLbAAIhE2sbtou5UESSt8Vei3-fAQADAgADeQADPQQ",
            "center": "AgACAgQAAxkBAAIC3mqXXm9DsfMF7RKuGnjX0DZZCDElAAJ2EmsbkuPAUGcJXuHpNXeRAQADAgADeQADPQQ",
            "left": "AgACAgQAAxkBAAIC4mqXXuc962m3PinFC3de9Cnd0yn9AAJ4EmsbkuPAUPPtWgmjylC3AQADAgADeQADPQQ",
        },
        "center": {
            "right": "AgACAgQAAxkBAAIC3GqXXk_YkocGUIQQLrUjVUsT6WFJAAJ1EmsbkuPAUKlvrIEsTFKiAQADAgADeQADPQQ",
            "center": "AgACAgQAAxkBAAIC1mqXXaAJP0tj2fHk37IEYyLojq8-AAJyEmsbkuPAUMnwQohZeWMRAQADAgADeQADPQQ",
            "left": "AgACAgQAAxkBAAIC4GqXXq47KtcOgOu_X2FaUbKinv5bAAJ3EmsbkuPAUM6TlGij3IEHAQADAgADeQADPQQ",
        },
        "left": {
            "right": "AgACAgQAAxkBAAIC2GqXXd6JOsmKg6XY4QmjioYpY6JBAAJzEmsbkuPAUN2RFOQM76ZjAQADAgADeQADPQQ",
            "center": "AgACAgQAAxkBAAIC5GqXXw7IjhzegXCjpRcxZwqjVS6WAAJ5EmsbkuPAUFp8zcXUDTg5AQADAgADeQADPQQ",
            "left": "AgACAgQAAxkBAAIC2mqXXi2MCyP1bavd0hR1Z7qzHoCAAAJ0EmsbkuPAUKVIWnY0MYkOAQADAgADeQADPQQ",
        },
    },

    "blue": {
        "left": {
            "left": "AgACAgQAAxkBAAIC5mqXX1YLbKkPxyFAuXt4GIyWpwr0AAJ6EmsbkuPAUJauXBMfrdsmAQADAgADeQADPQQ",
            "right": "AgACAgQAAxkBAAIC6mqXX5umjMZgl8QvHQ9cWVE7OBkrAAJ8EmsbkuPAUETvi9lxwAABoAEAAwIAA3kAAz0E",
            "center": "AgACAgQAAxkBAAIC-2qXY5T0b_X374-vZzZGl0HLQEEYAAKIEmsbkuPAUFT-iD8IXTJ6AQADAgADeQADPQQ",
        },
        "right": {
            "left": "AgACAgQAAxkBAAIC6GqXX3Rokn49gwNhssRA_Jr5Mim6AAJ7EmsbkuPAUBloAjhQo03mAQADAgADeQADPQQ",
            "center": "AgACAgQAAxkBAAIC7GqXX81g1Ntcm7CbDJFBr4XBTj0nAAJ9EmsbkuPAUC1szPgbscpJAQADAgADeQADPQQ",
            "right": "AgACAgQAAxkBAAIC7mqXX_UXpeFNif4tcrDWx1_KUoeSAAJ_EmsbkuPAUIc2qNsrW-HMAQADAgADeQADPQQ",
        },
        "center": {
            "left": "AgACAgQAAxkBAAIC8mqXYJiHXfglNwRGoIhIfxfC8bjdAAKCEmsbkuPAUGkJ2VH7L0tAAQADAgADeQADPQQ",
            "center": "AgACAgQAAxkBAAIC8GqXYHN9_lRYWV7MQ-2ViZNxESDxAAKAEmsbkuPAUBIAAa6Cdmoz2AEAAwIAA3kAAz0E",
            "right": "AgACAgQAAxkBAAIC9GqXYNPEKxVz0lKOSKIvI8jMwlTPAAKFEmsbkuPAUMilU52EcjlsAQADAgADeQADPQQ",
        },
    },
}


# =========================================================
# أسماء الحسابات
# =========================================================

def get_account_name(user):
    """
    اسم الحساب الظاهر في تيليجرام.
    لا يستخدم username ولا @username.
    """
    return user.full_name or user.first_name or "مستخدم"


# =========================================================
# الصلاحية - نفس نظام غميضة
# =========================================================

def can_manage_penalties(user_id):
    return get_rank_level(user_id) > 0


# =========================================================
# أدوات
# =========================================================

TEAM_NAMES = {
    "red": "الفريق الأحمر 🔴",
    "blue": "الفريق الأزرق 🔵",
}

TEAM_EMOJIS = {
    "red": "🔴",
    "blue": "🔵",
}

DIRECTION_NAMES = {
    "left": "اليسار",
    "center": "الوسط",
    "right": "اليمين",
}

DIRECTION_EMOJIS = {
    "left": "👈🏻",
    "center": "🎯",
    "right": "👉🏻",
}


def opposite_team(team):
    return "blue" if team == "red" else "red"


def get_team_ids(game, team):
    return list(dict.fromkeys(
        game["teams"][team]["shooters"]
        + game["teams"][team]["goalies"]
    ))


def get_team_names(game, team, role):
    return [
        get_account_name(game["players"][uid])
        for uid in game["teams"][team][role]
    ]


def format_names(names):
    if not names:
        return "لا يوجد"
    return "، ".join(names)


def distribution_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔘 يدوي",
                callback_data=f"penalty:dist:{chat_id}:manual"
            ),
            InlineKeyboardButton(
                "🔘 عشوائي",
                callback_data=f"penalty:dist:{chat_id}:random"
            ),
        ]
    ])


def kick_keyboard(chat_id, user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "يسار 👈🏻",
                callback_data=f"penalty:kick:{chat_id}:{user_id}:left"
            ),
            InlineKeyboardButton(
                "وسط 🎯",
                callback_data=f"penalty:kick:{chat_id}:{user_id}:center"
            ),
            InlineKeyboardButton(
                "يمين 👉🏻",
                callback_data=f"penalty:kick:{chat_id}:{user_id}:right"
            ),
        ]
    ])


# =========================================================
# بدء اللعبة
# =========================================================

async def start_penalty_game(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not can_manage_penalties(user.id):
        return

    if chat_id in active_penalty_games:
        await message.reply_text("❌ فيه مباراة بلنتيات شغالة بالفعل.")
        raise ApplicationHandlerStop

    active_penalty_games[chat_id] = {
        "players": {},
        "order": [],

        "phase": "registration",

        "teams": {
            "red": {
                "shooters": [],
                "goalies": [],
            },
            "blue": {
                "shooters": [],
                "goalies": [],
            },
        },

        "assigned": {},

        "distribution_message_id": None,
        "distribution_mode": None,

        "scores": {
            "red": 0,
            "blue": 0,
        },

        "kicks": {
            "red": 0,
            "blue": 0,
        },

        "shooter_index": {
            "red": 0,
            "blue": 0,
        },

        "goalie_index": {
            "red": 0,
            "blue": 0,
        },

        "turn_team": "red",

        "total_kicks": 0,

        "current_shooter": None,
        "current_goalie": None,
        "current_shooting_team": None,
        "current_goalie_team": None,

        "shooter_choice": None,
        "goalie_choice": None,

        "kick_message_id": None,
        "choice_task": None,

        "kick_resolving": False,
        "waiting_continue": False,

        "sudden_death": False,
    }

    await message.reply_text(
        "⚽️ تم بدء لعبة البلنتيات 🥅\n"
        "• للانضمام اكتب: دخول\n"
        "• للبدء اكتب: .ابدا"
    )

    raise ApplicationHandlerStop


# =========================================================
# دخول اللاعبين
# =========================================================

async def join_penalty_game(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "registration":
        return

    if user.id not in game["players"]:
        game["players"][user.id] = user
        game["order"].append(user.id)

        name = get_account_name(user)

        await update.effective_message.reply_text(
            f"انضم {name} ⚽ (العدد: {len(game['players'])})"
        )

    raise ApplicationHandlerStop


# =========================================================
# رسالة التوزيع
# =========================================================

async def distribute_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user
    message = update.effective_message

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] not in ("registration", "distribution", "manual"):
        await message.reply_text("❌ التوزيع انتهى بالفعل.")
        raise ApplicationHandlerStop

    if len(game["players"]) < 2:
        await message.reply_text("❌ تحتاج لاعبين على الأقل.")
        raise ApplicationHandlerStop

    # إعادة التوزيع من جديد
    game["phase"] = "distribution"
    game["distribution_mode"] = None
    game["assigned"] = {}

    game["teams"] = {
        "red": {
            "shooters": [],
            "goalies": [],
        },
        "blue": {
            "shooters": [],
            "goalies": [],
        },
    }

    admin_name = get_account_name(user)

    sent = await message.reply_text(
        f"🛡️ توزيع فرق مباراة البلنتيات (أحمر ضد أزرق)\n"
        f"يا {admin_name}، كيف تبي نوزّع اللاعبين؟",
        reply_markup=distribution_keyboard(chat_id)
    )

    game["distribution_message_id"] = sent.message_id

    # تثبيت رسالة التوزيع إذا البوت يملك الصلاحية
    try:
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=sent.message_id,
            disable_notification=True
        )
    except Exception:
        pass

    raise ApplicationHandlerStop


# =========================================================
# عرض التوزيع اليدوي
# =========================================================

def build_manual_distribution_text(game):

    lines = [
        "🛡️ التوزيع اليدوي لمباراة البلنتيات:",
        "",
        "📋 اللاعبين:",
    ]

    for index, uid in enumerate(game["order"], start=1):
        name = get_account_name(game["players"][uid])
        lines.append(f"{index}. {name}")

    lines.extend([
        "",
        "استخدم الأوامر:",
        ".احمر 1 2*",
        ".ازرق 3",
        "",
        "⭐ النجمة * = حارس",
        "بدون نجمة = مسدد",
    ])

    unassigned = [
        uid for uid in game["order"]
        if uid not in game["assigned"]
    ]

    if unassigned:
        lines.extend([
            "",
            "⏳ المتبقي:",
        ])

        for uid in unassigned:
            index = game["order"].index(uid) + 1
            name = get_account_name(game["players"][uid])
            lines.append(f"{index}. {name}")

    return "\n".join(lines)


def build_current_distribution(game):

    red_shooters = format_names(
        get_team_names(game, "red", "shooters")
    )

    red_goalies = format_names(
        get_team_names(game, "red", "goalies")
    )

    blue_shooters = format_names(
        get_team_names(game, "blue", "shooters")
    )

    blue_goalies = format_names(
        get_team_names(game, "blue", "goalies")
    )

    return (
        "\n\n"
        "🔴 الأحمر:\n"
        f"🎯 المسددين: {red_shooters}\n"
        f"🛡️ الحراس: {red_goalies}\n\n"
        "🔵 الأزرق:\n"
        f"🎯 المسددين: {blue_shooters}\n"
        f"🛡️ الحراس: {blue_goalies}"
    )


# =========================================================
# Callback التوزيع
# =========================================================

async def penalty_distribution_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data.split(":")

    if len(data) != 4:
        return

    _, _, chat_id_text, mode = data

    try:
        chat_id = int(chat_id_text)
    except ValueError:
        return

    game = active_penalty_games.get(chat_id)

    if not game:
        await query.edit_message_text("❌ انتهت مباراة البلنتيات.")
        return

    user = query.from_user

    if not can_manage_penalties(user.id):
        await query.answer(
            "❌ ما عندك صلاحية.",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # يدوي
    # -----------------------------------------------------

    if mode == "manual":

        game["phase"] = "manual"
        game["distribution_mode"] = "manual"

        await query.edit_message_text(
            build_manual_distribution_text(game)
        )

        return

    # -----------------------------------------------------
    # عشوائي
    # -----------------------------------------------------

    if mode == "random":

        game["phase"] = "ready"
        game["distribution_mode"] = "random"

        assign_random_teams(game)

        await query.edit_message_text(
            build_distribution_complete_text(game)
        )

        return


# =========================================================
# التوزيع العشوائي
# =========================================================

def assign_random_teams(game):

    ids = list(game["order"])
    random.shuffle(ids)

    count = len(ids)

    if count == 2:

        red_id = ids[0]
        blue_id = ids[1]

        game["teams"]["red"]["shooters"] = [red_id]
        game["teams"]["red"]["goalies"] = [red_id]

        game["teams"]["blue"]["shooters"] = [blue_id]
        game["teams"]["blue"]["goalies"] = [blue_id]

        game["assigned"] = {
            red_id: "red",
            blue_id: "blue",
        }

        return

    red_size = count // 2
    blue_size = count // 2

    if count % 2:
        if random.choice([True, False]):
            red_size += 1
        else:
            blue_size += 1

    red_players = ids[:red_size]
    blue_players = ids[red_size:]

    game["assigned"] = {}

    for uid in red_players:
        game["assigned"][uid] = "red"

    for uid in blue_players:
        game["assigned"][uid] = "blue"

    game["teams"]["red"] = make_random_roles(red_players)
    game["teams"]["blue"] = make_random_roles(blue_players)


def make_random_roles(players):

    players = list(players)
    random.shuffle(players)

    if len(players) == 1:
        return {
            "shooters": [players[0]],
            "goalies": [players[0]],
        }

    goalie = random.choice(players)

    shooters = [
        uid for uid in players
        if uid != goalie
    ]

    random.shuffle(shooters)

    return {
        "shooters": shooters,
        "goalies": [goalie],
    }


# =========================================================
# التوزيع اليدوي
# =========================================================

async def manual_red(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await handle_manual_assignment(
        update,
        context,
        "red"
    )


async def manual_blue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await handle_manual_assignment(
        update,
        context,
        "blue"
    )


async def handle_manual_assignment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    team
):

    chat_id = update.effective_chat.id
    user = update.effective_user
    message = update.effective_message

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "manual":
        return

    if not can_manage_penalties(user.id):
        return

    text = message.text.strip()

    prefix = ".احمر" if team == "red" else ".ازرق"

    raw = text[len(prefix):].strip()

    if not raw:
        return

    tokens = raw.split()

    for token in tokens:

        is_goalie = token.endswith("*")

        number_text = token[:-1] if is_goalie else token

        if not number_text.isdigit():
            await message.reply_text(
                "❌ استخدم أرقام اللاعبين فقط."
            )
            raise ApplicationHandlerStop

        number = int(number_text)

        if number < 1 or number > len(game["order"]):
            await message.reply_text(
                "❌ رقم اللاعب غير موجود."
            )
            raise ApplicationHandlerStop

        uid = game["order"][number - 1]

        # اللاعب معين لفريق آخر
        if uid in game["assigned"]:

            if game["assigned"][uid] != team:
                await message.reply_text(
                    "❌ هذا اللاعب موزع بالفعل في الفريق الآخر."
                )
                raise ApplicationHandlerStop

            await message.reply_text(
                "❌ هذا اللاعب موزع بالفعل في هذا الفريق."
            )
            raise ApplicationHandlerStop

        game["assigned"][uid] = team

        if is_goalie:
            game["teams"][team]["goalies"].append(uid)
        else:
            game["teams"][team]["shooters"].append(uid)

    # -----------------------------------------------------
    # إذا اكتمل التوزيع
    # -----------------------------------------------------

    if len(game["assigned"]) == len(game["players"]):

        # الفريق الذي فيه لاعب واحد:
        # اللاعب يكون مسدد + حارس
        for current_team in ("red", "blue"):

            ids = get_team_ids(game, current_team)

            if len(ids) == 1:

                uid = ids[0]

                if uid not in game["teams"][current_team]["shooters"]:
                    game["teams"][current_team]["shooters"].append(uid)

                if uid not in game["teams"][current_team]["goalies"]:
                    game["teams"][current_team]["goalies"].append(uid)

        valid, reason = validate_manual_distribution(game)

        if not valid:

            await message.reply_text(
                f"❌ ما اكتمل التوزيع اليدوي.\n{reason}\n\n"
                "تقدر تكتب .وزع لإعادة التوزيع."
            )

            raise ApplicationHandlerStop

        game["phase"] = "ready"

        await message.reply_text(
            build_distribution_complete_text(game)
        )

        raise ApplicationHandlerStop

    # -----------------------------------------------------
    # ما زال فيه لاعبين
    # -----------------------------------------------------

    await message.reply_text(
        build_manual_distribution_text(game)
        + build_current_distribution(game)
    )

    raise ApplicationHandlerStop


def validate_manual_distribution(game):

    for team in ("red", "blue"):

        ids = get_team_ids(game, team)

        if not ids:
            return False, f"❌ الفريق {TEAM_NAMES[team]} ما فيه لاعبين."

        if not game["teams"][team]["shooters"]:
            return False, f"❌ الفريق {TEAM_NAMES[team]} ما فيه مسدد."

        if not game["teams"][team]["goalies"]:
            return False, f"❌ الفريق {TEAM_NAMES[team]} ما فيه حارس."

    return True, ""


# =========================================================
# رسالة اكتمال التوزيع
# =========================================================

def build_distribution_complete_text(game):

    red_shooters = format_names(
        get_team_names(game, "red", "shooters")
    )

    red_goalies = format_names(
        get_team_names(game, "red", "goalies")
    )

    blue_shooters = format_names(
        get_team_names(game, "blue", "shooters")
    )

    blue_goalies = format_names(
        get_team_names(game, "blue", "goalies")
    )

    return (
        "🎯 اكتمل التوزيع اليدوي لمباراة البلنتيات!\n\n"
        "🔴 الفريق الأحمر:\n"
        f"🎯 المسددين: {red_shooters}\n"
        f"🛡️ الحراس: {red_goalies}\n\n"
        "🔵 الفريق الأزرق:\n"
        f"🎯 المسددين: {blue_shooters}\n"
        f"🛡️ الحراس: {blue_goalies}\n\n"
        "الأدمن يكتب .ابدا لبدء ركلات الترجيح! 🚀"
    )


# =========================================================
# بدء ركلات الترجيح
# =========================================================

async def begin_penalty_shootout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user
    message = update.effective_message

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] != "ready":
        await message.reply_text(
            "❌ وزّع الفرق أولًا."
        )
        raise ApplicationHandlerStop

    game["phase"] = "shooting"

    # إزالة تثبيت رسالة التوزيع
    if game.get("distribution_message_id"):

        try:
            await context.bot.unpin_chat_message(
                chat_id=chat_id,
                message_id=game["distribution_message_id"]
            )
        except Exception:
            pass

    # لا نحذف الرسالة، فقط نتركها في المحادثة.
    # التثبيت هو الذي يروح بعد بداية المباراة.

    await start_next_penalty_kick(
        context,
        chat_id
    )

    raise ApplicationHandlerStop


# =========================================================
# تحديد رسالة ركلة حاسمة / بقاء
# =========================================================

def get_decisive_warning(
    game,
    shooting_team,
    shooter_name,
    goalie_name
):

    if game["sudden_death"]:
        return None

    opponent = opposite_team(shooting_team)

    shooting_score = game["scores"][shooting_team]
    opponent_score = game["scores"][opponent]

    shooting_kicks = game["kicks"][shooting_team]
    opponent_kicks = game["kicks"][opponent]

    # هذه الركلة هي الركلة رقم shooting_kicks + 1
    remaining_shooting_after = 5 - (shooting_kicks + 1)
    remaining_opponent = 5 - opponent_kicks

    # إذا سجل، يحسم المباراة
    score_if_goal = shooting_score + 1

    if score_if_goal > opponent_score + remaining_opponent:

        return (
            "⚠️ ركلة حاسمة للبطولة!\n"
            f"إذا سجلها {shooter_name}، يفوز "
            f"{TEAM_NAMES[shooting_team]} باللقب! 🏆"
        )

    # إذا لم يسجل، الفريق الآخر يفوز رياضيًا
    if (
        opponent_score > shooting_score
        and opponent_score
        > shooting_score + remaining_shooting_after
    ):

        return (
            "⚠️ ضغوط هائلة!\n"
            f"يجب على {shooter_name} التسجيل للاستمرار، "
            f"إذا ضاعت أو صدها الحارس {goalie_name} "
            f"يفوز {TEAM_NAMES[opponent]} باللقب! 🏆"
        )

    return None


# =========================================================
# نص الاختيار
# =========================================================

def build_kick_caption(game):

    shooting_team = game["current_shooting_team"]
    goalie_team = game["current_goalie_team"]

    shooter = game["current_shooter"]
    goalie = game["current_goalie"]

    shooter_name = get_account_name(game["players"][shooter])
    goalie_name = get_account_name(game["players"][goalie])

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

    round_number = game["total_kicks"]

    if round_number == 1:
        kick_text = "الركلة الأولى"
    else:
        kick_text = f"الركلة {round_number}"

    return (
        f"🎮 *الجولة {round_number} — {kick_text} "
        f"{TEAM_EMOJIS[shooting_team]}*\n\n"
        f"🎯 المسدد: {shooter_name} "
        f"{TEAM_EMOJIS[shooting_team]} ({shooter_status})\n"
        f"🛡️ الحارس: {goalie_name} "
        f"{TEAM_EMOJIS[goalie_team]} ({goalie_status})\n\n"
        "اختر الزاوية من الأزرار بالأسفل:"
    )


# =========================================================
# بدء الركلة
# =========================================================

async def start_next_penalty_kick(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["phase"] != "shooting":
        return

    game["waiting_continue"] = False
    game["kick_resolving"] = False

    shooting_team = game["turn_team"]
    goalie_team = opposite_team(shooting_team)

    shooters = game["teams"][shooting_team]["shooters"]
    goalies = game["teams"][goalie_team]["goalies"]

    if not shooters or not goalies:
        return

    shooter_index = (
        game["shooter_index"][shooting_team]
        % len(shooters)
    )

    goalie_index = (
        game["goalie_index"][goalie_team]
        % len(goalies)
    )

    shooter_id = shooters[shooter_index]
    goalie_id = goalies[goalie_index]

    game["current_shooter"] = shooter_id
    game["current_goalie"] = goalie_id

    game["current_shooting_team"] = shooting_team
    game["current_goalie_team"] = goalie_team

    game["shooter_choice"] = None
    game["goalie_choice"] = None

    game["total_kicks"] += 1

    # -----------------------------------------------------
    # ركلة حاسمة / بقاء
    # -----------------------------------------------------

    warning = get_decisive_warning(
        game,
        shooting_team,
        get_account_name(game["players"][shooter_id]),
        get_account_name(game["players"][goalie_id])
    )

    if warning:
        await context.bot.send_message(
            chat_id=chat_id,
            text=warning
        )

    # -----------------------------------------------------
    # صورة الاستعداد + الكابشن في نفس الرسالة
    # -----------------------------------------------------

    caption = build_kick_caption(game)

    image_id = START_IMAGES[goalie_team]

    try:

        sent = await context.bot.send_photo(
            chat_id=chat_id,
            photo=image_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=kick_keyboard(
                chat_id,
                shooter_id
            )
        )

    except Exception:

        # في حال فشل إرسال الصورة، لا تتوقف اللعبة
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="Markdown",
            reply_markup=kick_keyboard(
                chat_id,
                shooter_id
            )
        )

    game["kick_message_id"] = sent.message_id

    # -----------------------------------------------------
    # مؤقت 30 ثانية
    # -----------------------------------------------------

    game["choice_task"] = asyncio.create_task(
        penalty_choice_timeout(
            context,
            chat_id
        )
    )


# =========================================================
# تحديث كابشن رسالة الصورة
# =========================================================

async def update_kick_message(
    context,
    chat_id,
    game,
    remove_buttons=False
):

    message_id = game.get("kick_message_id")

    if not message_id:
        return

    caption = build_kick_caption(game)

    markup = None

    if not remove_buttons:
        markup = kick_keyboard(
            chat_id,
            game["current_shooter"]
        )

    try:

        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=markup
        )

    except Exception:

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception:
            pass


# =========================================================
# اختيار اللاعب
# =========================================================

async def penalty_kick_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    data = query.data.split(":")

    if len(data) != 5:
        await query.answer()
        return

    _, _, chat_id_text, callback_user_text, direction = data

    try:
        chat_id = int(chat_id_text)
        callback_user_id = int(callback_user_text)
    except ValueError:
        await query.answer()
        return

    game = active_penalty_games.get(chat_id)

    if not game:
        await query.answer(
            "❌ انتهت المباراة.",
            show_alert=True
        )
        return

    user_id = query.from_user.id

    if user_id != callback_user_id:
        await query.answer(
            "❌ هذا الزر مو لك.",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # من خارج المباراة
    # -----------------------------------------------------

    if user_id not in game["players"]:

        await query.answer(
            "❌ انت مو بالقيم اصلا!",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # إذا انتهت الركلة
    # -----------------------------------------------------

    if game["kick_resolving"]:

        await query.answer(
            "❌ تم اختيار الاتجاه بالفعل.",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # المسدد
    # -----------------------------------------------------

    if user_id == game["current_shooter"]:

        if game["shooter_choice"] is not None:

            await query.answer(
                "❌ اخترت اتجاهك بالفعل.",
                show_alert=True
            )
            return

        game["shooter_choice"] = direction

        await query.answer(
            "✅ تم اختيار اتجاه التسديد."
        )

    # -----------------------------------------------------
    # الحارس
    # -----------------------------------------------------

    elif user_id == game["current_goalie"]:

        if game["goalie_choice"] is not None:

            await query.answer(
                "❌ اخترت اتجاهك بالفعل.",
                show_alert=True
            )
            return

        game["goalie_choice"] = direction

        await query.answer(
            "✅ تم اختيار اتجاه الحارس."
        )

    # -----------------------------------------------------
    # لاعب موجود لكنه مو دوره
    # -----------------------------------------------------

    else:

        await query.answer(
            "❌ انتظر، ليس دورك!",
            show_alert=True
        )
        return

    # تحديث نفس رسالة الصورة
    await update_kick_message(
        context,
        chat_id,
        game
    )

    # -----------------------------------------------------
    # الاثنين اختاروا
    # -----------------------------------------------------

    if (
        game["shooter_choice"] is not None
        and game["goalie_choice"] is not None
    ):

        game["kick_resolving"] = True

        if game.get("choice_task"):
            game["choice_task"].cancel()
            game["choice_task"] = None

        await update_kick_message(
            context,
            chat_id,
            game,
            remove_buttons=True
        )

        await resolve_penalty_kick(
            context,
            chat_id
        )


# =========================================================
# انتهاء 30 ثانية
# =========================================================

async def penalty_choice_timeout(
    context,
    chat_id
):

    try:

        await asyncio.sleep(30)

    except asyncio.CancelledError:
        return

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if game["kick_resolving"]:
        return

    game["kick_resolving"] = True

    # الذي ما اختار = وسط
    if game["shooter_choice"] is None:
        game["shooter_choice"] = "center"

    if game["goalie_choice"] is None:
        game["goalie_choice"] = "center"

    # نفس رسالة الصورة تتحدث إلى جاهز
    await update_kick_message(
        context,
        chat_id,
        game,
        remove_buttons=True
    )

    await resolve_penalty_kick(
        context,
        chat_id
    )


# =========================================================
# نتيجة الركلة
# =========================================================

async def resolve_penalty_kick(
    context,
    chat_id
):

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    shooter_direction = game["shooter_choice"]
    goalie_direction = game["goalie_choice"]

    shooting_team = game["current_shooting_team"]
    goalie_team = game["current_goalie_team"]

    shooter_id = game["current_shooter"]
    goalie_id = game["current_goalie"]

    shooter_name = get_account_name(
        game["players"][shooter_id]
    )

    goalie_name = get_account_name(
        game["players"][goalie_id]
    )

    # نفس الاتجاه = تصدي
    is_goal = shooter_direction != goalie_direction

    if is_goal:
        game["scores"][shooting_team] += 1

    # -----------------------------------------------------
    # التشويقية
    # -----------------------------------------------------

    teaser = await context.bot.send_message(
        chat_id=chat_id,
        text="هل يسجلها المسدد؟ ام يصدها الحارس…🧤🔥"
    )

    await asyncio.sleep(5)

    # لو الأدمن أنهى اللعبة أثناء الانتظار
    if active_penalty_games.get(chat_id) is not game:
        try:
            await teaser.delete()
        except Exception:
            pass
        return

    try:
        await teaser.delete()
    except Exception:
        pass

    # -----------------------------------------------------
    # صورة النتيجة
    # -----------------------------------------------------

    image_id = RESULT_IMAGES[
        goalie_team
    ][
        goalie_direction
    ][
        shooter_direction
    ]

    shooter_direction_text = DIRECTION_NAMES[shooter_direction]
    goalie_direction_text = DIRECTION_NAMES[goalie_direction]

    shooter_direction_emoji = DIRECTION_EMOJIS[
        shooter_direction
    ]

    goalie_direction_emoji = DIRECTION_EMOJIS[
        goalie_direction
    ]

    if is_goal:

        caption = (
            f"⚽ قوووول!! هدف لصالح {shooter_name} "
            f"(فريق {'الأحمر 🔴' if shooting_team == 'red' else 'الأزرق 🔵'}) 🔥\n\n"
            f"🎯 المسدد سدد في {shooter_direction_text} "
            f"{shooter_direction_emoji} والحارس ارتمى إلى "
            f"{goalie_direction_text} {goalie_direction_emoji}!\n\n"
            f"📊 النتيجة: "
            f"🔴 الأحمر {game['scores']['red']} - "
            f"{game['scores']['blue']} الأزرق 🔵"
        )

    else:

        caption = (
            "🧤 ياساتر صدها الحارس! مستحييل! 💥\n\n"
            f"🛡️ الحارس {goalie_name} "
            f"(فريق {'الأحمر 🔴' if goalie_team == 'red' else 'الأزرق 🔵'}) "
            f"تصدى للكرة في {goalie_direction_text} "
            f"{goalie_direction_emoji}!"
            "\n\n"
            f"📊 النتيجة: "
            f"🔴 الأحمر {game['scores']['red']} - "
            f"{game['scores']['blue']} الأزرق 🔵"
        )

    try:

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=image_id,
            caption=caption
        )

    except Exception:

        await context.bot.send_message(
            chat_id=chat_id,
            text=caption
        )

    # -----------------------------------------------------
    # تحديث عدد الركلات
    # -----------------------------------------------------

    game["kicks"][shooting_team] += 1

    game["shooter_index"][shooting_team] += 1
    game["goalie_index"][goalie_team] += 1

    # -----------------------------------------------------
    # هل انتهت المباراة؟
    # -----------------------------------------------------

    winner = get_match_winner(game)

    if winner:

        await finish_penalty_game(
            context,
            chat_id,
            winner
        )

        return

    # -----------------------------------------------------
    # الانتقال للفريق الآخر
    # -----------------------------------------------------

    game["turn_team"] = opposite_team(
        shooting_team
    )

    game["waiting_continue"] = True
    game["kick_resolving"] = False

    await context.bot.send_message(
        chat_id=chat_id,
        text="⏸️ اكتب .كمل للركلة التالية."
    )


# =========================================================
# تحديد الفائز
# =========================================================

def get_match_winner(game):

    red_score = game["scores"]["red"]
    blue_score = game["scores"]["blue"]

    red_kicks = game["kicks"]["red"]
    blue_kicks = game["kicks"]["blue"]

    # -----------------------------------------------------
    # الركلات المفاجئة
    # -----------------------------------------------------

    if game["sudden_death"]:

        # بعد أن نفذ الفريقان نفس العدد
        if red_kicks == blue_kicks:

            if red_score > blue_score:
                return "red"

            if blue_score > red_score:
                return "blue"

        return None

    # -----------------------------------------------------
    # أول خمس ركلات
    # -----------------------------------------------------

    remaining_red = 5 - red_kicks
    remaining_blue = 5 - blue_kicks

    if red_score > blue_score + remaining_red:
        return "red"

    if blue_score > red_score + remaining_blue:
        return "blue"

    # -----------------------------------------------------
    # خلصت الخمس لكل فريق
    # -----------------------------------------------------

    if red_kicks >= 5 and blue_kicks >= 5:

        if red_score > blue_score:
            return "red"

        if blue_score > red_score:
            return "blue"

        # تعادل -> ركلات مفاجئة
        game["sudden_death"] = True

        return None

    return None


# =========================================================
# .كمل
# =========================================================

async def continue_penalty_shootout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user
    message = update.effective_message

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game["phase"] != "shooting":
        return

    if not game["waiting_continue"]:
        return

    game["waiting_continue"] = False

    # بعد نهاية الخمس بالتعادل
    if game["sudden_death"] and game["kicks"]["red"] == 5:

        # أول ركلة مفاجئة ستكون للأحمر
        game["turn_team"] = "red"

        await context.bot.send_message(
            chat_id=chat_id,
            text="🔥 تعادل بعد 5 ركلات لكل فريق!\n"
                 "ننتقل الآن للركلات الحاسمة!!."
        )

    await start_next_penalty_kick(
        context,
        chat_id
    )

    raise ApplicationHandlerStop


# =========================================================
# إنهاء المباراة وإعطاء الجوائز
# =========================================================

async def finish_penalty_game(
    context,
    chat_id,
    winner
):

    game = active_penalty_games.pop(
        chat_id,
        None
    )

    if not game:
        return

    game["phase"] = "finished"

    # إلغاء المؤقت
    if game.get("choice_task"):

        try:
            game["choice_task"].cancel()
        except Exception:
            pass

        game["choice_task"] = None

    red_score = game["scores"]["red"]
    blue_score = game["scores"]["blue"]

    winner_emoji = TEAM_EMOJIS[winner]

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🏆 انتهت مباراة البلنتيات! 🏆\n\n"
            f"🎉 الفائز: {winner_emoji} "
            f"{TEAM_NAMES[winner]}!\n\n"
            f"النتيجة النهائية: "
            f"🔴 الأحمر {red_score} - "
            f"{blue_score} الأزرق 🔵"
        )
    )

    # -----------------------------------------------------
    # إلغاء تثبيت رسالة التوزيع بعد انتهاء المباراة
    # -----------------------------------------------------

    if game.get("distribution_message_id"):

        try:

            await context.bot.unpin_chat_message(
                chat_id=chat_id,
                message_id=game["distribution_message_id"]
            )

        except Exception:
            pass

    # -----------------------------------------------------
    # الجوائز
    # -----------------------------------------------------

    winner_ids = get_team_ids(
        game,
        winner
    )

    reward_lines = [
        "✨ جوائز الفريق الفائز: ✨"
    ]

    for uid in winner_ids:

        try:
            add_points(uid, 50)
        except Exception:
            pass

        name = get_account_name(
            game["players"][uid]
        )

        reward_lines.append(
            f"• {name} — حصل على 50 نقطة! 🎖️"
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(reward_lines)
    )


# =========================================================
# إنهاء يدوي
# =========================================================

async def end_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id
    user = update.effective_user

    game = active_penalty_games.get(chat_id)

    if not game:
        return

    if not can_manage_penalties(user.id):
        return

    if game.get("choice_task"):

        try:
            game["choice_task"].cancel()
        except Exception:
            pass

    active_penalty_games.pop(
        chat_id,
        None
    )

    try:

        await context.bot.unpin_chat_message(
            chat_id=chat_id,
            message_id=game.get("distribution_message_id")
        )

    except Exception:
        pass

    await update.effective_message.reply_text(
        "🛑 تم إنهاء مباراة البلنتيات."
    )

    raise ApplicationHandlerStop