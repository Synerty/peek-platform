import gzip
import logging
import os
import sys
import zlib
from logging.handlers import RotatingFileHandler, SysLogHandler
from logging.handlers import TimedRotatingFileHandler

from pathlib import Path
from typing import Optional

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"
DATE_FORMAT = "%d-%b-%Y %H:%M:%S"

logger = logging.getLogger(__name__)


def setupPeekLogger(serviceName: Optional[str] = None):
    logging.basicConfig(
        stream=sys.stdout,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        level=logging.DEBUG,
    )

    if serviceName:
        updatePeekLoggerHandlers(serviceName)


def _namer(name):
    return name + ".gz"


def _rotator(source, dest):
    READ_CHUNK = 512 * 1024
    with open(source, "rb") as sf:
        with gzip.open(dest, "wb") as f:
            data = sf.read(READ_CHUNK)
            while data:
                f.write(data)
                data = sf.read(READ_CHUNK)
    os.remove(source)


def updatePeekLoggerHandlers(
    serviceName: Optional[str] = None,
    daysToKeep=28,
    logToStdout=True,
):
    rootLogger = logging.getLogger()
    logFormatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    for handler in list(rootLogger.handlers):
        if isinstance(handler, TimedRotatingFileHandler):
            # Setup the file logging output
            rootLogger.removeHandler(handler)

        elif not sys.stdout.isatty() and not logToStdout:
            # Remove the stdout handler
            logger.info(
                "Logging to stdout disabled, see 'logToStdout' in config.json"
            )
            rootLogger.removeHandler(handler)

    fileName = str(Path.home() / ("%s.log" % serviceName))

    fh = TimedRotatingFileHandler(fileName, when="midnight", backupCount=daysToKeep)
    fh.setFormatter(logFormatter)
    fh.rotator = _rotator
    fh.namer = _namer
    rootLogger.addHandler(fh)


def setupLoggingToSyslogServer(host: str, port: int, facility: str):
    rootLogger = logging.getLogger()
    logFormatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    logging.getLogger().addHandler(logging.StreamHandler())

    if facility not in SysLogHandler.facility_names:
        logger.info(list(SysLogHandler.facility_names))
        raise Exception("Syslog facility name is a valid facility")

    facilityNum = SysLogHandler.facility_names[facility]

    fh = SysLogHandler(address=(host, port), facility=facilityNum)
    fh.setFormatter(logFormatter)
    rootLogger.addHandler(fh)
