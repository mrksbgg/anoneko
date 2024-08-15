from aiogram import Bot, Dispatcher, types, Router, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, or_f
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup
from aiogram_media_group import media_group_handler
from tinydb import TinyDB, Query, where
from aiogram.types import ContentType
import asyncio
import json
import logging
import random
import string
import strings
import os
import emoji_extractor
import requests
import nekos
from translate import Translator


API_TOKEN = "7360774007:AAGuPuQbFLnwuQ2IJcAdDISeN9HyZIB4nuM"


# Dispatcher is a root router
router = Router()
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)
# ... and all other routers should be attached to Dispatcher

# Initialize Bot instance with a default parse mode which will be passed to all API calls
bot = Bot(API_TOKEN, default=DefaultBotProperties(parse_mode="Html"))

user_db = TinyDB("users.json")
message_db = TinyDB("messages.json")

class Form(StatesGroup):
    waiting_for_message = State()

class NewNickname(StatesGroup):
    waiting_for_nickname = State()

class EditEmoji(StatesGroup):
    waiting_for_emoji = State()

async def check_user(message: types.Message):
    user = get_user_by_chat_id(message.from_user.id)
    if not user:
        user = add_user_to_db(message.from_user.id)
        lang = user["settings"]["lang"]
        await message.reply("🙌")
        await bot.send_message(chat_id=message.from_user.id, text=strings.welcome[lang] % get_username(user["secret_id"]))
        return user
    else:
        return user[0]

@dp.message(Command("start"))
async def on_start(message: types.Message, state: FSMContext):
    you = await check_user(message)
    lang = you["settings"]["lang"]
    if message.text.replace("/start", "") != "":
        await message.delete()
        secret_link = message.text.replace("/start", "").strip()
        if not get_user_by_link(secret_link):
            return await bot.send_message(chat_id=message.from_user.id, text="❌ " + strings.send_message[lang][0] % secret_link)
        #if get_user_by_link(secret_link)[0]["chat_id"] == message.from_user.id:
        #    return await bot.send_message(chat_id=message.from_user.id, text="❌ " + strings.send_message[lang][1], message_effect_id="5104858069142078462")
        chat_id = get_user_by_link(secret_link)[0]["chat_id"]
        cancel = InlineKeyboardButton(text=strings.cancel[lang], callback_data="message_send_cancel")
        markup = InlineKeyboardMarkup(inline_keyboard=[[cancel]])
        await bot.send_message(chat_id=message.from_user.id, text=strings.send_message[lang][2].format(f"[{get_user_by_link(secret_link)[0]["settings"]["emoji"]}] ", secret_link), reply_markup=markup)
        await state.update_data(chat_id=chat_id)
        await state.set_state(Form.waiting_for_message)
    else:
        nickname = get_username(you["secret_id"])
        link = f"https://t.me/anonekobot?start={you["link"]}" if you["link"] else "N/A"
        await message.reply(text=strings.about_you[lang].format(nickname, link))

@dp.message(Command("settings"))
async def settings(message: types.Message):
    you = await check_user(message)
    lang = you["settings"]["lang"]
    lang_icon = strings.languages[lang]
    emoji = you["settings"]["emoji"]
    language = InlineKeyboardButton(text=f"{strings.settings[lang][1]}{lang_icon}", callback_data="change_language")
    change_emoji = InlineKeyboardButton(text=f"{strings.settings[lang][2]}{emoji}", callback_data="change_emoji")
    buttons = [language]
    if you["is_premium"]: buttons.append(change_emoji)
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    await message.reply(strings.settings[lang][0], reply_markup=markup)

