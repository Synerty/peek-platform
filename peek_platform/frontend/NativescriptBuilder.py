import logging
import os

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC, \
    nodeModuleTsConfig
from typing import List

logger = logging.getLogger(__name__)


class NativescriptBuilder(FrontendBuilderABC):
    def __init__(self, frontendProjectDir: str, platformService: str,
                 jsonCfg, loadedPlugins: List):
        FrontendBuilderABC.__init__(self, frontendProjectDir, platformService,
                                    jsonCfg, loadedPlugins)

    def build(self) -> None:
        if not self._jsonCfg.feNativescriptBuildPrepareEnabled:
            logger.info("SKIPPING, Nativescript build prepare is disabled in config")
            return

        self._dirSyncMap = list()

        feBuildDir = os.path.join(self._frontendProjectDir, 'build-ns')
        feSrcAppDir = os.path.join(self._frontendProjectDir, 'src', 'app')

        feAppDir = os.path.join(feBuildDir, 'app')
        feAssetsDir = os.path.join(feBuildDir, 'app', 'assets')

        feNodeModulesDir = os.path.join(feBuildDir, 'node_modules')

        fePluginModulesDir = os.path.join(feNodeModulesDir,
                                          '@' + self._platformService)

        fePackageJson = os.path.join(feBuildDir, 'package.json')

        pluginDetails = self._loadPluginConfigs()

        ## --------------------
        # Check if node_modules exists

        if not os.path.exists(os.path.join(feBuildDir, 'node_modules')):
            raise NotADirectoryError("node_modules doesn't exist, ensure you've run "
                                     "`npm install` in dir %s" % feBuildDir)

        ## --------------------
        # Prepare the common frontend application

        self._addSyncMapping(feSrcAppDir, os.path.join(feAppDir, 'app'))

        ## --------------------
        # Prepare the home and title bar configuration for the plugins
        self._writePluginHomeLinks(feAppDir, pluginDetails)
        self._writePluginTitleBarLinks(feAppDir, pluginDetails)

        ## --------------------
        # Prepare the plugin lazy loaded part of the application
        self._writePluginRouteLazyLoads(feAppDir, pluginDetails)
        self._syncPluginFiles(feAppDir, pluginDetails, "angularFrontendAppDir")

        ## --------------------
        # Prepare the plugin assets
        self._syncPluginFiles(feAssetsDir, pluginDetails, "angularFrontendAssetsDir")

        ## --------------------
        # Prepare the shared / global parts of the plugins

        self._writePluginRootModules(feAppDir, pluginDetails, self._platformService)
        self._writePluginRootServices(feAppDir, pluginDetails, self._platformService)

        # Link the shared code, this allows plugins
        # * to import code from each other.
        # * provide global services.
        self._syncPluginFiles(fePluginModulesDir, pluginDetails,
                              "angularFrontendModuleDir")

        self._writeFileIfRequired(fePluginModulesDir, 'tsconfig.json', nodeModuleTsConfig)

        # Update the package.json in the peek_client_fe project so that it includes
        # references to the plugins linked under node_modules.
        # Otherwise nativescript doesn't include them in it's build.
        self._updatePackageJson(fePackageJson, pluginDetails, self._platformService)

        self.syncFiles()

        if self._jsonCfg.feSyncFilesForDebugEnabled:
            logger.info("Starting frontend development file sync")
            self.startFileSyncWatcher()

    def _syncFileHook(self, fileName: str, contents: bytes) -> bytes:
        if fileName.endswith(".ts"):
            return self._patchComponent(fileName, contents)

        return contents

    def _patchComponent(self, fileName: str, contents: bytes) -> bytes:

        if not b'@Component' in contents:
            return contents

        inComponentHeader = False

        newContents = b''
        for line in contents.splitlines(True):
            if line.startswith(b"@Component"):
                inComponentHeader = True

            elif line.startswith(b"export"):
                inComponentHeader = False

            elif inComponentHeader:
                line = (line
                        .replace(b'web.html', b'ns.html')
                        .replace(b'web.css', b'ns.css')
                        .replace(b'web.scss', b'ns.scss')
                        .replace(b"'./", b"'"))

            newContents += line

        return newContents
