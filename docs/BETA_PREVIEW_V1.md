# Beta preview V1 — the owner's UX review before the observation week

**Status:** `PREPARED` (2026-10-09, track A for ОПГ-1). The owner cancelled the 3b observation start of 2026-10-09. A **PREVIEW** deploy comes first, for the owner's UX review.
- every ready surface is on;
- automated sends go to the owner only;
- the test stays `NOT_OPEN`, and Day 0 is unset;
- model states are off.

The observation week starts only at the deploy the owner names after accepting the UX (`ORCHESTRATION_V1.md` §4a). Everything in the preview period is excluded from the test's metrics (`BETA_MEASUREMENT_CONTRACT_V1.md` §12.2).

**Code base.** The list below is checked against `bd35820b` (main after #434) and `config/beta_v0.yaml` there. The preview flag `access.preview_owner_only` and the command `/admin_preview [type]` come from track B (#439). The deploy SHA is `45213dda2039784faf96f057feb743f17aed059e` (ОПГ-1, after the merges).

## (a) What is ON and what is OFF

**Hard switches (environment, `/opt/signalbot/.env`; not in git).** Every runtime switch needs both the committed value and its env kill switch (`beta/config.py` `BetaSwitches`):
- `BETA_ENABLED`, `BETA_DETECTION_ENABLED` and `BETA_OUTCOME_TRACKING_ENABLED` must be true;
- `BETA_PUSH_ENABLED` must be an **explicit** true, or nothing is pushed;
- `BETA_TELEGRAM_ENABLED` must not be `0`;
- `BETA_RESEARCH_EVIDENCE_ENABLED` must not be `0`;
- the durable `/admin_pause_push` state must be resumed (`/admin_resume_push`).

Check them on the VPS: `/admin_health` prints `switches`, and `/admin_status` prints `push effective` and `d7 effective`.

**ON**

| Surface | Where it is switched (bd35820b) |
|---|---|
| **Preview: every automated send to the owner only** | `access.preview_owner_only: true` (#439) |
| Detection, episodes, the unusual-hour push | `enabled`/`detection_enabled`/`push_enabled` + the env switches above; `push_policy` (quiet hours 23:00–07:00, 60 min global cooldown) |
| `/btc` with the «Событие» / «1ч» / «24ч» / «🔬 Исследования» tabs and the «Уровни» / «Риск» buttons | always on; the 🔬 tab needs `decision.research_evidence.enabled: true` |
| `/catchup [1–24]`, `/history`, `/terms`, `/guide`, `/help`, `/lang`, `/type`, `/idea`, `/feedback` | always on |
| `/levels`, `/risk`, `/events`, `/accuracy` (corridor record) | always on; `decision.forecast_tracking: true` |
| `/check <price>` and the two-level `/check <p1> <p2>` | always on (`access.tiers_enforced: false` opens `check_two_levels`) |
| Level race: the HIST/T15 line in `/levels` and `/check` | `level_race.display_enabled: true` |
| Level race: the journal at every landmark | `level_race.journal_enabled: true` |
| Level-touch push trigger | `level_race.push_trigger: structural` |
| Market alerts (level touches, sharp moves, CPI/FOMC reminders) and `/alert` | `decision.market_alerts.enabled: true`, `decision.max_price_alerts: 5` |
| Morning briefing, `/brief on\|off\|HH:MM` | `briefing.enabled: true` (08:00 Kyiv by default) |
| Weekly report (Sunday 19:00 on the user's clock) | `decision.weekly_report.enabled: true` |
| Per-type mute `/push <type> on\|off`, time zone `/tz` | always on |
| The research tab and `/research` | `decision.research_evidence.enabled: true`. The feeds (`signalbot-beta-feeds.timer`, `signalbot-beta-stress.timer`) need their own owner go (`RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md` §D). Without them the tab lists what it cannot check, and why. |
| The claim journal | `decision.claim_journal: true` (internal; rows of the preview are reported as the preview period) |
| The owner-only signature index `/hypotheses`, `/pin` | `decision.signature_index: true` |
| «Другие монеты» (the U5 fake door) under `/help` | always on |
| D7 «High impact» line on `/btc` | **on during preview via `/admin_d7_on`** (architect, 2026-10-09). `regime_d7.enabled: true` is the hard allow; the durable owner state defaults off, so the owner turns it on in the route (step 6). Whether it stays on at the official start is an open item for the freeze (below). |

**OFF**

| Surface | Why it is off (bd35820b) |
|---|---|
| Level race model states (HIST → model) | `level_race.model_states_enabled: false` (one dated switch, later) |
| OKX liquidations (shown and voting) | `liquidations.okx_enabled: false` (#434, decision (d)) |
| Research lines on the main surfaces | `decision.research_evidence.main_surfaces_enabled: false` (`PRE_BETA_SCOPE_DECISION_V1` §6.1); they appear only in the 🔬 tab and `/research` |
| Tiers (free/paid gating) | `access.tiers_enforced: false` |
| The U3 offer `/admin_offer` | `access.u3_offer.price: null`, `method: null`: the command refuses |
| Live hysteresis | `episodization.live_hysteresis_enabled: false` (cannot be enabled) |
| The test and Day 0 | `/admin_test_open` is not run, so the test is `NOT_OPEN`; `briefing.withdrawal.day0_kyiv: null`, so there is no U1a withdrawal day |

## Open items for the freeze
Decided at the official start, not in the preview:
- **D7 «High impact» line.** It is on during the preview via `/admin_d7_on`. Whether it stays on at the official start is open, to be decided at the freeze and recorded in the release-candidate record of the starting deploy.

## (b) Маршрут проверки для владельца (по шагам)

Все команды — в чате с ботом в Telegram. Пока идёт превью, автоматические сообщения (push, сводка, оповещения, недельный отчёт) приходят **только владельцу**. Тестовый аккаунт видит всё, что запрашивает командами, но автоматических сообщений не получает.

**Важно до начала.**
- `/delete_me` **необратим**: он удаляет участника и все его данные. Делайте его **последним шагом** и **только с тестового аккаунта**, никогда со своего.
- `/admin_remove <id>` тоже удаляет участника безвозвратно.
- Не используйте `/admin_broadcast`: он рассылает текст всем активным участникам.
- Не используйте `/admin_test_open`: он открывает тест (Day 0 не задаём).
- Не используйте `/admin_offer` (предложение оплаты).
- **Тестовый аккаунт после проверки должен быть удалён** (`/delete_me` с него, шаг 7) или убран владельцем (`/admin_remove <id>`), чтобы он никогда не попал в официальную когорту.
- В `/hypotheses` только смотрите индекс. Решения `research`/`reject` записываются навсегда: «первое решение остаётся». `/pin` добавляет запись, которую нельзя убрать.

**0. Тестовый аккаунт (чтобы пройти путь нового пользователя).**
1. Второй аккаунт Telegram: второй номер, или второй аккаунт в том же приложении (Настройки → Добавить аккаунт).
2. Узнайте его числовой id: например, бот @userinfobot или `/admin_users` после первого `/start`.
3. Со своего аккаунта: `/admin_add <id тестового аккаунта>`. Или пригласительная ссылка: `/admin_invite_new 1 1 preview-test` (1 использование, 1 день) — откройте её с тестового аккаунта.

**1. Вход нового пользователя (с тестового аккаунта).**
1. `/start` → кнопка языка (Русский / English) → текст о данных.
2. Кнопка «Вступить» → приветствие и один вопрос «Как вы торгуете?» с кнопками-ответами (ответ не меняет сообщения бота).
3. `/help` — список команд и кнопки «Термины», «Другие монеты», «💡 Идея / чего не хватает», «📖 Как читать бота».
4. `/guide` — как читать бота.

**2. Состояние рынка (с любого аккаунта).**
1. `/btc` — состояние сейчас: коридор, уровни, события. Кнопки под сообщением:
   - «Событие» (если есть активное событие);
   - «1ч» и «24ч»;
   - «🔬 Исследования»;
   - «Уровни» и «Риск».
   Нажмите каждую.
2. `/catchup` — что было за 8 ч; `/catchup 2` и `/catchup 24` — другие окна.
3. `/levels` — уровни: расстояние, шанс дойти, строка «кто первый» (HIST, на истории), что было при касании.
4. `/check 64000` — подставьте цену рядом с текущей: шанс дойти за 1ч / 4ч / 24ч. Затем `/check <выше> <ниже>` — два уровня.
5. `/risk 0.5` — как часто цена проходит стоп 0,5 % против позиции.
6. `/events` — календарь: CPI, ФРС, экспирации.
7. `/accuracy` — насколько точен коридор (живая запись и история).
8. `/history` — недавние необычные события.

**3. Личные настройки (в боте нет единой команды «настройки»; это отдельные команды).**
1. `/tz` — текущий часовой пояс и тихие часы. `/tz +3` или `/tz Europe/Warsaw` — сменить; `/tz` снова — проверить.
2. Тихие часы — 23:00–07:00 по Киеву. В них не приходят push о событиях. Это общая настройка, отдельной команды для неё нет.
3. `/brief` — статус утренней сводки. `/brief 07:30` — своё время, `/brief off` / `/brief on` — выключить / включить.
4. `/push` — какие сообщения приходят. По типам: `/push levels off`, `/push events off`, `/push moves off`, `/push hours off`, `/push weekly off` — и обратно `on`. Всё сразу: `/push off` / `/push on`.
5. Под каждым push есть кнопка «🔕 Не присылать такие» и её отмена «↩️ Вернуть».
6. `/lang` — язык сообщений (проверьте оба: RU и EN).
7. `/type` — ответить на вопрос о стиле торговли ещё раз.

**4. Оповещения о цене.**
1. **Со своего аккаунта (владельца)**: `/alert 65000` — подставьте уровень рядом с ценой. `/alert` — список. `/alert del 1` — удалить первый, `/alert del all` — все.
2. Когда цена подойдёт или дойдёт, оповещение придёт владельцу. Оповещение, поставленное с тестового аккаунта, в превью **не придёт** никогда: автоматические сообщения уходят только владельцу.

**5. Исследования и тексты.**
1. Вкладка «🔬 Исследования» под `/btc`, затем `/research` (два сообщения: что подтвердилось и что нет).
2. `/terms` — термины. Проверьте строку «Ликвидации OKX не учитываются…».
3. `/feedback <текст>` — отзыв; придёт копия владельцу.
4. `/idea <текст>` — идея.
5. Обычный текст без команды — тоже уходит команде.

**6. Владелец: просмотр каждого типа автоматических сообщений.**
1. `/admin_preview` — список типов. Затем `/admin_preview <тип>` для каждого:
   - `hour` — push о необычном часе;
   - `level` — касание уровня;
   - `move` — резкое движение;
   - `event` — напоминание о CPI / FOMC;
   - `price` — личный `/alert`: цена дошла;
   - `approach` — личный `/alert`: цена подходит;
   - `brief` — утренняя сводка (по текущему состоянию);
   - `weekly` — недельный отчёт (по текущему состоянию).

   Для типа, которого ещё не было, бот ответит «ещё не было».
2. `/admin_d7_on` — включить строку D7 «High impact» на `/btc` (решение архитектора: в превью включена). Затем `/admin_status` должен показать `d7 effective True`; снова `/btc` — строка видна, когда текущий час её даёт. Выключить — `/admin_d7_off`.
3. `/admin_health` — алерты здоровья (ожидается пусто), переключатели и строка `test NOT_OPEN … Day 0 None`. `/admin_status` — `push effective` и `d7 effective`. `/admin_stats` — статистика (в превью не считается тестом).
4. `/hypotheses` — индекс сигнатур (только смотреть, см. «Важно до начала»).
5. Ответ стикером (#417): ответьте стикером на копию сообщения участника, которую прислал бот (например, на копию `/feedback` тестового аккаунта). Стикер уйдёт этому участнику. Работает только для копий, созданных **после деплоя 3a (2026-10-09 06:47Z)**; на более старые бот ответит `NOT_MAPPED`.

**7. Пауза и удаление (последними, только тестовый аккаунт).**
1. `/stop` — пауза: автоматические сообщения прекращаются, бот спросит причину (кнопки). Вернуться: `/start` → «Вступить».
2. `/delete_me` — **необратимо** удаляет тестового участника и все его данные. Только с тестового аккаунта и только в самом конце.

## (c) Preview deploy steps (VPS, the owner; deploy SHA `45213dda`)
Run them as the `signalbot` user from `/opt/signalbot` with the venv python, in this order:

1. **Backup:** `sudo /opt/signalbot/deploy/backup.sh` and check that the new file is in `backups/`.
2. **The fingerprint key**, only if `.env` has none. The block never prints the key. It first adds a missing trailing newline, so the appended line never joins the last one. It never ends the SSH session.
   ```bash
   if [ "$(sudo grep -c '^BETA_FINGERPRINT_KEY=' /opt/signalbot/.env)" = 0 ]; then
     [ -z "$(sudo tail -c1 /opt/signalbot/.env)" ] || echo | sudo tee -a /opt/signalbot/.env >/dev/null
     printf 'BETA_FINGERPRINT_KEY=%s\n' "$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
       | sudo tee -a /opt/signalbot/.env >/dev/null
   else
     echo "BETA_FINGERPRINT_KEY already set: nothing changed"
   fi
   sudo grep -c '^BETA_FINGERPRINT_KEY=' /opt/signalbot/.env   # must print 1
   ```
   Copy the key into the owner's password manager (`sudo grep '^BETA_FINGERPRINT_KEY=' /opt/signalbot/.env`, read it once on screen, never paste it into a chat). Never into a dump or a backup.
3. **The preview flag:** at `45213dda2039784faf96f057feb743f17aed059e`, `config/beta_v0.yaml` carries `access.preview_owner_only: true` (#439). Check it with `grep -n preview_owner_only config/beta_v0.yaml` after the checkout.
4. **Code:** `git fetch origin && git checkout 45213dda2039784faf96f057feb743f17aed059e`. There is no new Python dependency.
5. **Units:** `sudo deploy/install_beta_units.sh`. It copies the units, runs `daemon-reload` and writes `BUILD_SHA`; it enables nothing.
6. **Beta restart:** `sudo systemctl restart signalbot-beta-bot.service`. The notifier, detector and outcome timers pick up the new code on their next run.
7. **Health:** `.venv/bin/python main.py --beta-health --beta-json` should show `alerts: []`, or only known warm-up alerts.
No collector restart: `fe8ac969..45213dda` touches no collector or Stage-1 code (ОПГ-1, verified), and a restart would leave a #368 gap.

**Checks.**
- `--beta-health` stays clean.
- `/admin_health` shows `alerts []`, the switches, `test NOT_OPEN` and `Day 0 None`.
- `/admin_status` shows `push effective True`, and `d7 effective False` until the owner's `/admin_d7_on` in the route.
- `cat /opt/signalbot/BUILD_SHA` prints `45213dda2039784faf96f057feb743f17aed059e`.
- OKX heartbeat rows keep arriving (the collector is not restarted).
- `/btc` answers. One `/admin_preview <тип>` reaches the owner, and **nothing reaches the test account** unasked.

**Rollback** to `fe8ac969` (the deploy before the preview):
1. `git checkout fe8ac969 && sudo deploy/install_beta_units.sh`.
2. `sudo systemctl restart signalbot-beta-bot.service`.

The rollback is beta-only: the collector is not restarted.

The schema changes are additive, and the old code ignores the new tables and columns. Keep `BETA_FINGERPRINT_KEY` in `.env` (the old code ignores it). Fingerprints printed under the preview stay keyed.