@dp.callback_query(F.data == "change_language")
async def change_language(callback: types.CallbackQuery) -> None:
    you = await check_user(callback)
    lang = you["settings"]["lang"]
    new_lang = "en" if lang == "ru" else "ru"
    emoji = you["settings"]["emoji"]
    change_settings(callback.from_user.id, new_lang, emoji)
    lang_icon = strings.languages[new_lang]
    language = InlineKeyboardButton(text=f"{strings.settings[new_lang][1]}{lang_icon}", callback_data="change_language")
    change_emoji = InlineKeyboardButton(text=f"{strings.settings[new_lang][2]}{emoji}", callback_data="change_emoji")
    buttons = [language]
    if you["is_premium"]: buttons.append(change_emoji)
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    await callback.message.edit_text(strings.settings[new_lang][0], reply_markup=markup)

@dp.callback_query(F.data == "change_emoji")
async def change_emoji(callback: types.CallbackQuery, state: FSMContext) -> None:
    you = await check_user(callback)
    lang = you["settings"]["lang"]
    cancel = InlineKeyboardButton(text=strings.cancel[lang], callback_data="edit_settings_cancel")
    markup = InlineKeyboardMarkup(inline_keyboard=[[cancel]])
    await callback.message.edit_text(strings.settings[lang][3], reply_markup=markup)
    await state.update_data(message_id=callback.message.message_id)
    await state.set_state(EditEmoji.waiting_for_emoji)
    
@dp.message(EditEmoji.waiting_for_emoji)
async def get_new_emoji(message: types.Message, state: FSMContext):
    you = await check_user(message)
    lang = you["settings"]["lang"]
    if you["link"] != "ketamorine":
        emoji = emoji_extractor.extract_emojis(message.text)
    else:
        emoji = message.text
    await message.delete()
    new_emoji = ""
    if emoji:
        if you["link"] != "ketamorine":
            new_emoji = emoji[-1]
        else:
            new_emoji = emoji
        change_settings(message.from_user.id, lang, new_emoji)
    data = await state.get_data()
    await state.clear()
    lang_icon = strings.languages[lang]
    language = InlineKeyboardButton(text=f"{strings.settings[lang][1]}{lang_icon}", callback_data="change_language")
    change_emoji = InlineKeyboardButton(text=f"{strings.settings[lang][2]}{new_emoji if new_emoji else you['settings']['emoji']}", callback_data="change_emoji")
    buttons = [language]
    if you["is_premium"]: buttons.append(change_emoji)
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    await bot.edit_message_text(strings.settings[lang][0], chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)

@dp.message(Command("support"))
async def support(message: types.Message):
    user = await check_user(message)
    lang = user["settings"]["lang"]
    telegram = InlineKeyboardButton(text=strings.support[lang][1], url="t.me/ketamorine")
    donate = InlineKeyboardButton(text=strings.support[lang][2], url="yoomoney.ru/to/4100118632509966")
    buttons = [[telegram], [donate]]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply(text=strings.support[lang][0], reply_markup=markup)

@dp.message(Command("regen"))
async def regen(message: types.Message):
    you = await check_user(message)
    lang = you["settings"]["lang"]
    new_secret_id = reset_secret_id(message.from_user.id)
    await message.reply_dice()
    await asyncio.sleep(5)
    await bot.send_message(message.from_user.id, f"{strings.secret_id[lang]}\n\n{get_username(you['secret_id'])} → {get_username(new_secret_id)}")
    
@dp.callback_query(F.data == "message_send_cancel")
async def message_send_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.delete()

@dp.message(Command("link"))
async def change_link(message: types.Message):
    you = await check_user(message)
    lang = you["settings"]["lang"]
    link = f"{you['link']}" if you["link"] else "N/A"
    full_link = f"https://t.me/anonekobot?start={link}" if link != "N/A" else link
    edit_link = InlineKeyboardButton(text=strings.link[lang][3], callback_data="edit_link")
    share_link = InlineKeyboardButton(text=strings.link[lang][4], url=f"https://t.me/share/url?url={strings.link[lang][5]} ✌🏻\n{full_link}")
    buttons = [[edit_link]]
    if full_link != link: 
        buttons.append([share_link])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply(f"{strings.link[lang][0]}\n\n{strings.link[lang][1]}<code>{full_link}</code>{f'\n{strings.link[lang][2]}' if full_link == link else ''}\n\n{strings.link[lang][6]}", reply_markup=markup)

