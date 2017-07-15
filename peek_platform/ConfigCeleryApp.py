import logging
import typing

from kombu import serialization
from peek_platform.file_config.PeekFileConfigWorkerMixin import PeekFileConfigWorkerMixin
from vortex.Payload import Payload

logger = logging.getLogger(__name__)


def vortexDumps(arg: typing.Tuple) -> str:
    try:
        return Payload(tuples=[arg])._toJson()
    except Exception as e:
        logger.exception(e)
        raise


def vortexLoads(jsonStr: str) -> typing.Tuple:
    try:
        return Payload()._fromJson(jsonStr).tuples[0]
    except Exception as e:
        logger.exception(e)
        raise


serialization.register(
    'vortex', vortexDumps, vortexLoads,
    content_type='application/x-vortex',
    content_encoding='utf-8',
)


def configureCeleryApp(app, workerConfig: PeekFileConfigWorkerMixin):
    # Optional configuration, see the application user guide.
    app.conf.update(
        BROKER_URL=workerConfig.celeryBrokerUrl,
        CELERY_RESULT_BACKEND=workerConfig.celeryResultUrl,

        # Leave the logging to us
        CELERYD_HIJACK_ROOT_LOGGER=False,

        CELERY_TASK_RESULT_EXPIRES=3600,
        # CELERY_TASK_SERIALIZER='vortex',
        # CELERY_ACCEPT_CONTENT=['vortex'],  # Ignore other content
        CELERY_ACCEPT_CONTENT=['pickle', 'json', 'msgpack', 'yaml', 'vortex'],
        # CELERY_RESULT_SERIALIZER='vortex',
        CELERY_ENABLE_UTC=True,
    )
