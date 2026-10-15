# BACKUP_AND_RESTORE_PLAN_V1 — сохранение результатов Pulsy перед остановкой

**Статус:** план, 2026-10-15, исправлен 2026-10-15 по замечаниям владельца (шифрование до передачи, проверка команд, восстановление из зашифрованной копии). Подчинён `docs/PROJECT_CLOSURE_DECISION_V1.md`. Выполняется владельцем на VPS; ничего не останавливает и не удаляет; требует разрешения П2 (доступ к VPS). Пока копии не проверены, всё продолжает работать.

Исполнимые скрипты: `scripts/closure/closure_backup.sh` (VPS; dry-run по умолчанию, `--apply` для выполнения) и `scripts/closure/closure_restore_verify.sh` (чистая машина). Оба прошли сквозной тест на синтетических данных в режиме `local` (`scripts/closure/test_backup_restore.sh`: создание, шифрование, передача в тестовое хранилище и обратно, расшифровка, восстановление, сверка, подмена байта, неверный пароль, обезличенный повторный экспорт — `docs/closure/TEST_REPORT_2026-10-15.md`); режим `docker` (как на VPS), `rclone` и TimescaleDB тестом не покрыты, **на VPS скрипты не запускались**. Перед `--apply` владелец читает скрипт целиком. Хосты, учётные данные и идентификаторы в документе не приводятся.

---

## 1. Принципы

1. **Всё, что может содержать персональные данные, шифруется до того, как покинет каталог подготовки на VPS**: дампы базы (все таблицы `beta_*` с участниками), CSV-выгрузки, журналы journald (могли содержать токен до 2026-09-28), физические копии volumes, секреты, снимки состояния systemd (в них бывают строки журнала). Шифрование — `gpg --symmetric AES256`, пароль только у владельца в файле root:root 0600 на время выполнения и в менеджере паролей. Открытого текста после шифрования не остаётся (`shred -u`, иначе `rm`); каждая шифровка проверяется обратной расшифровкой и побайтовым сравнением.
2. Во внешние хранилища (rclone-remote, диск владельца, второе облако) копируются **только** `*.gpg`, `MANIFEST.sha256`, `COUNTS.txt`, `README.txt`. `COUNTS.txt` содержит только числа строк по таблицам.
3. Проверка восстановления выполняется **из зашифрованной копии** на чистой машине: расшифровка во временный каталог 700 (лучше tmpfs или зашифрованный диск), восстановление, сверка счётчиков, уничтожение открытого текста и контейнера.
4. Ошибки останавливают процесс (`set -euo pipefail`), каждый артефакт существует как `.partial`, пока не проверен (`gzip -t`, `pg_restore --list`, `cmp` после шифрования), каталоги создаются `install -d -m 700`, `umask 077`.
5. Mirror репозитория и закреплённые наборы данных персональных данных не содержат (скан истории: `PUBLIC_RELEASE_PROPOSAL_V1.md` §1), но содержат e-mail автора в коммитах; при хранении в стороннем облаке — тоже шифруются (`tar | gpg`).

## 2. Что сохраняется

