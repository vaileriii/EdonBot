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
            return f"*(Эдон запутался в мыслях)* [Ошибка разбора: {e}]"
    else:
        return f"*(Эдон потерял связь с миром)* [Ошибка API: {response.status_code} - {response.text}]"

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    reply = call_gemini(chat_id, message.text)
    bot.send_message(chat_id, reply)

@bot.message_handler(content_types=['video_note'])
def handle_video_note(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "*Эдон внимательно смотрит твой кружочек...*", parse_mode="Markdown")
    bot.send_chat_action(chat_id, 'typing')
    
    file_info = bot.get_file(message.video_note.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    video_base64 = base64.b64encode(downloaded_file).decode('utf-8')
    
    prompt = "Пользователь отправил тебе видеосообщение (кружочек). Внимательно посмотри видео, послушай голос, интонацию, выражение лица и ответь в своей роли, комментируя увиденное или услышанное, если это уместно."
    
    reply = call_gemini(chat_id, prompt, video_base64)
    bot.send_message(chat_id, reply)

print("=== БОТ ЭДОНА УСПЕШНО ЗАПУЩЕН И ЖДЕТ СООБЩЕНИЙ В ТЕЛЕГРАМЕ ===")
bot.infinity_polling()