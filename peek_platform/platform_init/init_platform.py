import logging

from setproctitle import setproctitle
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks
from vortex.VortexFactory import VortexFactory

from peek_plugin_base.PeekVortexUtil import peekAgentName
from peek_plugin_base.PeekVortexUtil import peekFieldName
from peek_plugin_base.PeekVortexUtil import peekOfficeName
from peek_plugin_base.PeekVortexUtil import peekServerName
from peek_plugin_base.PeekVortexUtil import peekVortexClientServiceNames
from peek_plugin_base.PeekVortexUtil import peekWorkerName


class InitPlatform:
    def __init__(self, serviceName: str, isPluginSubprocess: bool = False):
        self._serviceName = serviceName

        from peek_platform import PeekPlatformConfig

        PeekPlatformConfig.isPluginSubprocess = isPluginSubprocess

        PeekPlatformConfig.componentName = self._serviceName
        if not isPluginSubprocess:
            setproctitle(PeekPlatformConfig.componentName)

    def setupPlatform(self):

        self.setupInstallManagers()
        self.setupPluginLoader()
        self.setupConfig()
        self.setupLogging()
        self.setupMemoryDebugLogging()
        self.setupTwistedReactor()
        self.setupTempDirs()
        self.setupManhole()

    @inlineCallbacks
    def loadAndStartupPlugins(self):
        from peek_platform import PeekPlatformConfig

        yield PeekPlatformConfig.pluginLoader.loadCorePlugins()
        yield PeekPlatformConfig.pluginLoader.loadOptionalPlugins()
        yield PeekPlatformConfig.pluginLoader.startCorePlugins()
        yield PeekPlatformConfig.pluginLoader.startOptionalPlugins()

    @inlineCallbacks
    def stopAndShutdownPluginsAndVortex(self):
        from peek_platform import PeekPlatformConfig

        yield PeekPlatformConfig.pluginLoader.stopOptionalPlugins()
        yield PeekPlatformConfig.pluginLoader.stopCorePlugins()
        yield PeekPlatformConfig.pluginLoader.unloadOptionalPlugins()
        yield PeekPlatformConfig.pluginLoader.unloadCorePlugins()

        yield VortexFactory.shutdown()

    def setupManhole(self):
        from peek_platform import PeekPlatformConfig

        # Setup manhole
        if PeekPlatformConfig.config.manholeEnabled:
            from peek_platform.util.ManHoleUtil import start_manhole

            start_manhole(
                PeekPlatformConfig.config.manholePort,
                PeekPlatformConfig.config.manholePassword,
                PeekPlatformConfig.config.manholePublicKeyFile,
                PeekPlatformConfig.config.manholePrivateKeyFile,
            )

    def setupTempDirs(self):
        from peek_platform import PeekPlatformConfig

        # Initialise the txhttputil Directory object
        from pytmpdir.dir_setting import DirSetting

        DirSetting.defaultDirChmod = PeekPlatformConfig.config.DEFAULT_DIR_CHMOD
        DirSetting.tmpDirPath = PeekPlatformConfig.config.tmpPath

        from txhttputil.site.FileUploadRequest import FileUploadRequest

        FileUploadRequest.tmpFilePath = PeekPlatformConfig.config.tmpPath

    def setupTwistedReactor(self):
        from peek_platform import PeekPlatformConfig

        # Set the reactor thread count
        reactor.suggestThreadPoolSize(
            PeekPlatformConfig.config.twistedThreadPoolSize
        )

    def setupMemoryDebugLogging(self):
        from peek_platform import PeekPlatformConfig

        # If we need to enable memory debugging, turn that on.
        if PeekPlatformConfig.config.loggingDebugMemoryMask:
            from peek_platform.util.MemUtil import setupMemoryDebugging

            setupMemoryDebugging(
                PeekPlatformConfig.componentName,
                PeekPlatformConfig.config.loggingDebugMemoryMask,
            )

    def setupLogging(self):
        from peek_platform import PeekPlatformConfig

        # Set default logging level
        logging.root.setLevel(PeekPlatformConfig.config.loggingLevel)
        from peek_platform.util.LogUtil import updatePeekLoggerHandlers

        updatePeekLoggerHandlers(
            PeekPlatformConfig.componentName,
            PeekPlatformConfig.config.daysToKeep,
            PeekPlatformConfig.config.logToStdout,
        )
        if PeekPlatformConfig.config.loggingLogToSyslogHost:
            from peek_platform.util.LogUtil import setupLoggingToSyslogServer

            setupLoggingToSyslogServer(
                PeekPlatformConfig.config.loggingLogToSyslogHost,
                PeekPlatformConfig.config.loggingLogToSyslogPort,
                PeekPlatformConfig.config.loggingLogToSyslogFacility,
            )
        # Enable deferred debugging if DEBUG is on.
        if logging.root.level == logging.DEBUG:
            defer.setDebugging(True)

    def setupConfig(self):
        from peek_platform import PeekPlatformConfig

        if self._serviceName == peekOfficeName:
            # The config depends on the componentName, order is important
            from peek_office_service.PeekClientConfig import (
                PeekClientConfig as Config,
            )
            from peek_office_service import __version__

        elif self._serviceName == peekFieldName:
            # The config depends on the componentName, order is important
            from peek_field_service.PeekClientConfig import (
                PeekClientConfig as Config,
            )
            from peek_field_service import __version__

        elif self._serviceName == peekServerName:
            # The config depends on the componentName, order is important
            from peek_logic_service.PeekServerConfig import (
                PeekServerConfig as Config,
            )
            from peek_logic_service import __version__

        elif self._serviceName == peekAgentName:
            # The config depends on the componentName, order is important
            from peek_agent_service.PeekAgentConfig import (
                PeekAgentConfig as Config,
            )
            from peek_agent_service import __version__

        elif self._serviceName == peekWorkerName:
            # The config depends on the componentName, order is important
            from peek_worker_service.PeekWorkerConfig import (
                PeekWorkerConfig as Config,
            )
            from peek_worker_service import __version__

        else:
            raise NotImplementedError()

        PeekPlatformConfig.config = Config()
        PeekPlatformConfig.config.platformVersion = __version__

    def setupPluginLoader(self):
        from peek_platform import PeekPlatformConfig

        if self._serviceName == peekOfficeName:
            # Tell the platform classes about our instance of the PeekLoaderBase
            from peek_office_service.plugin.ClientPluginLoader import (
                ClientPluginLoader as Loader,
            )

        elif self._serviceName == peekFieldName:
            # Tell the platform classes about our instance of the PeekLoaderBase
            from peek_field_service.plugin.ClientPluginLoader import (
                ClientPluginLoader as Loader,
            )

        elif self._serviceName == peekServerName:
            # Tell the platform classes about our instance of the PeekLoaderBase
            from peek_logic_service.plugin.ServerPluginLoader import (
                ServerPluginLoader as Loader,
            )

        elif self._serviceName == peekAgentName:
            # Tell the platform classes about our instance of the PeekLoaderBase
            from peek_agent_service.plugin.AgentPluginLoader import (
                AgentPluginLoader as Loader,
            )

        elif self._serviceName == peekWorkerName:
            # Tell the platform classes about our instance of the PeekLoaderBase
            from peek_worker_service.plugin.WorkerPluginLoader import (
                WorkerPluginLoader as Loader,
            )

        else:
            raise NotImplementedError()

        PeekPlatformConfig.pluginLoader = Loader()

    def setupInstallManagers(self):
        from peek_platform import PeekPlatformConfig

        if self._serviceName == peekOfficeName:
            from peek_office_service.sw_install.PluginSwInstallManager import (
                PluginSwInstallManager,
            )
            from peek_office_service.sw_install.PeekSwInstallManager import (
                PeekSwInstallManager,
            )

        elif self._serviceName == peekFieldName:
            from peek_field_service.sw_install.PluginSwInstallManager import (
                PluginSwInstallManager,
            )
            from peek_field_service.sw_install.PeekSwInstallManager import (
                PeekSwInstallManager,
            )

        elif self._serviceName == peekServerName:
            from peek_logic_service.sw_install.PluginSwInstallManager import (
                PluginSwInstallManager,
            )
            from peek_logic_service.sw_install.PeekSwInstallManager import (
                PeekSwInstallManager,
            )

        elif self._serviceName == peekAgentName:
            from peek_agent_service.sw_install.PluginSwInstallManager import (
                PluginSwInstallManager,
            )
            from peek_agent_service.sw_install.PeekSwInstallManager import (
                PeekSwInstallManager,
            )

        elif self._serviceName == peekWorkerName:
            from peek_worker_service.sw_install.PluginSwInstallManager import (
                PluginSwInstallManager,
            )
            from peek_worker_service.sw_install.PeekSwInstallManager import (
                PeekSwInstallManager,
            )

        else:
            raise NotImplementedError()

        PeekPlatformConfig.pluginSwInstallManager = PluginSwInstallManager()
        PeekPlatformConfig.peekSwInstallManager = PeekSwInstallManager()

    def connectVortexClient(self) -> Deferred:
        assert (
            self._serviceName in peekVortexClientServiceNames
        ), f"Service {self._serviceName} is not meant to connect vortex clients"

        # First, setup the VortexServer Agent
        from peek_platform import PeekPlatformConfig

        dataExchangeCfg = PeekPlatformConfig.config.dataExchange

        scheme = "wss" if dataExchangeCfg.peekServerUseSSL else "ws"
        host = dataExchangeCfg.peekServerHost
        port = dataExchangeCfg.peekServerHttpPort

        return VortexFactory.createWebsocketClient(
            PeekPlatformConfig.componentName,
            host,
            port,
            url=f"{scheme}://{host}:{port}/vortexws",
            sslEnableMutualTLS=dataExchangeCfg.peekServerSSLEnableMutualTLS,
            sslClientCertificateBundleFilePath=dataExchangeCfg.peekServerSSLClientBundleFilePath,
            sslMutualTLSCertificateAuthorityBundleFilePath=dataExchangeCfg.peekServerSSLClientMutualTLSCertificateAuthorityBundleFilePath,
            sslMutualTLSTrustedPeerCertificateBundleFilePath=dataExchangeCfg.peekServerSSLMutualTLSTrustedPeerCertificateBundleFilePath,
        )
