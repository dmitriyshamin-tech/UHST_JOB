import os

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── Apify (LinkedIn + Facebook) ─────────────────────────────────────────────
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# ─── Target roles ─────────────────────────────────────────────────────────────
# Work.ua will be searched for each keyword below
TARGET_ROLES = [
    "контент менеджер",
    "content manager",
    "оператор колл-центру",
    "оператор кол-центра",
    "call center operator",
    "керівник відділу",
    "руководитель отдела",
    "дизайнер",
    "designer",
    "graphic designer",
    "ui ux designer",
    "програміст",
    "розробник",
    "frontend developer",
    "backend developer",
    "python developer",
    "web developer",
    "fullstack developer",
]

# ─── E-commerce keywords (filter / highlighting) ─────────────────────────────
ECOMMERCE_KEYWORDS = [
    "e-commerce", "ecommerce", "е-комерс", "екомерс",
    "інтернет-магазин", "интернет-магазин",
    "маркетплейс", "marketplace",
    "rozetka", "розетка",
    "prom.ua", "prom ", "olx",
    "онлайн-магазин", "онлайн магазин",
    "інтернет магазин", "интернет магазин",
    "shopify", "woocommerce", "opencart", "magento",
    "fulfilment", "фулфілмент", "фулфилмент",
    "кошик", "корзина",               # shopping cart context
    "каталог товарів", "каталог товаров",
    "nova poshta", "нова пошта", "meest", "укрпошта",
]

# ─── Work.ua settings ─────────────────────────────────────────────────────────
# period: 1=last day, 3=3 days, 7=week
WORKUA_PERIOD = 1
WORKUA_MAX_PAGES = 2     # pages per role keyword (15 results/page on Work.ua)

# ─── LinkedIn (via Apify) ─────────────────────────────────────────────────────
# Actor: bebity/linkedin-profile-scraper  (free tier: ~100 results/month)
LINKEDIN_APIFY_ACTOR = "bebity/linkedin-profile-scraper"
LINKEDIN_SEARCH_QUERIES = [
    "e-commerce content manager Kyiv open to work",
    "ecommerce designer Kyiv open to work",
    "ecommerce developer Kyiv open to work",
    "інтернет-магазин менеджер Київ",
    "ecommerce call center Ukraine",
]

# ─── Facebook groups (via Apify) ──────────────────────────────────────────────
# Actor: apify/facebook-groups-scraper
FACEBOOK_APIFY_ACTOR = "apify/facebook-groups-scraper"

# Add your group URLs below. Recommended Ukrainian e-commerce/job groups:
# • "E-commerce Ukraine" — search on Facebook and add the group URL
# • "Робота в Києві / Работа в Киеве IT"
# • "Digital Marketing Ukraine"
# • "UX/UI Designers Ukraine"
# • "Developers Ukraine"
FACEBOOK_GROUP_URLS = [
    "https://www.facebook.com/groups/ecu.club/",           # E-commerce Club Ukraine
    "https://www.facebook.com/groups/149047461949955/",    # UA e-commerce group
]

FACEBOOK_POSTS_LIMIT = 50   # posts per group to scan
# Keywords that indicate someone is looking for a job
JOB_SEEK_KEYWORDS = [
    "шукаю роботу", "ищу работу", "у пошуках роботи",
    "open to work", "#opentowork", "відкритий до пропозицій",
    "looking for job", "розгляну пропозиції", "рассмотрю предложения",
    "готовий до переїзду до Києва", "готова до переїзду",
]

# ─── Robota.ua settings ───────────────────────────────────────────────────────
ROBOTAUA_PERIOD = 1   # 1=last day
ROBOTAUA_MAX_PAGES = 2
# Robota.ua uses slug-style URLs: /ru/zapros/{slug}/kyiv
ROBOTAUA_ROLE_SLUGS = [
    "content-manager",
    "контент-менеджер",
    "designer",
    "дизайнер",
    "call-center",
    "оператор-колл-центра",
    "frontend-developer",
    "backend-developer",
    "python-developer",
    "web-developer",
    "керівник-відділу",
]

# ─── DOU.ua settings ──────────────────────────────────────────────────────────
DOU_SEARCH_KEYWORDS = [
    "eCommerce",
    "e-commerce",
    "content manager",
    "designer",
    "call center",
]
DOU_CITY = "Київ"
