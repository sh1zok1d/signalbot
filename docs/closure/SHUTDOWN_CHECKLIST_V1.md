# SHUTDOWN_CHECKLIST_V1 — технический чек-лист остановки Pulsy

**Статус:** чек-лист, 2026-10-15, исправлен 2026-10-15 (порядок: финальный дамп → обезличивание в живой базе → повторный экспорт → остановка контейнеров; резервные таймеры остаются включёнными до завершения финального копирования). Подчинён `docs/PROJECT_CLOSURE_DECISION_V1.md`. Выполняется строго по порядку. Шаги **[НЕОБРАТИМО]** требуют отдельного разрешения каждый (П4–П6). Ни один шаг не начинается, пока `BACKUP_AND_RESTORE_PLAN_V1.md` §6 не выполнен и не записан `BACKUP_MANIFEST_<дата>.md`.

Обозначения: `$CB_*` — каталоги подготовки на VPS (`/opt/signalbot/closure_backup_<метка>`), всё содержимое зашифровано скриптом `scripts/closure/closure_backup.sh`. Хосты и учётные данные не приводятся. Каждый выполненный шаг с датой и выводами команд (без секретов и идентификаторов) записывается в `docs/closure/SHUTDOWN_LOG_<дата>.md`.

---

## S0. Предусловия

- [ ] `BACKUP_MANIFEST_<дата>.md` существует: две копии вне VPS, манифесты совпадают, восстановление из зашифрованной копии проверено, счётчики совпали.
- [ ] Разрешение П3 получено (остановка таймеров, сервисов; контейнеры — позже, S8).
- [ ] Пароль архива (`/root/closure.pass`, root 0600) на месте — он нужен для S4 и S7; копия в менеджере паролей владельца.
- [ ] Инвентаризация участников (счётчики, без идентификаторов): `SELECT status, count(*) FROM beta_users GROUP BY status; SELECT count(*) FROM beta_allowlist; … beta_waitlist; … beta_feedback_messages; … beta_owner_forwards;` — в `SHUTDOWN_LOG`. Проверить, удалён ли тестовый аккаунт из `docs/BETA_PREVIEW_V1.md:68-80`.
- [ ] Dead-man проверка (`BETA_DEADMAN_PING_URL`): поставить на паузу или удалить **до** S2, иначе после остановки notify пойдут тревоги.
- [ ] Снимок «до»: `systemctl list-timers --all --no-pager > $CB_final/timers_before_stop.txt; docker ps > $CB_final/docker_before_stop.txt` (каталог создаст скрипт на S4; до этого — во временный файл root 600).

## S1. Финальное сообщение участникам (только если в `beta_users` есть кто-то, кроме владельца и тестовых аккаунтов)

- [ ] Одно сообщение через бот беты: проект закрыт, бот прекращает работу, данные участников удаляются в соответствии с privacy notice, контакт владельца для запросов. Без оценок и обещаний.
- [ ] Дождаться доставки (`beta_notification_deliveries`), затем S2.

## S2. Остановка таймеров приложения (обратимо)

```
systemctl disable --now signalbot-beta-notify.timer signalbot-beta-detector.timer signalbot-beta-outcomes.timer \
  signalbot-beta-d7.timer signalbot-beta-history.timer signalbot-beta-feeds.timer signalbot-beta-stress.timer
systemctl disable --now signalbot-shadow.timer signalbot-telegram.timer
systemctl list-timers --all --no-pager | grep signalbot
```

- [ ] Ожидаемый вывод последней команды: **только** `signalbot-backup.timer` и `signalbot-backup-verify.timer`. Они остаются включёнными до завершения финального копирования (S7). Следствие: если `signalbot-backup.timer` сработает (03:15 UTC) между S4 и S7, он, как и каждый день до этого, положит **незашифрованный** дамп локально и в off-site-тиры; эти дампы входят в инвентарь S7/§3.5 и удаляются вместе со старыми.
- [ ] `systemctl list-units --state=activating,active --no-pager 'signalbot-*'` — ни один oneshot не выполняется.

## S3. Остановка долгоживущих сервисов (обратимо; PostgreSQL и Redis продолжают работать)

```
systemctl disable --now signalbot-beta-bot.service          # Telegram long-polling беты
systemctl disable --now signalbot.service                   # V1 ingestion (WS Binance/Bybit/OKX, backfill)
systemctl disable --now btc-signal-bot.service 2>/dev/null || true   # deprecated, если ещё установлен
crontab -l; crontab -u signalbot -l 2>/dev/null; grep -rl signalbot /etc/cron* 2>/dev/null
```

