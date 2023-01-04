import json
import logging
import os
from base64 import b64decode
from base64 import b64encode

from twisted.internet import protocol
from twisted.internet import task
from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks
from vortex.DeferUtil import deferToThreadWrapWithLogger
from vortex.VortexFactory import VortexFactory

from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_state_protocol import (
    PluginSubprocChildStateProtocol,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    LOGGING_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    PLUGIN_STATE_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    PLUGIN_STATE_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_MSG_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_UUID_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_vortex_msg_tuple import (
    PluginSubprocVortexMsgTuple,
)


logger = logging.getLogger(__name__)


class PluginSubprocParentProtocol(protocol.ProcessProtocol):
    VORTEX_UUID_UPDATE_PERIOD = 30

    def __init__(self, subprocessGroupName):
        self._dataBytesArray = bytearray()
        self._logData = b""
        self._pluginStateData = b""

        self._vortexUpdateLoopingCall = task.LoopingCall(
            self._sendUpdatedVortexUuids
        )

        self._lastPluginStateCommandDeferred = None

        self._loggerForChild = logging.getLogger(
            f"subproc:{subprocessGroupName}"
        )

    @inlineCallbacks
    def childDataReceived(self, childFD: int, data: bytes):
        if childFD == VORTEX_MSG_FROM_CHILD_FD:
            yield self.outReceived(data)
        elif childFD == LOGGING_FROM_CHILD_FD:
            yield self.errReceived(data)
        # elif childFD == VORTEX_UUID_FROM_CHILD_FD:
        #     not used
        elif childFD == PLUGIN_STATE_FROM_CHILD_FD:
            yield self._pluginStateDataReceived(data)
        else:
            raise NotImplementedError(
                f"We didn't expect to get data from {childFD}"
            )

    def connectionMade(self):
        self._vortexUpdateLoopingCall.start(self.VORTEX_UUID_UPDATE_PERIOD)

    def inConnectionLost(self):
        """
        This will be called when stdin is closed.
        """
        if self._vortexUpdateLoopingCall:
            self._vortexUpdateLoopingCall.stop()
            self._vortexUpdateLoopingCall = None

    # ---------------------------------
    # Handle sending vortex uuid updates to subprocess

    @inlineCallbacks
    def _sendUpdatedVortexUuids(self):
        encodedUuids = yield self._encodeVortexUuids()
        self.transport.writeToChild(VORTEX_UUID_TO_CHILD_FD, encodedUuids)
        self.transport.writeToChild(VORTEX_UUID_TO_CHILD_FD, b".")

    @deferToThreadWrapWithLogger(logger)
    def _encodeVortexUuids(self):
        remoteInfoTuples = [
            [info.name, info.uuid]
            for info in VortexFactory.getRemoteClientVortexInfos()
        ]
        encodedUuids = b64encode(json.dumps(remoteInfoTuples).encode())
        return encodedUuids

    # ---------------------------------
    # Handle sending vortex messages from clients

    def errReceived(self, data: bytes):
        self._logData += data

        while b"\n" in self._logData:
            message, self._logData = self._logData.split(b"\n", 1)
            if not message:
                continue

            message = message.decode()

            if ":" not in message:
                self._loggerForChild.error(message)

            else:
                severity, logMsg = message.split(":", 1)
                if severity == "DEBUG":
                    self._loggerForChild.debug(logMsg)
                elif severity == "INFO":
                    self._loggerForChild.info(logMsg)
                elif severity == "WARNING":
                    self._loggerForChild.warning(logMsg)
                elif severity == "ERROR":
                    self._loggerForChild.error(logMsg)
                else:
                    self._loggerForChild.error(message)

    @inlineCallbacks
    def outReceived(self, data):
        self._dataBytesArray.append(data)

        if b"." not in data:
            return

        # Avoid accidentally referencing this
        del data

        joinedData = bytes(self._dataBytesArray)

        while b"." in joinedData:
            message, joinedData = joinedData.split(b".", 1)
            if not message:
                continue

            yield self._sendVortexMsgFromChild(message)

        self._dataArray = bytearray(joinedData)

    @inlineCallbacks
    def _sendVortexMsgFromChild(self, message: bytes):
        vortexMsgTuple = yield self._decodeVortexMsgTuple(message)

        yield VortexFactory.sendVortexMsg(
            vortexMsgs=vortexMsgTuple.vortexMsgs,
            destVortexUuid=vortexMsgTuple.vortexUuid,
        )

    @deferToThreadWrapWithLogger(logger)
    def _decodeVortexMsgTuple(self, message: bytes):
        return PluginSubprocVortexMsgTuple().fromJsonDict(
            json.loads(b64decode(message).decode())
        )

    # ---------------------------------
    # Handle the plugin state changes

    def sendPluginLoad(self, pluginName: str) -> Deferred:
        return self._sendPluginStateCommand(
            pluginName, PluginSubprocChildStateProtocol.COMMAND_LOAD
        )

    def sendPluginStart(self, pluginName: str) -> Deferred:
        return self._sendPluginStateCommand(
            pluginName, PluginSubprocChildStateProtocol.COMMAND_START
        )

    def sendPluginStop(self, pluginName: str) -> Deferred:
        return self._sendPluginStateCommand(
            pluginName, PluginSubprocChildStateProtocol.COMMAND_STOP
        )

    def sendPluginUnload(self, pluginName: str) -> Deferred:
        return self._sendPluginStateCommand(
            pluginName, PluginSubprocChildStateProtocol.COMMAND_UNLOAD
        )

    @inlineCallbacks
    def _sendPluginStateCommand(self, pluginName: str, command: bytes):
        assert not self._lastPluginStateCommandDeferred, (
            "There is already a pending " "command"
        )
        self._lastPluginStateCommandDeferred = Deferred()

        self.transport.writeToChild(
            PLUGIN_STATE_TO_CHILD_FD, f"{pluginName}:{command}".encode()
        )
        self.transport.writeToChild(PLUGIN_STATE_TO_CHILD_FD, b"\n")

        yield self._lastPluginStateCommandDeferred
        self._lastPluginStateCommandDeferred = None

    def _pluginStateDataReceived(self, data):
        self._pluginStateData += data

        while b"\n" in self._pluginStateData:
            message, self._pluginStateData = self._pluginStateData.split(
                b"\n", 1
            )
            if not message:
                continue

            if not self._lastPluginStateCommandDeferred:
                error = (
                    f"We got a result when we have no deferred to "
                    f"call, result={message}"
                )
                logger.error(error)
                raise Exception(error)

            pluginName, result = message.decode().split(":", 1)

            if result == PluginSubprocChildStateProtocol.COMMAND_SUCCESS:
                self._lastPluginStateCommandDeferred.callback(result)

            else:
                self._lastPluginStateCommandDeferred.errback(result)

            self._lastPluginStateCommandDeferred = None
