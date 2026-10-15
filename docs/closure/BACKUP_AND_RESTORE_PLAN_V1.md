# BACKUP_AND_RESTORE_PLAN_V1 — сохранение результатов Pulsy перед остановкой

**Статус:** план, 2026-10-15; подчинён `docs/PROJECT_CLOSURE_DECISION_V1.md`. Выполняется владельцем (или по его поручению) на VPS; ни один шаг этого плана не является необратимым, но все шаги требуют доступа к VPS и потому — отдельного разрешения владельца (§6 решения, п. 2). Остановка чего-либо в этом плане не предусмотрена: пока копии не проверены, всё продолжает работать.

Источник фактов: `deploy/*.service`, `deploy/backup.sh`, `deploy/restore.sh`, `deploy/sync_backup_offsite.sh`, `docs/DATA_DURABILITY_RUNBOOK.md`, `storage/*.sql`, `docker-compose.yml` (строки указаны в инвентаре закрытия). Хосты, учётные данные и идентификаторы в этом документе не приводятся намеренно.

---

## 1. Что именно сохраняется

| № | Объект | Где живёт | Почему невосполнимо | Способ |
|---|---|---|---|---|
| A | База PostgreSQL/TimescaleDB `POSTGRES_DB` (по умолчанию `btcbot`) целиком: `klines_1m` и агрегаты, OI, funding, mark price, ликвидации, Stage 2 (`forecast_predictions`, `forecast_outcomes` — предсказания V1 shadow), V2 эпизоды, все `beta_*` (лента состояний, эпизоды, исходы, **журнал заявок** `beta_claims`/`beta_claim_outcomes`/`beta_claim_displays`, коридоры `beta_forecasts`, история `beta_hist_*`, фиды, **участники и обратная связь**), `beta_shadow_*` (paired shadow, если схема применялась) | контейнер `btcbot_timescaledb`, volume `timescale_data` | ликвидации, heartbeat, лента состояний, журнал заявок и живые предсказания нигде больше не существуют; пропуски «нельзя забэкфиллить с биржи позже» (runbook §A) | `pg_dump` плюс физическая копия volume |
| B | Секреты и конфигурация VPS: `/opt/signalbot/.env`, `/opt/signalbot/.env.beta-feeds`, `/etc/signalbot/backup.env`, `/etc/signalbot/rclone.conf`, значение `BETA_TELEMETRY_SALT` (внутри `.env`) | VPS, файлы root/signalbot 0600 | по дизайну не входят в дампы; без `BETA_TELEMETRY_SALT` HMAC-отпечатки `beta_rejected_start_hashes` после восстановления не совпадут (runbook §J.1) | зашифрованный архив, отдельно от дампа |
| C | Юниты systemd и состояние: `/etc/systemd/system/signalbot*.{service,timer}`, вывод `systemctl list-timers --all`, `systemctl status` каждого юнита, `/opt/signalbot/BUILD_SHA`, `git rev-parse HEAD` в `/opt/signalbot` | VPS | фиксирует, что именно работало в момент закрытия | текстовый снимок |
| D | Журналы: `journalctl -u 'signalbot*'` за весь доступный период, `/var/log/signalbot-backup.log` (если есть) | journald | единственный след рассылок, ошибок и dead-man ping | `journalctl -o export` + текст |
| E | Артефакты вне git на VPS: `/opt/signalbot/artifacts/` (в т.ч. `artifacts/e1/` — рабочие выходы E1, **кроме holdout, который никогда не читался**), `/opt/signalbot/exports/`, `/opt/signalbot/data/`, `/opt/signalbot/logs/`, `/opt/signalbot/backups/` (локальные дампы) | VPS, gitignored | исследовательские выходы одноразовых прогонов | tar |
| F | Redis (`btcbot_redis`, volume `redis_data`) | VPS | только горячее состояние Stage 1 (`exchange_status`, heartbeat); ценности не имеет, но копируется ради полноты | `redis-cli --rdb` или копия volume |
| G | Репозиторий: все ветки и теги `origin` (включая 150+ веток `cursor/*`, `claude/*`, `research/*`) | GitHub, приватный | история решений и записей | `git clone --mirror` |
| H | Закреплённые наборы данных и sealed-результаты в git: `docs/research_data/` (245 МБ), `docs/research/` (199 МБ, в т.ч. V3 WORLD_RECORDS 96,6 МБ, цепочки памяти генератора, `run.sqlite` прогонов LLM) | внутри G | LLM-выходы и sealed-прогоны невоспроизводимы | входят в mirror; дополнительно отдельный tar с манифестом |
| I | Кэши диагностик 2026-10-14/15 (`btc5m.pkl`, панели альткоинов, выгрузки Binance Vision) | там, где запускались отчёты (`DIAG_DATA_DIR`, `XM_DATA_DIR`, `artifacts/`) | воспроизводимы из публичных архивов; копируются, если доступны, иначе отмечаются как «пересобираемые» | tar |
| J | Внешние копии, уже существующие: rclone-remote (`SIGNALBOT_BACKUP_REMOTE`, tiers `daily/`, `weekly/`, `monthly/`) | облачное хранилище | текущая off-site история дампов | инвентаризировать, не удалять |

