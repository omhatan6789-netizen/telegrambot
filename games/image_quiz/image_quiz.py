import asyncio
import io
import json
import os
import random
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List, Tuple

from PIL import Image

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes, filters


# =========================================================
# الإعدادات
# =========================================================

GAME_NAME = "توقع الصورة"

MIN_PLAYERS = 2

MIN_TARGET_POINTS = 5
MAX_TARGET_POINTS = 15

ROUND_FIRST_REWARD = 60
ROUND_SECOND_REWARD = 45
ROUND_THIRD_REWARD = 30
ROUND_FINAL_REWARD = 15

FINAL_GUESS_SECONDS = 5

# كل 20 ثانية ننتقل لصورة أقرب/أبعد
REVEAL_INTERVAL = 20

# مكان ملف الأسئلة
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")


# =========================================================
# الصلاحيات
# =========================================================

try:
    from permissions import get_permission_level
except Exception:
    get_permission_level = None


try:
    from handlers.roles import (
        is_primary_developer,
        is_secondary_developer,
        get_rank,
    )
except Exception:
    is_primary_developer = None
    is_secondary_developer = None
    get_rank = None


try:
    from handlers.points import add_points
except Exception:
    add_points = None


# =========================================================
# الحالات
# =========================================================

@dataclass
class ImagePlayer:
    user_id: int
    name: str
    game_points: int = 0
    original_points: int = 0


@dataclass
class ImageQuizState:
    chat_id: int
    host_id: int
    host_name: str

    players: Dict[int, ImagePlayer] = field(default_factory=dict)

    target_points: Optional[int] = None

    started: bool = False
    finished: bool = False

    current_round: int = 0

    current_question: Optional[dict] = None

    # رسالة اللوحة
    board_message_id: Optional[int] = None

    # رسالة الصورة
    image_message_id: Optional[int] = None

    # رسالة النتائج بعد الجولة
    result_message_id: Optional[int] = None

    # هل الجولة تنتظر .كمل؟
    waiting_continue: bool = False

    # هل تم العثور على الإجابة؟
    answer_locked: bool = False

    # وقت بداية الجولة
    round_started_at: Optional[float] = None

    # المرحلة الحالية:
    # 0 = مقربة جدًا
    # 1 = بعد 20 ثانية
    # 2 = بعد 40 ثانية
    # 3 = الصورة كاملة
    reveal_stage: int = 0

    # مهمة التوقيت
    round_task: Optional[asyncio.Task] = None

    # هل نحن في آخر 5 ثواني؟
    final_guess_phase: bool = False

    # اللاعبون الذين خرجوا أثناء القيم
    eliminated_players: Set[int] = field(default_factory=set)


IMAGE_QUIZZES: Dict[int, ImageQuizState] = {}


# =========================================================
# أدوات عامة
# =========================================================

def _get_rank_level(user_id: int) -> int:
    """
    يحاول استخدام نظام الصلاحيات الموجود في المشروع.
    """

    # Dev
    try:
        if is_primary_developer and is_primary_developer(user_id):
            return 6
    except Exception:
        pass

    try:
        if is_secondary_developer and is_secondary_developer(user_id):
            return 6
    except Exception:
        pass

    # permissions.py
    try:
        if get_permission_level:
            result = get_permission_level(user_id)

            if hasattr(result, "__await__"):
                # الدالة المفترض أنها sync في مشروعك.
                # لو كانت async لن نعتمد عليها هنا.
                return 0

            if isinstance(result, int):
                return result
    except Exception:
        pass

    # roles.py
    try:
        if get_rank:
            rank = get_rank(user_id)

            if isinstance(rank, int):
                return rank

            rank_levels = {
                "عضو": 0,
                "مميز": 1,
                "ادمن": 2,
                "ادمن اساسي": 3,
                "نائب المالك": 4,
                "المالك": 5,
                "Dev": 6,
            }

            return rank_levels.get(str(rank), 0)
    except Exception:
        pass

    return 0