@dp.callback_query(F.data == "edit_link")
async def edit_link(callback: types.CallbackQuery, state: FSMContext) -> None:
    you = await check_user(callback)
    lang = you["settings"]["lang"]
    cancel = InlineKeyboardButton(text=strings.cancel[lang], callback_data="edit_settings_cancel")
    markup = InlineKeyboardMarkup(inline_keyboard=[[cancel]])
    await callback.message.edit_text(f"{strings.link[lang][0]}\n\n{strings.edit_link[lang][0]}", reply_markup=markup)
    await state.update_data(message_id=callback.message.message_id)
    await state.set_state(NewNickname.waiting_for_nickname)

@dp.callback_query(F.data == "edit_settings_cancel")
async def edit_settings_cancel(callback: types.CallbackQuery, state: FSMContext) -> None:
    you = await check_user(callback)
    lang = you["settings"]["lang"]
    await state.clear()
    new_lang = "en" if lang == "ru" else "ru"
    emoji = you["settings"]["emoji"]
    lang_icon = strings.languages[new_lang]
    language = InlineKeyboardButton(text=f"{strings.settings[new_lang][1]}{lang_icon}", callback_data="change_language")
    change_emoji = InlineKeyboardButton(text=f"{strings.settings[new_lang][2]}{emoji}", callback_data="change_emoji")
    buttons = [language]
    if you["is_premium"]: buttons.append(change_emoji)
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    await callback.message.edit_text(strings.settings[new_lang][0], reply_markup=markup)

@dp.message(NewNickname.waiting_for_nickname)
async def new_nickname(message: types.Message, state: FSMContext):
    you = await check_user(message)
    lang = you["settings"]["lang"]
    await message.delete()
    data = await state.get_data()
    new_nickname = message.text
    new_nickname = new_nickname.replace(" ", "_")
    cancel = InlineKeyboardButton(text="Cancel", callback_data="edit_link_cancel")
    markup = InlineKeyboardMarkup(inline_keyboard=[[cancel]])
    gui = f"{strings.link[lang][0]}\n\n{strings.edit_link[lang][0]}"
    if new_nickname.lower() == "god":
        error = f"❌ {strings.edit_link[lang][1]}"
        return await bot.edit_message_text(gui + "\n\n" + error, chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)
    elif new_nickname.lower() == "angel":
        error = f"❌ {strings.edit_link[lang][2]}"
        return await bot.edit_message_text(gui + "\n\n" + error, chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)
    elif new_nickname.lower() == "keta" or new_nickname.lower() == "ketamorine" or new_nickname.lower() == "usedketa":
        error = "❌ <b>Ты не Кета.</b>"
        return await bot.edit_message_text(gui + "\n\n" + error, chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)
    elif new_nickname.lower() in ["adm", "admin", "administrator", "mod", "moder", "moderator"]:
        error = f"❌ {strings.edit_link[lang][3]}"
        return await bot.edit_message_text(gui + "\n\n" + error, chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)
    for symbol in new_nickname.lower():
        if not symbol in "abcdefghijklmnopqrstuvwxyz0123456789_":
            error = f"❌ <b>{strings.edit_link[lang][5]}</b>"
            return await bot.edit_message_text(gui + "\n\n" + error, chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)
    link_setted = set_link(message.from_user.id, new_nickname)
    if link_setted:
        you = await check_user(message)
        await state.clear()
        link = f"{you['link']}" if you["link"] else "N/A"
        full_link = f"https://t.me/anonekobot?start={link}" if link != "N/A" else link
        edit_link = InlineKeyboardButton(text=strings.link[lang][3], callback_data="edit_link")
        share_link = InlineKeyboardButton(text=strings.link[lang][4], url=f"https://t.me/share/url?url={strings.link[lang][5]} ✌🏻\n{full_link}")
        buttons = [[edit_link]]
        if full_link != link:
            buttons.append([share_link])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await bot.edit_message_text(text=f"{strings.link[lang][0]}\n\n{strings.link[lang][1]}<code>{full_link}</code>{f'\n{strings.link[lang][2]}' if full_link == link else ''}\n\n{strings.link[lang][6]}", reply_markup=markup, chat_id=message.from_user.id, message_id=data["message_id"])
    else:
        error = f"❌ {strings.edit_link[lang][5]}"
        return await bot.edit_message_text(gui + "\n\n" + error, chat_id=message.from_user.id, message_id=data["message_id"], reply_markup=markup)

