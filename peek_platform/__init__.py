from . import WindowsPatch

__version__ = '0.0.7'

class PeekPlatformConfig:
    """ Peek Platform Config

    This is really a GLOBAL pettern, It should be replaced at some stage.

    This class is populated with data when the peek processes start.
    This is required so that peek_platform common code can access the other parts
    of the system, which are peek_agent, peek_server, peek_worker.

    """

    # The component name of this part of the platform
    # EG, peek_server, peek_worker, peek_agent
    componentName = None

    # The config accessor class
    config = None

    # The inherited class of PluginSwInstallManagerABC
    pluginSwInstallManager = None

    # The inherited class of PeekSwInstallManagerABC
    peekSwInstallManager = None

    # The instance of the PluginLoaderABC
    pluginLoader = None