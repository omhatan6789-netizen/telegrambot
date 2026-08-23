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

PENALTY_ROUNDS = 5
CHOICE_TIME = 30
MIN_PLAYERS = 2
WIN_POINTS = 50


# ==================================================
# الألعاب النشطة
# ==================================================

active_penalty_games = {}


# ==================================================
# صلاحية إدارة اللعبة
# ==================================================

def can_manage_penalty_game(user_id):
    return get_rank_level(user_id) > 0


# ==================================================
# اسم اللاعب
# ==================================================

def get_player_name(user):
    
    if not user:
        return "مستخدم"
    
    if user.first_name:
        return user.first_name
    
    if user.username:
        return f"@{user.username}"
    
    return "مستخدم"


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
    
    if not can_manage_penalty_game(user.id):
        
        await update.message.reply_text(
            "❌ هذا الأمر للرتب فقط."
        )
        
        return
    
    if chat.id in active_penalty_games:
        
        await update.message.reply_text(
            "❌ توجد لعبة بلنتيات شغالة بالفعل."
        )
        
        return
    
    active_penalty_games[chat.id] = {
        
        "players": {},
        "order": [],
        
        "phase": "registration",
        
        "red_team": {
            "shooters": [],
            "goalkeeper": None,
            "score": 0
        },
        
        "blue_team": {
            "shooters": [],
            "goalkeeper": None,
            "score": 0
        },
        
        "current_round": 0,
        "current_shooter": None,
        "current_goalkeeper": None,
        "current_team": None,
        
        "choice_task": None,
        "resolving": False,
        
        "scores": {},
        
        "distribution_admin": None,
        "distribution_method": None,
    }
    
    await update.message.reply_text(
        "⚽🥅 تم فتح التسجيل في لعبة البلنتيات!\n\n"
        "• للانضمام اكتب: دخول\n"
        "• للبدء اكتب: ابدا\n"
        "• الحد الأدنى: 2 لاعبين."
    )


# ==================================================
# دخول لاعب
# ==================================================

async def join_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return
    
    chat = update.effective_chat
    
    if chat.id not in active_penalty_games:
        return
    
    game = active_penalty_games[chat.id]
    
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
    
    await update.message.reply_text(
        f"⚽ انضم {get_player_name(user)} "
        f"(العدد: {len(game['players'])})"
    )


# ==================================================
# توزيع الفرق
# ==================================================

