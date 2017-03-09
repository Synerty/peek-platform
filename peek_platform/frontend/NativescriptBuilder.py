import logging
import os

from typing import List

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC, \
    nodeModuleTsConfig

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

        self._hashFileName = os.path.join(feBuildDir, ".lastHash")

        pluginDetails = self._loadPluginConfigs()

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

    def _syncFileHook(self, fileName: str):
        if fileName.endswith(".ts"):
            self._patchComponent(fileName)

    def _patchComponent(self, fileName: str):

        with open(fileName, 'r') as f:
            contents = f.read()
            if not '@Component' in contents:
                return

        newContents = ''
        for line in contents.splitlines(True):
            if line.strip().startswith('templateUrl'):
                newContents += (line
                                .replace('web.html', 'ns.html')
                                .replace("'./", "'"))

            else:
                newContents += line

        with open(fileName, 'w') as f:
            f.write(newContents)