Не сохраняется (нечего): файловые записи рантайма — все юниты работают с `ProtectSystem=strict` и пишут только в базу.

## 2. Порядок выполнения

Все команды — на VPS от root, в `/opt/signalbot`; каталог назначения `/opt/signalbot/closure_backup_<UTC-дата>/` (далее `$CB`). Перед началом: `df -h` — нужно свободное место ≈ 3× размера `timescale_data` (узнать: `docker system df -v | grep timescale_data`).

### Шаг 0. Снимок состояния (до всего)

```
mkdir -p $CB && cd $CB
git -C /opt/signalbot rev-parse HEAD > GIT_HEAD.txt; cat /opt/signalbot/BUILD_SHA > BUILD_SHA.txt 2>/dev/null
systemctl list-timers --all > systemd_timers.txt
for u in $(systemctl list-units --all 'signalbot*' --no-legend | awk '{print $1}'); do systemctl status "$u" --no-pager -l > "status_$u.txt" 2>&1; done
cp /etc/systemd/system/signalbot*.service /etc/systemd/system/signalbot*.timer units/ 2>/dev/null || true
docker ps -a > docker_ps.txt; docker system df -v > docker_df.txt
```

### Шаг 1. Логический дамп базы (как делает `backup.sh`, но с кастодиальным форматом)

```
docker exec btcbot_timescaledb pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges | gzip -c > $CB/db_plain.sql.gz
docker exec btcbot_timescaledb pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/db_custom.dump && docker cp btcbot_timescaledb:/tmp/db_custom.dump $CB/db_custom.dump
docker exec btcbot_timescaledb pg_dumpall -U "$POSTGRES_USER" --globals-only > $CB/db_globals.sql
```

Плюс отдельный **CSV-экспорт человекочитаемых таблиц результатов**, чтобы данные были доступны без TimescaleDB: `forecast_predictions`, `forecast_outcomes`, `beta_claims`, `beta_claim_outcomes`, `beta_claim_displays`, `beta_forecasts`, `beta_episode_outcomes`, `beta_market_alerts`, `beta_hist_stats`, `beta_shadow_*` (если есть), `beta_feedback*`, `beta_message_votes` — через `\copy ... TO ... CSV HEADER` в `$CB/csv/`. Таблицы участников (`beta_users`, `beta_allowlist`, `beta_invites`, `beta_waitlist`, `beta_user_activity`, `beta_notification_deliveries`, `beta_admin_audit`) экспортируются **в отдельный каталог `$CB/pii/`** с отдельным шифрованием (см. `PAID_RESOURCES_AND_PII_V1.md` §3).

### Шаг 2. Физическая копия volumes (на случай, если логический дамп окажется неполным)

```
docker run --rm -v timescale_data:/src:ro -v $CB:/dst alpine tar czf /dst/timescale_data.tar.gz -C /src .
docker run --rm -v redis_data:/src:ro -v $CB:/dst alpine tar czf /dst/redis_data.tar.gz -C /src .
```

Копия volume при работающей базе может быть неконсистентной; поэтому она **дополняет** дамп, а не заменяет его. Консистентную физическую копию можно снять после остановки сервисов (чек-лист остановки, шаг S5), повторив команду.

### Шаг 3. Секреты и конфигурация

```
tar czf - /opt/signalbot/.env /opt/signalbot/.env.beta-feeds /etc/signalbot/ 2>/dev/null | gpg --symmetric --cipher-algo AES256 -o $CB/secrets.tar.gz.gpg
```

Пароль — только у владельца, хранится отдельно от архива (менеджер паролей). Незашифрованная копия секретов в `$CB` не создаётся.

