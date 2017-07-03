def configureCeleryApp(app):
    # Optional configuration, see the application user guide.
    app.conf.update(
        BROKER_URL='amqp://',
        CELERY_RESULT_BACKEND='redis://localhost',

        # Leave the logging to us
        CELERYD_HIJACK_ROOT_LOGGER=False,

        CELERY_TASK_RESULT_EXPIRES=3600,
        CELERY_TASK_SERIALIZER='json',
        CELERY_ACCEPT_CONTENT=['json'],  # Ignore other content
        CELERY_RESULT_SERIALIZER='json',
        CELERY_ENABLE_UTC=True
    )
