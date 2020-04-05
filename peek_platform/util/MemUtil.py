import os
from datetime import datetime
from typing import Optional

import objgraph
import pytz
from twisted.internet import reactor


def setupMemoryDebugging(serviceName: Optional[str] = None):
    def dump():
        homeDir = os.path.expanduser('~/memdump-%s.log' % serviceName)
        with open(homeDir, 'a') as f:
            f.write("-" * 80 + '\n')
            f.write(str(datetime.now(pytz.utc)) + '\n')
            f.write("-" * 80 + '\n')
            objgraph.show_most_common_types(limit=30, file=f)
            f.write("-" * 80 + '\n')
            objgraph.show_growth(file=f)

        reactor.callLater(10, dump)

    dump()
