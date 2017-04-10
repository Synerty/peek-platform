import logging
import os
from typing import List

from twisted.internet.task import LoopingCall

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC
from peek_platform.frontend.FrontendOsCmd import runTsc

logger = logging.getLogger(__name__)

nodeModuleTsConfig = """
{
  "strictNullChecks": true,
  "allowUnreachableCode": true,
  "compilerOptions": {
    "baseUrl": "",
    "declaration": false,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "forceConsistentCasingInFileNames":true,
    "lib": ["es2016", "dom"],
    "module": "commonjs",
    "moduleResolution": "node",
    "sourceMap": false,
    "target": "es5",
    "typeRoots": [
      "../@types"
    ]
  }
}
"""

nodeModuleTypingsD = """
/* SystemJS module definition */
declare let module: {
  id: string;
};

declare let require: any;
"""


class NativescriptBuilder(FrontendBuilderABC):
    def __init__(self, frontendProjectDir: str, platformService: str,
                 jsonCfg, loadedPlugins: List):
        FrontendBuilderABC.__init__(self, frontendProjectDir, platformService,
                                    jsonCfg, loadedPlugins)

        self._moduleCompileRequired = None
        self._moduleCompileLoopingCall = None
        self._feModuleDirs = None

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

        self._moduleCompileRequired = False
        self._moduleCompileLoopingCall = None

        self._feModuleDirs = [
            (os.path.join(feNodeModulesDir, '@peek'), "moduleDir"),
        ]

        fePackageJson = os.path.join(feBuildDir, 'package.json')

        pluginDetails = self._loadPluginConfigs()

        # --------------------
        # Check if node_modules exists

        if not os.path.exists(os.path.join(feBuildDir, 'node_modules')):
            raise NotADirectoryError("node_modules doesn't exist, ensure you've run "
                                     "`npm install` in dir %s" % feBuildDir)

        # --------------------
        # Prepare the common frontend application

        self.fileSync.addSyncMapping(feSrcAppDir, os.path.join(feAppDir, 'app'))

        # --------------------
        # Prepare the home and title bar configuration for the plugins
        self._writePluginHomeLinks(feAppDir, pluginDetails)
        self._writePluginTitleBarLinks(feAppDir, pluginDetails)

        # --------------------
        # Prepare the plugin lazy loaded part of the application
        self._writePluginRouteLazyLoads(feAppDir, pluginDetails)
        self._syncPluginFiles(feAppDir, pluginDetails, "appDir")

        # --------------------
        # Prepare the plugin assets
        self._syncPluginFiles(feAssetsDir, pluginDetails, "assetDir")

        # --------------------
        # Prepare the shared / global parts of the plugins

        self._writePluginRootModules(feAppDir, pluginDetails)
        self._writePluginRootServices(feAppDir, pluginDetails)

        # There are two
        for feModDir, jsonAttr, in self._feModuleDirs:
            # Link the shared code, this allows plugins
            # * to import code from each other.
            # * provide global services.
            self._syncPluginFiles(feModDir, pluginDetails, jsonAttr,
                                  postSyncCallback=self._scheduleModuleCompile)

            self._writeFileIfRequired(feModDir, 'tsconfig.json', nodeModuleTsConfig)
            self._writeFileIfRequired(feModDir, 'typings.d.ts', nodeModuleTypingsD)

            # Update the package.json in the peek_client_fe project so that it includes
            # references to the plugins linked under node_modules.
            # Otherwise nativescript doesn't include them in it's build.
            self._updatePackageJson(fePackageJson, pluginDetails)

            # Now sync those node_modules/@peek-xxx packages into the
            # "platforms" build dirs

            '''
            androidDir1 = os.path.join(feBuildDir,
                                       'platforms', 'android', 'src', 'main', 'assets',
                                       'app', 'tns_modules',
                                       os.path.basename(feModDir))
            androidDir2 = os.path.join(feBuildDir, 'platforms', 'android',
                                       'build', 'intermediates', 'assets', 'F0F1',
                                       'debug', 'app', 'tns_modules',
                                       os.path.basename(feModDir))

            self.fileSync.addSyncMapping(feModDir,
                                         androidDir1,
                                         parentMustExist=True)

            self.fileSync.addSyncMapping(feModDir,
                                         androidDir2,
                                         parentMustExist=True)
            '''

        # Lastly, Allow the clients to override any frontend files they wish.
        self.fileSync.addSyncMapping(self._jsonCfg.feFrontendCustomisationsDir,
                                     feAppDir,
                                     parentMustExist=True,
                                     deleteExtraDstFiles=False)

        self.fileSync.syncFiles()
        self._compilePluginModules(True)

        if self._jsonCfg.feSyncFilesForDebugEnabled:
            logger.info("Starting frontend development file sync")
            self._moduleCompileLoopingCall = LoopingCall(self._compilePluginModules)
            self._moduleCompileLoopingCall.start(1, now=False)
            self.fileSync.startFileSyncWatcher()

    def stopDebugWatchers(self):
        logger.info("Stoping frontend development file sync")
        self.fileSync.stopFileSyncWatcher()
        self._moduleCompileLoopingCall.stop()
        self._moduleCompileLoopingCall = None

    def _syncFileHook(self, fileName: str, contents: bytes) -> bytes:
        if fileName.endswith(".ts"):
            contents = contents.replace(b'@synerty/peek-web-ns/index.web',
                                        b'@synerty/peek-web-ns/index.nativescript')
            contents = contents.replace(b'@synerty/peek-web-ns/index.mweb',
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
                        .replace(b'.mweb.html', b'.ns.html')
                        .replace(b'.mweb.css', b'.ns.css')
                        .replace(b'.mweb.scss', b'.ns.scss')
                        .replace(b'.web.html', b'.ns.html')
                        .replace(b'.web.css', b'.ns.css')
                        .replace(b'.web.scss', b'.ns.scss')
                        .replace(b"'./", b"'"))

            newContents += line

        return newContents

    def _scheduleModuleCompile(self):
        self._moduleCompileRequired = True

    def _compilePluginModules(self, force=False) -> None:
        """ Compile the frontend

        this runs `ng build`

        We need to use a pty otherwise webpack doesn't run.

        """

        if not (self._moduleCompileRequired or force):
            return

        self._moduleCompileRequired = False

        for feModDir, _ in self._feModuleDirs:

            hashFileName = os.path.join(feModDir, ".lastHash")

            if not force and not self._recompileRequiredCheck(feModDir, hashFileName):
                logger.info("Modules have not changed, recompile not required.")
                return

            logger.info("Compiling plugin modules")

            try:
                runTsc(feModDir)

            except Exception as e:
                # if os.path.exists(hashFileName):
                #     os.remove(hashFileName)

                # Update the detail of the exception and raise it
                e.message = "The frontend plugin modules to compile."
                # raise
