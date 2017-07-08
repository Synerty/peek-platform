import logging
from typing import List

import os
from twisted.internet.task import LoopingCall

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC
from peek_platform.frontend.FrontendOsCmd import runTsc

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

        excludeRegexp = (
            r'.*[.]web[.]ts$',
            r'.*[.]mweb[.]ts$',
            r'.*[.]dweb[.]ts$',
            r'.*[.]web[.]html$',
            r'.*[.]mweb[.]html$',
            r'.*[.]dweb[.]html$',
            r'.*__pycache__.*',
            r'.*[.]py$'
        )

        self._dirSyncMap = list()

        feBuildDir = os.path.join(self._frontendProjectDir, 'build-ns')
        feSrcAppDir = os.path.join(self._frontendProjectDir, 'src', 'app')

        feAppDir = os.path.join(feBuildDir, 'app')
        feAssetsDir = os.path.join(feBuildDir, 'app', 'assets')

        self._moduleCompileRequired = False
        self._moduleCompileLoopingCall = None

        feModuleDirs = [
            (os.path.join(feAppDir, '@peek'), "moduleDir"),
        ]

        pluginDetails = self._loadPluginConfigs()

        # --------------------
        # Check if node_modules exists

        # if not os.path.exists(os.path.join(feBuildDir, 'node_modules')):
        #     raise NotADirectoryError("node_modules doesn't exist, ensure you've run "
        #                              "`npm install` in dir %s" % feBuildDir)

        # --------------------
        # Prepare the common frontend application

        self.fileSync.addSyncMapping(feSrcAppDir,
                                     os.path.join(feAppDir, 'app'),
                                     keepExtraDstJsAndMapFiles=True,
                                     excludeFilesRegex=excludeRegexp)

        # --------------------
        # Prepare the home and title bar configuration for the plugins
        self._writePluginHomeLinks(feAppDir, pluginDetails)
        self._writePluginTitleBarLinks(feAppDir, pluginDetails)

        # --------------------
        # Prepare the plugin lazy loaded part of the application
        self._writePluginRouteLazyLoads(feAppDir, pluginDetails)
        self._syncPluginFiles(feAppDir, pluginDetails, "appDir",
                              keepExtraDstJsAndMapFiles=True,
                              excludeFilesRegex=excludeRegexp)

        # --------------------
        # Prepare the plugin assets
        self._syncPluginFiles(feAssetsDir, pluginDetails, "assetDir",
                              excludeFilesRegex=excludeRegexp)

        # --------------------
        # Prepare the shared / global parts of the plugins

        self._writePluginRootModules(feAppDir, pluginDetails)
        self._writePluginRootServices(feAppDir, pluginDetails)

        # There are two
        for feModDir, jsonAttr, in feModuleDirs:
            # Link the shared code, this allows plugins
            # * to import code from each other.
            # * provide global services.
            self._syncPluginFiles(feModDir, pluginDetails, jsonAttr,
                                  keepExtraDstJsAndMapFiles=True,
                                  excludeFilesRegex=excludeRegexp)


        # Lastly, Allow the clients to override any frontend files they wish.
        self.fileSync.addSyncMapping(self._jsonCfg.feFrontendCustomisationsDir,
                                     feAppDir,
                                     parentMustExist=True,
                                     deleteExtraDstFiles=False,
                                     excludeFilesRegex=excludeRegexp)

        self.fileSync.syncFiles()

        if self._jsonCfg.feSyncFilesForDebugEnabled:
            logger.info("Starting frontend development file sync")
            self.fileSync.startFileSyncWatcher()

    def stopDebugWatchers(self):
        logger.info("Stoping frontend development file sync")
        self.fileSync.stopFileSyncWatcher()

    def _syncFileHook(self, fileName: str, contents: bytes) -> bytes:
        if fileName.endswith(".ts"):
            contents = contents.replace(b'@synerty/peek-util/index.web',
                                        b'@synerty/peek-util/index.ns')
            contents = contents.replace(b'@synerty/peek-util/index.mweb',
                                        b'@synerty/peek-util/index.ns')

            # replace imports that end with .web/.mweb with .ns
            # This will allow platform dependent typescript modules,
            # EG photo taking modules
            contents = contents.replace(b'.mweb";', b'.ns";')
            contents = contents.replace(b'.web";', b'.ns";')

            # Update the @peek import to use the /app path
            contents = contents.replace(b'from "@peek/', b'from "~/@peek/')

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
        """ Patch Component
        
        Apply patches to the WEB file to convert it to the NativeScript version

        :param fileName: The name of the file
        :param contents: The original contents of the file
        :return: The new contents of the file
        """
        inComponentHeader = False

        newContents = b''
        for line in contents.splitlines(True):
            if line.startswith(b"@Component"):
                inComponentHeader = True

            elif line.startswith(b"export"):
                inComponentHeader = False

            elif inComponentHeader:
                line = (line
                        .replace(b'.mweb;"', b'.ns";')
                        .replace(b'.mweb.html', b'.ns.html')
                        .replace(b'.mweb.css', b'.ns.css')
                        .replace(b'.mweb.scss', b'.ns.scss')
                        .replace(b'.web;"', b'.ns";')
                        .replace(b'.web.html', b'.ns.html')
                        .replace(b'.web.css', b'.ns.css')
                        .replace(b'.web.scss', b'.ns.scss')
                        .replace(b"'./", b"'")
                        )

            newContents += line

        return newContents
