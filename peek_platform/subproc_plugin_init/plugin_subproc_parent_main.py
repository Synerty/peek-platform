import json
import logging
import os
import sys

from peek_plugin_base.PeekVortexUtil import peekBackendNames
from sqlalchemy.util import b64encode
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from vortex.DeferUtil import deferToThreadWrapWithLogger
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.Tuple import Tuple

from peek_platform.subproc_plugin_init.plugin_subproc import (
    plugin_subproc_child_main,
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
    VORTEX_MSG_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_UUID_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_UUID_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_parent_protocol import (
    PluginSubprocParentProtocol,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_platform_config_tuple import (
    PluginSubprocPlatformConfigTuple,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_vortex_payload_envelope_tuple import (
    PluginSubprocVortexPayloadEnvelopeTuple,
)
from peek_plugin_base.PeekPlatformCommonHookABC import PeekPlatformCommonHookABC
from peek_plugin_base.PeekVortexUtil import peekServerName
from peek_plugin_base.PluginCommonEntryHookABC import PluginCommonEntryHookABC


logger = logging.getLogger(__name__)


class _NoKeycheckPayloadEndpoint(PayloadEndpoint):
    def _keyCheck(self, filt):
        pass


class PluginSubprocParentMain(PluginCommonEntryHookABC):
    def __init__(
        self,
        pluginName: str,
        pluginRootDir: str,
        platform: PeekPlatformCommonHookABC,
    ):
        super().__init__(pluginName, pluginRootDir)

        assert "-" not in pluginName, "Plugin name must not have hyphens"
        self._pluginName = pluginName
        self._platform = platform

        from peek_platform import PeekPlatformConfig

        self._serviceName = PeekPlatformConfig.componentName

        self._pluginEndpoint = None
        self._processTransport = None
        self._processProtocol = None

    @inlineCallbacks
    def load(self) -> None:
        self._processProtocol = PluginSubprocParentProtocol(self._pluginName)

        platformConfigTupleEncoded = b64encode(
            json.dumps(
                PluginSubprocPlatformConfigTuple(
                    serviceName=self._serviceName, pluginName=self._pluginName
                ).toJsonDict()
            ).encode()
        )

        # Start the subprocess
        self._processTransport = reactor.spawnProcess(
            self._processProtocol,
            sys.executable,
            args=[
                sys.executable,
                plugin_subproc_child_main.__file__,
                platformConfigTupleEncoded,
            ],
            env=os.environ,
            path=os.path.dirname(plugin_subproc_child_main.__file__),
            childFDs={
                VORTEX_MSG_TO_CHILD_FD: "w",
                VORTEX_MSG_FROM_CHILD_FD: "r",
                LOGGING_FROM_CHILD_FD: "r",
                VORTEX_UUID_TO_CHILD_FD: "w",
                VORTEX_UUID_FROM_CHILD_FD: "r",
                PLUGIN_STATE_TO_CHILD_FD: "w",
                PLUGIN_STATE_FROM_CHILD_FD: "r",
            },
        )

        yield self._processProtocol.sendPluginLoad()
        logger.debug("Loaded Standalone Plugin %s", self._pluginName)

    @inlineCallbacks
    def start(self) -> None:
        from peek_platform import PeekPlatformConfig

        yield self._processProtocol.sendPluginStart()

        self._pluginEndpoint = _NoKeycheckPayloadEndpoint(
            dict(plugin=self._pluginName),
            self._sendPayloadEnvelopeToChild,
            ignoreFromVortex=(peekServerName, PeekPlatformConfig.componentName),
        )

        logger.debug("Started Standalone Plugin %s", self._pluginName)

    @inlineCallbacks
    def stop(self) -> None:
        yield None
        # yield self._processProtocol.sendPluginStop()
        # logger.debug("Stopped Standalone Plugin %s", self._pluginName)
        logger.debug(
            "Standalone Plugin %s doesn't support stopping", self._pluginName
        )

    @inlineCallbacks
    def unload(self) -> None:
        yield None
        # yield self._processProtocol.sendPluginUnload()
        # logger.debug("Unloaded Standalone Plugin %s", self._pluginName)
        logger.debug(
            "Standalone Plugin %s doesn't support unloading", self._pluginName
        )

    @inlineCallbacks
    def _sendPayloadEnvelopeToChild(
        self,
        payloadEnvelope: PayloadEnvelope,
        vortexUuid: str,
        vortexName: str,
        **kwargs
    ):
        tuple_ = PluginSubprocVortexPayloadEnvelopeTuple(
            payloadEnvelope=payloadEnvelope,
            vortexUuid=vortexUuid,
            vortexName=vortexName,
        )
        encodedTuple = yield self._encodeTuple(tuple_)
        self._processTransport.write(encodedTuple)
        self._processTransport.write(b".")

    @deferToThreadWrapWithLogger(logger)
    def _encodeTuple(self, tuple_: Tuple) -> bytes:
        return b64encode(json.dumps(tuple_.toJsonDict()).encode()).encode()
