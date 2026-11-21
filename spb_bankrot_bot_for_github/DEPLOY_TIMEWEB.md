# Timeweb для новичка: куда нажимать и что вставлять

Это инструкция именно для **панели бота** (сайт + фоновый опрос лотов + Telegram).

## Важно заранее

У Timeweb бывает разное:

| Что у вас | Подойдёт? |
|-----------|-----------|
| **Timeweb Cloud → Apps** | Да, лучший вариант |
| **Timeweb Cloud → VPS / облачный сервер** | Да |
| Обычный «хостинг сайтов» (только PHP, папка `public_html`) | **Нет** для этого бота |

Если в личном кабинете вы видите только сайты на PHP — оформите в Cloud раздел **Apps** или **VPS**.  
Кабинет Cloud: https://timeweb.cloud

Вам понадобятся (уже есть у вас):

- `TELEGRAM_BOT_TOKEN` — от @BotFather  
- `TELEGRAM_CHAT_ID` — id чата/канала  

**Не присылайте их в чат** — только вставляйте в Timeweb.

---

# Часть 0. Положить код на GitHub

Timeweb Apps забирает код из **GitHub / GitLab / Bitbucket**.  
Самый простой для новичка — **GitHub**.

## 0.1. Аккаунт GitHub

1. Откройте https://github.com  
2. Войдите или зарегистрируйтесь.

## 0.2. Новый репозиторий

1. Справа сверху нажмите **+** → **New repository**.  
2. **Repository name:** `spb-bankrot-bot`  
3. Public или Private — на ваш выбор.  
4. **Не** ставьте галочки “Add a README / .gitignore / license” (репозиторий пустой).  
5. Нажмите **Create repository**.

## 0.3. Как залить код (выберите один способ)

### Способ А — через сайт GitHub (без терминала)

1. Откройте репозиторий на GitHub.  
2. Нажмите **uploading an existing file** (или **Add file** → **Upload files**).  
3. Перетащите **все файлы проекта** (папки `bankrot_bot`, `tests`, файлы `main.py`, `requirements.txt`, `README.md` и т.д.).  
   Не нужна папка `.git`, `.venv`, `data/lots.db`.  
4. Внизу **Commit changes**.

Код также лежит здесь: https://cursor.com/codebase/post2may/spb-bankrot-bot  
Можно скачать архив оттуда (если кабинет Cursor даёт Download) и загрузить на GitHub.

### Способ Б — через Cursor / терминал

Если проект уже на компьютере:

```bash
cd папка_с_проектом
git remote add github https://github.com/ВАШ_ЛОГИН/spb-bankrot-bot.git
git push -u github main
```

Подставьте свой логин GitHub вместо `ВАШ_ЛОГИН`.

Проверка: на странице репозитория должны быть видны `main.py` и папка `bankrot_bot`.

---

# Часть 1. Создать приложение в Timeweb Cloud Apps

## 1.1. Войти

1. Откройте https://timeweb.cloud  
2. Войдите в аккаунт.

## 1.2. Создать Apps

1. В левом меню найдите **Apps** (Приложения / App Platform).  
2. Нажмите **Создать** / **Create**.  
3. Выберите тип приложения: **Backend**.  
4. Выберите фреймворк: **FastAPI**.

## 1.3. Подключить репозиторий

1. Нажмите подключить **GitHub** (или GitLab / Bitbucket).  
2. Разрешите Timeweb доступ к репозиториям (окно авторизации GitHub → Authorize).  
3. В списке выберите репозиторий **`spb-bankrot-bot`**.  
4. Ветка: **`main`**.  
5. Корневая папка / Root directory: оставьте пустым или `/` (код в корне репозитория).

## 1.4. Версия Python

Выберите **Python 3.12** (подойдёт и 3.11–3.14).

## 1.5. Куда вставить команды

Найдите поля примерно с такими названиями:

- **Команда сборки** / Build command / Build  
- **Команда запуска** / Start command / Run  

### В поле «Команда сборки» вставьте РОВНО это:

```text
pip3 install --upgrade -r requirements.txt
```

### В поле «Команда запуска» вставьте РОВНО это:

```text
uvicorn main:app --host 0.0.0.0 --port 80
```

Почему так:

- `main:app` — файл `main.py`, объект `app` внутри него (у нас уже так сделано).  
- `--host 0.0.0.0` — чтобы сайт был доступен из интернета.  
- `--port 80` — стандартный порт для Apps.

## 1.6. Тариф / регион сервера

Выберите любой доступный минимальный тариф в РФ (или какой удобен).  
Нажмите дальше / создать приложение (ещё не обязательно деплоить до переменных — зависит от UI; если просит сразу Deploy — сначала добавьте переменные в настройках).

---

# Часть 2. Куда вставить токен Telegram

Это самое важное для бота.

1. Откройте созданное приложение в Apps.  
2. Найдите раздел:
   - **Переменные окружения**  
   - или **Environment**  
   - или **Env** / **Secrets**  