async def distribute_teams(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return
    
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.id not in active_penalty_games:
        return
    
    game = active_penalty_games[chat.id]
    
    if not can_manage_penalty_game(user.id):
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
    
    game["phase"] = "distribution"
    game["distribution_admin"] = user.id
    
    keyboard = [
        [
            InlineKeyboardButton(
                "🎲 عشوائي",
                callback_data=f"pen_dist:random:{chat.id}"
            ),
            InlineKeyboardButton(
                "✍️ يدوي",
                callback_data=f"pen_dist:manual:{chat.id}"
            )
        ]
    ]
    
    await update.message.reply_text(
        "🛡️ توزيع فرق مباراة البلنتيات (أحمر ضد أزرق)\n\n"
        f"يا {get_player_name(user)}، كيف تبي نوزّع اللاعبين؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================================================
# التوزيع العشوائي
# ==================================================

async def random_distribution(
    context,
    chat_id
):
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        return
    
    players = list(game["players"].values())
    random.shuffle(players)
    
    mid = len(players) // 2
    
    red_players = players[:mid]
    blue_players = players[mid:]
    
    game["phase"] = "playing"
    
    # تعيين المسددين والحراس
    if len(red_players) == 1:
        game["red_team"]["shooters"] = [p.id for p in red_players]
        game["red_team"]["goalkeeper"] = red_players[0].id
    else:
        game["red_team"]["shooters"] = [p.id for p in red_players[:-1]]
        game["red_team"]["goalkeeper"] = red_players[-1].id
    
    if len(blue_players) == 1:
        game["blue_team"]["shooters"] = [p.id for p in blue_players]
        game["blue_team"]["goalkeeper"] = blue_players[0].id
    else:
        game["blue_team"]["shooters"] = [p.id for p in blue_players[:-1]]
        game["blue_team"]["goalkeeper"] = blue_players[-1].id
    
    # بناء الرسالة
    red_shooters_names = [get_player_name(game["players"].get(pid)) for pid in game["red_team"]["shooters"]]
    red_goalkeeper_name = get_player_name(game["players"].get(game["red_team"]["goalkeeper"]))
    
    blue_shooters_names = [get_player_name(game["players"].get(pid)) for pid in game["blue_team"]["shooters"]]
    blue_goalkeeper_name = get_player_name(game["players"].get(game["blue_team"]["goalkeeper"]))
    
    text = (
        "📜 تم التوزيع العشوائي لمباراة البلنتيات ⚽🥅\n\n"
        "🔴 الفريق الأحمر:\n"
        f"🎯 المسددين: {', '.join(red_shooters_names)}\n"
        f"🛡️ الحراس: {red_goalkeeper_name}\n\n"
        "🔵 الفريق الأزرق:\n"
        f"🎯 المسددين: {', '.join(blue_shooters_names)}\n"
        f"🛡️ الحراس: {blue_goalkeeper_name}\n\n"
        "الحكم/الأدمن يكتب (ابدا) لبدء ركلات الترجيح! 🚀"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )


# ==================================================
# التوزيع اليدوي - عرض اللاعبين
# ==================================================

async def show_manual_distribution(
    context,
    chat_id
):
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        return
    
    game["phase"] = "manual_distribution"
    
    players_list = []
    for idx, player_id in enumerate(game["order"], 1):
        player = game["players"].get(player_id)
        if player:
            players_list.append(f"{idx}. {get_player_name(player)}")
    
    text = (
        "📋 توزيع اللاعبين يدوياً لمباراة البلنتيات:\n\n"
        + "\n".join(players_list) + "\n\n"
        "يرجى استخدام الأوامر التالية:\n"
        "• .احمر رقم رقم لضم اللاعبين للأحمر\n"
        "• .ازرق رقم رقم لضم اللاعبين للأزرق\n\n"
        "🛡️ لتحديد الحارس يدوياً: ضع * جنب رقمه\n"
        "مثال: .احمر 2 1* (اللاعب 1 حارس، اللاعب 2 مسدد)"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )


# ==================================================
# معالجة الأوامر اليدوية
# ==================================================

async def handle_manual_team_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return
    
    text = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    
    if chat_id not in active_penalty_games:
        return
    
    game = active_penalty_games[chat_id]
    
    if game["phase"] != "manual_distribution":
        return
    
    if not text.startswith((".احمر", ".ازرق")):
        return
    
    # منع المسافات الإضافية
    parts = text.split()
    
    if len(parts) < 2:
        return
    
    command = parts[0]
    team = "red" if command == ".احمر" else "blue"
    
    team_key = f"{team}_team"
    players_indices = []
    goalkeeper_index = None
    
    # معالجة الأرقام
    for part in parts[1:]:
        
        if "*" in part:
            goalkeeper_index = int(part.replace("*", ""))
        else:
            players_indices.append(int(part))
    
    # التحقق من صحة الأرقام
    for idx in players_indices + ([goalkeeper_index] if goalkeeper_index else []):
        
        if idx < 1 or idx > len(game["order"]):
            
            await update.message.reply_text(
                f"❌ رقم غير صحيح: {idx}"
            )
            
            return
    
    # إضافة اللاعبين
    shooters = []
    goalkeeper = None
    
    for idx in players_indices:
        player_id = game["order"][idx - 1]
        shooters.append(player_id)
    
    if goalkeeper_index:
        goalkeeper = game["order"][goalkeeper_index - 1]
    
    # إذا لم يتم تحديد حارس، نختار من المسددين
    if not goalkeeper and shooters:
        goalkeeper = shooters[-1]
        shooters = shooters[:-1]
    
    game[team_key]["shooters"] = shooters
    game[team_key]["goalkeeper"] = goalkeeper
    
    # عرض الحالة الحالية
    red_shooters_names = [get_player_name(game["players"].get(pid)) for pid in game["red_team"]["shooters"]]
    red_goalkeeper_name = get_player_name(game["players"].get(game["red_team"]["goalkeeper"])) if game["red_team"]["goalkeeper"] else "لم يتم التحديد"
    
    blue_shooters_names = [get_player_name(game["players"].get(pid)) for pid in game["blue_team"]["shooters"]]
    blue_goalkeeper_name = get_player_name(game["players"].get(game["blue_team"]["goalkeeper"])) if game["blue_team"]["goalkeeper"] else "لم يتم التحديد"
    
    # قائمة اللاعبين المتبقين
    all_assigned = set(game["red_team"]["shooters"] + game["blue_team"]["shooters"])
    if game["red_team"]["goalkeeper"]:
        all_assigned.add(game["red_team"]["goalkeeper"])
    if game["blue_team"]["goalkeeper"]:
        all_assigned.add(game["blue_team"]["goalkeeper"])
    
    remaining = [get_player_name(game["players"].get(game["order"][i])) for i in range(len(game["order"])) if game["order"][i] not in all_assigned]
    
    text = (
        "✅ تم تحديث الفريق 🔴 الأحمر:\n"
        f"🎯 المسددين: {', '.join(red_shooters_names) if red_shooters_names else 'لا أحد'}\n"
        f"🛡️ الحراس: {red_goalkeeper_name}\n\n"
        "🔵 الفريق الأزرق:\n"
        f"🎯 المسددين: {', '.join(blue_shooters_names) if blue_shooters_names else 'لا أحد'}\n"
        f"🛡️ الحراس: {blue_goalkeeper_name}\n\n"
    )
    
    if remaining:
        text += f"📌 اللاعبين المتبقين دون توزيع:\n"
        for idx, name in enumerate(remaining, 1):
            text += f"{idx}. {name}\n"
    
    await update.message.reply_text(text)
    
    # التحقق من اكتمال التوزيع
    if not remaining and game["red_team"]["goalkeeper"] and game["blue_team"]["goalkeeper"]:
        
        game["phase"] = "playing"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🎯 اكتمل التوزيع اليدوي لمباراة البلنتيات!\n\n"
                "الأدمن يكتب (ابدا) لبدء ركلات الترجيح! 🚀"
            )
        )


