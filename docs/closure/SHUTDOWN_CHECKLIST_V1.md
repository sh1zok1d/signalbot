# SHUTDOWN_CHECKLIST_V1 — технический чек-лист остановки Pulsy

**Статус:** чек-лист, 2026-10-15, исправлен 2026-10-15 дважды (порядок: финальный дамп → обезличивание в живой базе → повторный экспорт → остановка контейнеров; стоковые резервные таймеры отключаются вместе с таймерами приложения, потому что проверенная зашифрованная копия к этому моменту уже существует и ни одна процедура с незашифрованными копиями не должна оставаться активной; обезличивание — одна проверенная SQL-процедура; копия volumes и снапшот VPS — остаточные копии персональных данных, не архив). Подчинён `docs/PROJECT_CLOSURE_DECISION_V1.md`. Выполняется строго по порядку. Шаги **[НЕОБРАТИМО]** требуют отдельного разрешения каждый (П4–П6). Ни один шаг не начинается, пока `BACKUP_AND_RESTORE_PLAN_V1.md` §6 не выполнен и не записан `BACKUP_MANIFEST_<дата>.md`.

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

## S2. Остановка всех таймеров, включая стоковые резервные (обратимо)

Предпосылка: проверенная зашифрованная копия уже существует (этапы 2–3 операционного плана, `BACKUP_MANIFEST`), поэтому стоковая процедура резервного копирования больше ничего не защищает, а создаёт незашифрованные дампы и передаёт их в off-site. С этого шага ни одна процедура, создающая или передающая незашифрованные копии, не остаётся активной.

```
systemctl disable --now signalbot-beta-notify.timer signalbot-beta-detector.timer signalbot-beta-outcomes.timer \
  signalbot-beta-d7.timer signalbot-beta-history.timer signalbot-beta-feeds.timer signalbot-beta-stress.timer
systemctl disable --now signalbot-shadow.timer signalbot-telegram.timer
systemctl disable --now signalbot-backup.timer signalbot-backup-verify.timer
systemctl list-timers --all --no-pager | grep signalbot      # ожидается пусто
systemctl list-units --state=activating,active --no-pager 'signalbot-*'   # ни один oneshot не выполняется
```

- [ ] Если `signalbot-backup.service` выполняется в этот момент (03:15 UTC), дождаться его завершения, затем отключить таймеры.
- [ ] `crontab -l; crontab -u signalbot -l; grep -rl signalbot /etc/cron*` — нет cron-запусков `backup.sh`/`sync_backup_offsite.sh`; найденные отключить.
- [ ] Защита данных между S2 и S4 обеспечивается уже проверенной зашифрованной копией; окно без новой копии — минуты.

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

PostgreSQL работает; приложение остановлено (S3). Единственная процедура — `scripts/closure/deidentify_closure.sql` (одна транзакция: счётчик когорты по правилу `delete_participant` и OUT-8, удаление всех участников с каскадом, редакция остаточных текстов, деидентификация каждого персонального отпечатка в аудите через схемную `beta_audit_deidentify()`, встроенная проверка: таблицы участников пусты, в аудите нет отпечатков и деталей, счётчики таблиц результатов не изменились; любая ошибка откатывает всё). Проверена на изолированной базе (`scripts/closure/test_deidentify_closure.sh`, `docs/closure/TEST_REPORT_2026-10-15.md`); OUT-8 ею поглощён.

- [ ] Отпечатки владельца (keyed и legacy) вычислить в `venv` с `BETA_FINGERPRINT_KEY` из `.env`: `python -c "from beta.admin import fingerprint; from beta.pseudonym import legacy_pseudonym; print(fingerprint(ID)+','+legacy_pseudonym(ID))"` (ID не записывать в лог); `test_open_at` из вывода dry-run — записать в `SHUTDOWN_LOG` (после обезличивания он из базы исчезает).
- [ ] Dry-run: `psql -X -v ON_ERROR_STOP=1 -d $POSTGRES_DB -v owner_fps=<fp1,fp2> -v owner_id=<ID> -f scripts/closure/deidentify_closure.sql` — читать блоки `before`/`after`/`counter`; завершается `DRY RUN: rolled back`.
- [ ] Apply: та же команда с `-v apply=1`; завершается `COMMITTED`.
- [ ] Физические остатки: `VACUUM (FULL, ANALYZE) beta_users, beta_allowlist, beta_waitlist, beta_feedback, beta_feedback_messages, beta_message_votes, beta_reasons, beta_user_activity, beta_price_alerts, beta_owner_forwards, beta_notification_deliveries, beta_admin_audit, beta_invites, beta_rejected_start_hashes; CHECKPOINT;` — после этого удалённых строк нет в файлах таблиц, но они **остаются в сегментах WAL** (`pg_wal`) до их переиспользования; поэтому копия volumes (S8) и снапшот VPS (S10) считаются копиями с остаточными персональными данными (§3.5).
- [ ] Контроль: счётчики `beta_claims`, `beta_claim_outcomes`, `forecast_predictions`, `forecast_outcomes`, `beta_forecasts`, `beta_episode_outcomes` равны `COUNTS.txt` из `$CB_final` (скрипт проверяет это сам; повторить вручную и записать).

