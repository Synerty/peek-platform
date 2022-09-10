import json
import logging
from base64 import b64decode

from twisted.internet import protocol
from twisted.internet.defer import inlineCallbacks
from vortex.DeferUtil import deferToThreadWrapWithLogger
from vortex.VortexABC import VortexInfo

from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_vortex import (
    PluginSubprocChildVortex,
)


logger = logging.getLogger("child_vortex_uuid_protocol")


class PluginSubprocChildVortexUuidProtocol(protocol.Protocol):
    def __init__(self, vortex: PluginSubprocChildVortex):
        self._data = b""
        self._vortex = vortex

    @inlineCallbacks
    def dataReceived(self, data: bytes):
        self._data += data
        if not self._vortex:
            return

        while b"." in self._data:
            message, self._data = self._data.split(b".", 1)
            if not message:
                continue

            # Tell the child fake vortex about the remote UUIDs in our parent
            # process
            vortexInfoLists = yield self._decodeMessage(message)
            self._vortex.updateRemoteVortexUuids(
                [VortexInfo(name=o[0], uuid=o[1]) for o in vortexInfoLists]
            )

    @deferToThreadWrapWithLogger(logger)
    def _decodeMessage(self, message):
        return json.loads(b64decode(message))