@dp.message(Form.waiting_for_message)
@media_group_handler
async def process_user_message(messages: list[types.Message], state: FSMContext):
    print("тут появляемся")
    you = get_user_by_chat_id(messages[0].from_user.id)[0]
    lang = you["settings"]["lang"]
    message = messages[0]
    data = await state.get_data()
    anonymous = get_username(get_user_by_chat_id(message.from_user.id)[0]["secret_id"])
    await state.clear()
    link_owner_nickname = get_user_by_chat_id(data["chat_id"])[0]["link"]
    if messages[0].text and messages[0].text.startswith("!"):
        anon_message = await send_special(messages, data["chat_id"], anonymous)
    else:
        anon_message = await send_message(messages, data["chat_id"], anonymous)
    if anon_message:
        save_message(message.message_id, anon_message, message.from_user.id, data["chat_id"], data["chat_id"], get_user_by_chat_id(message.from_user.id)[0]["secret_id"], link_owner_nickname=link_owner_nickname)
        await set_sent_reaction(message.chat.id, message.message_id)
    else:
        await set_fail_reaction(message.chat.id, message.message_id)
        await message.reply(strings.send_message[lang][3])

async def set_sent_reaction(chat_id, message_id):
    await bot.set_message_reaction(chat_id, message_id, reaction=[{"type": "emoji", "emoji": "👀"}])

async def set_fail_reaction(chat_id, message_id):
    await bot.set_message_reaction(chat_id, message_id, reaction=[{"type": "emoji", "emoji": "👎"}])

@dp.message()
@media_group_handler
async def process_user_message(messages: list[types.Message]):
    print(messages[0].content_type)
    you = get_user_by_chat_id(messages[0].from_user.id)[0]
    lang = you["settings"]["lang"]
    replied_message = messages[0].reply_to_message
    message = messages[0]
    if replied_message:
        try:
            message_info = get_message_by_reply(replied_message.message_id, message.from_user.id)[0]
        except Exception as exc:
            print(exc)
            return
        you = get_user_by_chat_id(message.from_user.id)[0]
        s = get_username(you["secret_id"])
        l = you["link"]
        if message_info["link_owner"] != message.from_user.id and you["secret_id"] != message_info["sender_secret_id"]:
            await set_fail_reaction(message.chat.id, message.message_id)
            return await messages[0].reply(strings.reply[lang][0])
        elif message_info["link_owner"] == message.from_user.id and get_user_by_chat_id(message_info["sender_chat_id"])[0]["secret_id"] != message_info["sender_secret_id"]:
            await set_fail_reaction(message.chat.id, message.message_id)
            return await messages[0].reply(strings.reply[lang][1])
        elif message_info["link_owner"] == message.from_user.id and you["link"] != message_info["link_owner_nickname"]:
            await set_fail_reaction(message.chat.id, message.message_id)
            return await messages[0].reply(strings.reply[lang][1])
        author=l if message_info["link_owner"] == message.from_user.id else s 
        is_link_owner=True if message_info["link_owner"] == message.from_user.id else False
        if messages[0].text and messages[0].text.startswith("!"):
            answer = await send_special(messages, message_info["sender_chat_id"], author=author, message_id=message_info["orig_message_id"], is_link_owner=is_link_owner)
        else:
            answer = await send_message(messages, message_info["sender_chat_id"], author=author, message_id=message_info["orig_message_id"], is_link_owner=is_link_owner)
        if answer:
            save_message(message.message_id, answer, message.from_user.id, message_info["sender_chat_id"], message_info["link_owner"], message_info["sender_secret_id"], message_info["link_owner_nickname"])
            await set_sent_reaction(message.chat.id, message.message_id)
        else:
            await message.reply(strings.send_message[lang][3])

