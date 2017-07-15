import logging

from jsoncfg.value_mappers import require_string, require_dict

logger = logging.getLogger(__name__)


class PeekFileConfigWorkerMixin:
    @property
    def celeryBrokerUrl(self) -> str:
        # for BROKER_URL
        default = 'amqp://guest:guest@localhost:5672//'
        with self._cfg as c:
            return c.celery.brokerUrl(default, require_string)

    @property
    def celeryResultUrl(self) -> str:
        # for CELERY_RESULT_BACKEND
        default = 'redis://localhost:6379/0'
        with self._cfg as c:
            return c.celery.resultUrl(default, require_string)
