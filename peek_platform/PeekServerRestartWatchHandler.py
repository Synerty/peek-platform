'''
Created on 09/07/2014

@author: synerty
'''
import logging

from peek_platform import PeekPlatformConfig
from vortex.Payload import Payload
from vortex.PayloadEndpoint import PayloadEndpoint
from vortex.VortexFactory import VortexFactory

__author__ = 'peek'

logger = logging.getLogger(__name__)

# The filter we listen on
agentEchoFilt = {
    'plugin': 'peek_platform',
    'key': "peek_platform.echo"
}  # LISTEN / SEND


class PeekServerRestartWatchHandler(object):
    def __init__(self):
        self._ep = PayloadEndpoint(agentEchoFilt, self._process)
        self._lastPeekServerVortexUuid = None

        # When the vortex reconnects, this will make the server echo back to us.
        vortexClients = VortexFactory.getLocalVortexClients(
            localVortexName=PeekPlatformConfig.componentName)

        for vortexClient in vortexClients:
            vortexClient.addReconnectPayload(Payload(filt=agentEchoFilt))

    def _process(self, payload, vortexUuid, **kwargs):
        if self._lastPeekServerVortexUuid is None:
            self._lastPeekServerVortexUuid = vortexUuid
            return

        if self._lastPeekServerVortexUuid == vortexUuid:
            return

        logger.info("Peek Server restart detected, restarting...")
        from peek_platform import PeekPlatformConfig
        PeekPlatformConfig.peekSwInstallManager.restartProcess()


__peekServerRestartWatchHandler = PeekServerRestartWatchHandler()
