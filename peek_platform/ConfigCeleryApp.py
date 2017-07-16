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

        # The time results will stay in redis before expiring.
        # I believe they are cleared when the results are obtained
        # from txcelery._DeferredTask
        CELERY_TASK_RESULT_EXPIRES=3600,

        # The number of tasks each worker will prefetch.
        # CELERYD_PREFETCH_MULTIPLIER=2,

        # The number of workers to have at one time
        # CELERYD_CONCURRENCY=2,

        # The maximum number or results to keep for the client
        # We could have backlog of 1000 results waiting for the client to pick up
        # This would be a mega performance issue.
        CELERY_MAX_CACHED_RESULTS=1000, # Default is 100

        CELERY_TASK_SERIALIZER='vortex',
        # CELERY_ACCEPT_CONTENT=['vortex'],  # Ignore other content
        CELERY_ACCEPT_CONTENT=['pickle', 'json', 'msgpack', 'yaml', 'vortex'],
        CELERY_RESULT_SERIALIZER='vortex',
        CELERY_ENABLE_UTC=True,
    )