### Шаг 4. Журналы и артефакты

```
journalctl -u 'signalbot*' -o export | gzip > $CB/journal_signalbot.export.gz
journalctl -u 'signalbot*' --no-pager > $CB/journal_signalbot.txt
tar czf $CB/artifacts.tar.gz -C /opt/signalbot artifacts exports data logs backups 2>/dev/null || true
```

Если `artifacts/e1/` содержит holdout-объекты (не должен: holdout никогда не читался), они копируются как есть, без чтения.

### Шаг 5. Репозиторий и наборы данных

На машине владельца (не обязательно VPS):

```
git clone --mirror git@github.com:sh1zok1d/signalbot.git signalbot.git   # все ветки и теги
tar czf signalbot_research_data.tar.gz -C <checkout> docs/research_data docs/research/atlas docs/research/generator_v0_memory docs/e1
```

Mirror содержит `docs/research_data` и sealed-JSON в объектах; отдельный tar нужен для чтения без git.

### Шаг 6. Манифест целостности

```
cd $CB && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
```

Манифест кладётся **в каждую копию** и дополнительно вставляется (как текст) в `docs/closure/BACKUP_MANIFEST_<дата>.md` в репозитории — это единственное, что из бэкапа возвращается в git.

### Шаг 7. Три копии в двух местах

1. VPS (`$CB`) — временная, до остановки.
2. Существующий rclone-remote: `rclone copy $CB <SIGNALBOT_BACKUP_REMOTE>/closure_<дата>/ --checksum`; затем `rclone check $CB <remote>/closure_<дата>/`.
3. Локальный диск владельца (`rclone copy`/`scp`), затем ещё одна копия на отключаемый носитель или второй облачный аккаунт.

Правило: пока нет двух копий вне VPS с совпадающим `MANIFEST.sha256`, остановка VPS запрещена.

## 3. Проверка восстановления (обязательна)

На отдельной машине (ноутбук владельца, Docker):

1. `docker run -d --name restore_test -e POSTGRES_PASSWORD=x timescale/timescaledb:2.17.2-pg16` (тот же образ, что в `docker-compose.yml`).
2. `gunzip -c db_plain.sql.gz | docker exec -i restore_test psql -U postgres -d postgres -c 'CREATE DATABASE t;' && ... psql -d t` с обёрткой `SELECT timescaledb_pre_restore(); ... SELECT timescaledb_post_restore();` (как в `deploy/restore.sh`).
3. Проверки (те же, что `restore.sh --self-test`, плюс результаты):
   - `SELECT count(*) FROM klines_1m;` > 0 и `min(open_time)`, `max(open_time)` совпадают с VPS;
   - каждая таблица из `storage/beta_v0_schema.sql` существует;
   - `SELECT count(*) FROM beta_claims; ... beta_claim_outcomes; ... forecast_predictions; ... forecast_outcomes; ... beta_forecasts;` — числа записываются в манифест и сравниваются с VPS;
   - `python -m storage.db` / `Database.init_beta_v0_schema()` применяется без ошибок;
   - CSV-экспорт открывается pandas без ошибок, число строк равно count(*).
4. Результат проверки (команды, числа, дата) записывается в `docs/closure/BACKUP_MANIFEST_<дата>.md`. Без этой записи шаг «остановка» в чек-листе не начинается.
5. Тестовая база удаляется.

Дополнительно: `sha256sum -c MANIFEST.sha256` на каждой из трёх копий.

## 4. Что считается успехом

- три копии, два носителя вне VPS, манифесты совпадают;
- восстановление на чистой машине прошло, счётчики совпали с VPS;
- секреты зашифрованы, пароль у владельца;
- mirror репозитория снят после последнего коммита ветки закрытия;
- записан `BACKUP_MANIFEST_<дата>.md`.

## 5. Хранение после закрытия

- Срок: бессрочно для научных артефактов, кода и обезличенных результатов; для персональных данных — по `PAID_RESOURCES_AND_PII_V1.md` §3 (удаление из рабочих копий, один зашифрованный архив на срок, установленный владельцем).
- Место: минимум одно облачное и один носитель владельца. Проверка `sha256sum -c` раз в год, если архив ещё нужен.
- Существующие off-site дампы (`daily/weekly/monthly`) не удаляются до подтверждения закрывающей копии; затем можно оставить только `monthly/` и `closure_<дата>/`.
