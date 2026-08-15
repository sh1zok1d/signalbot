# BTC Signal Bot — Этап 1: data_ingestion + backfill + storage

Реализация первого этапа из спецификации: получение, сохранение и
валидация реальных 1m-баров по 4 биржам (Binance, Bybit, OKX, Bitget) +
30-дневный REST-бэкфилл + TimescaleDB/Redis storage. Telegram, percentile_engine
и signal_engine **сознательно не включены** — по плану из спеки следующий шаг
только после вашего подтверждения этого этапа.

> **Обновление (2026-07-17):** Этап 1 принят. Активный MVP работает на **3
> биржах** (Binance, Bybit, OKX) — Bitget отключён через
> `config.enabled_exchanges` (данные/код сохранены). Подробности и критерии
> повторного включения — в `docs/STAGE1_ACCEPTANCE.md`.

> **Forecasting status:** the codebase has since grown a Stage 2 shadow
> forecasting subsystem (`analytics/forecasting/`, a 5m single-bucket
> heuristic, plus a durable Telegram notifier). Further product development
> of that current forecast logic ("V1") is now **frozen** as a stable
> research baseline; the forecasting product now moves to a planned
> multi-timeframe direction ("V2"). See **`docs/FORECASTING_ROADMAP.md`** —
> the canonical source of truth for where the forecasting product is headed
> — and **`docs/V2_PRODUCT_CONTRACT.md`** for what V2 product behavior is
> frozen to mean. V2 is not yet implemented. This does not affect Stage 1
> ingestion, described below.

## Что поправлено при ревью (эта итерация)

1. **Блокирующий баг инициализации схемы.** `init_schema` выполнял весь
   `schema.sql` одним `conn.execute()`. asyncpg отправляет многооператорную
   строку одной неявной транзакцией, а continuous-aggregate'ы TimescaleDB
   (`CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` и
   `add_continuous_aggregate_policy`) **не могут выполняться внутри
   транзакции** — первый запуск падал бы. Теперь схема разбивается на
   отдельные операторы и каждый выполняется своим `execute()` (каждый — в
   собственной неявной транзакции). Все операторы идемпотентны, повторный
   запуск безопасен.
2. **Режим валидации `--validate`.** Спека для этапа 1 требует не только
   получить и сохранить, но и *провалидировать* 1m-бары. Добавлен
   read-only отчёт (`storage/validate.py`): по каждой бирже — число баров,
   диапазон дат, свежесть live-бара, оценка пропусков; счётчики OI / funding /
   mark / ликвидаций; сводка `backfill_runs` (включая `partial`/`failed`);
   состояние continuous-aggregate'ов; итоговый вердикт со списком проблем.
3. **Логирование восстановления связи.** В `_coverage_loop` событие `restore`
   фактически никогда не писалось (флаг сбрасывался в `touch()` раньше, чем
   его читал цикл). Учёт простоя перенесён в сам менеджер: теперь корректно
   пишутся оба события — `disconnect` и `restore` с downtime — то, что нужно
   для «restored»-алерта на этапе 3.

## Важное предупреждение

Этот код был написан и синтаксически проверен (`py_compile`) в песочнице
**без доступа в интернет** — то есть ни один WebSocket, ни один REST-запрос
к биржам, ни подключение к настоящей TimescaleDB/Redis здесь физически не
тестировались. Структура, эндпоинты и поля ответов соответствуют моим
знаниям API Binance/Bybit/OKX/Bitget, но биржевые API периодически меняются —
перед боевым использованием обязательно:

1. Прогнать `python main.py --backfill-only` на вашем сервере с реальным
   интернетом и проверить, что строки действительно пишутся в БД.
2. Прогнать `python main.py --skip-backfill` на пару минут и посмотреть в
   логах, что все 4 WS-клиента подключились и полились сделки/бары.
3. Особое внимание — на ликвидации: у Bitget нет надёжного публичного
   потока ликвидаций (см. `data_ingestion/bitget_client.py`), у OKX это
   агрегированный/задержанный канал `liquidation-orders` на business WS
   (см. `data_ingestion/okx_client.py`). Это осознанное решение, а не баг —
   но стоит explicitly перепроверить перед тем как полагаться на consensus
   ликвидаций для сигналов (этап 2).
4. У OKX и Bitget нет проверенных мной публичных эндпоинтов для
   исторического (30-дневного) Open Interest, а у Bitget — ещё и
   исторического Mark Price. Бэкфилл для этих источников помечается
   `status: partial` в таблице `backfill_runs` с пояснением в `note`, а не
   подделывается нулями (по вашему же правилу в спеке). Начиная с момента
   запуска бота эти метрики продолжат копиться уже live.

