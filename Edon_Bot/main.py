import os
import base64
import telebot
import requests

# ==========================================
# ⚙️ НАСТРОЙКИ LINK API И ТЕЛЕГРАМА (ИСПРАВЛЕНО):
# ==========================================
TELEGRAM_TOKEN = "8879272306:AAENHKswKWHT5gv9uRqdoFngtS3ypDe4t28"
GEMINI_API_KEY = "sk-KI1dgvQfqPJyOQFM8CuIlldedJeKBh4cQtMiAuhJgevRYAAR"

# Поменяли v1beta на v1, теперь сайт поймет наш запрос!
GEMINI_URL = "https://linkapi.ai/v1/chat/completions"
MODEL_NAME = "[次]gemini-3.1-pro-preview"
# ==========================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
histories = {}

def load_file(filename, default_text=""):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return default_text

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    histories[chat_id] = [] # Очищаем память при перезапуске
    greeting = load_file("greeting.txt", "— Ну привет. Чё хотела?")
    bot.send_message(chat_id, greeting)

def call_gemini(chat_id, new_message_text, video_base64=None):
    if chat_id not in histories:
        histories[chat_id] = []
    
    # Собираем системный промпт (инструкции + лор)
    system_instruction = load_file("character.txt") + "\n\n=== ЛОР МИРА ===\n" + load_file("lore.txt")
    
    # Формируем структуру сообщения для Link API
    content_list = [{"type": "text", "text": new_message_text}]
    
    # Если передано видео, добавляем его в запрос
    if video_base64:
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:video/mp4;base64,{video_base64}"
            }
        })
        
    histories[chat_id].append({
        "role": "user",
        "content": content_list
    })
    
    # Собираем полный пакет для отправки, включая системный промпт
    messages = [{"role": "system", "content": system_instruction}] + histories[chat_id][-20:]
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages
    }
    
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(GEMINI_URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        try:
            bot_text = data['choices'][0]['message']['content']
            histories[chat_id].append({
                "role": "assistant",
                "content": bot_text
            })
            return bot_text
        except Exception as e:
            return f"*(Запутался в мыслях)* [Ошибка разбора: {e}]"
    else:
        return f"*(Что-то не так...)* [Ошибка API: {response.status_code} - {response.text}]"

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    reply = call_gemini(chat_id, message.text)
    bot.send_message(chat_id, reply)

@bot.message_handler(content_types=['video_note'])
def handle_video_note(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Сейчас гляну!", parse_mode="Markdown")
    bot.send_chat_action(chat_id, 'typing')
    
    file_info = bot.get_file(message.video_note.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    video_base64 = base64.b64encode(downloaded_file).decode('utf-8')
    
    prompt = "Пользователь отправил тебе видеосообщение (кружочек). Внимательно посмотри видео, послушай голос, интонацию, выражение лица и ответь в своей роли, комментируя увиденное или услышанное, если это уместно."
    
    reply = call_gemini(chat_id, prompt, video_base64)
    bot.send_message(chat_id, reply)

import os
import re
import random
import urllib.parse
import requests

# === НАСТРОЙКИ МЕДИА-ДВИЖКА ===
NANO_BANANA_TOKEN = "-T4ZhWwDYe_v9cfOsUjfIbYk"
BANANA_BASE_URL = "https://naistera.org/prompt/"

# Папка для референсов внешности (создай её на Гитхабе с именем appearance_refs)
REFS_DIR = "appearance_refs" 

# Твой GitHub репозиторий (замени на свой ник и имя репозитория, чтобы Nano Banana могла брать картинки по прямым ссылкам)
# Формат: "https://raw.githubusercontent.com/твой_ник/имя_репо/main/appearance_refs/"
GITHUB_REFS_URL = "https://github.com/vaileriii/EdonBot/tree/main/Edon_Bot/appearance_refs"


def load_text_file(filename, default_text=""):
    """Универсальная функция чтения текстовых файлов (лор, характер, стиль)"""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()
    return default_text


def generate_media_via_banana(trigger_type, visual_description):
    """
    Основная функция генерации картинок и видео через Nano Banana.
    Связывает стили из image_prompt.txt и референсы из папки.
    """
    # 1. Загружаем базовые правила стиля генерации
    style_prompt = load_text_file("image_prompt.txt", default_text="realism")
    
    # 2. Собираем финальный детальный промпт
    final_prompt = f"{style_prompt}, {visual_description}"
    
    # 3. Если это селфи/фото персонажа — подмешиваем референс внешности
    if trigger_type == "селфи" or trigger_type == "себя":
        if os.path.exists(REFS_DIR) and os.listdir(REFS_DIR):
            # Выбираем случайное фото-референс из папки
            all_refs = [f for f in os.listdir(REFS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if all_refs:
                chosen_ref = random.choice(all_refs)
                # Так как Nano Banana — это URL-сеть, мы передаем ей прямую ссылку на файл из твоего GitHub
                ref_url = f"{GITHUB_REFS_URL}{chosen_ref}"
                final_prompt = f"Reference image: {ref_url}, appearance target identical to reference, {final_prompt}"

    # 4. Кодируем промпт для безопасной передачи в URL-строке
    encoded_prompt = urllib.parse.quote(final_prompt)
    
    # 5. Собираем итоговую ссылку
    api_url = f"{BANANA_BASE_URL}{encoded_prompt}?aspect_ratio=2:3&token={NANO_BANANA_TOKEN}&banana"
    
    try:
        # Делаем запрос к нейронке
        response = requests.get(api_url, timeout=60)
        if response.status_code == 200:
            # Проверяем, что нам вернулось: картинка или видео (умный анализ заголовков)
            content_type = response.headers.get('Content-Type', '').lower()
            return response.content, content_type
        else:
            print(f"[Ошибка Banana API]: Сервер вернул код {response.status_code}")
            return None, None
    except Exception as e:
        print(f"[Ошибка запроса генерации]: {e}")
        return None, None


def handle_bot_output_media(bot, chat_id, llm_response_text):
    """
    Функция-перехватчик. Ищет тег генерации в ответе ИИ, 
    вырезает его, отправляет медиа и возвращает чистый текст для юзера.
    """
    # Регулярное выражение ищет формат [ГЕНЕРАЦИЯ: тип, описание]
    pattern = r"\[ГЕНЕРАЦИЯ:\s*(.*?),\s*(.*?)\]"
    match = re.search(pattern, llm_response_text)
    
    if match:
        trigger_type = match.group(1).strip().lower() # селфи / окружение
        visual_description = match.group(2).strip()    # что именно нарисовать
        
        # Удаляем технический тег из сообщения, чтобы пользователь его не увидел
        clean_text = re.sub(pattern, "", llm_response_text).strip()
        
        # Сначала отправляем текст, чтобы бот не молчал во время генерации
        if clean_text:
            bot.send_message(chat_id, clean_text)
            clean_text = "" # Сбрасываем, чтобы дважды не отправлять
            
        # Запускаем генерацию медиа
        bot.send_chat_action(chat_id, 'upload_photo')
        media_bytes, content_type = generate_media_via_banana(trigger_type, visual_description)
        
        if media_bytes:
            # Если вернулось видео (mp4, webm и т.д.)
            if 'video' in content_type:
                bot.send_video(chat_id, media_bytes, caption="🎬")
            # Во всех остальных случаях отправляем как фото
            else:
                bot.send_photo(chat_id, media_bytes, caption="📸")
        else:
            bot.send_message(chat_id, "*(Прислал битый файл/Сообщение не загрузилось)*")
            
        return clean_text
    
    return llm_response_text


# === БЛОК ВОСПРИЯТИЯ ВХОДЯЩИХ ФАЙЛОВ ОТ ПОЛЬЗОВАТЕЛЯ ===
# Этот кусок кода регистрирует, когда пользователь кидает боту фото или видео

def register_media_handlers(bot, process_user_message_function):
    """
    Регистрирует хэндлеры для входящих фото и видео.
    process_user_message_function — это твоя основная функция обработки текста, 
    куда мы передадим описание файла вместо самого файла.
    """
    @bot.message_handler(content_types=['photo'])
    def handle_incoming_photo(message):
        # Бот видит фото. Так как мы не пишем зрение с нуля, мы передаем нейронке текстовый контекст
        caption = message.caption if message.caption else "без подписи"
        context_text = f"*[Пользователь отправил тебе ФОТОГРАФИЮ с комментарием: '{caption}'. Отреагируй на неё согласно твоему характеру]*"
        process_user_message_function(message, override_text=context_text)

    @bot.message_handler(content_types=['video', 'video_note'])
    def handle_incoming_video(message):
        # Обработка видео или кружочков
        caption = message.caption if message.caption else "без подписи"
        file_type = "КРУЖОЧЕК (видеосообщение)" if message.content_type == 'video_note' else "ВИДЕОФАЙЛ"
        context_text = f"*[Пользователь отправил тебе {file_type} с комментарием: '{caption}'. Отреагируй на него]*"
        process_user_message_function(message, override_text=context_text)


print("=== БОТ УСПЕШНО ЗАПУЩЕН И ЖДЕТ СООБЩЕНИЙ В ТЕЛЕГРАМЕ ===")
bot.infinity_polling()
