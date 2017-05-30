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
    "declaration": false,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "forceConsistentCasingInFileNames": true,
    "module": "commonjs",
    "moduleResolution": "node",
    "sourceMap": false,
    "target": "es5",
    "skipDefaultLibCheck": true,
    "skipLibCheck": true,
    "lib": [
            "es6",
            "dom",
            "es2015.iterable"
            ],
    "rootDir": ".",
    "typeRoots": [
      "../@types"
    ],
    "types": [
      "moment"
    ]
  }
}


"""

nodeModuleTypingsD = """

//declare let localStorage:any;
//declare let location:any;

// From node_modules/typescript/lib/lib.es6.d.ts
interface Console {
    assert(test?: boolean, message?: string, ...optionalParams: any[]): void;
    clear(): void;
    count(countTitle?: string): void;
    debug(message?: any, ...optionalParams: any[]): void;
    dir(value?: any, ...optionalParams: any[]): void;
    dirxml(value: any): void;
    error(message?: any, ...optionalParams: any[]): void;
    exception(message?: string, ...optionalParams: any[]): void;
    group(groupTitle?: string): void;
    groupCollapsed(groupTitle?: string): void;
    groupEnd(): void;
    info(message?: any, ...optionalParams: any[]): void;
    log(message?: any, ...optionalParams: any[]): void;
    msIsIndependentlyComposed(element: Element): boolean;
    profile(reportName?: string): void;
    profileEnd(): void;
    select(element: Element): void;
    table(...data: any[]): void;
    time(timerName?: string): void;
    timeEnd(timerName?: string): void;
    trace(message?: any, ...optionalParams: any[]): void;
    warn(message?: any, ...optionalParams: any[]): void;
}

declare var Console: {
    prototype: Console;
    new(): Console;
}


// From node_modules/typescript/lib/lib.es6.d.ts
interface WebSocketEventMap {
    "close": CloseEvent;
    "error": Event;
    "message": MessageEvent;
    "open": Event;
}

interface WebSocket extends EventTarget {
    binaryType: string;
    readonly bufferedAmount: number;
    readonly extensions: string;
    onclose: (this: WebSocket, ev: CloseEvent) => any;
    onerror: (this: WebSocket, ev: Event) => any;
    onmessage: (this: WebSocket, ev: MessageEvent) => any;
    onopen: (this: WebSocket, ev: Event) => any;
    readonly protocol: string;
    readonly readyState: number;
    readonly url: string;
    close(code?: number, reason?: string): void;
    send(data: any): void;
    readonly CLOSED: number;
    readonly CLOSING: number;
    readonly CONNECTING: number;
    readonly OPEN: number;
    addEventListener<K extends keyof WebSocketEventMap>(type: K, listener: (this: WebSocket, ev: WebSocketEventMap[K]) => any, useCapture?: boolean): void;
    addEventListener(type: string, listener: EventListenerOrEventListenerObject, useCapture?: boolean): void;
}


declare var WebSocket: {
    prototype: WebSocket;
    new(url: string, protocols?: string | string[]): WebSocket;
    readonly CLOSED: number;
    readonly CLOSING: number;
    readonly CONNECTING: number;
    readonly OPEN: number;
}


"""

nodeReferencesD = """

/// <reference path="../tns-core-modules/tns-core-modules.d.ts" />
// /// <reference path="../tns-core-modules/lib.core.d.ts" />
// /// <reference path="../tns-core-modules/lib.dom.d.ts" />

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

        self.fileSync.addSyncMapping(feSrcAppDir,
                                     os.path.join(feAppDir, 'app'),
                                     keepExtraDstJsAndMapFiles=True)

        # --------------------
        # Prepare the home and title bar configuration for the plugins
        self._writePluginHomeLinks(feAppDir, pluginDetails)
        self._writePluginTitleBarLinks(feAppDir, pluginDetails)

        # --------------------
        # Prepare the plugin lazy loaded part of the application
        self._writePluginRouteLazyLoads(feAppDir, pluginDetails)
        self._syncPluginFiles(feAppDir, pluginDetails, "appDir",
                                     keepExtraDstJsAndMapFiles=True)

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
                                  keepExtraDstJsAndMapFiles=True,
                                  postSyncCallback=self._scheduleModuleCompile)

            self._writeFileIfRequired(feModDir, 'tsconfig.json', nodeModuleTsConfig)
            self._writeFileIfRequired(feModDir, 'typings.d.ts', nodeModuleTypingsD)
            self._writeFileIfRequired(feModDir, 'references.d.ts', nodeReferencesD)

            # Update the package.json in the peek_client_fe project so that it includes
            # references to the plugins linked under node_modules.
            # Otherwise nativescript doesn't include them in it's build.
            self._updatePackageJson(fePackageJson, pluginDetails)

            # Now sync those node_modules/@peek-xxx packages into the
            # "platforms" build dirs

            androidDir1 = os.path.join(feBuildDir,
                                       'platforms', 'android', 'src', 'main', 'assets',
                                       'app', 'tns_modules',
                                       os.path.basename(feModDir))
            androidDir2 = os.path.join(feBuildDir, 'platforms', 'android',
                                       'build', 'intermediates', 'assets', 'F0F1',
                                       'debug', 'app', 'tns_modules',
                                       os.path.basename(feModDir))
            '''
            # LATEST STATUS
            # This all works just as it should, but nativescript TNS does not update
            # the app correctly.
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
            contents = contents.replace(b'@synerty/peek-mobile-util/index.web',
                                        b'@synerty/peek-mobile-util/index.nativescript')
            contents = contents.replace(b'@synerty/peek-mobile-util/index.mweb',
                                        b'@synerty/peek-mobile-util/index.nativescript')

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