| № | Объект | Где живёт | Почему невосполнимо | Артефакт (всегда `*.gpg`) |
|---|---|---|---|---|
| A | База `POSTGRES_DB` целиком: свечи, OI, funding, ликвидации, Stage 2 (`forecast_predictions`/`forecast_outcomes` — предсказания V1 shadow), V2, все `beta_*` (лента, эпизоды, исходы, **журнал заявок**, коридоры, история, фиды, **участники и обратная связь**), `beta_shadow_*` если схема применялась | контейнер `btcbot_timescaledb`, volume `timescale_data` | нигде больше не существует; пропуски «нельзя забэкфиллить» (`DATA_DURABILITY_RUNBOOK.md` §A) | `db_plain.sql.gz.gpg`, `db_custom.dump.gpg`, `db_globals.sql.gpg` |
| B | CSV-выгрузки: результаты (без идентификаторов) и участники (отдельный архив) | та же база | читаемость без TimescaleDB | `csv_results.tar.gz.gpg`, `csv_participants.tar.gz.gpg` |
| C | Физические копии volumes `timescale_data`, `redis_data` | Docker | страховка на случай неполного логического дампа; при работающей базе неконсистентна, консистентная снимается после остановки контейнеров (чек-лист S8). Даже после обезличивания содержит удалённые строки в WAL — это копия с остаточными персональными данными, уничтожается после подтверждения обезличенного архива (`PAID_RESOURCES_AND_PII_V1.md` §3.5, п. 6a) | `volume_*.tar.gz.gpg` |
| D | Секреты и конфигурация: `/opt/signalbot/.env`, `.env.beta-feeds`, `/etc/signalbot/` (`backup.env`, `rclone.conf`); в `.env` — `BETA_FINGERPRINT_KEY`, `BETA_TELEMETRY_SALT` | VPS | по дизайну не в дампах; без ключей отпечатки аудита не сверить | `secrets.tar.gz.gpg` |
| E | Снимок состояния: `git HEAD`, `BUILD_SHA`, таймеры, статусы юнитов, файлы юнитов, `docker ps`, crontab | VPS | что именно работало в момент закрытия | `state_snapshot.tar.gz.gpg` |
| F | Журналы `journalctl -u 'signalbot*'` (export и текст) | journald | единственный след рассылок и ошибок; мог содержать токен | `journal_signalbot.*.gz.gpg` |
| G | Артефакты вне git: `artifacts/` (в т.ч. `artifacts/e1/` — **holdout не читается, копируется как есть**), `exports/`, `data/`, `logs/`, `backups/` (локальные дампы) | VPS, gitignored | одноразовые прогоны | `artifacts.tar.gz.gpg` |
| H | Репозиторий: все ветки и теги | GitHub | история решений | `git clone --mirror` → `tar \| gpg` на машине владельца |
| I | Закреплённые наборы данных и sealed-результаты (`docs/research_data/` 245 МБ, `docs/research/` 199 МБ, `docs/e1/`) | внутри H | LLM-выходы и sealed-прогоны невоспроизводимы | входят в mirror; отдельный `tar | gpg` для чтения без git |
| J | Кэши диагностик 2026-10-14/15 (`btc5m.pkl`, панели) | машины, где запускались отчёты | пересобираемы из публичных архивов | копируются, если доступны; иначе отметка «пересобираемые» |
| K | Существующие off-site дампы (`daily/weekly/monthly`) | rclone-remote | текущая история; **содержат персональные данные в открытом виде** (дампы не шифровались) | инвентаризировать (`rclone lsl`), не удалять до §5; судьба — `PAID_RESOURCES_AND_PII_V1.md` §3.5 |

## 3. Порядок выполнения на VPS (`closure_backup.sh`)

Предусловия: root, `tmux`, свободное место ≥ 3× размера `timescale_data` (`docker system df -v`), установлены `gpg`, `shred` (coreutils), `docker`. Пароль архива: `install -m 600 -o root /dev/null /root/closure.pass; (вставить ≥ 20 символов) > /root/closure.pass`; тот же пароль — в менеджер паролей владельца **до** запуска.

```
cd /opt/signalbot && git pull --ff-only   # после merge ветки закрытия; иначе скопировать scripts/closure/ вручную
CLOSURE_PASSPHRASE_FILE=/root/closure.pass ./scripts/closure/closure_backup.sh            # dry run: preflight и план
CLOSURE_PASSPHRASE_FILE=/root/closure.pass ./scripts/closure/closure_backup.sh --apply    # выполнение
```

Что делает скрипт, по шагам (все пути внутри `$CB = /opt/signalbot/closure_backup_<UTC-метка>/`, каталог 700):

0. Preflight: root; инструменты; `.env` читается и даёт `POSTGRES_DB`/`POSTGRES_USER` (`set -a; . .env; set +a`); контейнер запущен, `pg_isready`; файл пароля root 0600 и ≥ 20 байт; свободное место. В dry-run на этом останавливается.
1. Снимок состояния (`state_snapshot.tar.gz.gpg`).
2. `COUNTS.txt`: `count(*)` по таблицам результатов, участников и сырым данным, `min/max(open_time)` свечей — открытым текстом, только числа.
3. Дампы: `pg_dump --no-owner --no-privileges | gzip` → `gzip -t`, размер > 1 МБ → `.gpg`; `pg_dump -Fc` через stdout → `pg_restore --list` → `.gpg`; `pg_dumpall --globals-only` (если роль позволяет) → `.gpg`.
4. CSV: `\copy (SELECT * FROM t) TO STDOUT CSV HEADER` для каждой существующей таблицы (`to_regclass`), результаты и участники в разные архивы → `.gpg`.
5. Volumes: `docker run --rm -v <vol>:/src:ro -v $CB:/dst alpine:3.20 tar czf …` → `gzip -t` → `.gpg` (`--no-volumes` отключает).
6. Секреты: `tar` → `.gpg`. 7. Журналы → `.gpg`. 8. Артефакты → `.gpg`.
9. `README.txt`, `MANIFEST.sha256` по всем файлам; проверка, что в `$CB` нет ни одного незашифрованного файла, кроме `MANIFEST.sha256`, `COUNTS.txt`, `README.txt`, и ни одного `.partial`.