## S7. Обезличенный дамп и повторный экспорт (зашифрованный)

```
CLOSURE_PASSPHRASE_FILE=/root/closure.pass CLOSURE_BACKUP_DIR=/opt/signalbot/closure_backup_deid_$(date -u +%Y%m%dT%H%M%SZ) \
  ./scripts/closure/closure_backup.sh --apply --no-volumes
```

- [ ] В `$CB_deid`: `csv_participants.tar.gz.gpg` отсутствует или содержит только заголовки CSV; `COUNTS.txt` показывает 0 по таблицам участников.
- [ ] Копии в off-site и на диск владельца, `rclone check`, `sha256sum -c`; `closure_restore_verify.sh` из скачанной копии `$CB_deid`; запись в `BACKUP_MANIFEST`. Это — **долгосрочный архив**.
- [ ] Локальные стоковые дампы с персональными данными: `shred -u /opt/signalbot/backups/*.sql.gz` (они уже входят в `artifacts.tar.gz.gpg` полного архива `$CB_final`).
- [ ] Журналы уже экспортированы в `$CB_final`: `journalctl --rotate && journalctl --vacuum-time=1s` — чтобы снапшот VPS (S10) не содержал старого токена и строк о пользователях.
- [ ] `shred -u /root/closure.pass` после подтверждения, что пароль есть в менеджере паролей (проверить расшифровкой одного файла на машине владельца), **но только после S8**, где пароль нужен ещё раз.

## S8. Остановка контейнеров и консистентная копия volumes (обратимо, пока volumes на месте)

```
cd /opt/signalbot && docker compose stop
docker ps -a; docker volume ls | grep -E 'timescale_data|redis_data'
```

- [ ] Volumes **не удаляются** (`docker compose down -v` запрещён).
- [ ] Консистентная физическая копия (база остановлена; таблицы обезличены и перезаписаны `VACUUM FULL`, но WAL может содержать удалённые строки): `closure_backup.sh` здесь не подходит (preflight требует работающий контейнер) — выполнить вручную только шаг volumes: `docker run --rm -v timescale_data:/src:ro -v $CB_vol:/dst alpine:3.20 tar czf /dst/volume_timescale_data.tar.gz -C /src . && gzip -t … && gpg --batch --pinentry-mode loopback --passphrase-file /root/closure.pass --symmetric --cipher-algo AES256 -o …gpg … && shred -u …tar.gz`; то же для `redis_data`; манифест; копии наружу. **Статус этой копии — «остаточные персональные данные»** (§3.5): она хранится до подтверждения `$CB_deid` на двух носителях и затем уничтожается; долгосрочный архив — только логический обезличенный дамп.
- [ ] Теперь `shred -u /root/closure.pass`.

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
- [ ] Снапшот VPS у провайдера — только после S7 (локальные дампы уничтожены, журнал очищен) и S8 (контейнеры остановлены). Даже тогда он содержит остаточные персональные данные (WAL, нераспределённые блоки диска, `.env` с отозванными секретами) и **не является архивом**: это кратковременная страховка на время уничтожения сервера, удаляемая по §3.5 сразу после подтверждения `$CB_deid` на двух носителях; дата удаления записывается в `SHUTDOWN_LOG`.
- [ ] `shutdown -h now`; удалить сервер или не продлевать (решение владельца); отключить автопродление и карту.
- [ ] Старые off-site дампы (незашифрованные, с персональными данными) — уничтожить по `PAID_RESOURCES_AND_PII_V1.md` §3.5 в том же окне П6, с очисткой корзины облака; `rclone ls` после — только `closure_deid_*` (и `closure_final_*`, если владелец записал основание и срок).

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