@dp.callback_query(F.data == "translate")
async def translate_message(callback: types.CallbackQuery):
    you = await check_user(callback)
    lang = you["settings"]["lang"]
    if you["is_premium"]:
        if callback.message.text:
            message = callback.message.text.replace(callback.message.text.split("\n")[0], "").replace(callback.message.text.split("\n")[-1], "")
        elif callback.message.caption:
            message = callback.message.caption.replace(callback.message.caption.split("\n")[0], "").replace(callback.message.caption.split("\n")[-1], "")
        else:
            return await callback.message.reply("У сообщения нет текста который можно перевести")
        print(message)
        translator = Translator(to_lang=lang)
        translation = translator.translate(message)
        await callback.message.answer(strings.translator[lang][0] + translation, reply_to_message_id=callback.message.message_id)
    else:
        await callback.message.answer(strings.translator[lang][1], reply_to_message_id=callback.message.message_id)

async def get_input_media(message: types.Message, gui, caption, enable_caption, lang):
    print(f"content type: {message.content_type}")
    match message.content_type:
        case "photo":
            return types.InputMediaPhoto(media=get_content_id(message), caption=gui + "\n\n" + f'{caption + "\n\n" if caption else ""}' + strings.message_gui[lang][2] if enable_caption else None, caption_entities=message.caption_entities)
        case "video":
            return types.InputMediaVideo(media=get_content_id(message), caption=gui + "\n\n" + f'{caption + "\n\n" if caption else ""}' + strings.message_gui[lang][2] if enable_caption else None, caption_entities=message.caption_entities)
        case "document":
            return types.InputMediaDocument(media=get_content_id(message), caption=gui + "\n\n" + f'{caption + "\n\n" if caption else ""}' + strings.message_gui[lang][2] if enable_caption else None, caption_entities=message.caption_entities)
        case "audio":
            return types.InputMediaAudio(media=get_content_id(message), caption=gui + "\n\n" + f'{caption + "\n\n" if caption else ""}' + strings.message_gui[lang][2] if enable_caption else None, caption_entities=message.caption_entities)
        case "animation":
            return types.InputMediaAnimation(media=get_content_id(message), caption=gui + "\n\n" + f'{caption + "\n\n" if caption else ""}' + strings.message_gui[lang][2] if enable_caption else None, caption_entities=message.caption_entities)

