import logging

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import connectionDone
from twisted.python import failure

from peek_platform.platform_init.init_platform import InitPlatform
from peek_plugin_base.PeekVortexUtil import peekServerName


logger = logging.getLogger("child_status_protocol")


class PluginSubprocChildStateProtocol(protocol.Protocol):
    COMMAND_LOAD = b"LOAD"
    COMMAND_START = b"START"
    COMMAND_STOP = b"STOP"
    COMMAND_UNLOAD = b"UNLOAD"
    COMMAND_SUCCESS = b"SUCCESS"

    def __init__(self, serviceName: str, pluginName: str):
        self._data = b""
        self._serviceName = serviceName
        self._pluginName = pluginName

    @inlineCallbacks
    def connectionMade(self):

        platformInitter = InitPlatform(
            self._serviceName, isPluginSubprocess=True
        )

        # Setup the platform
        platformInitter.setupPluginLoader()
        platformInitter.setupConfig()
        platformInitter.setupTwistedReactor()
        platformInitter.setupTempDirs()

        # Connect the vortex, only if we're not the logic service
        if self._serviceName != peekServerName:
            yield platformInitter.connectVortexClient()

    @inlineCallbacks
    def dataReceived(self, data: bytes):
        self._data += data

        while b"\n" in self._data:
            command, self._data = self._data.split(b"\n", 1)
            if not command:
                continue

            yield self._runCommand(command)

    @inlineCallbacks
    def _runCommand(self, command: str):
        from peek_platform import PeekPlatformConfig

        try:

            if command == self.COMMAND_LOAD:
                yield PeekPlatformConfig.pluginLoader.loadStandalonePlugin(
                    self._pluginName
                )
            elif command == self.COMMAND_START:
                yield PeekPlatformConfig.pluginLoader.startStandalonePlugin(
                    self._pluginName
                )
            elif command == self.COMMAND_STOP:
                yield PeekPlatformConfig.pluginLoader.stopStandalonePlugin(
                    self._pluginName
                )
            elif command == self.COMMAND_UNLOAD:
                yield PeekPlatformConfig.pluginLoader.unloadStandalonePlugin(
                    self._pluginName
                )
            else:
                raise NotImplementedError(f"Unhandled command '{command}'")

            # Send the success response
            self.transport.write(self.COMMAND_SUCCESS)
            self.transport.write(b"\n")

        except Exception as e:
            logger.exception(e)
            # Send the success response
            self.transport.write(
                (e.message if hasattr(e, "message") else str(e))
                .splitlines()[0]
                .encode()
            )
            self.transport.write(b"\n")
