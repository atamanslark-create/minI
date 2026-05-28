# minI - VPS Monitor Telegram Bot

Легкий Telegram-бот для быстрого мониторинга и диагностики VPS-сервера без сложной настройки Prometheus, Grafana или Zabbix.

## ✨ Возможности

### 📊 Мониторинг VPS
- Нагрузка CPU, использование RAM, заполнение диска
- Uptime сервера и load average
- Топ процессов по CPU

### 💾 Управление дисками
- Состояние всех разделов диска
- Использование памяти в процентах и гигабайтах

### 🧩 Управление сервисами
- Проверка статуса systemd-сервисов (SSH, nginx, MySQL и т.д.)
- Быстрая информация о состоянии сервисов

### 🩺 Диагностика
- Список неисправных systemd-сервисов
- Последние ошибки из journalctl
- Состояние прослушиваемых сетевых портов
- Полная диагностика системы

### ⚙️ Управление
- Удалённое удаление бота с VPS

## 🚀 Быстрая установка

### Требования
- Linux с systemd
- Python 3.8+
- pip

### Установка

```bash
# 1. Скопируйте репозиторий на VPS
git clone https://github.com/atamanslark-create/mini.git
cd mini

# 2. Запустите установщик (требует root)
sudo bash install.sh

# 3. Отредактируйте конфиг
sudo nano /etc/mini-bot/config.yaml

# 4. Запустите сервис
sudo systemctl start mini-bot

# 5. Проверьте статус
sudo systemctl status mini-bot
```

## ⚙️ Конфигурация

Файл конфигурации находится в `/etc/mini-bot/config.yaml`:

```yaml
telegram_token: YOUR_BOT_TOKEN_HERE
admin_chat_ids: YOUR_CHAT_ID_HERE

# Пример:
telegram_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
admin_chat_ids: 12345678,87654321
```

### Получение токена Telegram бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Создайте нового бота: `/newbot`
3. Скопируйте токен

### Получение своего Chat ID

1. Откройте [@userinfobot](https://t.me/userinfobot) в Telegram
2. Бот покажет ваш ID

## 📱 Использование

После запуска бота откройте его в Telegram и нажмите `/start`:

```
📊 Статус VPS     - основные метрики (CPU, RAM, uptime)
💾 Диски         - состояние разделов диска
🔥 Топ процессов - 5 главных потребителей CPU
🧩 Сервисы       - статус основных сервисов
🩺 Диагностика   - полная диагностика системы
⚙️ Управление     - управление ботом (удаление)
```

## 🔄 Управление сервисом

```bash
# Запустить бота
sudo systemctl start mini-bot

# Остановить бота
sudo systemctl stop mini-bot

# Перезагрузить бота
sudo systemctl restart mini-bot

# Проверить статус
sudo systemctl status mini-bot

# Просмотр логов
sudo journalctl -u mini-bot -f

# Отключить автозапуск
sudo systemctl disable mini-bot
```

## 🗑️ Удаление

### Способ 1: Через меню бота
В боте нажмите `⚙️ Управление` → `🧨 Удалить бота с VPS`

### Способ 2: Вручную через SSH
```bash
sudo bash /path/to/uninstall.sh
```

## 📝 Структура проекта

```
mini/
├── bot.py              # Основной Telegram-бот с меню
├── agent.py            # Сбор метрик системы
├── config.py           # Конфигурация и загрузка параметров
├── utils.py            # Вспомогательные функции
├── requirements.txt    # Python-зависимости
├── install.sh          # Скрипт установки
├── uninstall.sh        # Скрипт удаления
└── README.md           # Документация
```

## 🛠️ Дополнительная конфигурация

### Добавление собственных сервисов для мониторинга

Отредактируйте список `services` в `bot.py`:

```python
self.services = ['ssh', 'nginx', 'mysql', 'postgresql', 'redis-server', 'your-service']
```

## 📋 Заметки

- Бот требует прав root для доступа к системным метрикам и journalctl
- Все команды защищены проверкой admin_chat_ids
- Логи бота доступны через `journalctl -u mini-bot`
- Конфиг может быть задан через переменные окружения: `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_IDS`

## 📄 Лицензия

MIT

## 👨‍💻 Разработчик

atamanslark-create
