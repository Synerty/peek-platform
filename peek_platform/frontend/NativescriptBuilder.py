import logging
import os

from typing import List

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC, \
    nodeModuleTsConfig, nodeModuleTypingsD
from peek_platform.util.PtyUtil import PtyOutParser, spawnPty, logSpawnException

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

        pluingModulesDirName = '@' + self._platformService
        fePluginModulesDir = os.path.join(feNodeModulesDir,
                                          pluingModulesDirName)

        fePackageJson = os.path.join(feBuildDir, 'package.json')

        pluginDetails = self._loadPluginConfigs()

        ## --------------------
        # Check if node_modules exists

        if not os.path.exists(os.path.join(feBuildDir, 'node_modules')):
            raise NotADirectoryError("node_modules doesn't exist, ensure you've run "
                                     "`npm install` in dir %s" % feBuildDir)

        ## --------------------
        # Prepare the common frontend application

        self.fileSync.addSyncMapping(feSrcAppDir, os.path.join(feAppDir, 'app'))

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
        self._writeFileIfRequired(fePluginModulesDir, 'typings.d.ts', nodeModuleTypingsD)

        # Update the package.json in the peek_client_fe project so that it includes
        # references to the plugins linked under node_modules.
        # Otherwise nativescript doesn't include them in it's build.
        self._updatePackageJson(fePackageJson, pluginDetails, self._platformService)

        # Now sync those node_modules/@peek-xxx packages into the "platforms" build dirs

        compilePluginModules = lambda: self._compilePluginModules(fePluginModulesDir)

        androidDir1 = 'platforms/android/src/main/assets/app/tns_modules'
        androidDir2 = ('platforms/android'
                       '/build/intermediates/assets/F0F1/debug/app/tns_modules')

        self.fileSync.addSyncMapping(fePluginModulesDir,
                                     os.path.join(feBuildDir, androidDir1, pluingModulesDirName),
                                     parentMustExist=True,
                                     preSyncCallback=compilePluginModules)

        self.fileSync.addSyncMapping(fePluginModulesDir,
                                     os.path.join(feBuildDir, androidDir2, pluingModulesDirName),
                                     parentMustExist=True)

        self.fileSync.syncFiles()
        compilePluginModules()

        if self._jsonCfg.feSyncFilesForDebugEnabled:
            logger.info("Starting frontend development file sync")
            self.fileSync.startFileSyncWatcher()

    def _syncFileHook(self, fileName: str, contents: bytes) -> bytes:
        if fileName.endswith(".ts"):
            contents = contents.replace(b'@synerty/peek-web-ns/index.web',
                                        b'@synerty/peek-web-ns/index.nativescript')

            # if b'@NgModule' in contents:
            #     return self._patchModule(fileName, contents)

            if b'@Component' in contents:
                return self._patchComponent(fileName, contents)

        return contents

    # def _patchModule(self, fileName: str, contents: bytes) -> bytes:
    #     newContents = b''
    #     for line in contents.splitlines(True):
    #
    #         newContents += line
    #
    #     return newContents

    def _patchComponent(self, fileName: str, contents: bytes) -> bytes:
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

    def _compilePluginModules(self, fePluginModulesDir: str) -> None:
        """ Compile the frontend

        this runs `ng build`

        We need to use a pty otherwise webpack doesn't run.

        """

        hashFileName = os.path.join(fePluginModulesDir, ".lastHash")

        if not self._recompileRequiredCheck(fePluginModulesDir, hashFileName):
            logger.info("Modules have not changed, recompile not required.")
            return

        logger.info("Compiling plugin modules")

        try:
            parser = PtyOutParser(loggingStartMarker="Hash: ")
            spawnPty("cd %s && tsc" % fePluginModulesDir, parser)
            logger.info("Frontend plugin module compile complete.")

        except Exception as e:
            logSpawnException(e)
            # if os.path.exists(hashFileName):
            #     os.remove(hashFileName)

            # Update the detail of the exception and raise it
            e.message = "The frontend plugin modules to compile."
            # raise
