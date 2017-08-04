import logging
from datetime import datetime

import os
from typing import List

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC
from peek_platform.frontend.FrontendOsCmd import runNgBuild

logger = logging.getLogger(__name__)


class WebBuilder(FrontendBuilderABC):
    def __init__(self, frontendProjectDir: str, platformService: str,
                 jsonCfg, loadedPlugins: List):
        FrontendBuilderABC.__init__(self, frontendProjectDir, platformService,
                                    jsonCfg, loadedPlugins)

        self.isMobile = "mobile" in platformService
        self.isDesktop = "desktop" in platformService
        self.isAdmin = "admin" in platformService

    def build(self) -> None:
        if not self._jsonCfg.feWebBuildPrepareEnabled:
            logger.info("%s SKIPPING, Web build prepare is disabled in config",
                        self._platformService)
            return

        excludeRegexp = (
            r'.*[.]ns[.]ts$',
            r'.*[.]ns[.]html$',
            r'.*__pycache__.*',
            r'.*[.]py$'
        )

        if self.isMobile:
            excludeRegexp += (
                r'.*[.]dweb[.]ts$',
                r'.*[.]dweb[.]html$',
            )

        elif self.isDesktop:
            excludeRegexp += (
                r'.*[.]mweb[.]ts$',
                r'.*[.]mweb[.]html$',
            )

        elif self.isAdmin:
            pass

        else:
            raise NotImplementedError("This is neither admin, mobile or desktop web")

        self._dirSyncMap = list()

        feBuildDir = os.path.join(self._frontendProjectDir, 'build-web')
        feSrcAppDir = os.path.join(self._frontendProjectDir, 'src', 'app')

        feBuildSrcDir = os.path.join(feBuildDir, 'src')
        feBuildAssetsDir = os.path.join(feBuildDir, 'src', 'assets')

        feModuleDirs = [
            (os.path.join(feBuildSrcDir, '@peek'), "moduleDir"),
        ]

        pluginDetails = self._loadPluginConfigs()

        # --------------------
        # Check if node_modules exists

        if not os.path.exists(os.path.join(feBuildDir, 'node_modules')):
            raise NotADirectoryError(
                "%s node_modules doesn't exist, ensure you've run "
                "`npm install` in dir %s",
                self._platformService, feBuildDir)

        # --------------------
        # Prepare the common frontend application

        self.fileSync.addSyncMapping(feSrcAppDir, os.path.join(feBuildSrcDir, 'app'),
                                     excludeFilesRegex=excludeRegexp)

        # --------------------
        # Prepare the home and title bar configuration for the plugins
        self._writePluginHomeLinks(feBuildSrcDir, pluginDetails)
        self._writePluginTitleBarLinks(feBuildSrcDir, pluginDetails)

        # --------------------
        # Prepare the plugin lazy loaded part of the application
        self._writePluginRouteLazyLoads(feBuildSrcDir, pluginDetails)
        self._syncPluginFiles(feBuildSrcDir, pluginDetails, "appDir",
                              excludeFilesRegex=excludeRegexp)

        # --------------------
        # Prepare the plugin assets
        self._syncPluginFiles(feBuildAssetsDir, pluginDetails, "assetDir",
                              excludeFilesRegex=excludeRegexp)

        # --------------------
        # Prepare the shared / global parts of the plugins

        self._writePluginRootModules(feBuildSrcDir, pluginDetails)
        self._writePluginRootServices(feBuildSrcDir, pluginDetails)

        for feModDir, jsonAttr, in feModuleDirs:
            # Link the shared code, this allows plugins
            # * to import code from each other.
            # * provide global services.
            self._syncPluginFiles(feModDir, pluginDetails, jsonAttr,
                                  excludeFilesRegex=excludeRegexp)

        # Lastly, Allow the clients to override any frontend files they wish.
        self.fileSync.addSyncMapping(self._jsonCfg.feFrontendCustomisationsDir,
                                     feBuildSrcDir,
                                     parentMustExist=True,
                                     deleteExtraDstFiles=False,
                                     excludeFilesRegex=excludeRegexp)

        self.fileSync.syncFiles()

        if self._jsonCfg.feSyncFilesForDebugEnabled:
            logger.info("%s starting frontend development file sync",
                        self._platformService)
            self.fileSync.startFileSyncWatcher()

        if self._jsonCfg.feWebBuildEnabled:
            logger.info("%s starting frontend web build", self._platformService)
            self._compileFrontend(feBuildDir)

    def _syncFileHook(self, fileName: str, contents: bytes) -> bytes:
        # replace imports that end with .dweb or .mweb to the appropriate
        # value
        # Otherwise just .web should be used if no replacing is required.

        if self.isMobile:
            contents = contents.replace(b'.dweb";', b'.mweb";')

        elif self.isDesktop:
            contents = contents.replace(b'.mweb";', b'.dweb";')

        elif self.isAdmin:
            pass

        else:
            raise NotImplementedError("This is neither mobile or desktop web")

        return contents

    def _compileFrontend(self, feBuildDir: str) -> None:
        """ Compile the frontend

        this runs `ng build`

        We need to use a pty otherwise webpack doesn't run.

        """
        startDate = datetime.now()
        hashFileName = os.path.join(feBuildDir, ".lastHash")

        if not self._recompileRequiredCheck(feBuildDir, hashFileName):
            logger.info("%s Frontend has not changed, recompile not required.",
                        self._platformService)
            return

        logger.info("%s Rebuilding frontend distribution", self._platformService)

        try:
            runNgBuild(feBuildDir)

        except Exception as e:
            if os.path.exists(hashFileName):
                os.remove(hashFileName)

            # Update the detail of the exception and raise it
            e.message = "%s angular frontend failed to build." % self._platformService
            raise

        logger.info("%s frontend rebuild completed in %s",
                    self._platformService, datetime.now() - startDate)
