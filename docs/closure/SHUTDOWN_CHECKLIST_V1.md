# SHUTDOWN_CHECKLIST_V1 — технический чек-лист остановки Pulsy

**Статус:** чек-лист, 2026-10-15; подчинён `docs/PROJECT_CLOSURE_DECISION_V1.md`. Выполняется строго по порядку. Шаги с пометкой **[НЕОБРАТИМО]** требуют отдельного разрешения владельца каждый (решение §6, пп. 3–5). Ни один шаг не начинается, пока `docs/closure/BACKUP_AND_RESTORE_PLAN_V1.md` §4 не выполнен и не записан `BACKUP_MANIFEST_<дата>.md`.

Факты о юнитах — из `deploy/` (инвентарь закрытия). Хосты и учётные данные не приводятся.

---

## S0. Предусловия

- [ ] `BACKUP_MANIFEST_<дата>.md` существует, в нём: три копии, два носителя вне VPS, восстановление проверено, счётчики совпали.
- [ ] Ветка `claude/pulsy-closure-yerlly` слита в `main` (решение в силе) — или владелец явно разрешил остановку до слияния.
- [ ] Список участников беты сверен (`PAID_RESOURCES_AND_PII_V1.md` §3): если есть хоть один внешний пользователь, подготовлено финальное сообщение.
- [ ] Зафиксировано текущее состояние: `systemctl list-timers --all > $CB/timers_before_stop.txt`; `docker ps > $CB/docker_before_stop.txt`.

## S1. Финальное сообщение пользователям (если внешние пользователи есть)

- [ ] Одно сообщение через существующий бот (owner-команда или прямой вызов `BETA_TELEGRAM_BOT_TOKEN`): проект закрыт, бот прекращает работу, данные участников удаляются/анонимизируются по §3 документа о персональных данных, контакт владельца для запросов.
- [ ] Без оценок, обещаний и ссылок на будущие продукты.
- [ ] Дождаться доставки (таблица `beta_notification_deliveries`), затем перейти к S2.

## S2. Остановка таймеров и oneshot-юнитов (обратимо: `systemctl enable --now` возвращает)

Порядок: сначала таймеры (чтобы ничего не стартовало заново), потом сервисы.

```
systemctl disable --now signalbot-beta-notify.timer signalbot-beta-detector.timer signalbot-beta-outcomes.timer \
  signalbot-beta-d7.timer signalbot-beta-history.timer signalbot-beta-feeds.timer signalbot-beta-stress.timer
systemctl disable --now signalbot-shadow.timer signalbot-telegram.timer
systemctl list-timers --all | grep signalbot   # должно быть пусто
```

- [ ] беты: notify, detector, outcomes, d7, history, feeds, stress;
- [ ] V1: shadow (`*:00/5:05`), telegram (`*:00/5:35`);
- [ ] **backup-таймеры (`signalbot-backup.timer`, `signalbot-backup-verify.timer`) НЕ отключаются** до S6: пусть последний дамп снимется уже после остановки записи.
- [ ] Проверить, что ни один oneshot не выполняется: `systemctl list-units --state=activating,active 'signalbot-*'`.

## S3. Остановка долгоживущих сервисов (обратимо)

```
systemctl disable --now signalbot-beta-bot.service     # Telegram long-polling беты
systemctl disable --now signalbot.service              # V1 ingestion (Stage 1): WS Binance/Bybit/OKX, backfill
systemctl disable --now btc-signal-bot.service 2>/dev/null || true   # deprecated; если ещё установлен
```

- [ ] `systemctl status signalbot-beta-bot signalbot` — оба `inactive (dead)`, `disabled`.
- [ ] Paired shadow: юнита нет; убедиться, что нет cron/ручных запусков `scripts/beta/run_paired_shadow_hour.py` (`crontab -l` для root и signalbot; `grep -r paired /etc/cron*`).
- [ ] Прочие cron-записи с `/opt/signalbot` (старые `backup.sh` по cron, из комментария в скрипте) — зафиксировать и отключить.
- [ ] Dead-man ping (`BETA_DEADMAN_PING_URL`, healthchecks-подобный сервис): после остановки notify он начнёт слать тревоги — отключить или удалить проверку на стороне сервиса (см. `PAID_RESOURCES_AND_PII_V1.md`).

## S4. Последний дамп после остановки записи

- [ ] `systemctl start signalbot-backup.service` (делает `backup.sh` + `sync_backup_offsite.sh`); дождаться `inactive (dead)` с кодом 0; `journalctl -u signalbot-backup -n 50`.
- [ ] Повторить шаги 1–2, 6 плана резервного копирования в новый каталог `$CB_final` (дамп консистентен: записи больше нет); физическая копия `timescale_data` теперь консистентна.
- [ ] `rclone check` закрывающей копии с remote; обновить `BACKUP_MANIFEST_<дата>.md` разделом «после остановки».
- [ ] Только после этого: `systemctl disable --now signalbot-backup.timer signalbot-backup-verify.timer`.

