import logging.config
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


def configure_logging(log_level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "correlation_id": {"()": CorrelationIdFilter},
            },
            "formatters": {
                "console": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s [%(correlation_id)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "filters": ["correlation_id"],
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["console"],
            },
        }
    )
