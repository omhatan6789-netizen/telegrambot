# ==================================================
# قفل الألعاب الكبيرة
# ==================================================

active_big_games = {}


def get_big_game(chat_id):
    return active_big_games.get(chat_id)


def lock_big_game(chat_id, key, name):
    """
    يقفل القروب للعبة كبيرة واحدة فقط.
    يرجع True إذا تم القفل.
    يرجع False إذا فيه لعبة كبيرة شغالة.
    """

    if chat_id in active_big_games:
        return False

    active_big_games[chat_id] = {
        "key": key,
        "name": name
    }

    return True


def unlock_big_game(chat_id, key=None):
    """
    فك القفل.
    إذا تم تمرير key، ما يفك إلا إذا كان القفل لنفس اللعبة.
    """

    current = active_big_games.get(chat_id)

    if not current:
        return

    if key is not None and current["key"] != key:
        return

    active_big_games.pop(chat_id, None)