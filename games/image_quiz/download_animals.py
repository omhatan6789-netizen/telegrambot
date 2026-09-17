import json
import os
import time
import requests
from PIL import Image
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGES_DIR = os.path.join(BASE_DIR, "images", "animals")
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")
SOURCES_FILE = os.path.join(BASE_DIR, "animals_sources.json")

os.makedirs(IMAGES_DIR, exist_ok=True)

ANIMALS = [
    ("أسد", ["lion"]),
    ("نمر", ["tiger"]),
    ("فهد", ["cheetah"]),
    ("ذئب", ["wolf"]),
    ("ثعلب", ["fox"]),
    ("دب", ["bear"]),
    ("فيل", ["elephant"]),
    ("زرافة", ["giraffe"]),
    ("حمار وحشي", ["zebra"]),
    ("وحيد القرن", ["rhinoceros", "rhino"]),
    ("فرس النهر", ["hippopotamus"]),
    ("غوريلا", ["gorilla"]),
    ("شمبانزي", ["chimpanzee"]),
    ("أورانغوتان", ["orangutan"]),
    ("باندا", ["panda"]),
    ("كوالا", ["koala"]),
    ("كنغر", ["kangaroo"]),
    ("كسلان", ["sloth"]),
    ("غزال", ["gazelle"]),
    ("حمار", ["donkey"]),
    ("حصان", ["horse"]),
    ("جمل", ["camel"]),
    ("بقرة", ["cow"]),
    ("خروف", ["sheep"]),
    ("ماعز", ["goat"]),
    ("خنزير", ["pig"]),
    ("أرنب", ["rabbit"]),
    ("قنفذ", ["hedgehog"]),
    ("سنجاب", ["squirrel"]),
    ("فأر", ["mouse"]),
    ("قط", ["cat"]),
    ("كلب", ["dog"]),
    ("بومة", ["owl"]),
    ("نسر", ["eagle"]),
    ("صقر", ["falcon"]),
    ("ببغاء", ["parrot"]),
    ("طاووس", ["peacock"]),
    ("فلامنغو", ["flamingo"]),
    ("بطريق", ["penguin"]),
    ("بطة", ["duck"]),
    ("دجاجة", ["chicken"]),
    ("ديك", ["rooster"]),
    ("نعامة", ["ostrich"]),
    ("بجعة", ["swan"]),
    ("نقار الخشب", ["woodpecker"]),
    ("حمامة", ["pigeon"]),
    ("غراب", ["crow"]),
    ("كناري", ["canary"]),
    ("بومة ثلجية", ["snowy owl"]),
    ("سلحفاة", ["turtle"]),
    ("تمساح", ["crocodile"]),
    ("أفعى", ["snake"]),
    ("كوبرا", ["cobra"]),
    ("حرباء", ["chameleon"]),
    ("ضفدع", ["frog"]),
    ("سمندر", ["salamander"]),
    ("قرش", ["shark"]),
    ("دولفين", ["dolphin"]),
    ("حوت", ["whale"]),
    ("أخطبوط", ["octopus"]),
    ("حبار", ["squid"]),
    ("قنديل البحر", ["jellyfish"]),
    ("فرس البحر", ["seahorse"]),
    ("نجم البحر", ["starfish"]),
    ("سرطان البحر", ["crab"]),
    ("روبيان", ["shrimp"]),
    ("سلطعون", ["crayfish"]),
    ("فراشة", ["butterfly"]),
    ("نحلة", ["bee"]),
    ("نملة", ["ant"]),
    ("دعسوقة", ["ladybug"]),
    ("جرادة", ["grasshopper"]),
    ("يعسوب", ["dragonfly"]),
    ("عنكبوت", ["spider"]),
    ("عقرب", ["scorpion"]),
    ("حلزون", ["snail"]),
    ("خفاش", ["bat"]),
    ("قندس", ["beaver"]),
    ("راكون", ["raccoon"]),
    ("سمور", ["otter"]),
]


def search_openverse(query):
    url = "https://api.openverse.org/v1/images/"

    params = {
        "q": query,
        "license": "cc0,pdm,by",
        "page_size": 20,
        "mature": "false",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={
            "User-Agent": "TelegramImageQuiz/1.0"
        },
    )

    response.raise_for_status()

    return response.json().get("results", [])


def download_image(url):
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "TelegramImageQuiz/1.0"
        },
    )

    response.raise_for_status()

    image = Image.open(BytesIO(response.content))

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    image.thumbnail((1600, 1600))

    return image.convert("RGB")


def save_image(image, path):
    image.save(
        path,
        "JPEG",
        quality=88,
        optimize=True,
    )


def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        return []

    try:
        with open(
            QUESTIONS_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_questions(questions):
    with open(
        QUESTIONS_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            questions,
            f,
            ensure_ascii=False,
            indent=2,
        )


def main():

    questions = load_questions()

    sources = []

    existing_ids = {
        q.get("id")
        for q in questions
        if isinstance(q, dict)
    }

    start_id = max(existing_ids, default=0) + 1

    print("=" * 60)
    print("تحميل 80 صورة حيوانات")
    print("=" * 60)

    for index, (arabic_name, searches) in enumerate(
        ANIMALS,
        start=1,
    ):

        filename = f"{index:03d}.jpg"

        image_path = os.path.join(
            IMAGES_DIR,
            filename,
        )

        if os.path.exists(image_path):
            print(
                f"[{index}/80] موجودة مسبقًا: {filename}"
            )
            continue

        result = None

        for search in searches:

            print(
                f"[{index}/80] البحث عن: {arabic_name} ({search})"
            )

            try:
                results = search_openverse(search)

            except Exception as e:
                print(
                    f"خطأ في البحث: {e}"
                )
                continue

            for item in results:

                image_url = item.get("url")

                if not image_url:
                    continue

                license_name = (
                    item.get("license") or ""
                ).lower()

                if license_name not in (
                    "cc0",
                    "pdm",
                    "by",
                ):
                    continue

                try:

                    image = download_image(
                        image_url
                    )

                    if image.width < 500 or image.height < 500:
                        continue

                    save_image(
                        image,
                        image_path,
                    )

                    result = item
                    break

                except Exception as e:

                    print(
                        f"تخطي صورة: {e}"
                    )

            if result:
                break

        if not result:

            print(
                f"❌ لم نجد صورة مناسبة لـ {arabic_name}"
            )
            continue

        question = {
            "id": start_id + index - 1,
            "image": f"images/animals/{filename}",
            "answer": arabic_name,
            "alternative_answers": [],
            "category": "animals",
            "difficulty": "easy",
        }

        questions.append(question)

        sources.append({
            "id": question["id"],
            "image": question["image"],
            "answer": arabic_name,
            "source": result.get("source"),
            "creator": result.get("creator"),
            "creator_url": result.get("creator_url"),
            "license": result.get("license"),
            "license_version": result.get(
                "license_version"
            ),
            "license_url": result.get(
                "license_url"
            ),
            "source_url": result.get(
                "foreign_landing_url"
            ),
            "original_image_url": result.get(
                "url"
            ),
        })

        print(
            f"✅ تم: {filename} = {arabic_name}"
        )

        time.sleep(0.5)

    save_questions(questions)

    with open(
        SOURCES_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            sources,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 60)
    print("انتهى التحميل")
    print("=" * 60)
    print(
        f"الصور: {IMAGES_DIR}"
    )
    print(
        f"الأسئلة: {QUESTIONS_FILE}"
    )
    print(
        f"المصادر والتراخيص: {SOURCES_FILE}"
    )


if __name__ == "__main__":
    main()
