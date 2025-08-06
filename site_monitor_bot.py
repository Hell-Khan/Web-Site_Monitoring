import logging
import asyncio
import aiohttp
import json
from pathlib import Path
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# === Конфигурация ===
BOT_TOKEN = "8089626698:AAGqLnFtz6_TdJQg7UqnQI1u4slt3iQb0NI"
DATA_FILE = Path("urls.json")

# === Логирование ===
logging.basicConfig(
    filename="monitor.log",
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

user_urls = {}
unreachable_urls = {}

# === Загрузка URL-ов ===
def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_urls, f, indent=2)

# === Проверка сайта ===
async def check_url(url):
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                return resp.status < 400
    except:
        return False

# === Фоновый мониторинг ===
async def monitor_sites(app):
    while True:
        for user_id, urls in user_urls.items():
            for url in urls:
                is_up = await check_url(url)
                was_unreachable = unreachable_urls.get((user_id, url), False)

                if not is_up and not was_unreachable:
                    await app.bot.send_message(chat_id=user_id, text=f"⚠️ Сайт недоступен: {url}")
                    unreachable_urls[(user_id, url)] = True
                    logging.warning(f"{url} недоступен (user {user_id})")

                elif is_up and was_unreachable:
                    await app.bot.send_message(chat_id=user_id, text=f"✅ Сайт снова доступен: {url}")
                    unreachable_urls[(user_id, url)] = False
                    logging.info(f"{url} снова доступен (user {user_id})")

        await asyncio.sleep(150)

# === Команды Telegram ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Используй /add <url1> <url2> ... чтобы добавить сайты для мониторинга.")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    urls = update.message.text.split()[1:]

    if not urls:
        await update.message.reply_text("Пример: /add https://example.com")
        return

    user_urls.setdefault(user_id, [])
    for url in urls:
        if url not in user_urls[user_id]:
            user_urls[user_id].append(url)

    save_data()
    await update.message.reply_text("✅ URL-ы добавлены!")

async def list_urls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    urls = user_urls.get(user_id, [])
    if urls:
        await update.message.reply_text("🔍 Текущие сайты:\n" + "\n".join(urls))
    else:
        await update.message.reply_text("Список пуст.")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_urls[user_id] = []
    save_data()
    await update.message.reply_text("🧹 Список очищен.")

# === Основная логика ===
async def main():
    global user_urls
    user_urls = load_data()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_urls))
    app.add_handler(CommandHandler("clear", clear))

    asyncio.create_task(monitor_sites(app))

    print("✅ Бот запущен. Ожидает команды...")
    await app.run_polling()

# === Точка входа ===
if __name__ == "__main__":
    import sys
    import warnings

    # Поддержка Windows + отключение предупреждений
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    async def safe_main():
        try:
            await main()
        except Exception:
            logging.error("Ошибка при запуске бота", exc_info=True)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.create_task(safe_main())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен.")
