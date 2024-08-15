from tinydb import TinyDB, Query

user_db = TinyDB("users.json")
message_db = TinyDB("messages.json")

def update_user_db_scheme():
    User = Query()
    user_db.update({"settings": {"lang": "ru", "emoji": ""}, "is_premium": False}, User.settings.exists())
    print("Готово!")

def get_user_count():
    print(len(user_db.all()))

get_user_count()