def _is_admin(user_id: int) -> bool:
    return _get_rank_level(user_id) >= 2


def _is_developer(user_id: int) -> bool:
    return _get_rank_level(user_id) >= 6


def _is_controller(user_id: int) -> bool:
    """
    في هذه اللعبة أي أدمن يقدر يتحكم.
    """
    return _is_admin(user_id)


def _ensure_group(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.type in (
        "group",
        "supergroup",
    ))


def _player_name(user) -> str:
    if getattr(user, "first_name", None):
        return user.first_name

    if getattr(user, "username", None):
        return f"@{user.username}"

    return str(user.id)


def _normalize_text(text: str) -> str:
    """
    تطبيع الإجابة حتى نتعامل مع اختلافات الكتابة.
    """

    if not text:
        return ""

    text = str(text).strip().lower()

    # إزالة التشكيل
    text = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # توحيد المسافات
    text = re.sub(r"\s+", " ", text)

    # إزالة بعض علامات الترقيم
    text = re.sub(r"[.!؟?,،:;؛\"'`_\-]+", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


def _question_answers(question: dict) -> Set[str]:
    answers = set()

    answer = question.get("answer")

    if answer:
        answers.add(_normalize_text(answer))

    alternatives = question.get("alternative_answers", [])

    if isinstance(alternatives, str):
        alternatives = [alternatives]

    for alt in alternatives:
        if alt:
            answers.add(_normalize_text(alt))

    return answers


def _is_correct_answer(question: dict, text: str) -> bool:
    normalized = _normalize_text(text)

    if not normalized:
        return False

    return normalized in _question_answers(question)


# =========================================================
# تحميل الأسئلة
# =========================================================

def load_questions() -> List[dict]:
    if not os.path.exists(QUESTIONS_FILE):
        return []

    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            return []

        valid = []

        for question in data:
            if not isinstance(question, dict):
                continue

            if not question.get("image"):
                continue

            if not question.get("answer"):
                continue

            valid.append(question)

        return valid

    except Exception:
        return []


def choose_question(state: ImageQuizState) -> Optional[dict]:
    questions = load_questions()

    if not questions:
        return None

    # نحاول عدم تكرار نفس الصورة في نفس القيم.
    used_ids = set()

    # نخزنها مؤقتًا في state إذا احتجنا.
    used = getattr(state, "_used_questions", set())

    available = [
        q for q in questions
        if str(q.get("id", "")) not in used
    ]

    if not available:
        used.clear()
        available = questions[:]

    question = random.choice(available)

    used.add(str(question.get("id", "")))
    state._used_questions = used

    return question


# =========================================================
# بناء لوحة اللاعبين
# =========================================================

def build_board_text(state: ImageQuizState) -> str:
    lines = [
        f"🖼️ *{GAME_NAME}*",
        "",
    ]

    if state.started:
        lines.append(f"🎯 نقاط الفوز: *{state.target_points}*")
    else:
        if state.target_points:
            lines.append(f"🎯 نقاط الفوز: *{state.target_points}*")
        else:
            lines.append("🎯 نقاط الفوز: *غير محددة*")

    lines.append("")

    if state.players:
        lines.append("👥 *اللاعبون:*")

        sorted_players = list(state.players.values())

        # أثناء اللعب نرتب حسب نقاط القيم
        if state.started:
            sorted_players.sort(
                key=lambda p: (-p.game_points, p.name)
            )

        for index, player in enumerate(sorted_players, 1):
            lines.append(
                f"{index}. {player.name} — {player.game_points} نقطة"
            )
    else:
        lines.append("👥 *اللاعبون:* لا يوجد لاعبين")

    lines.append("")

    if not state.started:
        lines.append("⏳ بانتظار بدء القيم...")
    elif state.waiting_continue:
        lines.append("⏸️ الأدمن يكتب `.كمل` للجولة التالية.")

    return "\n".join(lines)


async def update_board(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
):
    if not state.board_message_id:
        return

    try:
        await context.bot.edit_message_text(
            chat_id=state.chat_id,
            message_id=state.board_message_id,
            text=build_board_text(state),
            parse_mode="Markdown",
        )
    except Exception:
        pass


# =========================================================
# الصور
# =========================================================

def _get_image_path(question: dict) -> Optional[str]:
    image_path = question.get("image")

    if not image_path:
        return None

    if os.path.isabs(image_path):
        return image_path

    return os.path.join(BASE_DIR, image_path)


def _crop_zoom_image(
    image_path: str,
    stage: int,
) -> Optional[io.BytesIO]:
    """
    stage:
        0 = مقربة جدًا
        1 = أقرب قليلًا
        2 = أبعد
        3 = كاملة
    """

    try:
        image = Image.open(image_path).convert("RGB")

        width, height = image.size

        # النسب المقصودة:
        # البداية جزء صغير جدًا من الصورة
        crop_ratios = {
            0: 0.30,
            1: 0.52,
            2: 0.72,
            3: 1.00,
        }

        ratio = crop_ratios.get(stage, 1.0)

        if ratio < 1:
            crop_width = int(width * ratio)
            crop_height = int(height * ratio)

            left = max(0, (width - crop_width) // 2)
            top = max(0, (height - crop_height) // 2)

            right = min(width, left + crop_width)
            bottom = min(height, top + crop_height)

            image = image.crop(
                (left, top, right, bottom)
            )

        # نعيد تكبير الجزء المقصوص إلى حجم مناسب.
        image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        output.name = "image.jpg"

        image.save(
            output,
            format="JPEG",
            quality=92,
        )

        output.seek(0)

        return output

    except Exception:
        return None


async def send_or_edit_image(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
    stage: int,
):
    question = state.current_question

    if not question:
        return False

    image_path = _get_image_path(question)

    if not image_path or not os.path.exists(image_path):
        return False

    image_bytes = _crop_zoom_image(
        image_path,
        stage,
    )

    if not image_bytes:
        return False

    state.reveal_stage = stage

    if stage == 0:
        reward_text = "💰 الجائزة الحالية: +60 نقطة"
        time_text = "⏱️ أول 20 ثانية"
    elif stage == 1:
        reward_text = "💰 الجائزة الحالية: +45 نقطة"
        time_text = "⏱️ من 20 إلى 40 ثانية"
    elif stage == 2:
        reward_text = "💰 الجائزة الحالية: +30 نقطة"
        time_text = "⏱️ من 40 إلى 60 ثانية"
    else:
        reward_text = "💰 الجائزة: +15 نقطة"
        time_text = "⏱️ آخر 5 ثوانٍ"

    category = question.get("category", "عام")

    caption = (
        f"🖼️ *{GAME_NAME}* — الجولة {state.current_round}\n\n"
        f"🏷️ التصنيف: {category}\n"
        f"{reward_text}\n"
        f"{time_text}\n\n"
        "✍️ اكتب إجابتك في القروب!"
    )

    try:
        if state.image_message_id:
            message = await context.bot.edit_message_media(
                chat_id=state.chat_id,
                message_id=state.image_message_id,
                media=InputMediaPhoto(
                    media=image_bytes,
                    caption=caption,
                    parse_mode="Markdown",
                ),
            )
        else:
            message = await context.bot.send_photo(
                chat_id=state.chat_id,
                photo=image_bytes,
                caption=caption,
                parse_mode="Markdown",
            )

            state.image_message_id = message.message_id

        return True

    except Exception:
        return False


# =========================================================
# بدء الجولة
# =========================================================

async def start_round(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
):
    if state.finished:
        return

    if len(state.players) < MIN_PLAYERS:
        state.waiting_continue = True

        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                f"⚠️ ما يمدي تبدأ الجولة.\n\n"
                f"لازم يكون فيه {MIN_PLAYERS} لاعبين على الأقل."
            ),
        )

        return

    question = choose_question(state)

    if not question:
        state.waiting_continue = True

        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                "❌ ما لقيت أسئلة صور في `questions.json`.\n\n"
                "أضف الأسئلة والصور أولًا."
            ),
            parse_mode="Markdown",
        )

        return

    state.current_round += 1
    state.current_question = question
    state.answer_locked = False
    state.waiting_continue = False
    state.final_guess_phase = False
    state.round_started_at = asyncio.get_running_loop().time()
    state.image_message_id = None

    await send_or_edit_image(
        context,
        state,
        0,
    )

    # تحديث اللوحة
    await update_board(context, state)

    if state.round_task:
        try:
            state.round_task.cancel()
        except Exception:
            pass

    state.round_task = asyncio.create_task(
        run_round_timer(context, state)
    )


