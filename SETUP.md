# E-commerce Candidate Monitor — Инструкция запуска

## Что делает скрипт

Каждый день в 10:00 (Киев) автоматически:
1. Ищет новые резюме на **Work.ua** (Киев, последние 24 часа)
2. Ищет LinkedIn-профили через **Apify** (люди в поиске работы в e-commerce)
3. Мониторит посты в **Facebook-группах** через Apify
4. Отправляет дайджест в **Telegram-чат**
5. Запоминает найденных кандидатов — повторно не присылает

---

## Шаг 1 — Создать репозиторий на GitHub

1. Зайдите на https://github.com → New repository
2. Назовите `ecommerce-monitor`
3. Сделайте **Private** (данные кандидатов — личная информация)
4. Загрузите все файлы этого проекта в репозиторий

---

## Шаг 2 — Добавить секреты в GitHub

GitHub → Settings → Secrets and variables → Actions → **New repository secret**

| Имя секрета | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен вашего бота (от @BotFather) |
| `TELEGRAM_CHAT_ID` | ID вашего чата (как получить — ниже) |
| `APIFY_API_TOKEN` | Токен Apify (если используете LinkedIn/FB) |

### Как получить TELEGRAM_CHAT_ID
1. Напишите любое сообщение в чат с вашим ботом
2. Откройте в браузере: `https://api.telegram.org/bot<ВАШ_ТОКЕН>/getUpdates`
3. Найдите `"chat": {"id": XXXXXXX}` — это и есть chat_id

---

## Шаг 3 — Настроить Apify (для LinkedIn и Facebook)

1. Зарегистрируйтесь на https://apify.com (бесплатный план)
2. Перейдите: Console → Settings → Integrations → API token → скопируйте
3. Добавьте в GitHub Secrets как `APIFY_API_TOKEN`

**Бесплатный лимит Apify:** ~$5/месяц кредитов — достаточно для ежедневного мониторинга.

---

## Шаг 4 — Настроить Facebook-группы

Откройте `config.py` и заполните `FACEBOOK_GROUP_URLS`.

### Рекомендованные украинские группы для поиска:
- Facebook: поиск → **"E-commerce Ukraine"**
- Facebook: поиск → **"Робота Київ маркетинг"**
- Facebook: поиск → **"Digital Marketing Ukraine"**
- Facebook: поиск → **"UX UI дизайнери Україна"**
- Facebook: поиск → **"Розробники Украина"**
- Facebook: поиск → **"Контент менеджери"**
- Facebook: поиск → **"Ищу работу Киев 2024"**

Вступайте в группы, копируйте URL и вставляйте в config.py:
```python
FACEBOOK_GROUP_URLS = [
    "https://www.facebook.com/groups/123456789",
    "https://www.facebook.com/groups/987654321",
]
```

---

## Шаг 5 — Проверить работу вручную

В GitHub → Actions → E-commerce Candidate Monitor → **Run workflow**

Или локально:
```bash
pip install -r requirements.txt
set TELEGRAM_BOT_TOKEN=ваш_токен
set TELEGRAM_CHAT_ID=ваш_chat_id
python main.py
```

---

## Как выглядит сообщение в Telegram

```
🔍 E-commerce кандидати — 19.05.2026
Знайдено: 5 нових | ✅ підтверджений e-com досвід: 3

── Work.ua (3) ──

✅ 📋 Іванченко Олена — Контент-менеджер
   3 роки досвіду в інтернет-магазині одягу...
   📅 Сьогодні
   Відкрити профіль →

❓ 📋 Петров Дмитро — Дизайнер
   Шукаю нові можливості...
   📅 Сьогодні
   Відкрити профіль →

── LinkedIn (2) ──
...
```

**Значки:**
- ✅ — у кандидата в профиле/резюме есть ключевые слова e-commerce
- ❓ — e-commerce в описании не найдено, но роль подходит

---

## Настройка ключевых слов

Отредактируйте `config.py`:

- `TARGET_ROLES` — какие должности искать
- `ECOMMERCE_KEYWORDS` — что считать признаком e-commerce опыта
- `JOB_SEEK_KEYWORDS` — фразы, по которым понимаем, что человек ищет работу
- `WORKUA_PERIOD` — за сколько дней смотреть резюме (1 = вчера/сегодня)

---

## Структура проекта

```
├── main.py                          # Точка входа
├── config.py                        # Все настройки ← редактируйте здесь
├── requirements.txt
├── scrapers/
│   ├── workua.py                    # Work.ua парсер
│   ├── linkedin_apify.py            # LinkedIn через Apify
│   └── facebook_apify.py            # Facebook через Apify
├── notifications/
│   └── telegram.py                  # Отправка в Telegram
├── data/
│   └── seen_ids.json               # Память о найденных (авто-обновляется)
└── .github/workflows/
    └── monitor.yml                  # Расписание GitHub Actions
```
