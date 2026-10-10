import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / '.env')

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()

# Список числовых ID администраторов
admin_ids_raw = os.getenv('ADMIN_ID', '').strip()
ADMIN_IDS = [int(x.strip()) for x in admin_ids_raw.split(',') if x.strip().isdigit()]

# Список юзернеймов администраторов (без @, в нижнем регистре)
admin_usernames_raw = os.getenv('ADMIN_USERNAME', '').strip()
ADMIN_USERNAMES = [
    u.strip().lstrip('@').lower()
    for u in admin_usernames_raw.split(',')
    if u.strip()
]

# ID закрытой группы (по умолчанию)
GROUP_ID_RAW = os.getenv('GROUP_ID', '').strip()
DEFAULT_GROUP_ID = int(GROUP_ID_RAW) if (GROUP_ID_RAW.startswith('-') and GROUP_ID_RAW[1:].isdigit()) or GROUP_ID_RAW.isdigit() else None

# Название группы
DEFAULT_GROUP_NAME = os.getenv('GROUP_NAME', 'алфавит').strip()

# Порт для веб-сервера (нужен для хостингов вроде Render)
PORT = int(os.getenv('PORT', '8080'))

DB_PATH = BASE_DIR / 'alphabet_bot.db'
