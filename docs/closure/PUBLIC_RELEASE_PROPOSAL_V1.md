# PUBLIC_RELEASE_PROPOSAL_V1 — предложение по отдельной очищенной публичной версии

**Статус:** предложение, 2026-10-15; подчинено `docs/PROJECT_CLOSURE_DECISION_V1.md` §1 п. 5. Публикация **не разрешена**; оригинальный репозиторий остаётся приватным. Этот документ описывает, как сделать публичную копию, если владелец решит её сделать, и что показал аудит git-истории.

---

## 1. Аудит git-истории (выполнен 2026-10-15, только чтение)

Скрипт: `scripts/closure/scan_git_history.py`; результат (пути и счётчики, без значений): `docs/closure/GIT_HISTORY_SCAN_2026-10-15.json`. Просканировано 11 372 текстовых blob-объекта, достижимых из 151 ref (все локальные и удалённые ветки и теги). Паттерны: токены Telegram, ключи OpenAI/Anthropic/AWS/GitHub, приватные ключи, присваивания `api_key/secret/password/token`, DSN с паролем, публичные IPv4, e-mail, присваивания chat/user id, ssh-цели, hostname, файлы `.env`.

| Категория | Файлов | Совпадений | Оценка (проверено по форме значений, без вывода значений) |
|---|---|---|---|
| Токен Telegram-бота | 0 | 0 | — |
| Ключи OpenAI / Anthropic | 5 | 36 / 18 | только `tests/research/test_generator_v0_*.py`; все значения вида `sk-ant-test…` / `sk-op…` фиксированной тестовой длины — фикстуры |
| AWS / GitHub / приватные ключи | 0 | 0 | — |
| Присваивания secret/token/password | 9 | 24 | только `tests/`; значения `12345…`, `SUPER…`, `sk-te…` — фикстуры |
| DSN PostgreSQL с паролем | 15 | 118 | `.github/workflows/*`, `.env.example`, `tests/storage/*`: хосты `localhost`/`127.0.0.1`, пароли `postgres`, `secret`, `s3cre…`; одно значение в `.env.example` — **пример по умолчанию, владелец подтверждает, что реальный пароль VPS другой** |
| Публичный IPv4 | 1 | 1 | `tests/research/test_generator_v0_textnorm.py`: строка `2.0.2…` — номер версии, не адрес |
| E-mail | 30 | 216 | домены `example.com`, `example.invalid`, `signalbot.invalid`, `github.com`, `nyse.com`, `binance.com`, сборки `*.min.js` (vendored HTML Binance в `docs/research_data/SPRINT04_…/fee_authority/`, в нём же `sentry.io` ingest-адрес Binance); личных адресов не найдено |
| chat/user id | 2 | 6 | `tests/beta/test_beta_audit_deidentify_pg.py`, `tests/notifications/test_telegram_client.py` — фикстуры |
| Hostname | 6 | 380 | `docs/RESEARCH_LEDGER.md` (число `5.6371…`, ложное срабатывание), `api.anthropic.com`, `data.binance.vision`, `127.0.0.1` |
| Файлы `.env*` (кроме `.example`) | 0 | 0 | никогда не коммитились; `.gitignore` закрывает `.env`, `.env.*`, `*.pem`, `*.key`, `rclone.conf`, `backup.env` |

Вывод: по паттернам в истории **секретов и персональных идентификаторов не найдено**. Это необходимое, но не достаточное условие (см. §2.2). Отдельно отмечено: hotfix утечки токена в journald (`53ccec14`, 2026-09-28) касался логов на VPS, а не git; в git токен не попадал.

Что ещё содержит история и что надо решить отдельно:
- имена и ники в трейлерах коммитов (`Co-Authored-By`, `Claude-Session` ссылки на сессии claude.ai/code, ветки `cursor/*`) — ссылки на приватные сессии инструментов; e-mail автора коммитов (владельца) — в каждом коммите;
- упоминания «владелец», «известные контакты», тестовые аккаунты — без идентификаторов, но по контексту документы беты описывают реальных людей обобщённо;
- `docs/research_data/` 245 МБ и sealed JSON в `docs/research/` ~150 МБ (в т.ч. V3 WORLD_RECORDS 96,6 МБ) — лицензионный статус снапшотов бирж (Binance Vision, OKX, Bybit, BitMEX) и `run.sqlite` LLM-прогонов (содержат промпты и ответы моделей);
- vendored HTML Binance (страница комиссий) — чужой контент.

## 2. Предлагаемая форма публичной версии

### 2.1. Что публиковать

Отдельный новый репозиторий (например, `pulsy-archive`), **не форк и не ветка** приватного, с заново построенной историей или одним коммитом:

- **Вариант A (рекомендуемый): один коммит «archive» без истории.** Содержимое — снимок `main` после слияния ветки закрытия, пропущенный через фильтр §2.3. Простая проверка, никаких рисков из истории, никаких трейлеров. История остаётся в приватном репозитории.
- **Вариант B: история, переписанная `git filter-repo`** (удаление `docs/research_data/`, `run.sqlite`, vendored HTML, замена e-mail автора на `noreply`, удаление трейлеров `Claude-Session`). Ценность истории для внешнего читателя невелика, а риск пропустить что-то — реальный. Только если владелец хочет показать эволюцию.

