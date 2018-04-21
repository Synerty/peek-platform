import logging

from pathlib import Path

from txhttputil.util.LoggingUtil import LOG_FORMAT, DATE_FORMAT


def setupServiceLogOutput(serviceName):
    fileName = str(Path.home() / '%s.log' % serviceName)

    logFormatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    rootLogger = logging.getLogger()

    fileHandler = logging.FileHandler(fileName)
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)