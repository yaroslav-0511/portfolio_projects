# DEPLOY VPS (prod)

## 1) Что нужно на сервере
- Ubuntu 22.04+ (или совместимый Linux)
- 1 vCPU / 2 GB RAM / 20+ GB disk (минимум)
- Открыт SSH-доступ

## 2) Установка Docker и Compose plugin
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Проверка:
```bash
docker --version
docker compose version
```

## 3) Копирование проекта
На сервере:
```bash
mkdir -p ~/apps
cd ~/apps
```

Дальше перенеси папку проекта любым удобным способом (git clone / scp / rsync).

## 4) Прод-конфиг
В корне проекта:
```bash
cp .env.prod.example .env
```

Заполни `.env`:
- `BOT_TOKEN`
- `OWNER_TELEGRAM_IDS`
- при необходимости `MAX_INVITE_ATTEMPTS` и `INVITE_ATTEMPT_WINDOW`

Важно для прод:
- `APP_ENV=prod`
- `INVITE_RATE_LIMIT_ENABLED=true`

## 5) Первый запуск
В корне проекта в `docker-compose.yml` задано фиксированное имя проекта Compose (`name: mental-support-bot`): тома PostgreSQL/Redis не привязаны к имени папки на диске (удобно при переименовании каталога). Если стек уже поднимался **до** появления этой строки, старые тома могли быть созданы под другим именем проекта — проверьте `docker compose ls` и `docker volume ls`; при необходимости один раз укажите прежний project name (`docker compose -p …`) или перенесите данные.

```bash
cd "/home/<user>/apps/Psy for IT BOT"
docker compose up --build -d
docker compose logs --tail=150 bot
```

Ожидается:
- миграции проходят без ошибок
- `Bot starting polling...`

## 6) Обновление релиза
```bash
cd "/home/<user>/apps/Psy for IT BOT"
docker compose up --build -d
docker compose logs --tail=100 bot
```

## 7) Проверки после деплоя
- `/start` у Owner открывает панель Owner
- создание компании и генерация инвайтов
- вход U по коду
- лог без traceback: `docker compose logs --tail=200 bot`

## 8) Бэкап базы (PostgreSQL)
Создать бэкап:
```bash
cd "/home/<user>/apps/Psy for IT BOT"
docker compose exec -T db pg_dump -U postgres -d mental_support > backup_mental_support.sql
```

Восстановить из бэкапа:
```bash
cd "/home/<user>/apps/Psy for IT BOT"
docker compose exec -T db psql -U postgres -d mental_support < backup_mental_support.sql
```

## 9) Быстрый откат (если релиз неудачный)
- Вернуть предыдущий код проекта (git checkout/tag или старый архив)
- Запустить:
```bash
docker compose up --build -d
docker compose logs --tail=150 bot
```

## 10) Домен и webhook (когда будете готовы)
- Текущий запуск работает в polling и не требует домена.
- Для webhook позже понадобится:
  - домен
  - reverse proxy (nginx/caddy)
  - TLS (Let's Encrypt)
  - публичный HTTPS endpoint