# ==================================================
# بدء اللعبة
# ==================================================

async def begin_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return
    
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.id not in active_penalty_games:
        return
    
    game = active_penalty_games[chat.id]
    
    if not can_manage_penalty_game(user.id):
        return
    
    if game["phase"] not in ("distribution", "manual_distribution", "playing"):
        return
    
    if not game["red_team"]["goalkeeper"] or not game["blue_team"]["goalkeeper"]:
        
        await update.message.reply_text(
            "❌ لم تكتمل عملية التوزيع بعد."
        )
        
        return
    
    game["phase"] = "playing"
    game["current_round"] = 1
    
    await start_next_round(
        context,
        chat.id
    )


# ==================================================
# بدء جولة جديدة
# ==================================================

async def start_next_round(
    context,
    chat_id
):
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        return
    
    if game["current_round"] > PENALTY_ROUNDS:
        
        await finish_penalty_game(
            context,
            chat_id
        )
        
        return
    
    # تحديد الفريق الحالي
    if game["current_round"] % 2 == 1:
        current_team = "red"
        opposite_team = "blue"
    else:
        current_team = "blue"
        opposite_team = "red"
    
    game["current_team"] = current_team
    
    # اختيار المسدد والحارس
    shooters = game[f"{current_team}_team"]["shooters"]
    shooter_idx = (game["current_round"] - 1) % len(shooters)
    shooter_id = shooters[shooter_idx]
    
    goalkeeper_id = game[f"{opposite_team}_team"]["goalkeeper"]
    
    game["current_shooter"] = shooter_id
    game["current_goalkeeper"] = goalkeeper_id
    
    shooter = game["players"].get(shooter_id)
    goalkeeper = game["players"].get(goalkeeper_id)
    
    # تحديد لون الفريق
    team_color = "🔴" if current_team == "red" else "🔵"
    team_name = "الأحمر" if current_team == "red" else "الأزرق"
    
    text = (
        f"🎮 الجولة {game['current_round']} — الركلة {((game['current_round'] - 1) // 2 + 1)} {team_color}\n\n"
        f"🎯 المسدد: {get_player_name(shooter)} {team_color} (⏳ ينتظر الاختيار)\n"
        f"🛡️ الحارس: {get_player_name(goalkeeper)} {'🔵' if current_team == 'red' else '🔴'} (⏳ ينتظر الاختيار)\n\n"
        f"اختر الزاوية من الأزرار بالأسفل:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(
                "يسار ⬅️",
                callback_data=f"pen_choice:{chat_id}:left"
            ),
            InlineKeyboardButton(
                "وسط ⬇️",
                callback_data=f"pen_choice:{chat_id}:center"
            ),
            InlineKeyboardButton(
                "يمين ➡️",
                callback_data=f"pen_choice:{chat_id}:right"
            )
        ]
    ]
    
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # حفظ معرف الرسالة
    game["round_message_id"] = message.message_id
    game["resolving"] = False
    
    # مؤقت الخيار
    game["choice_task"] = asyncio.create_task(
        penalty_choice_timeout(
            context,
            chat_id
        )
    )


