import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATHS = [
    Path("/etc/mini-bot/config.yaml"),
    Path(Path.home() / ".config/mini-bot/config.yaml"),
    Path("./config.yaml"),
]

def load_config():
    """Load configuration from YAML file or environment variables."""
    config_path = None
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            config_path = path
            break

    config = {}

    # Load from YAML if found
    if config_path:
        with open(config_path, 'r') as f:
            loaded = yaml.safe_load(f)
            config = loaded if isinstance(loaded, dict) else {}

    # Override with environment variables
    config['telegram_token'] = os.getenv('TELEGRAM_BOT_TOKEN', config.get('telegram_token'))
    admin_ids = os.getenv('ADMIN_CHAT_IDS', config.get('admin_chat_ids', ''))

    if isinstance(admin_ids, str):
        config['admin_chat_ids'] = [int(id.strip()) for id in admin_ids.split(',') if id.strip()]
    else:
        config['admin_chat_ids'] = admin_ids

    # GLaDoS integration (optional)
    config['glados_token'] = os.getenv('GLADOS_BOT_TOKEN', config.get('glados_token'))
    config['glados_owner_id'] = os.getenv('GLADOS_OWNER_ID', config.get('glados_owner_id'))
    if config['glados_owner_id'] and isinstance(config['glados_owner_id'], str):
        config['glados_owner_id'] = int(config['glados_owner_id'])

    if not config.get('telegram_token'):
        raise ValueError("TELEGRAM_BOT_TOKEN not found in config or environment variables")

    if not config.get('admin_chat_ids'):
        raise ValueError("ADMIN_CHAT_IDS not found in config or environment variables")

    return config

CONFIG = load_config()
