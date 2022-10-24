import json
import logging
import os
import sys

from sqlalchemy.util import b64encode
from twisted.internet import reactor
from twisted.internet.defer import Deferred
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


logger = logging.getLogger(__name__)


class _NoKeycheckPayloadEndpoint(PayloadEndpoint):
    def _keyCheck(self, filt):
        pass


class PluginSubprocParentMain:
    def __init__(self, subprocessGroup: str):

        from peek_platform import PeekPlatformConfig

        self._serviceName = PeekPlatformConfig.componentName
        self._subprocessGroup = subprocessGroup

        self._processProtocol = PluginSubprocParentProtocol(
            self._subprocessGroup
        )

        platformConfigTupleEncoded = b64encode(
            json.dumps(
                PluginSubprocPlatformConfigTuple(
                    serviceName=self._serviceName,
                    subprocessGroup=self._subprocessGroup,
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
        logger.debug("Spawned subprocess group %s", self._subprocessGroup)

    def __call__(
        self,
        pluginName: str,
        pluginRootDir: str,
        platform: PeekPlatformCommonHookABC,
    ):
        """This method simulates the call to the plugins constructor.

        :param pluginName:
        :param pluginRootDir:
        :param platform:
        :return:  PluginSubprocParentMainDelegate
        """
        from peek_platform.subproc_plugin_init.plugin_subproc_parent_main_delegate import (
            PluginSubprocParentMainDelegate,
        )

        return PluginSubprocParentMainDelegate(
            pluginName, pluginRootDir, platform, self
        )

    @inlineCallbacks
    def sendPayloadEnvelopeToChild(
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

    def sendPluginLoad(self, pluginName: str) -> Deferred:
        return self._processProtocol.sendPluginLoad(pluginName)

    def sendPluginStart(self, pluginName: str) -> Deferred:
        return self._processProtocol.sendPluginStart(pluginName)

    def sendPluginStop(self, pluginName: str) -> Deferred:
        return self._processProtocol.sendPluginStop(pluginName)

    def sendPluginUnload(self, pluginName: str) -> Deferred:
        return self._processProtocol.sendPluginUnload(pluginName)