# ==================================================
# اختيار الزاوية
# ==================================================

async def penalty_choice_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    query = update.callback_query
    
    try:
        
        parts = query.data.split(":")
        
        if len(parts) != 3:
            await query.answer()
            return
        
        _, chat_id_str, choice = parts
        chat_id = int(chat_id_str)
        
    except Exception:
        
        await query.answer()
        return
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        
        await query.answer(
            "❌ انتهت اللعبة.",
            show_alert=True
        )
        
        return
    
    if game["phase"] != "playing":
        
        await query.answer(
            "❌ انتهت اللعبة.",
            show_alert=True
        )
        
        return
    
    if game["resolving"]:
        
        await query.answer(
            "⏳ جاري حساب النتيجة...",
            show_alert=True
        )
        
        return
    
    # التحقق من أن الضاغط هو المسدد أو الحارس
    if query.from_user.id not in (game["current_shooter"], game["current_goalkeeper"]):
        
        await query.answer(
            "❌ انتظر، ليس دورك!",
            show_alert=True
        )
        
        return
    
    game["resolving"] = True
    
    # إلغاء المؤقت
    if game["choice_task"]:
        game["choice_task"].cancel()
        game["choice_task"] = None
    
    await query.answer(f"✅ اختيار: {choice}")
    
    # تحديد الاختيار (إذا كان من المسدد أم الحارس)
    if query.from_user.id == game["current_shooter"]:
        game["shooter_choice"] = choice
    else:
        game["goalkeeper_choice"] = choice
    
    # إذا كلاهما اختار، حل الجولة
    if "shooter_choice" in game and "goalkeeper_choice" in game:
        
        await resolve_penalty_round(
            context,
            chat_id
        )


# ==================================================
# انتهاء وقت الاختيار
# ==================================================

async def penalty_choice_timeout(
    context,
    chat_id
):
    
    try:
        
        await asyncio.sleep(CHOICE_TIME)
        
    except asyncio.CancelledError:
        
        return
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        return
    
    if game["phase"] != "playing":
        return
    
    if game["resolving"]:
        return
    
    # اختيارات عشوائية إذا لم يختر أحدهم
    if "shooter_choice" not in game:
        game["shooter_choice"] = random.choice(["left", "center", "right"])
    
    if "goalkeeper_choice" not in game:
        game["goalkeeper_choice"] = random.choice(["left", "center", "right"])
    
    game["resolving"] = True
    
    await resolve_penalty_round(
        context,
        chat_id
    )


# ==================================================
# حل جولة الركلة الحرة
# ==================================================

async def resolve_penalty_round(
    context,
    chat_id
):
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        return
    
    shooter_choice = game.get("shooter_choice")
    goalkeeper_choice = game.get("goalkeeper_choice")
    
    shooter_id = game["current_shooter"]
    goalkeeper_id = game["current_goalkeeper"]
    
    shooter = game["players"].get(shooter_id)
    goalkeeper = game["players"].get(goalkeeper_id)
    
    current_team = game["current_team"]
    team_color = "🔴" if current_team == "red" else "🔵"
    
    # التحقق من هدف
    is_goal = shooter_choice != goalkeeper_choice
    
    if is_goal:
        game[f"{current_team}_team"]["score"] += 1
        game["scores"][shooter_id] = game["scores"].get(shooter_id, 0) + 1
    
    # بناء رسالة النتيجة
    text = (
        f"🎮 الجولة {game['current_round']} — الركلة {((game['current_round'] - 1) // 2 + 1)} {team_color}\n\n"
        f"🎯 المسدد: {get_player_name(shooter)} {team_color} (✅ جاهز)\n"
        f"🛡️ الحارس: {get_player_name(goalkeeper)} {'🔵' if current_team == 'red' else '🔴'} (✅ جاهز)\n\n"
    )
    
    if is_goal:
        text += f"⚽ جول!! 🎉\n{get_player_name(shooter)} سجّل!"
    else:
        text += f"❌ لا جول!\nصدّ {get_player_name(goalkeeper)} الكورة بنجاح."
    
    # التحقق من نهاية اللعبة
    red_score = game["red_team"]["score"]
    blue_score = game["blue_team"]["score"]
    
    # إذا كان هناك فائز مؤكد
    remaining_rounds = PENALTY_ROUNDS - game["current_round"]
    
    if red_score > blue_score + remaining_rounds or blue_score > red_score + remaining_rounds:
        
        text += f"\n\n🏆 انتهت اللعبة! الفريق {'الأحمر' if red_score > blue_score else 'الأزرق'} هو الفائز!"
        
        game["phase"] = "finished"
        
        try:
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game.get("round_message_id"),
                text=text
            )
            
        except Exception:
            pass
        
        await finish_penalty_game(
            context,
            chat_id
        )
        
        return
    
    # الجولة التالية
    game["current_round"] += 1
    game["resolving"] = False
    
    # حذف الاختيارات
    game.pop("shooter_choice", None)
    game.pop("goalkeeper_choice", None)
    
    try:
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game.get("round_message_id"),
            text=text
        )
        
    except Exception:
        pass
    
    # انتظر قليلاً قبل الجولة التالية
    await asyncio.sleep(2)
    
    await start_next_round(
        context,
        chat_id
    )


