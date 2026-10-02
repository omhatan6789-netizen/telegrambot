import json
import os
import time
import requests
from PIL import Image
from io import BytesIO

# =========================================================
# الإعدادات
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

OPENVERSE_API = "https://api.openverse.org/v1/images/"

MIN_WIDTH = 500
MIN_HEIGHT = 500
TIMEOUT = 30

# =========================================================
# الفئات
# =========================================================

CATEGORIES = {
    "vehicles": {
        "count": 60,
        "searches": [
            "car",
            "sports car",
            "bus",
            "truck",
            "motorcycle",
            "bicycle",
            "train",
            "airplane",
            "helicopter",
            "ship",
            "boat",
            "taxi",
        ],
    },

    "food": {
        "count": 60,
        "searches": [
            "pizza",
            "burger",
            "fries",
            "sandwich",
            "pasta",
            "rice",
            "cake",
            "donut",
            "ice cream",
            "chocolate",
            "apple",
            "banana",
            "orange",
            "watermelon",
            "strawberry",
            "coffee",
            "tea",
            "juice",
            "milk",
            "bread",
        ],
    },

    "football": {
        "count": 60,
        "searches": [
            "football player",
            "soccer player",
            "football match",
            "footballer",
            "soccer",
            "football stadium",
        ],
    },

    "gaming": {
        "count": 50,
        "searches": [
            "gaming controller",
            "game controller",
            "video game console",
            "PlayStation controller",
            "Xbox controller",
            "Nintendo controller",
            "gaming keyboard",
            "gaming mouse",
            "gaming headset",
            "computer gaming",
        ],
    },

    "household": {
        "count": 60,
        "searches": [
            "chair",
            "table",
            "sofa",
            "bed",
            "lamp",
            "television",
            "refrigerator",
            "washing machine",
            "microwave",
            "kitchen",
            "cup",
            "plate",
            "spoon",
            "fork",
            "door",
            "window",
            "clock",
            "mirror",
            "vacuum cleaner",
            "toilet",
        ],
    },

    "technology": {
        "count": 30,
        "searches": [
            "smartphone",
            "mobile phone",
            "computer",
            "laptop",
            "tablet",
            "camera",
            "smartwatch",
            "keyboard",
            "mouse",
            "headphones",
            "computer monitor",
        ],
    },

    "everyday": {
        "count": 20,
        "searches": [
            "backpack",
            "umbrella",
            "shoes",
            "wallet",
            "keys",
            "bottle",
            "glasses",
            "book",
            "pen",
            "pencil",
            "scissors",
            "ball",
        ],
    },

    "anime": {
        "count": 80,
        "searches": [
            "anime character",
            "anime drawing",
            "anime illustration",
            "Japanese animation character",
            "manga character",
        ],
    },
}

# =========================================================
# إجمالي الصور
# =========================================================

TOTAL = sum(item["count"] for item in CATEGORIES.values())

# =========================================================
# قراءة الأسئلة الحالية
# =========================================================

def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        return []

    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return data

    except Exception as e:
        print(f"❌ خطأ في قراءة questions.json: {e}")
        return []


def save_questions(questions):
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            questions,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# تنظيف النص
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return (
        str(text)
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


# =========================================================
# الحصول على نتائج Openverse
# =========================================================

def search_openverse(query, page=1, page_size=50):
    params = {
        "q": query,
        "page": page,
        "page_size": page_size,
        "license": "cc0,pdm,by",
    }

    try:
        response = requests.get(
            OPENVERSE_API,
            params=params,
            timeout=TIMEOUT,
        )

        if response.status_code != 200:
            print(
                f"⚠️ Openverse HTTP {response.status_code} "
                f"للبحث: {query}"
            )
            return []

        data = response.json()

        return data.get("results", [])

    except Exception as e:
        print(f"❌ خطأ Openverse: {e}")
        return []


# =========================================================
# تحميل الصورة
# =========================================================

def download_image(url):
    if not url:
        return None

    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": "ImageQuizBot/1.0"
            },
        )

        if response.status_code != 200:
            return None

        if not response.content:
            return None

        image = Image.open(BytesIO(response.content))

        # معالجة الصور المتحركة
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        width, height = image.size

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            return None

        # تحويل إلى RGB
        if image.mode == "RGBA":
            background = Image.new(
                "RGB",
                image.size,
                "white",
            )
            background.paste(
                image,
                mask=image.getchannel("A"),
            )
            image = background
        else:
            image = image.convert("RGB")

        return image

    except Exception:
        return None


# =========================================================
# حفظ الصورة
# =========================================================

def save_image(image, path):
    try:
        os.makedirs(
            os.path.dirname(path),
            exist_ok=True,
        )

        image.save(
            path,
            "JPEG",
            quality=92,
            optimize=True,
        )

        return True

    except Exception as e:
        print(f"❌ فشل حفظ الصورة: {e}")
        return False


# =========================================================
# اسم الإجابة
# =========================================================

def make_answer(category, query, title):
    title = clean_text(title)

    if title:
        return title

    return clean_text(query)


# =========================================================
# هل السؤال موجود؟
# =========================================================

def question_exists(questions, image_path):
    normalized = image_path.replace("\\", "/")

    for question in questions:
        existing = str(
            question.get("image", "")
        ).replace("\\", "/")

        if existing == normalized:
            return True

    return False