Рекомендую для дальнейшей итеративной разработки (запуск, отладка по
реальным логам, фиксы под конкретные ответы API) использовать **Claude Code**
на вашем сервере — там у Claude будет реальный сетевой доступ, чтобы
запускать и чинить это по факту, а не вслепую.

## Структура проекта

```
btc-signal-bot/
├── config/config.yaml       # все пороги/окна/cooldown - ничего не хардкожено в коде
├── common/                  # config loader, logging
├── storage/                 # TimescaleDB schema + asyncpg writer, Redis hot-state
├── data_ingestion/          # WS-клиенты 4 бирж + live 1m bar aggregator + coverage/reconnect
├── backfill/                # REST 30-дневный бэкфилл klines/OI/funding/mark price
├── deploy/                  # пример systemd unit
├── main.py                  # entrypoint этапа 1
├── docker-compose.yml       # TimescaleDB + Redis для локального запуска
├── requirements.txt
├── .env.example / .env      # .env уже заполнен вашим Telegram токеном/chat_id
```

## Запуск локально

```bash
# 1. Инфраструктура (TimescaleDB + Redis)
docker compose up -d

# 2. Виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. .env уже создан и содержит ваш TELEGRAM_BOT_TOKEN/CHAT_ID (пока не
#    используются в этом этапе, но уже готовы для этапа 3) и DSN, совпадающий
#    с docker-compose. Проверьте/поправьте при необходимости.

# 4. Только бэкфилл (проверить, что данные реально льются в БД)
python main.py --backfill-only

# 5. Полный запуск: бэкфилл (если ещё не делался) + live-ingestion
python main.py

# Быстрая проверка, что льётся live, без повторного бэкфилла:
python main.py --skip-backfill

# Валидация: read-only отчёт по тому, что реально лежит в БД
# (число баров/диапазон/свежесть/пропуски/backfill_runs). Ничего не пишет.
python main.py --validate
```

После `--backfill-only` (или после нескольких минут live) запустите
`python main.py --validate` — это и есть «показать рабочий прототип» из
спеки в машиночитаемом виде. Если по всем 4 биржам видны разумные объёмы
1m-баров за ~30 дней и вердикт зелёный — этап 1 можно считать принятым.

Бэкфилл идемпотентен: `backfill_runs` хранит статус по каждой паре
(биржа, источник), повторный запуск не будет заново тянуть уже
завершённые (`status = complete`) окна.

### Проверка в базе

```sql
SELECT exchange, count(*), min(ts), max(ts) FROM klines_1m GROUP BY exchange;
SELECT exchange, source, status, rows_written, note FROM backfill_runs ORDER BY id DESC LIMIT 20;
SELECT * FROM connectivity_events ORDER BY ts DESC LIMIT 20;
```

## Продакшн (ваш локальный сервер, systemd)

```bash
sudo mkdir -p /opt/btc-signal-bot
# скопируйте весь проект туда, создайте .venv и установите зависимости
sudo cp deploy/btc-signal-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now btc-signal-bot
journalctl -u btc-signal-bot -f
```

Это даёт auto-restart при падении процесса (`Restart=always`), что вместе с
heartbeat-проверкой (уже пишется в Redis, ключ `bot:last_heartbeat`) и
даст оба независимых механизма отказоустойчивости из спеки (п.5) — второй
механизм, Telegram-алерт при "молчании", подключится на этапе 3.

## О безопасности токена

В файле `fbot`, который вы загрузили в проект, Telegram-токен и chat_id
лежали открытым текстом — я перенёс их в `.env` (который в `.gitignore` и
никогда не должен попадать в git/публичные места). Раз токен уже
"засветился" в текстовом файле проекта, стоит по своему усмотрению решить,
нужно ли перевыпустить его через @BotFather (`/revoke`) — это не обязательно,
если файл `fbot` нигде публично не публиковался, но это дешёвая
предосторожность.

## Что дальше (по вашей же спеке)

Этап 1 не переходит в Этап 2 без вашего подтверждения. Когда прогоните
бэкфилл и live-ingestion на реальном сервере и убедитесь, что 1m-бары по
всем 4 биржам действительно пишутся и выглядят разумно — подтвердите, и
следующим шагом будет `percentile_engine/` + `signal_engine/` (без Telegram,
с прогоном на исторических данных и показом распределения событий — как и
написано в промпте для Claude Code).
