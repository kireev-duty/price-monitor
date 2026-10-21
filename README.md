# price-monitor — мониторинг цен конкурентов

[![CI](https://github.com/kireev-duty/price-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/kireev-duty/price-monitor/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![Excel](https://img.shields.io/badge/отчёт-Excel-217346?logo=microsoftexcel&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

Собирает цены и наличие товаров с сайтов, хранит историю в SQLite, выгружает отчёт в Excel
и присылает в Telegram, что подорожало, подешевело или закончилось.

Новый сайт подключается **без изменения кода**: достаточно описать CSS-селекторы карточки товара в `sources.toml`.

## Что умеет

- Обход каталога постранично с паузой между запросами и повтором при сетевых ошибках
- Разбор цен в любом формате: `£47.82`, `1 299 ₽`, `1.299,00 €`, `от 2 490 руб.`
- Наличие по ключевым словам; «нет в наличии» не путается с «в наличии»
- История каждого замера: текущая и предыдущая цена, минимум и максимум за всё время
- Отчёт Excel из трёх листов:
  - **Цены** — текущие цены, изменение в % (рост красным, снижение зелёным), фильтры, ссылки на товары
  - **Изменения** — что поменялось за последний запуск
  - **История** — все замеры, удобно строить сводные таблицы и графики
- Уведомление в Telegram с порогом: например, писать только об изменениях от 5%
- Если один сайт недоступен, остальные всё равно собираются

## Быстрый старт

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; на Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python -m price_monitor run --report reports/prices.xlsx
```

В `sources.toml` для примера настроены две категории демо-сайта [books.toscrape.com](https://books.toscrape.com) —
он создан специально для практики парсинга. Первый запуск собирает 43 товара и создаёт `reports/prices.xlsx`.
Следующие запуски записывают новый замер и показывают только то, что изменилось.

```
python -m price_monitor run                 # собрать цены и уведомить об изменениях
python -m price_monitor run --report r.xlsx # то же + отчёт
python -m price_monitor run --no-notify     # без Telegram
python -m price_monitor report -o r.xlsx    # только отчёт по накопленной истории
python -m price_monitor -c shop.toml run    # другой файл источников
```

## Подключить свой сайт

```toml
[[source]]
name = "Магазин"
url = "https://example.ru/catalog/kettles/"
max_pages = 10

[source.selectors]
item = ".product-card"            # карточка товара в списке
title = ".product-card__name"
link = "a.product-card__link"
price = ".product-card__price"
availability = ".product-card__stock"   # необязательно
next_page = "a.pagination__next"        # необязательно
```

Селекторы удобно подбирать в браузере: правый клик на товаре → «Исследовать элемент».

## Уведомления в Telegram

Создайте бота у [@BotFather](https://t.me/BotFather) и задайте переменные окружения
(пример — в [.env.example](.env.example)):

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
export TELEGRAM_CHAT_ID=123456789
```

Порог изменения в процентах задаётся параметром `notify_threshold` в `[settings]`.

## Запуск по расписанию

**Docker** (база и отчёты сохраняются в папках на хосте):

```bash
docker build -t price-monitor .
docker run --rm --env-file .env -v "$PWD/data:/app/data" -v "$PWD/reports:/app/reports" price-monitor
```

**cron** — каждый день в 9:00:

```
0 9 * * * cd /opt/price-monitor && .venv/bin/python -m price_monitor run --report reports/prices.xlsx
```

На Windows то же самое настраивается в Планировщике заданий.

## Тесты

```bash
pip install pytest
pytest -q
```

Тесты не ходят в интернет: страницы подставляются через `httpx.MockTransport`.

## Структура

```
price_monitor/
  config.py    чтение sources.toml и переменных окружения
  scraper.py   загрузка страниц, разбор карточек и цен, пагинация
  storage.py   SQLite: товары, замеры, поиск изменений
  report.py    отчёт Excel (openpyxl)
  notify.py    уведомления в Telegram
  __main__.py  командная строка
```

## Что можно добавить под задачу

- Сайты, которые рендерятся на JavaScript: Playwright вместо httpx
- Сбор с карточки товара (характеристики, остатки по складам), а не только из списка
- Выгрузка в Google Sheets, PostgreSQL или 1С
- Прокси и ротация User-Agent для сайтов с защитой
- Веб-панель с графиками цен

Не забывайте про правила сайтов: соблюдайте `robots.txt` и пользовательское соглашение и не нагружайте чужие серверы.

## Лицензия

[MIT](LICENSE)
