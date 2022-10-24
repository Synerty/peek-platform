import json
import logging
import os
import sys

from peek_platform.subproc_plugin_init.plugin_subproc_parent_main import (
    PluginSubprocParentMain,
)
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


class PluginSubprocParentMainDelegate(PluginCommonEntryHookABC):
    def __init__(
        self,
        pluginName: str,
        pluginRootDir: str,
        platform: PeekPlatformCommonHookABC,
        subprocessGroupMain: PluginSubprocParentMain,
    ):
        super().__init__(pluginName, pluginRootDir)

        assert "-" not in pluginName, "Plugin name must not have hyphens"
        self._pluginName = pluginName
        self._platform = platform
        self._subprocessGroupMain = subprocessGroupMain

        from peek_platform import PeekPlatformConfig

        self._serviceName = PeekPlatformConfig.componentName

        self._pluginEndpoint = None

    @inlineCallbacks
    def load(self) -> None:

        yield self._subprocessGroupMain.sendPluginLoad(self._pluginName)
        logger.debug("Loaded Standalone Plugin %s", self._pluginName)

    @inlineCallbacks
    def start(self) -> None:
        from peek_platform import PeekPlatformConfig

        yield self._subprocessGroupMain.sendPluginStart(self._pluginName)

        self._pluginEndpoint = _NoKeycheckPayloadEndpoint(
            dict(plugin=self._pluginName),
            self._subprocessGroupMain.sendPayloadEnvelopeToChild,
            ignoreFromVortex=(peekServerName, PeekPlatformConfig.componentName),
        )

        logger.debug("Started Standalone Plugin %s", self._pluginName)

    @inlineCallbacks
    def stop(self) -> None:
        yield None

        if self._pluginEndpoint:
            yield self._pluginEndpoint.shutdown()
            self._pluginEndpoint = None

        # yield self._subprocessGroupMain.sendPluginStop(self._pluginName)
        # logger.debug("Stopped Standalone Plugin %s", self._pluginName)
        logger.debug(
            "Standalone Plugin %s doesn't support stopping", self._pluginName
        )

    @inlineCallbacks
    def unload(self) -> None:
        yield None
        # yield self._subprocessGroupMain.sendPluginUnload(self._pluginName)
        # logger.debug("Unloaded Standalone Plugin %s", self._pluginName)
        logger.debug(
            "Standalone Plugin %s doesn't support unloading", self._pluginName
        )
