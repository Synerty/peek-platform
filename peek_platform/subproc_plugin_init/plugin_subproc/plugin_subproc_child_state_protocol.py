import logging

from twisted.internet import protocol
from twisted.internet.defer import inlineCallbacks

from peek_platform.platform_init.init_platform import InitPlatform
from peek_plugin_base.PeekVortexUtil import peekServerName


logger = logging.getLogger("child_status_protocol")


class PluginSubprocChildStateProtocol(protocol.Protocol):
    COMMAND_LOAD = "LOAD"
    COMMAND_START = "START"
    COMMAND_STOP = "STOP"
    COMMAND_UNLOAD = "UNLOAD"
    COMMAND_SUCCESS = "SUCCESS"

    def __init__(self, serviceName: str, subprocessGroup: str):
        self._data = b""
        self._serviceName = serviceName
        self._subprocessGroup = subprocessGroup

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
            message, self._data = self._data.split(b"\n", 1)
            if not message:
                continue

            pluginName, command = message.decode().split(":", 1)

            yield self._runCommand(pluginName, command)

    @inlineCallbacks
    def _runCommand(self, pluginName: str, command: str):
        from peek_platform import PeekPlatformConfig

        try:

            if command == self.COMMAND_LOAD:
                yield PeekPlatformConfig.pluginLoader.loadStandalonePlugin(
                    pluginName
                )
            elif command == self.COMMAND_START:
                yield PeekPlatformConfig.pluginLoader.startStandalonePlugin(
                    pluginName
                )
            elif command == self.COMMAND_STOP:
                yield PeekPlatformConfig.pluginLoader.stopStandalonePlugin(
                    pluginName
                )
            elif command == self.COMMAND_UNLOAD:
                yield PeekPlatformConfig.pluginLoader.unloadStandalonePlugin(
                    pluginName
                )
            else:
                raise NotImplementedError(f"Unhandled command '{command}'")

            # Send the success response
            self.transport.write(
                f"{pluginName}:{self.COMMAND_SUCCESS}".encode()
            )
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