### 2.2. Аудит перед публикацией (обязателен при любом варианте)

1. `gitleaks detect --source . --log-opts='--all'` и `trufflehog git file://. --only-verified` — поверх моего паттерн-скана (они не установлены в репозитории; ставятся на машине владельца).
2. Ручной просмотр: `grep -rniE 'telegram_user_id|chat_id|@[a-z0-9_]{4,}' docs/` на упоминания реальных ников; `git log --format='%an %ae' | sort -u` — авторы; все `*.md` в `docs/` с «owner», «known contact», «invite» на предмет описания конкретных людей.
3. Проверка `docs/research/**/run.sqlite` и `generator_v0_memory/` на содержимое промптов (ключи — нет, но могут быть внутренние адреса инструментов).
4. Лицензии данных: Binance Vision, OKX, Bybit — публичные архивы, условия использования допускают исследовательское хранение, но **перепубликация** снапшотов требует проверки условий каждой биржи; безопаснее публиковать только манифесты (`MANIFEST.json` с хэшами и ссылками на первоисточник) и скрипты загрузки.

### 2.3. Фильтр содержимого (вариант A)

Исключить:
- `docs/research_data/**` (оставить `*/MANIFEST.json`, `*/DATASET_MANIFEST.json`, README);
- `docs/research/**/run.sqlite`, `docs/research/**/checkpoint/`, `generator_v0_*` каталоги с LLM-выходами (оставить `generator_v0_memory/` только если владелец согласен публиковать промпты/ответы; иначе оставить `HEAD.json` и хэши);
- `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_WORLD_RECORDS.json` и V2 (96,6 + 20 МБ): заменить на SHA-256 и описание; сами файлы доступны по запросу;
- `deploy/*.service`, `deploy/*.sh`, `docs/VPS_DEPLOY.md`, `DATA_DURABILITY_RUNBOOK.md`, `*_DEPLOY.md`, `docs/closure/BACKUP_*`, `SHUTDOWN_*`, `PAID_RESOURCES_AND_PII_V1.md` — инфраструктурные детали (пути, роли, расписания) публичному читателю не нужны и описывают сервер владельца;
- `docs/BETA_*`, `docs/FIRST_EXTERNAL_COHORT_*`, `docs/PRIVATE_BETA_*`, `beta/i18n.py` тексты privacy notice — по решению владельца (описывают беты и участников обобщённо; риска идентификации нет, но и ценности для читателя мало);
- `.github/workflows/` (DSN тестовых контейнеров безвредны, но CI публичной копии не нужен);
- vendored HTML Binance.

Включить:
- `README.md` новый: одна страница — что это, итог (текст `PUBLIC_SUMMARY_EN.md`/`_RU.md`), как читать каталог, лицензия;
- `docs/closure/RESEARCH_CATALOG_FINAL_V1.md`, `PUBLIC_SUMMARY_*`, `PROJECT_CLOSURE_DECISION_V1.md`;
- все `docs/research/*_DESIGN.md`, `*_RESULT.md`, `*_RESULT.json` (малые), атлас (`docs/research/atlas/`), `RESEARCH_LEDGER.md`, `PROJECT_HISTORY.md`, `EVIDENCE_AND_CLAIMS_DECISION_V1.md`, контракты оценки;
- пять отчётов `docs/PULSY_*_2026-10-1[45].md` и их скрипты (`scripts/research/independent_diagnostics_2026_10/`, `cross_market_2026_10/`, `signal_engine_audit_2026_10/`);
- исследовательский код `scripts/research/**`, `analytics/**`, `beta/levels.py` и другие чистые модули; продуктовый код `beta/`, `runtime/`, `storage/` — включить (секретов нет), либо исключить, если владелец не хочет публиковать продукт;
- тесты.

### 2.4. Лицензия и оформление

- Код: MIT или Apache-2.0 (владелец выбирает; Apache-2.0 даёт явный патентный пункт).
- Тексты и записи: CC BY 4.0.
- Данные: не публикуются (манифесты — под той же лицензией, что тексты).
- Имя автора в лицензии — как решит владелец (имя, ник или «Pulsy project»).
- Статус репозитория сразу Archived (read-only), Issues и Discussions выключены — это архив, не проект.

### 2.5. Трудоёмкость

Вариант A: 1–2 дня (фильтр, gitleaks/trufflehog, ручной просмотр документов, README, лицензия). Вариант B: +2–3 дня на `filter-repo` и повторный аудит переписанной истории.

## 3. Что это предложение не делает

Не публикует ничего, не создаёт репозиторий, не меняет видимость. Для исполнения нужно отдельное разрешение владельца (решение §6 п. 6) с выбором варианта (A/B), набора исключений (§2.3) и лицензий (§2.4).