- [ ] `systemctl status signalbot-beta-bot signalbot` — `inactive (dead)`, `disabled`.
- [ ] Нет cron-запусков `scripts/beta/run_paired_shadow_hour.py`, `backup.sh` и других скриптов проекта; найденные — отключить и записать.
- [ ] С этого момента в базу никто не пишет: `SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND state <> 'idle';` → только текущая сессия.

## S4. Финальный полный дамп после остановки записи (зашифрованный)

```
CLOSURE_PASSPHRASE_FILE=/root/closure.pass CLOSURE_BACKUP_DIR=/opt/signalbot/closure_backup_final_$(date -u +%Y%m%dT%H%M%SZ) \
  ./scripts/closure/closure_backup.sh --apply --no-volumes
```

- [ ] Скрипт завершился без ошибки; в `$CB_final` только `*.gpg`, `MANIFEST.sha256`, `COUNTS.txt`, `README.txt`.
- [ ] `rclone copy --checksum $CB_final <remote>/closure_final_<метка>/ && rclone check …`; копия на диск владельца; `sha256sum -c` на обеих.
- [ ] `closure_restore_verify.sh` на чистой машине из скачанной копии `$CB_final` (счётчики должны совпасть с `COUNTS.txt` этого каталога); запись в `BACKUP_MANIFEST`.
- [ ] Стоковый `signalbot-backup.service` вручную **не запускается**: он копирует незашифрованный дамп в off-site.

## S5. Контроль перед необратимым шагом

- [ ] Разрешение П4 получено, в нём: решение по сроку и основанию хранения полного дампа с персональными данными (`PAID_RESOURCES_AND_PII_V1.md` §3.5) и подтверждение, что финальное сообщение (S1) доставлено или не требовалось.
- [ ] `sha256sum -c MANIFEST.sha256` в `$CB_final` и на обеих внешних копиях — OK.

## S6. Обезличивание в живой базе **[НЕОБРАТИМО для базы на VPS; полный дамп S4 сохраняется по §3.5]** — П4

PostgreSQL работает; приложение остановлено (S3). Порядок — `PAID_RESOURCES_AND_PII_V1.md` §3.3 п. 3:

- [ ] Dry-run редакции аудита: `psql … -f deploy/signalbot-beta-audit-deidentify-count.sql` — записать счётчики.
- [ ] Для каждого участника — `delete_participant` (`storage/beta_v0_store.py:1207-1250`; через `python -m runtime.beta_cli` владельческой командой или прямым вызовом в `venv` с `BETA_FINGERPRINT_KEY` из `.env`): каскад по `user_pk`, `beta_deleted_cohort_counts`, деидентификация аудита.
- [ ] Вручную, в одной транзакции: `DELETE FROM beta_waitlist; DELETE FROM beta_allowlist; UPDATE beta_invites SET label = NULL; UPDATE beta_notification_deliveries SET error_summary = NULL WHERE user_pk IS NULL; UPDATE telegram_notification_deliveries SET recipient_fingerprint = NULL; DELETE FROM beta_rejected_start_hashes;` затем `deploy/signalbot-beta-audit-deidentify.sql`.
- [ ] Проверка: `SELECT count(*) FROM beta_users; … beta_allowlist; … beta_waitlist; … beta_feedback_messages; … beta_owner_forwards; … beta_user_activity;` — все 0; `SELECT count(*) FROM beta_admin_audit WHERE target_fingerprint IS NOT NULL;` — записать (строки о живых людях OUT-8 не трогает; после удаления всех участников их быть не должно).
- [ ] Результаты и журнал заявок не изменились: `count(*)` по `beta_claims`, `beta_claim_outcomes`, `forecast_predictions`, `forecast_outcomes`, `beta_forecasts`, `beta_episode_outcomes` равны `COUNTS.txt` из `$CB_final`.

## S7. Обезличенный дамп и повторный экспорт (зашифрованный)

```
CLOSURE_PASSPHRASE_FILE=/root/closure.pass CLOSURE_BACKUP_DIR=/opt/signalbot/closure_backup_deid_$(date -u +%Y%m%dT%H%M%SZ) \
  ./scripts/closure/closure_backup.sh --apply --no-volumes
```

