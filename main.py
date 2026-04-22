# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID_RAW = os.getenv("TELEGRAM_GROUP_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")


# --- SAFE CHECKS (чтобы не падало молча) ---

if not BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не задан в переменных окружения")

if not GROUP_ID_RAW:
    raise ValueError("❌ TELEGRAM_GROUP_ID не задан в переменных окружения")

try:
    GROUP_ID = int(GROUP_ID_RAW)
except ValueError:
    raise ValueError("❌ TELEGRAM_GROUP_ID должен быть числом, пример: -1001234567890")

if not CRYPTO_TOKEN:
    raise ValueError("❌ CRYPTO_TOKEN не задан в переменных окружения")


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
