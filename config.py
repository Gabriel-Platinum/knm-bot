from dotenv import load_dotenv
import os

load_dotenv()  

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4'
}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "default_admin")  # если в .env нет, будет default_admin
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "").encode() if os.getenv("ADMIN_PASSWORD_HASH") else None

