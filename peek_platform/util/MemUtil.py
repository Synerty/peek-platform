import os
import tracemalloc
from datetime import datetime
from tracemalloc import _format_size
from typing import Optional

from twisted.internet import reactor


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


def setupMemoryDebugging(serviceName: Optional[str] = None):
    import os
    import pytz

    tracemalloc.start()
    from vortex.Jsonable import Jsonable
    import psutil
    Jsonable.setupMemoryLogging()

    def dump():
        snapshot = tracemalloc.take_snapshot()
        topStats = snapshot.statistics('lineno')

        jsonableDump = Jsonable.memoryLoggingDump(top=20, over=500)

        homeDir = os.path.expanduser('~/memdump-%s.log' % serviceName)
        with open(homeDir, 'a') as f:
            f.write("-" * 80 + '\n')
            f.write("START - " + str(datetime.now(pytz.utc)) + '\n')

            f.write("-" * 80 + '\n')
            process = psutil.Process(os.getpid())
            f.write("Total python processes memory usage: "
                    + rpad(_format_size(process.memory_info().rss, False), 10)
                    + '\n')

            f.write("-" * 80 + '\n')
            for stat in topStats[:50]:
                f.write(_formatStatistic(stat) + '\n')

            f.write("-" * 80 + '\n')
            if jsonableDump:
                for objectType, count in jsonableDump:
                    f.write(' ' + rpad(str(count), 10) + ' ' + objectType + '\n')

            else:
                f.write('There are no large Jsonable objects\n')

            f.write("-" * 80 + '\n')
            f.write("END - " + str(datetime.now(pytz.utc)) + '\n')
            f.write("-" * 80 + '\n')

        reactor.callLater(60, dump)

    dump()
