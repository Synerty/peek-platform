import logging
import tracemalloc
from datetime import datetime
from tracemalloc import _format_size
from typing import Optional

from twisted.internet import reactor

logger = logging.getLogger(__name__)


def rpad(val, count):
    val = str(val)
    while len(val) < count:
        val += ' '
    return val


def lpad(val, count):
    val = str(val)
    while len(val) < count:
        val = ' ' + val
    return val


def _formatStatistic(stat: tracemalloc.Statistic):
    average = stat.size / stat.count

    sitePkgs = 'site-packages'
    tracePath = str(stat.traceback)
    if sitePkgs in tracePath:
        tracePath = tracePath[tracePath.index(sitePkgs) + len(sitePkgs) + 1:]

    text = " "
    text += "   size:%s" % lpad(_format_size(stat.size, False), 10)
    text += "   count:%s" % lpad(stat.count, 10)
    text += "   average:%s" % lpad(_format_size(average, False), 10)
    text += "   " + tracePath

    return text


def setupMemoryDebugging(serviceName: Optional[str] = None,
                         level: int = 0):
    import os
    import pytz
    import psutil

    # Start tracemalloc logging
    if level >= 3:
        tracemalloc.start(6)

    # Start JSonable logging
    from vortex.Jsonable import Jsonable
    if level >= 2:
        Jsonable.setupMemoryLogging()

    from vortex.handler.TupleDataObservableCache import _CachedSubscribedData
    if level >= 1:
        # Start cached encoded payload logging
        _CachedSubscribedData.setupMemoryLogging()

    TOP = 10

    logger.error("Memory Logging is enabled, this will significantly"
                 " tie up the Twisted Reactors main thread."
                 " You should expect to see severely degraded performance.")

    def dump():

        if level >= 3:
            snapshot = tracemalloc.take_snapshot()

            # Get the objects by their line of malloc
            # topLineStats = snapshot.statistics('lineno')
            topLineStats = snapshot.statistics('traceback')
            # Filter out lines less than 1mb
            topLineStats = list(filter(lambda s: s.size > 1 * 1024 * 1024, topLineStats))
            topLineStats = topLineStats[:TOP]

        if level >= 2:
            jsonableDump = Jsonable.memoryLoggingDump(top=TOP, over=10 * 1024)

        if level >= 1:
            vortexCacheDump = _CachedSubscribedData.memoryLoggingDump(top=TOP, over=10 * 1024)

        homeDir = os.path.expanduser('~/memdump-%s.log' % serviceName)
        with open(homeDir, 'a') as f:
            # Write the start datetime
            f.write("=" * 80 + '\n')
            f.write("START - " + str(datetime.now(pytz.utc)) + '\n')

            # Write the total process memory
            f.write("-" * 80 + '\n')
            process = psutil.Process(os.getpid())
            f.write("Total python processes memory usage: "
                    + rpad(_format_size(process.memory_info().rss, False), 10)
                    + '\n')

            if level >= 3:
                # Write the dump of the tracemalloc line allocatons
                f.write("-" * 80 + '\n')
                if topLineStats:
                    f.write("Python Tracemalloc Information\n")
                    for stat in topLineStats:
                        f.write(_formatStatistic(stat) + '\n')
                        for line in stat.traceback.format():
                            f.write((' ' * 8) + line + '\n')
                        f.write('\n')

                else:
                    f.write('There are no large tracemalloc objects\n')

            if level >= 2:
                # Write the dump of the Jsonable objects
                f.write("-" * 80 + '\n')
                if jsonableDump:
                    f.write("Vortex Jsonable Objects\n")
                    f.write(' ' + rpad("COUNT", 10) + ' ' + "OBJECT TYPE" + '\n')
                    for objectType, count in jsonableDump:
                        f.write(' ' + rpad(str(count), 10) + ' ' + objectType + '\n')

                else:
                    f.write('There are no large Vortex Jsonable Objects\n')

            if level >= 1:
                # Write the dump of the cached vortex payloads
                f.write("-" * 80 + '\n')
                if vortexCacheDump:
                    f.write("Vortex Observable Caches\n")
                    f.write(' ' + rpad("COUNT", 10)
                            + ' ' + rpad("TOTAL", 10)
                            + ' ' + "OBJECT TYPE" + '\n')

                    for objectType, count, total in vortexCacheDump:
                        f.write(' ' + rpad(str(count), 10)
                                + ' ' + rpad(str(total), 10)
                                + ' ' + objectType + '\n')

                else:
                    f.write('There are no large Vortex Observable Caches\n')

            # Write the enddate
            f.write("-" * 80 + '\n')
            f.write("END - " + str(datetime.now(pytz.utc)) + '\n')
            f.write("-" * 80 + '\n')

        reactor.callLater(60, dump)

    dump()
