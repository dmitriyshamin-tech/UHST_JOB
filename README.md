# Google Sheets Media Radar для e-commerce: YouTube + RSS + AI + Telegram

Этот пакет разворачивает Google Sheets-дашборд, который подтягивает RSS украинских бизнес/tech/retail-медиа, собирает релевантные YouTube-видео, оценивает материалы по влиянию на e-commerce бизнес матрасы/мебель и отправляет недельный топ-5 событий в Telegram-канал.

## Что внутри

- `Code.gs` — Google Apps Script для Google Sheets.
- Листы, которые создаёт `setupDashboard()`:
  - `Dashboard` — краткая сводка и топ недели.
  - `Settings` — API-ключи, Telegram, расписание, AI-провайдер.
  - `Sources` — редактируемый список RSS/YouTube источников.
  - `Raw RSS` — сырые RSS-материалы.
  - `Raw YouTube` — сырые YouTube-видео.
  - `Scored Content` — AI/heuristic оценка 1–5.
  - `Weekly Top 5` — события недели для реакции.
  - `Telegram Queue` — очередь отправки сообщений.
  - `Logs` — ошибки и технический журнал.

## Быстрый запуск

1. Создайте новую Google Sheet.
2. Откройте `Extensions → Apps Script`.
3. Вставьте содержимое `Code.gs`.
4. Сохраните проект.
5. Запустите функцию `setupDashboard()` и выдайте разрешения.
6. На листе `Settings` заполните:
   - `YOUTUBE_API_KEY` — ключ YouTube Data API v3.
   - `AI_PROVIDER` — `HEURISTIC`, `OPENAI` или `GEMINI`.
   - `OPENAI_API_KEY` или `GEMINI_API_KEY`, если нужен настоящий AI scoring.
   - `TELEGRAM_BOT_TOKEN` — токен бота от BotFather.
   - `TELEGRAM_CHAT_ID` — `@channelusername` или numeric channel/chat id.
7. Добавьте бота администратором Telegram-канала с правом публиковать сообщения.
8. Запустите `refreshAll()` для первого заполнения.
9. Запустите `sendWeeklyDigestToTelegram()` для тестовой отправки.
10. Запустите `installTriggers()` для автообновления и еженедельной отправки.

## Как добавлять источники

Откройте лист `Sources` и добавьте новую строку:

| Type | Name | URL_OR_ID | Query | Enabled | Weight | Notes |
|---|---|---|---|---|---|---|
| RSS | Название медиа | `https://example.com/feed/` | пусто | TRUE | 1.0 | комментарий |
| YOUTUBE_SEARCH | Название запроса | пусто | `SEO e-commerce Україна` | TRUE | 1.3 | комментарий |
| YOUTUBE_CHANNEL | Название канала | `UC...` | пусто | TRUE | 1.1 | комментарий |

Чтобы временно отключить источник, поставьте `Enabled = FALSE`. Код менять не нужно.

## Стартовые источники

В шаблоне уже добавлены проверенные RSS endpoints:

- AIN.ua — `https://ain.ua/feed/`
- DOU — `https://dou.ua/lenta/feed/`
- Vector — `https://vctr.media/feed/`
- Економічна правда — `https://www.epravda.com.ua/rss/`
- RAU — `https://rau.ua/feed/`
- MMR — `https://mmr.ua/feed`
- MC.today — `https://mc.today/feed/`
- Українська правда — `https://www.pravda.com.ua/rss/view_news/` отключён по умолчанию как общий источник

Forbes.ua и LIGA Business оставлены вне стартового списка, потому что типовые `/rss` и `/feed` endpoints на момент проверки не отдавали валидный RSS. Их можно добавить через RSS.app, Feed43 или другой генератор RSS, если нужен стабильный поток.

## AI scoring

Оценка 1–5 рассчитана под e-commerce бизнес матрасы/мебель:

- `5` — нужна реакция в течение недели.
- `4` — сильный стратегический сигнал.
- `3` — стоит мониторить и, возможно, адаптировать контент/рекламу.
- `2` — слабая косвенная релевантность.
- `1` — можно игнорировать.

Критерии:

- влияние на SEO и Google выдачу;
- Google Merchant Center, Shopping, алгоритмы;
- спрос на мебель/матрасы и товары для дома;
- маркетплейсы, retail, доставка, импорт, склад;
- рекламные платформы и стоимость привлечения;
- регулирование, доверие, репутация, персональные данные;
- конкурентные действия и повторяющиеся сигналы в нескольких источниках.

Если `AI_PROVIDER = HEURISTIC`, скрипт работает без платного AI API и использует ключевые слова. Для более качественного ранжирования поставьте `OPENAI` или `GEMINI`.

## Telegram

Функция `sendWeeklyDigestToTelegram()`:

1. обновляет лист `Weekly Top 5`;
2. формирует digest в HTML-разметке Telegram;
3. кладёт сообщение в `Telegram Queue`;
4. отправляет через Telegram Bot API.

Бот должен быть администратором канала. Для публичного канала можно использовать `@channelusername`; для приватного канала обычно нужен numeric chat id.

## Рекомендуемый рабочий режим

- Обновление данных: каждые 6 часов.
- Еженедельный digest: понедельник, 09:00 Europe/Kiev.
- Просмотр вручную: листы `Dashboard` и `Weekly Top 5`.
- Добавление новых источников: только через `Sources`.
- Изменение весов/порогов: через `Settings`.

## Что можно улучшить дальше

- Подключить Search Console и Merchant Center для автоматической оценки влияния новостей на реальные позиции и товарные фиды.
- Добавить daily urgent alerts для score 5.
- Добавить отдельные рубрики: SEO, Ads, Competitors, Supply, Legal, Category Demand.
- Подключить Telegram inline-кнопки: `React`, `Ignore`, `Create task`, `Add keyword`.
