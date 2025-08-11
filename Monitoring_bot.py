import logging
import asyncio
import aiohttp
import json
from pathlib import Path
from flask import Flask
from telebot.async_telebot import AsyncTeleBot

# === Конфигурация ===
BOT_TOKEN = '8089626698:AAGqLnFtz6_TdJQg7UqnQI1u4slt3iQb0NI'
bot = AsyncTeleBot(BOT_TOKEN)
DATA_FILE = Path("urls.json")

# === Логирование ===
logging.basicConfig(
    filename="monitor.log",
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

user_urls = {}
unreachable_urls = {}

# === Flask-сервер (для Railway) ===
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# === Загрузка/сохранение URL-ов ===
def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_urls, f, indent=2)

# === Проверка URL ===
async def check_url(url):
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False, headers=headers) as resp:
                return resp.status < 400
    except Exception as e:
        logging.error(f"Ошибка при проверке {url}: {e}")
        return False

# === Проверка заглушки ===
async def check_stub(url):
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False) as resp:
                text = await resp.text()
                keywords = [
                    "технические работы",
                    "временно недоступен",
                    "site maintenance",
                    "scheduled maintenance"
                ]
                return any(word.lower() in text.lower() for word in keywords)
    except Exception as e:
        logging.error(f"Ошибка при проверке заглушки {url}: {e}")
        return False

# === Фоновый мониторинг ===
async def monitor_sites():
    while True:
        for user_id, urls in user_urls.items():
            for url in urls:
                is_up = await check_url(url)
                was_unreachable = unreachable_urls.get((user_id, url), False)

                if not is_up and not was_unreachable:
                    await bot.send_message(user_id, f"⚠️ Сайт недоступен: {url}")
                    unreachable_urls[(user_id, url)] = True

                elif is_up and was_unreachable:
                    await bot.send_message(user_id, f"✅ Сайт снова доступен: {url}")
                    unreachable_urls[(user_id, url)] = False
        await asyncio.sleep(150)

# === Команды Telegram ===
@bot.message_handler(commands=['start'])
async def cmd_start(message):
    user = message.from_user
    user_id = str(user.id)
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    await bot.send_message(message.chat.id, f"Привет, {full_name}!\nИспользуй /add <url> чтобы добавить сайт.")

@bot.message_handler(commands=['add'])
async def cmd_add(message):
    user_id = str(message.from_user.id)
    urls = message.text.split()[1:]
    if not urls:
        await bot.send_message(message.chat.id, "Пример: /add https://example.com")
        return
    user_urls.setdefault(user_id, [])
    for url in urls:
        if url not in user_urls[user_id]:
            user_urls[user_id].append(url)
    save_data()
    await bot.send_message(message.chat.id, "✅ URL-ы добавлены!")

@bot.message_handler(commands=['list'])
async def cmd_list(message):
    user_id = str(message.from_user.id)
    urls = user_urls.get(user_id, [])
    if urls:
        await bot.send_message(message.chat.id, "🔍 Текущие сайты:\n" + "\n".join(urls))
    else:
        await bot.send_message(message.chat.id, "Список пуст.")

@bot.message_handler(commands=['clear'])
async def cmd_clear(message):
    user_id = str(message.from_user.id)
    user_urls[user_id] = []
    save_data()
    await bot.send_message(message.chat.id, "🧹 Список очищен.")

@bot.message_handler(commands=['check'])
async def cmd_check(message):
    user_id = str(message.from_user.id)
    urls = user_urls.get(user_id, [])
    if not urls:
        await bot.send_message(message.chat.id, "Список пуст. Добавьте сайты через /add <url>")
        return
    results = []
    for url in urls:
        is_up = await check_url(url)
        status = "✅ Доступен" if is_up else "⚠️ Недоступен"
        results.append(f"{status}: {url}")
    await bot.send_message(message.chat.id, "📡 Результаты проверки:\n" + "\n".join(results))

@bot.message_handler(commands=['check_in'])
async def cmd_check_in(message):
    user_id = str(message.from_user.id)
    urls = user_urls.get(user_id, [])
    if not urls:
        await bot.send_message(message.chat.id, "Список пуст. Добавьте сайты через /add <url>")
        return
    results = []
    for url in urls:
        has_stub = await check_stub(url)
        status = "⚠️ Заглушка найдена" if has_stub else "✅ Работает штатно"
        results.append(f"{status}: {url}")
    await bot.send_message(message.chat.id, "🛠️ Проверка на заглушку:\n" + "\n".join(results))

# === Запуск ===
async def main():
    global user_urls
    user_urls = load_data()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, lambda: app.run(host="0.0.0.0", port=8080))
    await asyncio.gather(bot.infinity_polling(), monitor_sites())

if __name__ == "__main__":
    asyncio.run(main())
