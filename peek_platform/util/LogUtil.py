import logging
from logging.handlers import RotatingFileHandler

from pathlib import Path

from txhttputil.util.LoggingUtil import LOG_FORMAT, DATE_FORMAT


def setupServiceLogOutput(serviceName):
    fileName = str(Path.home() / ('%s.log' % serviceName))

    logFormatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    rootLogger = logging.getLogger()

    fh = RotatingFileHandler(fileName, maxBytes=(1024*1024*20), backupCount=2)
    fh.setFormatter(logFormatter)
    rootLogger.addHandler(fh)