- [ ] В `$CB_deid`: `csv_participants.tar.gz.gpg` отсутствует или содержит только заголовки CSV; `COUNTS.txt` показывает 0 по таблицам участников.
- [ ] Копии в off-site и на диск владельца, `rclone check`, `sha256sum -c`; `closure_restore_verify.sh` из скачанной копии `$CB_deid`; запись в `BACKUP_MANIFEST`. Это — **долгосрочный архив**.
- [ ] Только теперь: `systemctl disable --now signalbot-backup.timer signalbot-backup-verify.timer` (финальное копирование завершено).
- [ ] `shred -u /root/closure.pass` после подтверждения, что пароль есть в менеджере паролей (проверить расшифровкой одного файла на машине владельца).

## S8. Остановка контейнеров и консистентная копия volumes (обратимо, пока volumes на месте)

```
cd /opt/signalbot && docker compose stop
docker ps -a; docker volume ls | grep -E 'timescale_data|redis_data'
```

- [ ] Volumes **не удаляются** (`docker compose down -v` запрещён).
- [ ] Консистентная физическая копия (база остановлена; уже обезличена): `CLOSURE_PASSPHRASE_FILE=… CLOSURE_BACKUP_DIR=/opt/signalbot/closure_backup_volumes_<метка> ./scripts/closure/closure_backup.sh` **не подходит** (preflight требует работающий контейнер) — выполнить вручную только шаг volumes: `docker run --rm -v timescale_data:/src:ro -v $CB_vol:/dst alpine:3.20 tar czf /dst/volume_timescale_data.tar.gz -C /src . && gzip -t … && gpg --batch --pinentry-mode loopback --passphrase-file /root/closure.pass --symmetric --cipher-algo AES256 -o …gpg … && shred -u …tar.gz`; то же для `redis_data`; манифест; копии наружу.

## S9. Отзыв ключей и закрытие доступов **[НЕОБРАТИМО]** — П5

- [ ] Telegram `@BotFather`: `/revoke` для бота беты (`BETA_TELEGRAM_BOT_TOKEN`; обязателен — hotfix утечки в journald 2026-09-28 без зафиксированной ротации) и V1-нотификатора (`TELEGRAM_BOT_TOKEN`); `/deletebot` — по решению владельца.
- [ ] Владелец удаляет пересланные тексты участников из своего чата с ботом (`PAID_RESOURCES_AND_PII_V1.md` §3.3 п. 5).
- [ ] Ключи Anthropic/OpenAI — отозвать; мониторинг — удалить проверку и аккаунт.
- [ ] Биржи: ключей в рантайме нет; проверить аккаунты и отозвать любые выданные.
- [ ] rclone-remote — **не отзывать** до переноса закрывающих копий.
- [ ] GitHub: отключить интеграции и Actions; секретов в Actions нет (проверить `Settings → Secrets`); репозиторий остаётся приватным.
- [ ] SSH/пароли VPS: лишние учётные записи удалить, если VPS ещё живёт.

## S10. Остановка VPS **[НЕОБРАТИМО]** — П6

- [ ] `sha256sum -c MANIFEST.sha256` для `$CB_final`, `$CB_deid`, `$CB_vol` на двух копиях вне VPS — OK.
- [ ] Снапшот VPS у провайдера (содержит открытые данные на диске — удалить по §3.5 после подтверждения архива; срок записать).
- [ ] `shutdown -h now`; удалить сервер или не продлевать (решение владельца); отключить автопродление и карту.
- [ ] Старые off-site дампы и локальные `backups/` — по `PAID_RESOURCES_AND_PII_V1.md` §3.5.

## S11. Репозиторий

- [ ] Финальный коммит в `main`: `BACKUP_MANIFEST_<дата>.md`, `SHUTDOWN_LOG_<дата>.md` (без секретов и идентификаторов).
- [ ] `git clone --mirror` после финального коммита → `tar | gpg` → архив.
- [ ] GitHub: Archive repository; приватность сохраняется.

## S12. Что никогда не делается

- `docker compose down -v`, `docker volume rm` до подтверждения копий `$CB_deid` и `$CB_vol` вне VPS.
- Запуск стокового `backup.sh`/`sync_backup_offsite.sh` после S3 (незашифрованная передача).
- Открытие holdout E1.
- Удаление веток, force-push, переписывание истории.
- Публикация репозитория или его частей без П7.