# ==================================================
# نهاية اللعبة
# ==================================================

async def finish_penalty_game(
    context,
    chat_id
):
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        return
    
    if game["phase"] == "finished":
        return
    
    game["phase"] = "finished"
    
    # إلغاء المؤقت
    if game["choice_task"]:
        game["choice_task"].cancel()
    
    red_score = game["red_team"]["score"]
    blue_score = game["blue_team"]["score"]
    
    # تحديد الفائز
    if red_score > blue_score:
        winner_team = "red"
        winner_name = "الفريق الأحمر 🔴"
    elif blue_score > red_score:
        winner_team = "blue"
        winner_name = "الفريق الأزرق 🔵"
    else:
        winner_team = None
        winner_name = "تعادل 🤝"
    
    # الفائزون يأخذون نقاط
    if winner_team:
        
        winner_ids = (
            game[f"{winner_team}_team"]["shooters"] +
            [game[f"{winner_team}_team"]["goalkeeper"]]
        )
        
        for winner_id in winner_ids:
            
            add_points(winner_id, WIN_POINTS)
    
    # بناء الرسالة النهائية
    text = f"🏆 انتهت مباراة البلنتيات!\n\n"
    text += f"🔴 الفريق الأحمر: {red_score}\n"
    text += f"🔵 الفريق الأزرق: {blue_score}\n\n"
    text += f"🥇 الفائز: {winner_name}"
    
    if winner_team:
        text += f"\n🎁 حصل كل لاعب على +{WIN_POINTS} نقطة"
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=text
    )
    
    # حذف اللعبة
    active_penalty_games.pop(chat_id, None)


# ==================================================
# إنهاء اللعبة يدويًا
# ==================================================

async def end_penalty_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if chat_id not in active_penalty_games:
        return
    
    if not can_manage_penalty_game(user.id):
        return
    
    await update.message.reply_text(
        "🛑 تم إنهاء لعبة البلنتيات."
    )
    
    game = active_penalty_games.pop(chat_id, None)
    
    if not game:
        return
    
    if game["choice_task"]:
        game["choice_task"].cancel()


# ==================================================
# معالج .وزع
# ==================================================

async def handle_distribute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    if not update.message:
        return
    
    text = (update.message.text or "").strip()
    
    if text != ".وزع":
        return
    
    await distribute_teams(update, context)


# ==================================================
# معالج توزيع عشوائي/يدوي
# ==================================================

async def distribution_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    query = update.callback_query
    
    try:
        
        parts = query.data.split(":")
        
        if len(parts) != 3:
            await query.answer()
            return
        
        _, method, chat_id_str = parts
        chat_id = int(chat_id_str)
        
    except Exception:
        
        await query.answer()
        return
    
    game = active_penalty_games.get(chat_id)
    
    if not game:
        
        await query.answer(
            "❌ انتهت اللعبة.",
            show_alert=True
        )
        
        return
    
    await query.answer()
    
    if method == "random":
        
        await random_distribution(context, chat_id)
        
    elif method == "manual":
        
        await show_manual_distribution(context, chat_id)