# =========================================================
# مؤقت الجولة
# =========================================================

async def run_round_timer(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
):
    try:
        # أول 20 ثانية
        await asyncio.sleep(20)

        if state.answer_locked or state.finished:
            return

        await send_or_edit_image(
            context,
            state,
            1,
        )

        # 20 ثانية أخرى
        await asyncio.sleep(20)

        if state.answer_locked or state.finished:
            return

        await send_or_edit_image(
            context,
            state,
            2,
        )

        # 20 ثانية أخرى
        await asyncio.sleep(20)

        if state.answer_locked or state.finished:
            return

        # الصورة كاملة
        state.final_guess_phase = True

        await send_or_edit_image(
            context,
            state,
            3,
        )

        await context.bot.send_message(
            chat_id=state.chat_id,
            text=(
                "⏱️ *آخر 5 ثواني!*\n"
                "🖼️ الصورة كاملة الآن.\n\n"
                "💰 الإجابة الصحيحة الآن = +15 نقطة أصلية."
            ),
            parse_mode="Markdown",
        )

        # آخر 5 ثواني
        await asyncio.sleep(FINAL_GUESS_SECONDS)

        if state.answer_locked or state.finished:
            return

        # لم يجب أحد
        await finish_round_without_answer(
            context,
            state,
        )

    except asyncio.CancelledError:
        return

    except Exception:
        return


