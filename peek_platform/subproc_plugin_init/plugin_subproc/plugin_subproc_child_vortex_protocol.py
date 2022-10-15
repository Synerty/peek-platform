import json
import logging
from base64 import b64decode
from base64 import b64encode
from typing import Union

from twisted.internet import protocol
from twisted.internet.defer import inlineCallbacks
from vortex.DeferUtil import deferToThreadWrapWithLogger
from vortex.PayloadEnvelope import VortexMsgList
from vortex.PayloadIO import PayloadIO
from vortex.PayloadPriority import DEFAULT_PRIORITY

from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_vortex import (
    PluginSubprocChildVortex,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_vortex_msg_tuple import (
    PluginSubprocVortexMsgTuple,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_vortex_payload_envelope_tuple import (
    PluginSubprocVortexPayloadEnvelopeTuple,
)


logger = logging.getLogger("child_vortex_protocol")


class PluginSubprocChildVortexProtocol(protocol.Protocol):
    def __init__(self, vortex: PluginSubprocChildVortex):
        self._data = b""
        self._vortex = vortex

    @inlineCallbacks
    def dataReceived(self, data: bytes):
        self._data += data

        while b"." in self._data:
            message, self._data = self._data.split(b".", 1)
            if not message:
                continue

            vortexPayloadTuple = yield self._decodeVortexPayloadTuple(message)

            # assign these locally so they are not used in the closure.
            payloadEnvelope = vortexPayloadTuple.payloadEnvelope
            vortexUuid = vortexPayloadTuple.vortexUuid
            vortexName = vortexPayloadTuple.vortexName
            del vortexPayloadTuple

            self._vortex.ensureRemoteVortexIsRegistered(
                vortexUuid=vortexUuid, vortexName=vortexName
            )

            def sendResponse(
                vortexMsgs: Union[VortexMsgList, bytes],
                priority: int = DEFAULT_PRIORITY,
            ):
                return self.sendVortexMsg(
                    vortexMsgs=vortexMsgs,
                    vortexUuid=vortexUuid,
                    priority=priority,
                )

            PayloadIO().process(
                payloadEnvelope=payloadEnvelope,
                vortexUuid=vortexUuid,
                vortexName=vortexName,
                httpSession=None,
                sendResponse=sendResponse,
            )

    @inlineCallbacks
    def sendVortexMsg(
        self,
        vortexMsgs: Union[VortexMsgList, bytes],
        vortexUuid: str,
        priority: int = DEFAULT_PRIORITY,
    ):

        tuple_ = PluginSubprocVortexMsgTuple(
            vortexUuid=vortexUuid, vortexMsgs=vortexMsgs, priority=priority
        )
        vortexMsgTuple = yield self._encodeVortexMsgTuple(tuple_)
        self.transport.write(vortexMsgTuple)
        self.transport.write(b".")

    @deferToThreadWrapWithLogger(logger)
    def _decodeVortexPayloadTuple(self, message):
        vortexPayloadTuple = (
            PluginSubprocVortexPayloadEnvelopeTuple().fromJsonDict(
                json.loads(b64decode(message))
            )
        )
        return vortexPayloadTuple

    @deferToThreadWrapWithLogger(logger)
    def _encodeVortexMsgTuple(self, tuple_):
        return b64encode(json.dumps(tuple_.toJsonDict()).encode())
