import logging 
import os
import re
from logging.config import dictConfig
from pathlib import Path
from typing import Optional

from infrastructure.config import get_config, BotConfig


class LoggerManager:
    _config: BotConfig = get_config()
    _instance: Optional['LoggerManager'] = None
    LOGGER_NAMES = ("discord_bot", "infrastructure", "application", "presentation")
    ACTIVITY_LOGGER_NAMES = ("activity",)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configure()
        return cls._instance
    
    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)
    
    def _configure(self) -> None:
        log_level = self._config.log_level
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        service_name = re.sub(
            r"[^a-zA-Z0-9_.-]+",
            "_",
            os.getenv("MUXIVO_DISCORD_SERVICE_NAME", "discord_bot"),
        ).strip("._") or "discord_bot"
        log_file = log_dir / f"{service_name}.log"
        activity_log_file = log_dir / f"{service_name}_activity.log"

        handlers = {}
        active_handlers = []

        handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": "default",
            "stream": "ext://sys.stdout",
        }
        active_handlers.append("console")

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "default",
            "filename": str(log_file),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "encoding": "utf-8",
        }
        active_handlers.append("file")

        handlers["activity_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "default",
            "filename": str(activity_log_file),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }

        dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": log_format,
                    "datefmt": date_format,
                }
            },
            "handlers": handlers,
            "loggers": {
                **{
                    logger_name: {
                        "level": log_level,
                        "handlers": active_handlers,
                        "propagate": False,
                    }
                    for logger_name in self.LOGGER_NAMES
                },
                **{
                    logger_name: {
                        "level": log_level,
                        "handlers": ["console", "activity_file"],
                        "propagate": False,
                    }
                    for logger_name in self.ACTIVITY_LOGGER_NAMES
                },
            },
            "root": {
                "level": log_level,
                "handlers": active_handlers,
            }
        })

def get_logger(name: str) -> logging.Logger:
    return LoggerManager().get_logger(name)
