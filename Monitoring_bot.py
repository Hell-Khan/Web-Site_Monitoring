import logging
import asyncio
import aiohttp
import json
import telebot
from pathlib import Path

# === Конфигурация ===
BOT_TOKEN = '8089626698:AAGqLnFtz6_TdJQg7UqnQI1u4slt3iQb0NI'
bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = Path("urls.json")

# === Логирование ===
logging.basicConfig(
    filename="monitor.log",
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

user_urls = {}
unreachable_urls = {}
user_logger = logging.getLogger("users")
user_handler = logging.FileHandler("users.log", encoding="utf-8")
user_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
user_logger.setLevel(logging.INFO)
user_logger.addHandler(user_handler)

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
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False, headers=headers) as resp:
                return resp.status < 400
    except Exception as e:
        logging.error(f"Ошибка при проверке {url}: {e}")
        return False


# === Фоновый мониторинг ===
async def monitor_sites():
    while True:
        for user_id, urls in user_urls.items():
            for url in urls:
                is_up = await check_url(url)
                was_unreachable = unreachable_urls.get((user_id, url), False)

                if not is_up and not was_unreachable:
                    bot.send_message(user_id, f"⚠️ Сайт недоступен: {url}")
                    unreachable_urls[(user_id, url)] = True
                    logging.warning(f"{url} недоступен (user {user_id})")

                elif is_up and was_unreachable:
                    bot.send_message(user_id, f"✅ Сайт снова доступен: {url}")
                    unreachable_urls[(user_id, url)] = False
                    logging.info(f"{url} снова доступен (user {user_id})")

        await asyncio.sleep(150)

# === Команды Telegram ===
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user = message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "без username"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    # Лог в файл users.log
    user_logger.info(f"New user: {user_id} - {username} - {full_name}")

    # Ответ пользователю
    text = (
        f"Привет, {full_name}!\n"
        "Я мониторю сайты. Используй /add <url> чтобы начать."
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['add'])
def cmd_add(message):
    user_id = str(message.from_user.id)
    urls = message.text.split()[1:]
    if not urls:
        bot.send_message(message.chat.id, "Пример: /add https://example.com")
        return

    user_urls.setdefault(user_id, [])
    for url in urls:
        if url not in user_urls[user_id]:
            user_urls[user_id].append(url)

    save_data()
    bot.send_message(message.chat.id, "✅ URL-ы добавлены!")

@bot.message_handler(commands=['list'])
def cmd_list(message):
    user_id = str(message.from_user.id)
    urls = user_urls.get(user_id, [])
    if urls:
        bot.send_message(message.chat.id, "🔍 Текущие сайты:\n" + "\n".join(urls))
    else:
        bot.send_message(message.chat.id, "Список пуст.")

@bot.message_handler(commands=['clear'])
def cmd_clear(message):
    user_id = str(message.from_user.id)
    user_urls[user_id] = []
    save_data()
    bot.send_message(message.chat.id, "🧹 Список очищен.")

@bot.message_handler(commands=['check'])
def cmd_check(message):
    user_id = str(message.from_user.id)
    urls = user_urls.get(user_id, [])

    if not urls:
        bot.send_message(message.chat.id, "Список сайтов пуст. Добавьте сайты через /add <url>")
        return

    async def check_all():
        results = []
        for url in urls:
            is_up = await check_url(url)
            status = "✅ Доступен" if is_up else "⚠️ Недоступен"
            results.append(f"{status}: {url}")
            logging.info(f"Ручная проверка: {url} -> {status} (user {user_id})")

        response = "\n".join(results)
        bot.send_message(message.chat.id, "📡 Результаты проверки:\n" + response)

    asyncio.run(check_all())


# === Запуск ===
if __name__ == "__main__":
    import threading
    import sys

    user_urls = load_data()

    # Поток для телебота
    threading.Thread(target=bot.polling, kwargs={"non_stop": True}).start()

    # Запуск asyncio цикла
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(monitor_sites())
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен.")