# =========================================================
# الحصول على ID جديد
# =========================================================

def next_category_number(questions, category):
    numbers = []

    prefix = f"{category}_"

    for question in questions:
        question_id = str(
            question.get("id", "")
        )

        if question_id.startswith(prefix):
            try:
                number = int(
                    question_id[len(prefix):]
                )
                numbers.append(number)
            except ValueError:
                pass

    if not numbers:
        return 1

    return max(numbers) + 1


# =========================================================
# تنزيل فئة كاملة
# =========================================================

def download_category(
    category,
    settings,
    questions,
):
    target = settings["count"]
    searches = settings["searches"]

    category_dir = os.path.join(
        IMAGES_DIR,
        category,
    )

    os.makedirs(
        category_dir,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # نبدأ من الصور الموجودة فعليًا
    # -----------------------------------------------------

    existing_files = []

    for name in os.listdir(category_dir):
        if name.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            existing_files.append(name)

    current_count = len(existing_files)

    print()
    print("=" * 60)
    print(f"📂 الفئة: {category}")
    print(f"🎯 المطلوب: {target}")
    print(f"📦 الموجود: {current_count}")
    print("=" * 60)

    if current_count >= target:
        print("✅ الفئة مكتملة.")
        return

    next_number = current_count + 1

    search_index = 0
    page = 1

    used_urls = set()

    while current_count < target:
        query = searches[
            search_index % len(searches)
        ]

        print(
            f"🔎 بحث: {query} "
            f"(صفحة {page})"
        )

        results = search_openverse(
            query,
            page=page,
            page_size=50,
        )

        if not results:
            search_index += 1
            page = 1

            if search_index >= len(searches) * 2:
                print(
                    "⚠️ لم نجد نتائج إضافية مناسبة."
                )
                break

            continue

        for result in results:
            if current_count >= target:
                break

            url = (
                result.get("url")
                or result.get("thumbnail")
            )

            if not url:
                continue

            if url in used_urls:
                continue

            used_urls.add(url)

            image = download_image(url)

            if image is None:
                continue

            filename = (
                f"{next_number:03d}.jpg"
            )

            file_path = os.path.join(
                category_dir,
                filename,
            )

            if os.path.exists(file_path):
                next_number += 1
                continue

            if not save_image(
                image,
                file_path,
            ):
                continue

            relative_path = (
                f"images/{category}/{filename}"
            )

            title = clean_text(
                result.get("title", "")
            )

            answer = make_answer(
                category,
                query,
                title,
            )

            question_id = (
                f"{category}_{next_number:03d}"
            )

            question = {
                "id": question_id,
                "image": relative_path,
                "answer": answer,
                "alternative_answers": [],
                "category": category,
                "difficulty": "medium",
            }

            if not question_exists(
                questions,
                relative_path,
            ):
                questions.append(question)

            current_count += 1
            next_number += 1

            print(
                f"✅ {current_count}/{target} "
                f"{relative_path}"
            )

            # حفظ questions.json بعد كل صورة
            save_questions(questions)

            time.sleep(0.4)

        page += 1

        # لا نترك الصفحات ترتفع بلا نهاية
        if page > 10:
            search_index += 1
            page = 1

        if search_index >= len(searches):
            search_index = 0

    print(
        f"🏁 انتهت {category}: "
        f"{current_count}/{target}"
    )


# =========================================================
# التحقق من الصور والأسئلة
# =========================================================

def verify_questions(questions):
    print()
    print("=" * 60)
    print("🔍 فحص الصور")
    print("=" * 60)

    missing = []

    for question in questions:
        image_path = question.get(
            "image",
            "",
        )

        full_path = os.path.join(
            BASE_DIR,
            image_path,
        )

        if not os.path.exists(full_path):
            missing.append(
                (
                    question.get("id"),
                    image_path,
                )
            )

    if not missing:
        print(
            "✅ كل الأسئلة لها صور."
        )
        return

    print(
        f"⚠️ صور مفقودة: {len(missing)}"
    )

    for question_id, image_path in missing[:30]:
        print(
            f"❌ {question_id}: "
            f"{image_path}"
        )


# =========================================================
# Main
# =========================================================

def main():
    print()
    print("🎯 Image Quiz Downloader")
    print("📦 تحميل مكتبة توقع الصورة")
    print()

    questions = load_questions()

    print(
        f"📄 الأسئلة الحالية: "
        f"{len(questions)}"
    )

    # -----------------------------------------------------
    # تنزيل كل الفئات ما عدا الحيوانات
    # -----------------------------------------------------

    for category, settings in CATEGORIES.items():

        download_category(
            category,
            settings,
            questions,
        )

    # -----------------------------------------------------
    # حفظ نهائي
    # -----------------------------------------------------

    save_questions(questions)

    print()
    print("=" * 60)
    print("🎉 انتهى التحميل")
    print("=" * 60)

    print(
        f"📄 إجمالي الأسئلة: "
        f"{len(questions)}"
    )

    verify_questions(questions)

    print()
    print(
        "⚠️ ملاحظة: الصور المرخصة من Openverse "
        "ينبغي التحقق من ترخيص كل عمل قبل الاستخدام."
    )


if __name__ == "__main__":
    main()