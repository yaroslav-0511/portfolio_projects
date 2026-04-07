@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════╗
echo ║        Mental Support Bot — Быстрая установка      ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: Проверяем наличие Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Docker не установлен!
    echo.
    echo Скачай и установи Docker Desktop:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    echo После установки Docker перезапусти этот файл.
    pause
    exit /b 1
)
echo [OK] Docker найден.

:: Проверяем наличие .env файла
if not exist ".env" (
    echo.
    echo [!] Файл .env не найден. Создаю из шаблона...
    copy ".env.example" ".env" >nul
    echo.
    echo ════════════════════════════════════════════════
    echo  ВАЖНО: Открой файл .env в блокноте и заполни:
    echo  1. BOT_TOKEN  — токен твоего Telegram бота
    echo  2. OWNER_TELEGRAM_IDS — твой Telegram ID
    echo ════════════════════════════════════════════════
    echo.
    echo Открыть .env для редактирования сейчас? (y/n)
    set /p OPEN_ENV="> "
    if /i "%OPEN_ENV%"=="y" (
        notepad .env
        echo.
        echo После сохранения файла нажми любую клавишу для продолжения...
        pause >nul
    ) else (
        echo Заполни .env вручную, затем снова запусти setup.bat
        pause
        exit /b 0
    )
) else (
    echo [OK] Файл .env найден.
)

:: Проверяем что BOT_TOKEN заполнен
for /f "tokens=2 delims==" %%a in ('findstr /i "BOT_TOKEN" .env') do set TOKEN=%%a
if "%TOKEN%"=="" (
    echo.
    echo [ОШИБКА] BOT_TOKEN в файле .env пустой!
    echo Открой .env и заполни BOT_TOKEN=твой_токен_здесь
    pause
    exit /b 1
)
if "%TOKEN%"=="your_bot_token_here" (
    echo.
    echo [ОШИБКА] BOT_TOKEN не заменён! Измени 'your_bot_token_here' на настоящий токен.
    pause
    exit /b 1
)

echo.
echo [>>] Запускаю Docker и собираю бота... (первый запуск может занять 3-5 минут)
echo.

docker-compose up --build -d

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось запустить бота.
    echo Проверь, что Docker Desktop запущен и попробуй снова.
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║              Бот успешно запущен!                  ║
echo ╚══════════════════════════════════════════════════╝
echo.
echo Чтобы посмотреть логи, выполни в этой папке:
echo   docker-compose logs -f bot
echo.
echo Чтобы остановить бота:
echo   docker-compose down
echo.
pause