Ограничения скрипта, о которых надо знать: копия volume при работающей базе неконсистентна (шаг 5 повторяется после остановки контейнеров, чек-лист S8); `pg_dumpall --globals-only` требует суперпользователя — в образе TimescaleDB `POSTGRES_USER` им является, иначе шаг пропускается с сообщением; `shred` на SSD не гарантирует физического уничтожения — диск VPS уничтожается вместе с сервером.

## 4. Копии вне VPS

```
cd /opt/signalbot/closure_backup_<метка> && sha256sum -c MANIFEST.sha256
rclone copy --checksum --transfers 2 . <SIGNALBOT_BACKUP_REMOTE>/closure_<метка>/ && rclone check . <remote>/closure_<метка>/
```

На машине владельца: `rclone copy <remote>/closure_<метка>/ ~/pulsy-archive/closure_<метка>/` (или `scp -r` напрямую с VPS), затем `sha256sum -c MANIFEST.sha256`; вторая копия — отключаемый носитель или второе облако, с той же проверкой. Mirror репозитория:

```
git clone --mirror git@github.com:sh1zok1d/signalbot.git signalbot.git && tar czf - signalbot.git | gpg --symmetric --cipher-algo AES256 -o signalbot_git_mirror.tar.gz.gpg
```

Правило: пока нет двух копий вне VPS с совпадающим `MANIFEST.sha256`, чек-лист остановки не начинается.

## 5. Проверка восстановления из зашифрованной копии (`closure_restore_verify.sh`)

На чистой машине с Docker (не на VPS), из **скачанной** копии, а не из `$CB`:

```
CLOSURE_PASSPHRASE_FILE=~/closure.pass SIGNALBOT_REPO=~/signalbot CLOSURE_VERIFY_WORK=/dev/shm/closure_verify \
  ./scripts/closure/closure_restore_verify.sh ~/pulsy-archive/closure_<метка>
```

Шаги скрипта: `sha256sum -c MANIFEST.sha256` → расшифровка `db_plain.sql.gz.gpg` в рабочий каталог 700 (`/dev/shm` или зашифрованный диск) → `gzip -t` → контейнер `timescale/timescaledb:2.17.2-pg16` (образ из `docker-compose.yml`) → `CREATE DATABASE verify; timescaledb_pre_restore()` → `psql < дамп` → `timescaledb_post_restore()` → сверка `count(*)` каждой таблицы из `COUNTS.txt` (любое расхождение — ошибка) → повторное применение `storage/beta_v0_schema.sql`, если указан checkout → `min/max(open_time)` → `trap`: контейнер удаляется, открытый текст `shred -u`, каталог удаляется.

Результат (только счётчики и даты, без идентификаторов) записывается в `docs/closure/BACKUP_MANIFEST_<дата>.md` вместе с `MANIFEST.sha256` и `COUNTS.txt`. Без этой записи чек-лист остановки не начинается.

Дополнительно на той же машине: расшифровать и `tar -tzf` для `csv_results.tar.gz.gpg`, `secrets.tar.gz.gpg` (только список файлов, не содержимое), `artifacts.tar.gz.gpg`; результат — в тот же манифест.

## 6. Что считается успехом

- `closure_backup.sh --apply` завершился без ошибки, в `$CB` только `*.gpg` + манифест + счётчики + README;
- две копии вне VPS, манифесты совпадают;
- `closure_restore_verify.sh` прошёл на чистой машине из скачанной копии, счётчики совпали;
- пароль архива в менеджере паролей владельца; файл `/root/closure.pass` удалён после завершения всех шагов, использующих его (включая финальный дамп после остановки, чек-лист S5, и обезличенный дамп, S7);
- mirror репозитория снят после финального коммита ветки закрытия и зашифрован;
- `BACKUP_MANIFEST_<дата>.md` записан.

## 7. Хранение после закрытия

- Научные артефакты, код, обезличенный дамп (`db_plain_deidentified.sql.gz.gpg`, создаётся в чек-листе S7) — бессрочно, в двух местах, проверка `sha256sum -c` раз в год.
- Полный дамп и CSV участников, журналы, старые off-site дампы — по `PAID_RESOURCES_AND_PII_V1.md` §3.5: основание и срок хранения определяет владелец явно, с записью в `SHUTDOWN_LOG`; по умолчанию основания для хранения после закрытия нет.
- Пароль архива — в менеджере паролей, с указанием, какие файлы им закрыты; утрата пароля равна утрате архива.