# =========================================================
# نهاية الجولة بدون إجابة
# =========================================================

async def finish_round_without_answer(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
):
    if state.finished:
        return

    state.answer_locked = True
    state.waiting_continue = True
    state.final_guess_phase = False

    question = state.current_question or {}

    answer = question.get(
        "answer",
        "غير معروفة",
    )

    await context.bot.send_message(
        chat_id=state.chat_id,
        text=(
            f"⏱️ انتهى وقت الجولة {state.current_round}.\n\n"
            f"🎯 الإجابة: *{answer}*\n\n"
            "❌ ما أحد جاوب بشكل صحيح.\n\n"
            "⏸️ الأدمن يكتب `.كمل` للجولة التالية."
        ),
        parse_mode="Markdown",
    )

    await update_board(context, state)


# =========================================================
# معالجة الإجابة
# =========================================================

async def check_image_quiz_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    ترجع True إذا تعاملت اللعبة مع الرسالة.
    """

    if not update.effective_message:
        return False

    if not update.effective_chat:
        return False

    if update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return False

    state = IMAGE_QUIZZES.get(update.effective_chat.id)

    if not state:
        return False

    if not state.started:
        return False

    if state.finished:
        return False

    if state.answer_locked:
        return False

    if not state.current_question:
        return False

    user = update.effective_user

    if not user:
        return False

    user_id = user.id

    # اللاعب لازم يكون داخل القيم
    player = state.players.get(user_id)

    if not player:
        return False

    # لا نقبل إجابات اللاعبين الخارجين
    if user_id in state.eliminated_players:
        return False

    text = update.effective_message.text

    if not text:
        return False

    # لا نعترض على أوامر اللعبة
    stripped = text.strip()

    game_commands = {
        "دخول",
        "خروج",
        ".ابدا",
        ".كمل",
        ".انهاء",
        ".اعدادات",
        ".اضافة",
        "توقع الصورة",
    }

    if stripped in game_commands:
        return False

    if not _is_correct_answer(
        state.current_question,
        text,
    ):
        return False

    # الإجابة صحيحة
    state.answer_locked = True
    state.final_guess_phase = False

    # إلغاء المؤقت
    if state.round_task:
        try:
            state.round_task.cancel()
        except Exception:
            pass

        state.round_task = None

    # حساب الجائزة حسب الوقت
    now = asyncio.get_running_loop().time()

    elapsed = 0

    if state.round_started_at:
        elapsed = now - state.round_started_at

    if elapsed < 20:
        original_reward = ROUND_FIRST_REWARD
    elif elapsed < 40:
        original_reward = ROUND_SECOND_REWARD
    elif elapsed < 60:
        original_reward = ROUND_THIRD_REWARD
    else:
        original_reward = ROUND_FINAL_REWARD

    # +1 نقطة قيم
    player.game_points += 1

    # النقاط الأصلية
    player.original_points += original_reward

    question = state.current_question

    answer = question.get(
        "answer",
        "غير معروفة",
    )

    # اسم الفائز في الجولة
    winner_name = player.name

    await context.bot.send_message(
        chat_id=state.chat_id,
        text=(
            f"✅ *إجابة صحيحة!*\n\n"
            f"👤 اللاعب: {winner_name}\n"
            f"🎯 الإجابة: *{answer}*\n\n"
            f"⭐ نقاط القيم: +1\n"
            f"💰 النقاط الأصلية: +{original_reward}\n"
        ),
        parse_mode="Markdown",
    )

    # إضافة النقاط الأصلية إلى نظام البوت
    await _add_original_points(
        user_id,
        original_reward,
    )

    # تحديث اللوحة
    await update_board(context, state)

    # هل وصل لنقاط الفوز؟
    if (
        state.target_points is not None
        and player.game_points >= state.target_points
    ):
        await finish_game(
            context,
            state,
            winner_id=user_id,
        )

        return True

    # الجولة انتهت وننتظر .كمل
    state.waiting_continue = True

    await context.bot.send_message(
        chat_id=state.chat_id,
        text="⏸️ الأدمن يكتب `.كمل` للجولة التالية.",
    )

    await update_board(context, state)

    return True


# =========================================================
# إضافة النقاط الأصلية
# =========================================================

async def _add_original_points(
    user_id: int,
    amount: int,
):
    if amount <= 0:
        return

    if not add_points:
        return

    try:
        result = add_points(
            user_id,
            amount,
        )

        if hasattr(result, "__await__"):
            await result

    except Exception:
        pass


# =========================================================
# بدء إنشاء اللعبة
# =========================================================

async def start_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    user = update.effective_user

    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    chat_id = update.effective_chat.id

    if chat_id in IMAGE_QUIZZES:
        await update.effective_message.reply_text(
            "⚠️ فيه قيم توقع الصورة شغال أو مجهز هنا بالفعل."
        )
        return

    state = ImageQuizState(
        chat_id=chat_id,
        host_id=user.id,
        host_name=_player_name(user),
    )

    IMAGE_QUIZZES[chat_id] = state

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚙️ الإعدادات",
                callback_data="iq:settings",
            )
        ]
    ])

    message = await update.effective_message.reply_text(
        (
            "🖼️ *توقع الصورة!*\n\n"
            "🎮 تم إنشاء القيم.\n\n"
            "👥 اكتب `دخول` للمشاركة.\n"
            "🚪 اكتب `خروج` للخروج.\n\n"
            "⚙️ الأدمن يكتب `.اعدادات` لاختيار نقاط الفوز.\n"
            "▶️ وبعدها أي أدمن يقدر يكتب `.ابدا` للبدء.\n\n"
            "⚠️ الحد الأدنى للبدء: لاعبين."
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    state.board_message_id = message.message_id


# =========================================================
# دخول
# =========================================================

async def join_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    chat_id = update.effective_chat.id
    state = IMAGE_QUIZZES.get(chat_id)

    if not state:
        return

    if state.started:
        await update.effective_message.reply_text(
            "❌ القيم بدأ بالفعل، ما تقدر تدخل الآن."
        )
        return

    user = update.effective_user

    if not user:
        return

    if user.id in state.players:
        await update.effective_message.reply_text(
            "⚠️ أنت داخل القيم بالفعل."
        )
        return

    player = ImagePlayer(
        user_id=user.id,
        name=_player_name(user),
    )

    state.players[user.id] = player

    await update.effective_message.reply_text(
        f"✅ دخل {player.name} القيم!\n"
        f"👥 عدد اللاعبين: {len(state.players)}"
    )

    await update_board(
        context,
        state,
    )


# =========================================================
# خروج
# =========================================================

async def leave_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    chat_id = update.effective_chat.id
    state = IMAGE_QUIZZES.get(chat_id)

    if not state:
        return

    user = update.effective_user

    if not user:
        return

    player = state.players.get(user.id)

    if not player:
        await update.effective_message.reply_text(
            "⚠️ أنت مو داخل القيم."
        )
        return

    # قبل البداية
    if not state.started:
        del state.players[user.id]

        await update.effective_message.reply_text(
            f"🚪 خرج {player.name} من القيم."
        )

        await update_board(
            context,
            state,
        )

        return

    # أثناء القيم
    state.eliminated_players.add(user.id)
    del state.players[user.id]

    await update.effective_message.reply_text(
        f"🚪 خرج {player.name} من القيم.\n\n"
        "📊 تم تحديث لوحة اللاعبين."
    )

    # إذا بقي أقل من لاعبين
    if len(state.players) < MIN_PLAYERS:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ عدد اللاعبين أصبح أقل من لاعبين.\n"
                "لن يتمكن القيم من بدء جولة جديدة حتى يعود العدد إلى 2."
            ),
        )

    await update_board(
        context,
        state,
    )


# =========================================================
# .اضافة
# =========================================================

async def add_image_quiz_player(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    user = update.effective_user

    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    state = IMAGE_QUIZZES.get(
        update.effective_chat.id
    )

    if not state:
        await update.effective_message.reply_text(
            "❌ ما فيه قيم توقع الصورة."
        )
        return

    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text(
            "❌ استخدم `.اضافة` بالرد على رسالة الشخص اللي تبيه يدخل القيم."
        )
        return

    target = update.effective_message.reply_to_message.from_user

    if not target:
        await update.effective_message.reply_text(
            "❌ ما قدرت أحدد الشخص."
        )
        return

    if target.id in state.players:
        await update.effective_message.reply_text(
            "⚠️ هذا الشخص داخل القيم بالفعل."
        )
        return

    if target.id in state.eliminated_players:
        state.eliminated_players.discard(target.id)

    player = ImagePlayer(
        user_id=target.id,
        name=_player_name(target),
    )

    state.players[target.id] = player

    await update.effective_message.reply_text(
        f"➕ تمت إضافة {player.name} إلى القيم."
    )

    await update_board(
        context,
        state,
    )


# =========================================================
# الإعدادات
# =========================================================

def settings_keyboard() -> InlineKeyboardMarkup:
    rows = []

    current = []

    for number in range(
        MIN_TARGET_POINTS,
        MAX_TARGET_POINTS + 1,
    ):
        current.append(
            InlineKeyboardButton(
                str(number),
                callback_data=f"iq:points:{number}",
            )
        )

        if len(current) == 6:
            rows.append(current)
            current = []

    if current:
        rows.append(current)

    return InlineKeyboardMarkup(rows)


async def image_quiz_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    user = update.effective_user

    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    state = IMAGE_QUIZZES.get(
        update.effective_chat.id
    )

    if not state:
        await update.effective_message.reply_text(
            "❌ ما فيه قيم توقع الصورة."
        )
        return

    if state.started:
        await update.effective_message.reply_text(
            "❌ ما تقدر تغير الإعدادات بعد بدء القيم."
        )
        return

    current = (
        str(state.target_points)
        if state.target_points
        else "غير محددة"
    )

    await update.effective_message.reply_text(
        (
            "⚙️ *إعدادات توقع الصورة!*\n\n"
            f"🎯 نقاط الفوز الحالية: *{current}*\n\n"
            "اختر عدد النقاط المطلوبة للفوز:"
        ),
        parse_mode="Markdown",
        reply_markup=settings_keyboard(),
    )


# =========================================================
# .ابدا
# =========================================================

async def begin_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    user = update.effective_user

    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    state = IMAGE_QUIZZES.get(
        update.effective_chat.id
    )

    if not state:
        await update.effective_message.reply_text(
            "❌ ما فيه قيم توقع الصورة."
        )
        return

    if state.started:
        await update.effective_message.reply_text(
            "⚠️ القيم بدأ بالفعل."
        )
        return

    if state.target_points is None:
        await update.effective_message.reply_text(
            "⚠️ حدد نقاط الفوز أولًا عن طريق `.اعدادات`."
        )
        return

    if len(state.players) < MIN_PLAYERS:
        await update.effective_message.reply_text(
            f"⚠️ لازم يدخل على الأقل {MIN_PLAYERS} لاعبين."
        )
        return

    state.started = True
    state.current_round = 0
    state.waiting_continue = False

    await update.effective_message.reply_text(
        (
            "🚀 *بدأ قيم توقع الصورة!*\n\n"
            f"🎯 نقاط الفوز: *{state.target_points}*\n"
            f"👥 عدد اللاعبين: *{len(state.players)}*\n\n"
            "🖼️ الجولة الأولى تبدأ الآن!"
        ),
        parse_mode="Markdown",
    )

    await update_board(
        context,
        state,
    )

    await start_round(
        context,
        state,
    )


# =========================================================
# .كمل
# =========================================================

async def continue_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    user = update.effective_user

    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    state = IMAGE_QUIZZES.get(
        update.effective_chat.id
    )

    if not state:
        return

    if not state.started:
        await update.effective_message.reply_text(
            "⚠️ القيم ما بدأ."
        )
        return

    if not state.waiting_continue:
        await update.effective_message.reply_text(
            "⚠️ ما فيه جولة تنتظر `.كمل` حاليًا."
        )
        return

    if len(state.players) < MIN_PLAYERS:
        await update.effective_message.reply_text(
            f"⚠️ لازم يبقى على الأقل {MIN_PLAYERS} لاعبين."
        )
        return

    await start_round(
        context,
        state,
    )


# =========================================================
# .انهاء
# =========================================================

async def end_image_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not _ensure_group(update):
        return

    user = update.effective_user

    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text(
            "❌ هذا الأمر للأدمن فقط."
        )
        return

    state = IMAGE_QUIZZES.get(
        update.effective_chat.id
    )

    if not state:
        await update.effective_message.reply_text(
            "❌ ما فيه قيم توقع الصورة."
        )
        return

    await finish_game(
        context,
        state,
        winner_id=None,
        manually=True,
    )


# =========================================================
# نهاية القيم
# =========================================================

async def finish_game(
    context: ContextTypes.DEFAULT_TYPE,
    state: ImageQuizState,
    winner_id: Optional[int] = None,
    manually: bool = False,
):
    if state.finished:
        return

    state.finished = True

    # إلغاء المؤقت
    if state.round_task:
        try:
            state.round_task.cancel()
        except Exception:
            pass

        state.round_task = None

    # بناء النتائج
    players = list(state.players.values())

    players.sort(
        key=lambda p: (
            -p.game_points,
            -p.original_points,
            p.name,
        )
    )

    if manually:
        title = "🛑 تم إنهاء قيم توقع الصورة!"

        lines = [
            title,
            "",
            "📊 *النتائج الحالية:*",
        ]

        if players:
            for index, player in enumerate(players, 1):
                lines.append(
                    f"{index}. {player.name} — "
                    f"{player.game_points} نقطة"
                )
        else:
            lines.append("لا يوجد لاعبين.")

        lines.append("")
        lines.append("💰 *النقاط الأصلية المكتسبة:*")

        if players:
            for player in players:
                if player.original_points > 0:
                    lines.append(
                        f"👤 {player.name} — "
                        f"+{player.original_points} نقطة"
                    )
        else:
            lines.append("لا يوجد.")

        await context.bot.send_message(
            chat_id=state.chat_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )

    else:
        winner = None

        if winner_id is not None:
            winner = state.players.get(winner_id)

        if winner is None and players:
            winner = players[0]

        lines = [
            "🏆 *انتهى القيم!*",
            "",
        ]

        if winner:
            lines.extend([
                f"👑 *الفائز: {winner.name}*",
                "",
            ])

        lines.append("📊 *النتائج النهائية:*")

        medals = ["🥇", "🥈", "🥉"]

        for index, player in enumerate(players):
            medal = medals[index] if index < 3 else f"{index + 1}."
            lines.append(
                f"{medal} {player.name} — "
                f"{player.game_points} نقطة"
            )

        lines.extend([
            "",
            "💰 *النقاط المكتسبة:*",
        ])

        for player in players:
            if player.original_points > 0:
                lines.append(
                    f"👤 {player.name} — "
                    f"+{player.original_points} نقطة"
                )

        await context.bot.send_message(
            chat_id=state.chat_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )

    # إزالة اللعبة
    IMAGE_QUIZZES.pop(
        state.chat_id,
        None,
    )


# =========================================================
# Callback Query
# =========================================================

async def image_quiz_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    if not data.startswith("iq:"):
        return

    chat = query.message.chat if query.message else None

    if not chat:
        return

    state = IMAGE_QUIZZES.get(chat.id)

    if not state:
        await query.answer(
            "القيم غير موجود.",
            show_alert=True,
        )
        return

    user = query.from_user

    # فتح الإعدادات
    if data == "iq:settings":
        if not _is_admin(user.id):
            await query.answer(
                "هذا الخيار للأدمن فقط.",
                show_alert=True,
            )
            return

        if state.started:
            await query.answer(
                "لا يمكن تغيير الإعدادات بعد البداية.",
                show_alert=True,
            )
            return

        await query.message.reply_text(
            (
                "⚙️ *إعدادات توقع الصورة!*\n\n"
                "🎯 اختر نقاط الفوز:"
            ),
            parse_mode="Markdown",
            reply_markup=settings_keyboard(),
        )

        return

    # اختيار نقاط الفوز
    if data.startswith("iq:points:"):
        if not _is_admin(user.id):
            await query.answer(
                "هذا الخيار للأدمن فقط.",
                show_alert=True,
            )
            return

        if state.started:
            await query.answer(
                "القيم بدأ بالفعل.",
                show_alert=True,
            )
            return

        try:
            points = int(
                data.split(":")[-1]
            )
        except Exception:
            await query.answer(
                "قيمة غير صحيحة.",
                show_alert=True,
            )
            return

        if not (
            MIN_TARGET_POINTS
            <= points
            <= MAX_TARGET_POINTS
        ):
            await query.answer(
                "النقاط يجب أن تكون من 5 إلى 15.",
                show_alert=True,
            )
            return

        state.target_points = points

        await query.answer(
            f"تم تحديد نقاط الفوز: {points}",
            show_alert=False,
        )

        try:
            await query.message.edit_text(
                (
                    "⚙️ *إعدادات توقع الصورة!*\n\n"
                    f"🎯 نقاط الفوز: *{points}*\n\n"
                    "تم حفظ الإعدادات."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await update_board(
            context,
            state,
        )

        return


# =========================================================
# فلتر اللعبة
# =========================================================

class ImageQuizActiveFilter(filters.MessageFilter):
    def filter(self, message):
        try:
            chat_id = message.chat.id

            state = IMAGE_QUIZZES.get(chat_id)

            if not state:
                return False

            if not state.started:
                return False

            if state.finished:
                return False

            return True

        except Exception:
            return False


image_quiz_active_filter = ImageQuizActiveFilter()
