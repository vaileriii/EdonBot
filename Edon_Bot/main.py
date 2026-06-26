import os
import base64
import telebot
import requests
import re
import random
import urllib.parse

# ==========================================
# ⚙️ НАСТРОЙКИ LINK API И ТЕЛЕГРАМА:
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://linkapi.ai/v1/chat/completions"
MODEL_NAME = "[次]gemini-3.1-pro-preview"

# === НАСТРОЙКИ МЕДИА-ДВИЖКА ===
NANO_BANANA_TOKEN = os.getenv("NANO_BANANA_TOKEN")
BANANA_BASE_URL = "https://naistera.org/prompt/"
REFS_DIR = "appearance_refs" 

# ИСПРАВЛЕНО: Прямая raw-ссылка, по которой Nano Banana сможет забирать референсы внешности
GITHUB_REFS_URL = "https://raw.githubusercontent.com/vaileriii/EdonBot/main/Edon_Bot/appearance_refs/"
# ==========================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)
histories = {}

def load_file(filename, default_text=""):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    return default_text


def generate_media_via_banana(trigger_type, visual_description):
    """Генерация картинок и видео через Nano Banana со стилями и референсами"""
    style_prompt = load_file("image_prompt.txt", "realism, 90s retro style, analog film grain, cinematic lighting")
    final_prompt = f"{style_prompt}, {visual_description}"
    
    if trigger_type == "селфи" or trigger_type == "себя":
        if os.path.exists(REFS_DIR) and os.listdir(REFS_DIR):
            all_refs = [f for f in os.listdir(REFS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if all_refs:
                chosen_ref = random.choice(all_refs)
                ref_url = f"{GITHUB_REFS_URL}{chosen_ref}"
                final_prompt = f"Reference image: {ref_url}, appearance target identical to reference, {final_prompt}"

    encoded_prompt = urllib.parse.quote(final_prompt)
    api_url = f"{BANANA_BASE_URL}{encoded_prompt}?aspect_ratio=2:3&token={NANO_BANANA_TOKEN}&banana"
    
    try:
        response = requests.get(api_url, timeout=60)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            return response.content, content_type
        else:
            return None, f"API Error {response.status_code}"
    except Exception as e:
        return None, str(e)


def handle_bot_output_media(bot, chat_id, llm_response_text):
    """Перехватчик тегов генерации. Вырезает тег, отправляет медиа."""
    pattern = r"\[ГЕНЕРАЦИЯ:\s*(.*?),\s*(.*?)\]"
    match = re.search(pattern, llm_response_text)
    
    if match:
        trigger_type = match.group(1).strip().lower()
        visual_description = match.group(2).strip()
        
        # Чистим текст от технического тега
        clean_text = re.sub(pattern, "", llm_response_text).strip()
        
        if clean_text:
            bot.send_message(chat_id, clean_text)
            
        bot.send_chat_action(chat_id, 'upload_photo')
        
        try:
            media_bytes, content_type = generate_media_via_banana(trigger_type, visual_description)
            
            if media_bytes:
                if 'video' in content_type:
                    bot.send_video(chat_id, media_bytes, caption="🎬")
                else:
                    bot.send_photo(chat_id, media_bytes, caption="📸")
            else:
                bot.send_message(chat_id, f"❌ ОШИБКА BANANA API: {content_type}")
                
        except Exception as e:
            bot.send_message(chat_id, f"❌ КРИТИЧЕСКАЯ ОШИБКА МЕДИА-ДВИЖКА:\n`{str(e)}`", parse_mode='Markdown')
            
        return "" # Сигнал, что текст уже обработан и отправлен внутри функции
    
    return llm_response_text


def call_gemini(chat_id, new_message_text, video_base64=None):
    if chat_id not in histories:
        histories[chat_id] = []
    
    # ИСПРАВЛЕНО: Теперь system_prompt.txt со всеми правилами генерации ОБЯЗАТЕЛЬНО склеивается в инструкции!
    system_instruction = (
        load_file("system_prompt.txt") + "\n\n" +
        load_file("character.txt") + "\n\n=== ЛОР МИРА ===\n" +
        load_file("lore.txt")
    )
    
    content_list = [{"type": "text", "text": new_message_text}]
    
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


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    histories[chat_id] = []
    greeting = load_file("greeting.txt", "— Ну привет. Чё хотела?")
    bot.send_message(chat_id, greeting)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    
    # Получаем сырой ответ от ИИ
    reply = call_gemini(chat_id, message.text)
    
    # ИСПРАВЛЕНО: Прогоняем через перехватчик медиа!
    final_text = handle_bot_output_media(bot, chat_id, reply)
    
    # Если там не было тегов генерации, отправляем обычный текст
    if final_text:
        bot.send_message(chat_id, final_text)


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
    
    # Тут тоже включаем перехватчик на случай, если он захочет ответить картинкой на кружочек
    final_text = handle_bot_output_media(bot, chat_id, reply)
    if final_text:
        bot.send_message(chat_id, final_text)


# Хэндлеры для входящих файлов (картинок и видео от юзера)
@bot.message_handler(content_types=['photo'])
def handle_incoming_photo(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    caption = message.caption if message.caption else "без подписи"
    context_text = f"*[Пользователь отправил тебе ФОТОГРАФИЮ с комментарием: '{caption}'. Отреагируй на неё согласно твоему характеру]*"
    reply = call_gemini(chat_id, context_text)
    final_text = handle_bot_output_media(bot, chat_id, reply)
    if final_text:
        bot.send_message(chat_id, final_text)


print("=== БОТ СВЯЗАН С МЕДИА-ДВИЖКОМ И ЗАПУЩЕН ===")
bot.infinity_polling()

