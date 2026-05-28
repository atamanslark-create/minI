# GLaDoS Integration Guide

Это руководство объясняет, как настроить двусторонню коммуникацию между mini-bot и GLaDoS главным ботом.

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│  GLaDoS (Главный управляющий бот)                   │
│  - Управляет множеством подчинённых ботов           │
│  - Получает отчёты каждый час от каждого VPS      │
│  - Отправляет команды на выполнение                 │
└─────────────────────────────────────────────────────┘
              ↕ (Двусторонняя коммуникация)
┌─────────────────────────────────────────────────────┐
│  mini-bot (VPS мониторинг)                          │
│  - Запускается на каждом VPS                       │
│  - Отправляет отчёты в GLaDoS каждый час          │
│  - Получает команды от GLaDoS                       │
│  - Выполняет действия и отправляет результаты      │
└─────────────────────────────────────────────────────┘
```

## Настройка

### 1. Уже имеющиеся боты

Для mini-bot нужны следующие данные от GLaDoS:
- **GLADOS_BOT_TOKEN** - токен GLaDoS бота (получить от @BotFather)
- **GLADOS_OWNER_ID** - ID владельца GLaDoS (получить от @userinfobot)

### 2. Конфигурация mini-bot

Добавьте настройки GLaDoS в файл конфигурации:

**Способ 1: Через config.yaml**
```yaml
telegram_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
admin_chat_ids: 12345678,87654321

# GLaDoS интеграция
glados_token: 9876543:ZYX-CBA9876fedcba543w2v1u098ZYX
glados_owner_id: 7774398077
```

**Способ 2: Через переменные окружения**
```bash
export GLADOS_BOT_TOKEN="9876543:ZYX-CBA9876fedcba543w2v1u098ZYX"
export GLADOS_OWNER_ID="7774398077"
```

### 3. Добавление mini-bot в GLaDoS

После настройки mini-bot его нужно зарегистрировать в GLaDoS:

1. Откройте чат с GLaDoS ботом
2. Нажмите **🤖 Боты** → **➕ Добавить бота**
3. Введите имя бота (например, "mini-bot-vps1")
4. Введите токен mini-bot
5. (Опционально) Добавьте заметку

## Функциональность

### Отправка отчётов из mini-bot в GLaDoS

mini-bot **автоматически** отправляет полный отчёт о статусе VPS в GLaDoS каждый час:

```
📊 mini-bot: Hourly Status Report

📊 Статус системы

CPU: 45% (4 cores)
RAM: 62% (2.04 GB / 3.29 GB)
Uptime: 5 days, 3:45:21

Диски:
  /dev/sda1: 73%
  /dev/sdb1: 45%

Сервисы:
  ✅ nginx: active
  ✅ mysql: active
  ❌ redis: inactive

Детали:
• Hostname: my-vps-01
• Kernel: 6.1.0-21-generic
```

### Получение команд из GLaDoS

mini-bot может получать команды от GLaDoS и выполнять их. Команды отправляются в формате:
```
command:arg1:arg2
```

Пример команд:
- `status` - получить текущий статус VPS
- `service:restart:nginx` - перезагрузить сервис
- `speedtest` - запустить тест скорости
- `report:now` - отправить отчёт прямо сейчас

## Преимущества интеграции

1. **Централизованный мониторинг** - видеть статус всех VPS в одном месте
2. **Автоматические отчёты** - каждый час получать полную статистику
3. **Удалённое управление** - отправлять команды из GLaDoS напрямую на VPS
4. **История и логирование** - вся коммуникация сохраняется в GLaDoS

## Структура модуля GLaDosClient

```python
class GLaDosClient:
    def __init__(self, glados_token, glados_chat_id, bot_name="mini-bot")
    
    # Отправить отчёт в GLaDoS
    async def send_report(title, content, details=None)
    
    # Отправить результат выполнения команды
    async def send_command_result(command, success, message)
    
    # Обработать входящую команду
    async def handle_message(message_text)
    
    # Зарегистрировать обработчик команды
    def register_command(command, handler)
```

## Примеры кода

### Отправка кастомного отчёта

```python
await glados_client.send_report(
    title="Custom Alert",
    content="Обнаружена проблема с диском",
    details={
        "Partition": "/dev/sda1",
        "Usage": "95%",
        "Available": "500MB"
    }
)
```

### Регистрация обработчика команды

```python
async def handle_restart_nginx(args):
    result = SystemAgent.manage_service("nginx", "restart")
    return f"nginx restarted: {result['message']}"

glados_client.register_command("nginx:restart", handle_restart_nginx)
```

## Возможные проблемы и решения

### Отчёты не отправляются

1. Проверьте переменные окружения:
   ```bash
   echo $GLADOS_BOT_TOKEN
   echo $GLADOS_OWNER_ID
   ```

2. Убедитесь, что токены верные:
   - mini-bot запустил /start в чате с GLaDoS
   - GLaDoS знает ID владельца

3. Проверьте логи:
   ```bash
   systemctl status mini-bot
   journalctl -u mini-bot -n 50
   ```

### Команды не работают

1. Убедитесь, что обработчик команды зарегистрирован
2. Проверьте формат команды (должна содержать `:`)
3. Посмотрите в логи GLaDoS для деталей ошибки

## Отключение GLaDoS интеграции

Чтобы отключить интеграцию с GLaDoS:

1. Удалите из config.yaml строки `glados_token` и `glados_owner_id`
2. ИЛИ не устанавливайте переменные окружения
3. mini-bot продолжит работать без GLaDoS, но отчёты не будут отправляться

## Безопасность

- Токены хранятся в защищённой конфигурации
- Используется HTTPS для всей коммуникации с Telegram API
- Только зарегистрированные владельцы могут управлять ботом
