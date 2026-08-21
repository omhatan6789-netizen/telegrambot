import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random
import asyncio
from datetime import datetime
from collections import defaultdict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

games_data = defaultdict(lambda: {
    'state': 'waiting',
    'players': [],
    'hidden_positions': {},
    'board_size': 0,
    'boxes': [],
    'rewards': {},
    'elimination_order': [],
    'points': defaultdict(int),
    'search_order': [],
    'current_searcher_index': 0,
    'player_names': {},
    'admin_id': None,
    'bomb_victims': defaultdict(int),
    'discoveries': defaultdict(int),
})

HIDE_DURATION = 60  # ثانية
SEARCH_DURATION = 30  # ثانية

def calculate_board_size(num_players):
    """حساب حجم اللوحة بناءً على عدد اللاعبين"""
    if num_players <= 2:
        return 16
    elif num_players <= 5:
        return 20
    else:
        return 24

def distribute_rewards(num_boxes):
    """توزيع الهدايا العشوائية على المربعات"""
    rewards = {}
    
    num_bombs = max(1, num_boxes // 4)
    num_extra = max(1, num_boxes // 7)
    num_plus5 = max(1, num_boxes // 7)
    num_plus10 = max(1, num_boxes // 10)
    num_minus3 = max(1, num_boxes // 7)
    num_minus5 = max(1, num_boxes // 7)
    
    reward_list = (
        ['bomb'] * num_bombs +
        ['extra_chance'] * num_extra +
        ['plus5'] * num_plus5 +
        ['plus10'] * num_plus10 +
        ['minus3'] * num_minus3 +
        ['minus5'] * num_minus5 +
        ['empty'] * (num_boxes - sum([num_bombs, num_extra, num_plus5, num_plus10, num_minus3, num_minus5]))
    )
    
    random.shuffle(reward_list)
    
    for box_num in range(1, num_boxes + 1):
        rewards[box_num] = reward_list[box_num - 1]
    
    return rewards

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء لعبة جديدة - اكتب: غميضة"""
    text = update.message.text.strip()
    
    if text.lower() != "غميضة":
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "لاعب"
    
    if chat_id in games_data and games_data[chat_id]['state'] != 'finished':
        await update.message.reply_text("❌ هناك لعبة قيد التشغيل بالفعل!")
        return
    
    games_data[chat_id] = {
        'state': 'waiting',
        'players': [user_id],
        'hidden_positions': {},
        'board_size': 0,
        'boxes': [],
        'rewards': {},
        'elimination_order': [],
        'points': defaultdict(int),
        'search_order': [user_id],
        'current_searcher_index': 0,
        'player_names': {user_id: username},
        'admin_id': user_id,
        'bomb_victims': defaultdict(int),
        'discoveries': defaultdict(int),
    }
    
    keyboard = [
        [InlineKeyboardButton("دخول 🎮", callback_data="join_game")],
        [InlineKeyboardButton("ابدأ ▶️", callback_data="start_playing")],
        [InlineKeyboardButton("إنهاء ❌", callback_data="end_game")]
    ]
    
    await update.message.reply_text(
        f"""🚪 تم فتح التسجيل في لعبة الغميضة!

• نوع اللوحة المختار: الأرقام 🔢
• اكتب دخول للانضمام إلى اللعبة.
• عندما يكتمل اللاعبون، يكتب الأدمن ابدا لبدء اللعبة.
• الحد الأدنى لبدء اللعبة: 2 لاعبين.

👥 اللاعبون المسجلون: 1""",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الانضمام للعبة"""
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    username = query.from_user.first_name or "لاعب"
    
    await query.answer()
    
    if chat_id not in games_data:
        await query.answer("❌ لا توجد لعبة نشطة!", show_alert=True)
        return
    
    game = games_data[chat_id]
    
    if game['state'] != 'waiting':
        await query.answer("❌ اللعبة بدأت بالفعل!", show_alert=True)
        return
    
    if user_id in game['players']:
        await query.answer("⚠️ أنت مسجل بالفعل!", show_alert=True)
        return
    
    game['players'].append(user_id)
    game['player_names'][user_id] = username
    game['search_order'].append(user_id)
    
    players_list = "\n".join([f"• {game['player_names'][pid]}" for pid in game['players']])
    
    keyboard = [
        [InlineKeyboardButton("دخول 🎮", callback_data="join_game")],
        [InlineKeyboardButton("ابدأ ▶️", callback_data="start_playing")],
        [InlineKeyboardButton("إنهاء ❌", callback_data="end_game")]
    ]
    
    await query.edit_message_text(
        text=f"""🚪 تم فتح التسجيل في لعبة الغميضة!

• نوع اللوحة المختار: الأرقام 🔢
• اكتب دخول للانضمام إلى اللعبة.
• عندما يكتمل اللاعبون، يكتب الأدمن ابدا لبدء اللعبة.
• الحد الأدنى لبدء اللعبة: 2 لاعبين.

👥 اللاعبون المسجلون ({len(game['players'])}):
{players_list}""",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    await query.answer(f"✅ {username} انضم للعبة!")

async def start_playing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء مرحلة الاختباء"""
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    await query.answer()
    
    if chat_id not in games_data:
        await query.answer("❌ لا توجد لعبة!", show_alert=True)
        return
    
    game = games_data[chat_id]
    
    if game['admin_id'] != user_id:
        await query.answer("❌ فقط الأدمن يستطيع بدء اللعبة!", show_alert=True)
        return
    
    if len(game['players']) < 2:
        await query.answer("❌ يجب 2 لاعبين على الأقل!", show_alert=True)
        return
    
    game['state'] = 'hiding'
    game['board_size'] = calculate_board_size(len(game['players']))
    game['boxes'] = list(range(1, game['board_size'] + 1))
    game['rewards'] = distribute_rewards(game['board_size'])
    
    await query.delete_message()
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"""🎮 بدأت لعبة الغميضة!

📊 معلومات اللعبة:
• عدد اللاعبين: {len(game['players'])}
• عدد المربعات: {game['board_size']}
• مدة الاختباء: {HIDE_DURATION} ثانية

جاري إرسال الرسائل الخاصة..."""
    )
    
    for player_id in game['players']:
        keyboard = []
        for i in range(1, game['board_size'] + 1, 4):
            row = []
            for j in range(4):
                box_num = i + j
                if box_num <= game['board_size']:
                    row.append(InlineKeyboardButton(
                        str(box_num),
                        callback_data=f"hide:{chat_id}:{box_num}"
                    ))
            keyboard.append(row)
        
        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=f"""🫣 اختر الرقم الذي تريد الاختباء فيه

⏱️ المتبقي: {HIDE_DURATION} ثانية""",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة خاصة: {e}")
    
    context.application.create_task(hide_timer(context, chat_id))

async def hide_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """مؤقت الاختباء"""
    game = games_data[chat_id]
    await asyncio.sleep(HIDE_DURATION)
    
    for player_id in game['players']:
        if player_id not in game['hidden_positions']:
            game['hidden_positions'][player_id] = random.choice(game['boxes'])
    
    game['state'] = 'searching'
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="""😶‍🌫️ لقد اختبأ جميع اللاعبين بنجاح.

تبدأ الآن أدوار البحث! في كل دور، يختار اللاعب أحد المربعات المتاحة للبحث فيه.
💥 إذا تم العثور على لاعبين في المربع المختار، يتم استبعادهم فورًا!

🎁 تم توزيع الهدايا العشوائية في المربعات!
الهدايا المتوفرة خلف المربعات:
• 🔄 فرصة اختيار أخرى
• 💣 قنبلة (تكشف تلميحاً عن رقمك السري)
• 🎁 +5 نقاط، +10 نقاط
• 💥 -3 نقاط، -5 نقاط

🏆 تستمر الأدوار حتى يتبقى فائز واحد!"""
    )
    
    await asyncio.sleep(2)
    await start_search_turn(context, chat_id)

async def start_search_turn(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """بدء دور بحث جديد"""
    game = games_data[chat_id]
    
    active_players = [p for p in game['search_order'] if p not in game['elimination_order']]
    
    if len(active_players) <= 1:
        await end_game_session(context, chat_id)
        return
    
    current_idx = game['current_searcher_index'] % len(active_players)
    searcher_id = active_players[current_idx]
    searcher_name = game['player_names'].get(searcher_id, "لاعب")
    
    keyboard = []
    for i in range(0, len(game['boxes']), 4):
        row = []
        for j in range(4):
            if i + j < len(game['boxes']):
                box_num = game['boxes'][i + j]
                row.append(InlineKeyboardButton(
                    str(box_num),
                    callback_data=f"search:{chat_id}:{box_num}"
                ))
        keyboard.append(row)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"""🫣 تفضل يا {searcher_name} اختر مربع لكشف ما بداخله 🫣

⏱️ المتبقي: {SEARCH_DURATION} ثانية""",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    game['last_searcher_id'] = searcher_id
    context.application.create_task(search_timer(context, chat_id, searcher_id))

async def search_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, searcher_id: int):
    """مؤقت البحث"""
    game = games_data[chat_id]
    await asyncio.sleep(SEARCH_DURATION)
    
    if game.get('last_searcher_id') == searcher_id and game['state'] == 'searching':
        if game['boxes']:
            random_box = random.choice(game['boxes'])
            await process_search(context, chat_id, random_box, searcher_id)

async def process_search(context: ContextTypes.DEFAULT_TYPE, chat_id: int, box_num: int, searcher_id: int):
    """معالجة البحث وإظهار النتيجة"""
    game = games_data[chat_id]
    
    if game['state'] != 'searching':
        return
    
    searcher_name = game['player_names'].get(searcher_id, "لاعب")
    
    found_players = [p for p, pos in game['hidden_positions'].items() 
                     if pos == box_num and p not in game['elimination_order']]
    reward = game['rewards'].get(box_num, 'empty')
    
    result_text = f"""🎯 قام اللاعب {searcher_name} بالبحث في المربع {box_num}:\n"""
    
    if found_players:
        found_names = ", ".join([game['player_names'].get(p, "لاعب") for p in found_players])
        result_text += f"""
💥 تم كشف المخبأ!
تم العثور على اللاعبين: {found_names} ❌ (تم استبعادهم من اللعبة)."""
        
        game['elimination_order'].extend(found_players)
        game['discoveries'][searcher_id] += len(found_players)
    else:
        result_text += "\n💨 كان المربع فارغاً! لم يتم العثور على أحد."
        
        if reward == 'bomb':
            hidden_box = game['hidden_positions'].get(searcher_id, 1)
            is_even = hidden_box % 2 == 0
            result_text += f"\n💣 انفجرت قنبلة!\nتم كشف تلميح للمجموعة عن موقع اللاعب {searcher_name}: الرقم السري الذي يختبئ فيه هو رقم {'زوجي' if is_even else 'فردي'}!"
            game['bomb_victims'][searcher_id] += 1
            game['points'][searcher_id] -= 5
        
        elif reward == 'extra_chance':
            result_text += f"\n🔄 حصل اللاعب {searcher_name} على هدية فرصة إضافية!\nيمكنه الاختيار واللعب مرة أخرى في هذا الدور."
            game['current_searcher_index'] -= 1
        
        elif reward == 'plus5':
            result_text += f"\n🎁 حصل اللاعب {searcher_name} على +5 نقاط!"
            game['points'][searcher_id] += 5
        
        elif reward == 'plus10':
            result_text += f"\n🎁 حصل اللاعب {searcher_name} على +10 نقاط!"
            game['points'][searcher_id] += 10
        
        elif reward == 'minus3':
            result_text += f"\n💥 خصم 3 نقاط من اللاعب {searcher_name}."
            game['points'][searcher_id] -= 3
        
        elif reward == 'minus5':
            result_text += f"\n💥 خصم 5 نقاط من اللاعب {searcher_name}."
            game['points'][searcher_id] -= 5
    
    await context.bot.send_message(chat_id=chat_id, text=result_text)
    
    if box_num in game['boxes']:
        game['boxes'].remove(box_num)
    
    game['current_searcher_index'] += 1
    
    active_players = [p for p in game['search_order'] if p not in game['elimination_order']]
    
    if len(active_players) <= 1:
        await end_game_session(context, chat_id)
    else:
        await asyncio.sleep(2)
        await start_search_turn(context, chat_id)

async def end_game_session(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """إنهاء اللعبة وإظهار النتائج"""
    game = games_data[chat_id]
    game['state'] = 'finished'
    
    active_players = [p for p in game['search_order'] if p not in game['elimination_order']]
    winner_id = active_players[0] if active_players else None
    winner_name = game['player_names'].get(winner_id, "لا أحد") if winner_id else "لا أحد"
    
    stats_text = f"""🏆 انتهت لعبة الغميضة!

🥇 {winner_name} — الفائز"""
    
    if game['discoveries']:
        top_discoverer = max(game['discoveries'].items(), key=lambda x: x[1])
        stats_text += f"\n\n🔎 أكثر لاعب اكتشف مخابئ: {game['player_names'].get(top_discoverer[0], 'لاعب')} ({top_discoverer[1]} اكتشافات)\n(+5 نقاط إضافية)"
        game['points'][top_discoverer[0]] += 5
    
    if game['bomb_victims']:
        top_bomb = max(game['bomb_victims'].items(), key=lambda x: x[1])
        stats_text += f"\n💣 أكثر لاعب أصابته القنابل: {game['player_names'].get(top_bomb[0], 'لاعب')} ({top_bomb[1]} قنابل)\n(-5 نقاط إضافية)"
        game['points'][top_bomb[0]] -= 5
    
    stats_text += f"\n\n📊 النقاط النهائية:\n"
    sorted_points = sorted(game['points'].items(), key=lambda x: x[1], reverse=True)
    for idx, (pid, points) in enumerate(sorted_points, 1):
        stats_text += f"{idx}. {game['player_names'].get(pid, 'لاعب')}: {points} نقاط\n"
    
    await context.bot.send_message(chat_id=chat_id, text=stats_text)

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنهاء اللعبة"""
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    await query.answer()
    
    if chat_id not in games_data:
        await query.edit_message_text("❌ لا توجد لعبة نشطة!")
        return
    
    game = games_data[chat_id]
    
    if game['admin_id'] != user_id:
        await query.answer("❌ فقط الأدمن يستطيع إنهاء اللعبة!", show_alert=True)
        return
    
    game['state'] = 'finished'
    await query.edit_message_text("❌ تم إنهاء اللعبة من قبل الأدمن!")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج عام للأزرار"""
    query = update.callback_query
    data = query.data
    
    await query.answer()
    
    if data == "join_game":
        await join_game(update, context)
    elif data == "start_playing":
        await start_playing(update, context)
    elif data == "end_game":
        await end_game(update, context)
    elif data.startswith("hide:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        box_num = int(parts[2])
        user_id = query.from_user.id
        game = games_data[chat_id]
        game['hidden_positions'][user_id] = box_num
        await query.edit_message_text(f"✅ تم اختيارك للمربع {box_num}")
    elif data.startswith("search:"):
        parts = data.split(":")
        chat_id = int(parts[1])
        box_num = int(parts[2])
        searcher_id = query.from_user.id
        game = games_data[chat_id]
        game['last_searcher_id'] = None
        await process_search(context, chat_id, box_num, searcher_id)

def setup_game_handlers(app: Application):
    """تسجيل معالجات اللعبة في التطبيق"""
    from telegram.ext import MessageHandler, filters
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