def get_content_id(message: types.Message):
    match message.content_type:
        case "photo":
            return message.photo[-1].file_id
        case "video":
            return message.video.file_id
        case "document":
            return message.document.file_id
        case "audio":
            return message.audio.file_id
        case "animation":
            print("ЭТО АНИМАЦИЯ1!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            return message.animation.file_id
        case "sticker":
            return message.sticker.file_id
        case "voice":
            return message.voice.file_id
        case "video_note":
            return message.video_note.file_id

async def send_message(messages: list[types.Message], chat_id, author, message_id=None, is_link_owner=False):
    print("тут умираем")
    if messages[0].content_type not in ["text", "photo", "video", "document", "audio", "animation", "sticker", "voice", "video_note"]:
        return
    you = await check_user(messages[0])
    user = get_user_by_chat_id(chat_id)[0]
    emoji = ""
    if is_link_owner and you["settings"]["emoji"] != "": emoji = f"[{you["settings"]["emoji"]}] "
    lang = user["settings"]["lang"]
    gui = strings.message_gui[lang][0].format(emoji, author) if not message_id else strings.message_gui[lang][1].format(emoji, author)
    new_message = None
    translate = InlineKeyboardButton(text=strings.translate_to[lang], callback_data="translate")
    buttons = []
    if messages[0].caption or messages[0].text:
        buttons.append(translate)
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    if messages[0].content_type != "text":
        if messages[0].content_type == "animation":
            message = await bot.send_animation(chat_id, get_content_id(messages[0]), caption=gui + "\n\n" + f'{messages[0].caption + "\n\n" if messages[0].caption else ""}' + strings.message_gui[lang][2], reply_to_message_id=message_id, reply_markup=markup)
            return [message.message_id]
        elif messages[0].content_type == "sticker":
            notification = await bot.send_message(chat_id, text=gui + "\n\n" + strings.message_gui[lang][2], reply_to_message_id=message_id, reply_markup=markup)
            message = await bot.send_sticker(chat_id, get_content_id(messages[0]))
            return [notification.message_id, message.message_id]
        elif messages[0].content_type == "voice":
            message = await bot.send_voice(chat_id, get_content_id(messages[0]), caption=gui + "\n\n" + f'{messages[0].caption + "\n\n" if messages[0].caption else ""}' + strings.message_gui[lang][2], reply_to_message_id=message_id, reply_markup=markup)
            return [message.message_id]
        elif messages[0].content_type == "video_note":
            notification = await bot.send_message(chat_id, text=gui + "\n\n" + strings.message_gui[lang][2], reply_to_message_id=message_id, reply_markup=markup)
            message = await bot.send_video_note(chat_id, get_content_id(messages[0]))
            return [notification.message_id, message.message_id]
        media = []
        for m in messages:
            media.append(await get_input_media(m, gui, messages[0].caption, messages[0].message_id == m.message_id, lang))
        new_message = await bot.send_media_group(chat_id, media=media, reply_to_message_id=message_id, reply_markup=markup)
        print("-----")
        ids = []
        for message in new_message:
            ids.append(message.message_id)
        print(ids)
        print("-----")
        return ids
    else:
        new_message = await bot.send_message(chat_id, text=gui + "\n\n" + messages[0].text + "\n\n" + strings.message_gui[lang][2], reply_to_message_id=message_id, reply_markup=markup)
        return [new_message.message_id]

async def send_special(messages: list[types.Message], chat_id, author, message_id=None, is_link_owner=False):
    print("привет!")
    you = await check_user(messages[0])
    emoji = ""
    if is_link_owner: emoji = f"[{you["settings"]["emoji"]}] "
    lang = you["settings"]["lang"]
    gui = strings.special_message_gui[lang].format(messages[0].text.strip().split(" ", 1)[0], emoji, author) if not message_id else strings.special_message_gui[lang].format(messages[0].text.strip().split(" ", 1)[0], emoji, author)
    translate = InlineKeyboardButton(text=strings.translate_to[lang], callback_data="translate")
    buttons = []
    match messages[0].text.strip().split(" ", 1)[0]:
        case "!cat":
            if messages[0].text.replace("!cat", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            url = nekos.cat()
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + "\n\n" + messages[0].text.replace("!cat", "") + ("\n\n" if messages[0].text.replace("!cat", "") != "" else "") + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
        case "!dog":
            if messages[0].text.replace("!dog", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            url = nekos.img("woof")
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + "\n\n" + messages[0].text.replace("!dog", "") + ("\n\n" if messages[0].text.replace("!dog", "") != "" else "")  + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
        case "!anime":
            if messages[0].text.replace("!anime", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            url = nekos.img(random.choice(["waifu", "fox_girl", "neko"]))
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + "\n\n" + messages[0].text.replace("!anime", "") + ("\n\n" if messages[0].text.replace("!anime", "") != "" else "") + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
        case "!fox":
            if messages[0].text.replace("!fox", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            response = requests.get('https://randomfox.ca/floof/')
            if response.status_code == 200:
                url = response.json()['link']
            else:
                url = None
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + " <b>(!fox)</b>\n\n" + messages[0].text.replace("!fox", "") + ("\n\n" if messages[0].text.replace("!fox", "") != "" else "") + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
        case "!kiss":
            if messages[0].text.replace("!kiss", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            url = nekos.img("kiss")
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + " <b>(!kiss)</b>\n\n" + messages[0].text.replace("!kiss", "") + ("\n\n" if messages[0].text.replace("!kiss", "") != "" else "") + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
        case "!pat":
            if messages[0].text.replace("!pat", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            url = nekos.img("pat")
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + " <b>(!pat)</b>\n\n" + messages[0].text.replace("!pat", "") + ("\n\n" if messages[0].text.replace("!pat", "") != "" else "") + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
        case "!hug":
            if messages[0].text.replace("!hug", "") != "":
                buttons.append(translate)
            markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            url = nekos.img("hug")
            await messages[0].reply_photo(url)
            message = await bot.send_photo(chat_id, url, caption=gui + " <b>(!hug)</b>\n\n" + messages[0].text.replace("!hug", "") + ("\n\n" if messages[0].text.replace("!hug", "") != "" else "") + strings.message_gui[lang][2], reply_markup=markup)
            return [message.message_id]
            
            
def add_user_to_db(chat_id, link=None):
    User = Query()
    if user_db.search(User.chat_id == chat_id):
        return
    secret_id = generate_int(10)
    while user_db.search(User.secret_id == secret_id):
        secret_id = generate_int(10)
    user_db.insert({'chat_id': chat_id, 'secret_id': secret_id, 'link': link, 'settings': {"lang": "ru", "emoji": ""}, 'is_premium': False})
    return {'chat_id': chat_id, 'secret_id': secret_id, 'link': link, 'settings': {"lang": "ru", "emoji": ""}, 'is_premium': False}

def reset_secret_id(chat_id):
    User = Query()
    secret_id = generate_int(10)
    while user_db.search(User.secret_id == secret_id):
        secret_id = generate_int(10)
    user_db.update({"secret_id": secret_id}, User.chat_id == chat_id)
    return secret_id

def generate_int(length):
    all_symbols = string.digits
    result = ''.join(random.choice(all_symbols) for _ in range(length))
    return int(result)

def get_user_by_chat_id(chat_id):
    User = Query()
    return user_db.search(User.chat_id == chat_id)

def get_user_by_secret_id(secret_id):
    User = Query()
    return user_db.search(User.secret_id == secret_id)

def get_user_by_link(link):
    User = Query()
    return user_db.search(User.link == link)

def set_link(chat_id, link):
    User = Query()
    if user_db.search(User.link == link):
        print(f"Ссылка занята. {user_db.search(User.link == link)}")
        return None
    user_db.update({"link": link}, User.chat_id == chat_id)
    return link

def change_settings(chat_id, lang, emoji):
    User = Query()
    user_db.update({"settings": {"lang": lang, "emoji": emoji}}, User.chat_id == chat_id)
    return lang

def get_message_by_reply(message_id, chat_id):
    print(message_id)
    print(chat_id)
    Message = Query()
    result = message_db.search(Message.sent_message_id.any([message_id]))
    print(f"get_message_by_reply: {result}")
    return result
    return table.search(Message.sent_message_id == message_id & Message.chat_id == chat_id)

def save_message(orig_message_id, sent_message_id, sender_chat_id, chat_id, link_owner, sender_secret_id, link_owner_nickname):
    message_db.insert({"sent_message_id": sent_message_id, "orig_message_id": orig_message_id, "sender_chat_id": sender_chat_id, "chat_id": chat_id, "link_owner": link_owner, "sender_secret_id": sender_secret_id, "link_owner_nickname": link_owner_nickname})

def get_username(user_id: int) -> str:
    random.seed(user_id)

    directory_path = os.path.dirname(__file__)
    adjectives, nouns = [], []

    with open(os.path.join(directory_path, 'adjectives.txt'), 'r') as file_adjective:
        with open(os.path.join(directory_path, 'nouns.txt'), 'r') as file_noun:
            for line in file_adjective:
                adjectives.append(line.strip())

            for line in file_noun:
                nouns.append(line.strip())

    adjective = random.choice(adjectives)
    noun = random.choice(nouns).capitalize()
    num = str(random.randrange(10,99))
    result = adjective + noun + num

    random.seed()

    return result

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())