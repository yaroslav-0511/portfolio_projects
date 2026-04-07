# SESSION_STATE (обновляется автоматически)

Этот файл — источник правды о состоянии работы, чтобы мы не зависели от сохранности чата.

## Правило завершения сессии

Если вы пишете что-то вроде **«на сегодня всё» / «я завершаю» / «стоп»**, я **не спрашиваю**, а **сам автоматически**:
- обновляю `SESSION_STATE.md` (где остановились, что сделано, что дальше);
- обновляю `DECISIONS.md` (что согласовали и почему);
- при необходимости обновляю `ИНСТРУКЦИЯ.md` (если в процессе поменялись шаги запуска/деплоя);
- в конце сообщения даю короткий “что делать завтра” (1-3 пункта).

## Текущий статус

- **Дата/время**: 2026-03-28
- **Фаза**: **локальная проверка заказчиком (брат)** на своей машине; VPS — после приёмки
- **Текущий этап общего плана (из 7)**: **Этап 6 закрыт**; **этап 7** — сначала приёмка у брата локально (Docker, тесты, смоук), **затем** выкладка на VPS по [`DEPLOY_VPS.md`](DEPLOY_VPS.md) и handover по чеклисту
- **Блокер**: нет
- **Контекст папки и Docker**: рабочая папка проекта переименована в **`Psy for IT BOT`** (раньше было с суффиксом V2). В `docker-compose.yml` зафиксировано **`name: mental-support-bot`** — имя проекта Compose не зависит от имени каталога; при смене/дублировании папки помните про **тома** (старые данные могут подцепиться к тому же имени проекта). Типичные сбои при первом запуске у нового человека: **permission denied** к Docker-сокету (Linux/WSL — группа `docker` или `sudo`) и **порт 5432 занят** другим Postgres или старым `docker compose` — см. обновлённую [`ИНСТРУКЦИЯ.md`](ИНСТРУКЦИЯ.md).
- **Получатель handover (брат)**: ориентир **Windows** — основной сценарий в [`ИНСТРУКЦИЯ.md`](ИНСТРУКЦИЯ.md) и блок «Если у тебя Windows» в [`docs/START_HERE_RECIPIENT.md`](docs/START_HERE_RECIPIENT.md) / **`ЧИТАТЬ_СНАЧАЛА.md`**. Папка для передачи по умолчанию: **`../Psy for IT BOT-YYYYMMDD`** (скрипт [`scripts/export_handover_directory.sh`](scripts/export_handover_directory.sh)).

## Что сделано