3. Нажмите **Добавить переменную** / **Add variable**.

Добавьте по одной (имя слева, значение справа):

| Имя переменной (Name) | Что вставить в Value |
|------------------------|----------------------|
| `TELEGRAM_BOT_TOKEN` | токен от @BotFather (длинная строка с `:`) |
| `TELEGRAM_CHAT_ID` | число id чата/канала (например `123456789` или `-100…`) |
| `HOST` | `0.0.0.0` |
| `PORT` | `80` |
| `SCAN_INTERVAL_SEC` | `300` |
| `DRY_RUN` | `false` |

Как выглядит одна строка:

- **Name:** `TELEGRAM_BOT_TOKEN`  
- **Value:** `7123…:AAH…` ← ваш токен, без кавычек и пробелов  

То же для `TELEGRAM_CHAT_ID`.

Сохраните переменные (**Save** / **Сохранить**).

---

# Часть 3. Запуск (Deploy)

1. Кнопка **Деплой** / **Deploy** / **Запустить**.  
2. Подождите 1–5 минут.  
3. Смотрите вкладку **Логи** / **Logs**:
   - хорошо, если видно установку пакетов и запуск uvicorn;
   - плохо, если красный traceback — скопируйте текст ошибки (без токенов) и можно прислать мне.

После успеха Timeweb покажет адрес вида:

`https://что-то.twc1.net`

Откройте его в браузере — это ваша панель бота (без входа в Cursor).

---

# Часть 4. Проверка, что всё работает

1. В браузере открылась панель **SPB Bankrot Bot**.  
2. Есть счётчики и список лотов (или кнопка «Сканировать сейчас»).  
3. В Telegram в нужный чат/канал приходят сообщения о лотах (не сразу — после скана).  
4. Если в панели написано «Telegram: нужен токен» — переменные в Timeweb не подхватились: проверьте имена **точно** `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`, сохраните и сделайте **Redeploy**.

---

# Если у вас только VPS (облачный сервер), не Apps

## Программа на компьютере

- Windows: **PuTTY** или встроенный OpenSSH  
- Mac: **Terminal**  
- Или веб-консоль SSH в панели Timeweb

## Команды на сервере (вставлять по очереди)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/ВАШ_ЛОГИН/spb-bankrot-bot.git
cd spb-bankrot-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Создайте файл секретов:

```bash
nano .env
```

**Вставьте внутрь файла** (подставьте свои значения):

```env
TELEGRAM_BOT_TOKEN=сюда_токен
TELEGRAM_CHAT_ID=сюда_id
HOST=0.0.0.0
PORT=8765
SCAN_INTERVAL_SEC=300
DRY_RUN=false
```

Сохранить в nano: `Ctrl+O`, Enter, выход: `Ctrl+X`.

Запуск:

```bash
source .venv/bin/activate
python main.py
```

Панель: `http://IP_ВАШЕГО_СЕРВЕРА:8765`  
(IP смотрите в карточке VPS в Timeweb; в файрволе откройте порт 8765.)

Чтобы работало после закрытия SSH — настройте systemd (см. ниже) или оставьте Apps.

### systemd (чтобы бот не выключался)

```bash
sudo nano /etc/systemd/system/spb-bankrot.service
```

Вставьте (замените `ubuntu` и путь на свои):

```ini
[Unit]
Description=SPB Bankrot Bot
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/spb-bankrot-bot
EnvironmentFile=/home/ubuntu/spb-bankrot-bot/.env
ExecStart=/home/ubuntu/spb-bankrot-bot/.venv/bin/python main.py
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now spb-bankrot
sudo systemctl status spb-bankrot
```

---

# Частые ошибки

| Симптом | Что сделать |
|---------|-------------|
| Сайт не открывается | Проверьте команду запуска с `--host 0.0.0.0 --port 80`, статус Deploy = success |
| В панели нет Telegram | Проверьте env-переменные и Redeploy |
| Build failed / No module | Команда сборки должна быть `pip3 install --upgrade -r requirements.txt` |
| Репозиторий пустой | На GitHub должны быть `main.py` и `bankrot_bot/` |
| PHP-хостинг | Этот бот туда не ставится — нужен Apps или VPS |

---

# Краткая шпаргалка «что куда»

| Куда | Что вставить |
|------|----------------|
| GitHub → новый репозиторий | файлы проекта (`main.py`, `bankrot_bot`, …) |
| Timeweb Apps → фреймворк | FastAPI |
| Timeweb Apps → репозиторий | ваш `spb-bankrot-bot`, ветка `main` |
| Поле Build | `pip3 install --upgrade -r requirements.txt` |
| Поле Start | `uvicorn main:app --host 0.0.0.0 --port 80` |
| Env Name/Value | `TELEGRAM_BOT_TOKEN` = токен, `TELEGRAM_CHAT_ID` = id |
| Браузер | URL вида `https://….twc1.net` из карточки Apps |