## S5. Остановка контейнеров (обратимо, пока volumes на месте)

```
cd /opt/signalbot && docker compose stop            # btcbot_timescaledb, btcbot_redis (и прочие из docker-compose.yml)
docker ps -a; docker volume ls | grep -E 'timescale_data|redis_data'
```

- [ ] Volumes `timescale_data`, `redis_data` **не удаляются** (`docker compose down -v` запрещён).
- [ ] Снять консистентную физическую копию volumes (план, шаг 2) — если не сделано в S4.

## S6. Персональные данные **[НЕОБРАТИМО]** — отдельное разрешение (решение §6, п. 5)

Выполняется по `PAID_RESOURCES_AND_PII_V1.md` §3 после того, как зашифрованный архив `$CB/pii/` подтверждён.

- [ ] Решение владельца: (а) хранить один зашифрованный архив участников N месяцев и затем удалить, или (б) удалить сразу, оставив только агрегированные счётчики (`beta_deleted_cohort_counts`).
- [ ] В рабочих копиях дампа (все три) таблицы участников заменяются обезличенными (скрипт-аналог `deploy/signalbot-beta-audit-deidentify.sql`, расширенный на `beta_users`, `beta_allowlist`, `beta_invites`, `beta_waitlist`, `beta_user_activity`, `beta_notification_deliveries`, `beta_feedback_messages`, `beta_owner_forwards`); результат — отдельный `db_plain_deidentified.sql.gz` с манифестом.
- [ ] Удалить незашифрованные CSV участников, если создавались.

## S7. Отзыв ключей и закрытие доступов **[НЕОБРАТИМО]** — отдельное разрешение (решение §6, п. 4)

- [ ] Telegram: `@BotFather` → `/revoke` для бота беты (`BETA_TELEGRAM_BOT_TOKEN`) и для V1-нотификатора (`TELEGRAM_BOT_TOKEN`), если это разные боты; затем `/deletebot` по решению владельца (удаление необратимо, имя бота освобождается).
- [ ] Биржевые ключи: в рантайме их нет (все API публичные) — проверить `.env` на наличие лишних переменных и аккаунты бирж на выданные ключи; отозвать любые.
- [ ] `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (исследовательские инструменты): отозвать в консолях провайдеров.
- [ ] Dead-man ping / мониторинг: удалить проверку и аккаунт.
- [ ] rclone-remote (Google Drive или иной): **не отзывать**, пока закрывающая копия там нужна; при отзыве — после переноса копии в другое место.
- [ ] GitHub: деактивировать интеграции (Claude GitHub App, Copilot review, Actions-секреты `POSTGRES_*` в workflow — там только тестовые значения, но проверить `Settings → Secrets`); репозиторий остаётся приватным; ветка `main` защищена; архивировать репозиторий (`Settings → Archive`) **после** слияния ветки закрытия и снятия mirror.
- [ ] SSH-ключи и пароли VPS: ротировать или удалить лишние учётные записи, если VPS остаётся жить какое-то время.

## S8. Остановка VPS **[НЕОБРАТИМО]** — отдельное разрешение (решение §6, п. 3)

- [ ] Ещё раз: `sha256sum -c MANIFEST.sha256` на двух копиях вне VPS — OK.
- [ ] Снять финальный образ/снапшот VPS у провайдера (если провайдер даёт снапшоты — это четвёртая копия на короткий срок).
- [ ] `shutdown -h now`; затем в панели провайдера — удалить сервер или оставить выключенным до конца оплаченного периода (решение владельца; см. платные ресурсы).
- [ ] Удалить DNS-записи/домен, если были (инвентаризация в `PAID_RESOURCES_AND_PII_V1.md`).

## S9. Репозиторий

- [ ] Финальный коммит в `main`: `docs/closure/BACKUP_MANIFEST_<дата>.md`, `docs/closure/SHUTDOWN_LOG_<дата>.md` (кто, когда, какие шаги, выводы команд без секретов).
- [ ] `git clone --mirror` после финального коммита — в архив.
- [ ] GitHub: Archive repository. Приватность сохраняется.

## S10. Что никогда не делается

- `docker compose down -v`, `docker volume rm timescale_data` до подтверждения трёх копий.
- Открытие holdout E1 «раз уж всё равно закрываем».
- Удаление веток, force-push, переписывание истории.
- Публикация репозитория или его частей без отдельного разрешения (`PUBLIC_RELEASE_PROPOSAL_V1.md`).