- Добавлены: `.gitignore`, `requirements-dev.txt`, `pytest.ini`, `tests/test_config.py`
- Переведен запуск БД на Alembic: добавлен runner миграций, baseline миграция, обновлен `bot/main.py`
- Починены критичные сценарии: инвайты (FK на activated_by), soft-delete пользователя/консультанта, перенос сессий, восстановление консультанта у Owner
- Починен старт контейнера: миграция `20260327_000004` (ошибка `op.inspect`)
- Добавлены регрессионные тесты на lifecycle консультанта и инвайт-сервис
- Обновлена инструкция по запуску тестов (сборка `tests` перед `run`, чтобы не тестировать старый образ)
- Добавлены `DEPLOY_VPS.md` и `HANDOVER_CHECKLIST.md`
- Зафиксирован текущий прод-режим: **без домена, через polling**; в `DECISIONS.md` — **`handle_as_tasks=False`** в `start_polling`, чтобы не было гонок FSM при быстрых callback
- Добавлен GitHub Actions CI: `.github/workflows/ci.yml` (pytest на push/PR)
- В `ИНСТРУКЦИЯ.md` для конечного получателя: **Git не обязателен**; отдельный handover-пакет (папка/ZIP без `.git`) — **перед передачей заказчику**, не вместо текущей рабочей копии
- Добавлены unit-тесты на `bot/services/proxy.py` (`get_active_conversation`, `start_conversation`, `end_conversation`)
- В `HANDOVER_CHECKLIST.md` — раздел **6**: финальная упаковка для заказчика; скрипты [`scripts/package_for_handover.sh`](scripts/package_for_handover.sh) (архив `.tar.gz`) и [`scripts/export_handover_directory.sh`](scripts/export_handover_directory.sh) (чистая папка + `ЧИТАТЬ_СНАЧАЛА.md` в корне); для получателя — [`docs/START_HERE_RECIPIENT.md`](docs/START_HERE_RECIPIENT.md)
- По ТЗ (секция 9): **WHO-5** (опрос, сохранение в `wellbeing_responses`, миграция `20260327_000005`), **полезные материалы** (3 страницы в i18n), кнопки в меню User; у Owner — **статистика WHO-5**; роутер [`bot/handlers/wellbeing.py`](bot/handlers/wellbeing.py); тесты [`tests/test_wellbeing.py`](tests/test_wellbeing.py)
- В `DECISIONS.md`: если ассистент нарушает формат «Что/Зачем/Важность» — напоминание одним словом **«DECISIONS»**
- Аудит FSM/меню (этап 6): `state.clear()` при входе в «Главное» Owner/Consultant (`o_menu:main`, `c_menu:main`); при входе User в «Полезные материалы», «Экстренная», «Группы», «Мои сессии», «Настройки» — чтобы старые inline-кнопки не оставляли «залипший» FSM (сессия, фидбек и т.д.)
- **Один активный UI-якорь на чат:** [`bot/middlewares/ui_surface.py`](bot/middlewares/ui_surface.py) + `touch_ui_surface` / `sync_ui_surface_if_other` в хендлерах; неэкземптные callback не с якорного сообщения — алерт `ui_use_latest_message`; кнопки на старых сообщениях визуально остаются, но не обрабатываются (см. [`bot/services/ui_surface.py`](bot/services/ui_surface.py) — exempt: главные меню, `skip`, `feedback:`, срочные, напоминания и т.д.)
- **WHO-5:** в callback встроены `who5_session_id` и индекс вопроса; после `callback.answer()` повторное чтение FSM перед записью ответа; устаревшие кнопки не проходят проверку сессии
- Пользователь подтвердил **ручной смоук** в Telegram («всё работает как надо») по сценариям из [`CHECKLIST_U_C_O.md`](CHECKLIST_U_C_O.md)
- Автотесты в репозитории: **23** теста в `tests/` (подсчёт по файлам: `test_config` 4, `test_wellbeing` 4, `test_consultant_lifecycle` 5, `test_invite_service` 6, `test_proxy_service` 4). Актуальный прогон в Docker — команды ниже.

## Что делаем следующим шагом

1) **Брат** — локально: `ЧИТАТЬ_СНАЧАЛА.md` / [`docs/START_HERE_RECIPIENT.md`](docs/START_HERE_RECIPIENT.md), [`ИНСТРУКЦИЯ.md`](ИНСТРУКЦИЯ.md), поднять стек, прогнать тесты и смоук по [`CHECKLIST_U_C_O.md`](CHECKLIST_U_C_O.md).
2) **После локальной приёмки** — VPS: [`DEPLOY_VPS.md`](DEPLOY_VPS.md), приёмка по [`HANDOVER_CHECKLIST.md`](HANDOVER_CHECKLIST.md).
3) Комплект без Git для передачи: [`scripts/export_handover_directory.sh`](scripts/export_handover_directory.sh) или [`scripts/package_for_handover.sh`](scripts/package_for_handover.sh) (раздел 6 в `HANDOVER_CHECKLIST.md`).

## Регресс pytest в Docker (после правок)

Из корня проекта:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build tests
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm tests
```

Ожидается **23 passed** (если число изменится — обновите этот файл после прогона).

## Что нужно от вас (на сейчас)

- **Брат:** локальная приёмка по `ЧИТАТЬ_СНАЧАЛА.md` / `ИНСТРУКЦИЯ.md` и смоук по `CHECKLIST_U_C_O.md`.
- При следующем крупном изменении кода — прогнать команды регресса выше; при расхождении с **23 passed** сообщить или обновить счётчик в этом файле.
- **VPS** — после локальной приёмки, по `DEPLOY_VPS.md`.
