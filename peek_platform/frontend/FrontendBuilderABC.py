import json
import logging
import os
import shutil
import subprocess
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from subprocess import PIPE

from jsoncfg.value_mappers import require_bool
from typing import List
from watchdog.events import FileSystemEventHandler, FileMovedEvent, FileModifiedEvent, \
    FileDeletedEvent, FileCreatedEvent
from watchdog.observers import Observer as WatchdogObserver

from peek_platform import PeekPlatformConfig
from peek_platform.file_config.PeekFileConfigFrontendDirMixin import \
    PeekFileConfigFrontendDirMixin
from peek_platform.file_config.PeekFileConfigOsMixin import PeekFileConfigOsMixin
from peek_platform.util.PtyUtil import PtyOutParser, spawnPty, logSpawnException
from peek_plugin_base.PeekVortexUtil import peekClientName, peekServerName
from peek_plugin_base.PluginPackageFileConfig import PluginPackageFileConfig

logger = logging.getLogger(__name__)

# Quiten the file watchdog
logging.getLogger("watchdog.observers.inotify_buffer").setLevel(logging.INFO)

PluginDetail = namedtuple("PluginDetail",
                          ["pluginRootDir",
                           "pluginName",
                           "pluginTitle",
                           "angularFrontendAppDir",
                           "angularFrontendModuleDir",
                           "angularFrontendAssetsDir",
                           "angularMainModule",
                           "angularRootModule",
                           "angularRootService",
                           "angularPluginIcon",
                           "showPluginHomeLink",
                           "showPluginInTitleBar",
                           "titleBarLeft",
                           "titleBarText"])

_routesTemplate = """
    {
        path: '%s',
        loadChildren: "./%s/%s"
    }"""

nodeModuleTsConfig = """
{
  "strictNullChecks": true,
  "allowUnreachableCode": true,
  "compilerOptions": {
    "baseUrl": "",
    "declaration": true,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "forceConsistentCasingInFileNames":true,
    "lib": ["es6", "dom"],
    "mapRoot": "./",
    "module": "commonjs",
    "moduleResolution": "node",
    "sourceMap": true,
    "target": "es5",
    "typeRoots": [
      "../@types"
    ]
  }
}
"""


class FrontendBuilderABC(metaclass=ABCMeta):
    """ Peek App Frontend Installer Mixin

    This class is used for the client and server.

    This class contains the logic for:
        * Linking in the frontend angular components to the frontend project
        * Compiling the frontend project

    :TODO: Use find/sort to generate a string of the files when this was last run.
        Only run it again if anything has changed.

    """

    def __init__(self, frontendProjectDir: str, platformService: str, jsonCfg,
                 loadedPlugins: List):
        assert platformService in (peekClientName, peekServerName), (
            "Unexpected service %s" % platformService)

        self._platformService = platformService
        self._jsonCfg = jsonCfg
        self._frontendProjectDir = frontendProjectDir
        self._loadedPlugins = loadedPlugins

        if not isinstance(self._jsonCfg, PeekFileConfigFrontendDirMixin):
            raise Exception("The file config must inherit the"
                            " PeekFileConfigFrontendDirMixin")

        if not isinstance(self._jsonCfg, PeekFileConfigOsMixin):
            raise Exception("The file config must inherit the"
                            " PeekFileConfigOsMixin")

        if not os.path.isdir(frontendProjectDir):
            raise Exception("% doesn't exist" % frontendProjectDir)

        self._dirSyncMap = list()
        self._fileWatchdogObserver = None

    def XXXXbuildFrontend(self) -> None:

        from peek_platform.plugin.PluginLoaderABC import PluginLoaderABC
        assert isinstance(self, PluginLoaderABC)

        from peek_platform import PeekPlatformConfig

        if not isinstance(PeekPlatformConfig.config, PeekFileConfigFrontendDirMixin):
            raise Exception("The file config must inherit the"
                            " PeekFileConfigFrontendDirMixin")

        if not isinstance(PeekPlatformConfig.config, PeekFileConfigOsMixin):
            raise Exception("The file config must inherit the"
                            " PeekFileConfigOsMixin")

        feSrcDir = PeekPlatformConfig.config.feSrcDir
        feAppDir = os.path.join(feSrcDir, 'app')
        feAssetsDir = os.path.join(feSrcDir, 'app', 'assets')

        feNodeModulesDir = os.path.join(self._findNodeModulesDir(),
                                        '@' + PeekPlatformConfig.componentName)

        fePackageJson = os.path.join(os.path.dirname(feSrcDir), 'package.json')

        self._hashFileName = os.path.join(os.path.dirname(feSrcDir), ".lastHash")

        pluginDetails = self._loadPluginConfigs()

        # Write files that link the plugins into Peek.
        self._writePluginRouteLazyLoads(feAppDir, pluginDetails)
        self._writePluginRootModules(feAppDir, pluginDetails,
                                     PeekPlatformConfig.componentName)
        self._writePluginRootServices(feAppDir, pluginDetails,
                                      PeekPlatformConfig.componentName)
        self._writePluginHomeLinks(feAppDir, pluginDetails)
        self._writePluginTitleBarLinks(feAppDir, pluginDetails)

        # Link the lazy loaded plugins
        self._relinkPluginDirs(feAppDir, pluginDetails, "angularFrontendAppDir")

        # Link in the assets dir
        self._relinkPluginDirs(feAssetsDir, pluginDetails, "angularFrontendAssetsDir")

        # Link the shared code, this allows plugins
        # * to import code from each other.
        # * provide global services.
        self._relinkPluginDirs(feNodeModulesDir,
                               pluginDetails,
                               "angularFrontendModuleDir")

        # Update the package.json in the peek_client_fe project so that it includes
        # references to the plugins linked under node_modules.
        # Otherwise nativescript doesn't include them in it's build.
        self._updatePackageJson(fePackageJson, pluginDetails,
                                PeekPlatformConfig.componentName)

        if not PeekPlatformConfig.config.feBuildEnabled:
            logger.warning("Frontend build disabled by config file, Not Building.")
            return

        self._compileFrontend(feSrcDir)

    def _loadPluginConfigs(self) -> [PluginDetail]:
        pluginDetails = []

        for plugin in self._loadedPlugins.values():
            assert isinstance(plugin.packageCfg, PluginPackageFileConfig)
            pluginPackageConfig = plugin.packageCfg.config

            jsonCfgNode = pluginPackageConfig[self._platformService.replace('peek-', '')]

            enabled = (jsonCfgNode.enableAngularFrontend(True, require_bool))

            if not enabled:
                continue

            angularFrontendAppDir = (jsonCfgNode.angularFrontendAppDir(None))
            angularFrontendModuleDir = (jsonCfgNode.angularFrontendModuleDir(None))
            angularFrontendAssetsDir = (jsonCfgNode.angularFrontendAssetsDir(None))
            angularMainModule = (jsonCfgNode.angularMainModule(None))

            showPluginHomeLink = (jsonCfgNode.showPluginHomeLink(True))
            showPluginInTitleBar = (jsonCfgNode.showPluginInTitleBar(False))
            titleBarLeft = (jsonCfgNode.titleBarLeft(False))
            titleBarText = (jsonCfgNode.titleBarText(None))

            def checkThing(name, data):
                sub = (name, plugin.name)
                if data:
                    assert data["file"], "%s.file is missing for %s" % sub
                    assert data["class"], "%s.class is missing for %s" % sub

            angularRootModule = (jsonCfgNode.angularRootModule(None))
            checkThing("angularRootModule", angularRootModule)

            angularRootService = (jsonCfgNode.angularRootService(None))
            checkThing("angularRootService", angularRootService)

            angularPluginIcon = (jsonCfgNode.angularPluginIcon(None))

            pluginDetails.append(
                PluginDetail(pluginRootDir=plugin.rootDir,
                             pluginName=plugin.name,
                             pluginTitle=plugin.title,
                             angularFrontendAppDir=angularFrontendAppDir,
                             angularFrontendModuleDir=angularFrontendModuleDir,
                             angularFrontendAssetsDir=angularFrontendAssetsDir,
                             angularMainModule=angularMainModule,
                             angularRootModule=angularRootModule,
                             angularRootService=angularRootService,
                             angularPluginIcon=angularPluginIcon,
                             showPluginHomeLink=showPluginHomeLink,
                             showPluginInTitleBar=showPluginInTitleBar,
                             titleBarLeft=titleBarLeft,
                             titleBarText=titleBarText)
            )

        pluginDetails.sort(key=lambda x: x.pluginName)
        return pluginDetails

    def _writePluginHomeLinks(self, feAppDir: str,
                              pluginDetails: [PluginDetail]) -> None:
        """
        export const homeLinks = [
            {
                name: 'plugin_noop',
                title: "Noop",
                resourcePath: "/peek_plugin_noop",
                pluginIconPath: "/peek_plugin_noop/home_icon.png"
            }
        ];
        """

        links = []
        for pluginDetail in pluginDetails:
            if not (pluginDetail.angularMainModule and pluginDetail.showPluginHomeLink):
                continue

            links.append(dict(name=pluginDetail.pluginName,
                              title=pluginDetail.pluginTitle,
                              resourcePath="/%s" % pluginDetail.pluginName,
                              pluginIconPath=pluginDetail.angularPluginIcon))

        contents = "// This file is auto generated, the git version is blank and .gitignored\n"
        contents += "export const homeLinks = %s;\n" % json.dumps(
            links, sort_keys=True, indent=4, separators=(', ', ': '))

        self._writeFileIfRequired(feAppDir, 'plugin-home-links.ts', contents)

    def _writePluginTitleBarLinks(self, feAppDir: str,
                                  pluginDetails: [PluginDetail]) -> None:
        """
        
        import {TitleBarLink} from "@synerty/peek-client-fe-util";

        export const titleBarLinks :TitleBarLink = [
            {
                plugin : "peek_plugin_noop",
                text: "Noop",
                left: false,
                resourcePath: "/peek_plugin_noop/home_icon.png",
                badgeCount : null
            }
        ];
        """

        links = []
        for pluginDetail in pluginDetails:
            if not (pluginDetail.angularMainModule and pluginDetail.showPluginInTitleBar):
                continue

            links.append(dict(plugin=pluginDetail.pluginName,
                              text=pluginDetail.titleBarText,
                              left=pluginDetail.titleBarLeft,
                              resourcePath="/%s" % pluginDetail.pluginName,
                              badgeCount=None))

        contents = "// This file is auto generated, the git version is blank and .gitignored\n\n"
        contents += "import {TitleBarLink} from '@synerty/peek-client-fe-util';\n\n"
        contents += "export const titleBarLinks :TitleBarLink[] = %s;\n" % json.dumps(
            links, sort_keys=True, indent=4, separators=(', ', ': '))

        self._writeFileIfRequired(feAppDir, 'plugin-title-bar-links.ts', contents)

    def _writePluginRouteLazyLoads(self, feAppDir: str,
                                   pluginDetails: [PluginDetail]) -> None:
        """
        export const pluginRoutes = [
            {
                path: 'plugin_noop',
                loadChildren: "plugin-noop/plugin-noop.module#default"
            }
        ];
        """
        routes = []
        for pluginDetail in pluginDetails:
            if not pluginDetail.angularMainModule:
                continue
            routes.append(_routesTemplate
                          % (pluginDetail.pluginName,
                             pluginDetail.pluginName,
                             pluginDetail.angularMainModule))

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += "export const pluginRoutes = ["
        routeData += ",".join(routes)
        routeData += "\n];\n"

        self._writeFileIfRequired(feAppDir, 'plugin-routes.ts', routeData)

    def _writePluginRootModules(self, feAppDir: str,
                                pluginDetails: [PluginDetail],
                                serviceName: str) -> None:

        imports = []
        modules = []
        for pluginDetail in pluginDetails:
            if not pluginDetail.angularRootModule:
                continue
            imports.append('import {%s} from "@%s/%s/%s";'
                           % (pluginDetail.angularRootModule["class"],
                              serviceName,
                              pluginDetail.pluginName,
                              pluginDetail.angularRootModule["file"]))
            modules.append(pluginDetail.angularRootModule["class"])

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += '\n'.join(imports) + '\n'
        routeData += "export const pluginRootModules = [\n\t"
        routeData += ",\n\t".join(modules)
        routeData += "\n];\n"

        self._writeFileIfRequired(feAppDir, 'plugin-root-modules.ts', routeData)

    def _writePluginRootServices(self, feAppDir: str,
                                 pluginDetails: [PluginDetail],
                                 serviceName: str) -> None:

        imports = []
        services = []
        for pluginDetail in pluginDetails:
            if not pluginDetail.angularRootService:
                continue
            imports.append('import {%s} from "@%s/%s/%s";'
                           % (pluginDetail.angularRootService["class"],
                              serviceName,
                              pluginDetail.pluginName,
                              pluginDetail.angularRootService["file"]))
            services.append(pluginDetail.angularRootService["class"])

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += '\n'.join(imports) + '\n'
        routeData += "export const pluginRootServices = [\n\t"
        routeData += ",\n\t".join(services)
        routeData += "\n];\n"

        self._writeFileIfRequired(feAppDir, 'plugin-root-services.ts', routeData)

    def _writeFileIfRequired(self, dir, fileName, contents):
        fullFilePath = os.path.join(dir, fileName)

        # Since writing the file again changes the date/time,
        # this messes with the self._recompileRequiredCheck
        if os.path.isfile(fullFilePath):
            with open(fullFilePath, 'r') as f:
                if contents == f.read():
                    logger.debug("%s is up to date", fileName)
                    return

        logger.debug("Writing new %s", fileName)

        with open(fullFilePath, 'w') as f:
            f.write(contents)

    def _syncPluginFiles(self, targetDir: str,
                         pluginDetails: [PluginDetail],
                         attrName: str) -> None:

        if not os.path.exists(targetDir):
            os.mkdir(targetDir)  # The parent must exist

        # Remove all the old symlinks
        for item in os.listdir(targetDir):
            path = os.path.join(targetDir, item)
            if item.startswith("peek_plugin_"):
                if os.path.islink(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

        for pluginDetail in pluginDetails:
            frontendDir = getattr(pluginDetail, attrName, None)
            if not frontendDir:
                continue

            srcDir = os.path.join(pluginDetail.pluginRootDir, frontendDir)
            if not os.path.exists(srcDir):
                logger.warning("%s FE dir %s doesn't exist",
                               pluginDetail.pluginName, frontendDir)
                continue

            linkPath = os.path.join(targetDir, pluginDetail.pluginName)

            self._addSyncMapping(srcDir, linkPath)

    def _addSyncMapping(self, srcDir, dstDir):
        self._dirSyncMap.append((srcDir, dstDir))

    def _fileCopier(self, src, dst):
        dstFile = shutil.copy2(src, dst)
        self._syncFileHook(dstFile)

    def startFileSyncWatcher(self):
        self._fileWatchdogObserver = WatchdogObserver()

        for srcDir, dstDir in self._dirSyncMap:
            self._fileWatchdogObserver.schedule(
                _FileChangeHandler(self._syncFileHook, srcDir, dstDir),
                srcDir, recursive=True)
        self._fileWatchdogObserver.start()

    def stopFileSyncWatcher(self):
        self._fileWatchdogObserver.stop()
        self._fileWatchdogObserver.join()
        self._fileWatchdogObserver = None

    def syncFiles(self):
        for srcDir, dstDir in self._dirSyncMap:
            if os.path.exists(dstDir):
                shutil.rmtree(dstDir)

            shutil.copytree(srcDir, dstDir, copy_function=self._fileCopier)

    @abstractmethod
    def _syncFileHook(self, fileName: str):
        """ Sync File Hook
        
        This method is called after each file is sync'd, allowing the files to be 
        modified for a particular build.
        
        EG, Replace 
            templateUrl: "app.component.web.html"
        with
            templateUrl: "app.component.ns.html"
        
        """
        pass

    def _updatePackageJson(self, targetJson: str,
                           pluginDetails: [PluginDetail],
                           serviceName: str) -> None:

        # Remove all the old symlinks

        with open(targetJson, 'r') as f:
            jsonData = json.load(f)

        dependencies = jsonData["dependencies"]
        for key in list(dependencies):
            if key.startswith('@' + serviceName):
                del dependencies[key]

        for pluginDetail in pluginDetails:
            if not pluginDetail.angularFrontendModuleDir:
                continue

            moduleDir = os.path.join(pluginDetail.pluginRootDir,
                                     pluginDetail.angularFrontendModuleDir)

            name = "@%s/%s" % (serviceName, pluginDetail.pluginName)
            dependencies[name] = "file:" + moduleDir

        with open(targetJson, 'w') as f:
            json.dump(jsonData, f, sort_keys=True, indent=2, separators=(',', ': '))

    def _recompileRequiredCheck(self, feSrcDir: str) -> bool:
        """ Recompile Check

        This command lists the details of the source dir to see if a recompile is needed

        The find command outputs the following

        543101    0 -rw-r--r--   1 peek     sudo            0 Nov 29 17:27 ./src/app/environment/environment.component.css
        543403    4 drwxr-xr-x   2 peek     sudo         4096 Dec  2 17:37 ./src/app/environment/env-worker
        543446    4 -rw-r--r--   1 peek     sudo         1531 Dec  2 17:37 ./src/app/environment/env-worker/env-worker.component.html

        """
        ignore = (".git", ".idea", "dist", '__pycache__')
        ignore = ["'%s'" % i for i in ignore]  # Surround with quotes
        grep = "grep -v -e %s " % ' -e '.join(ignore)  # Xreate the grep command
        cmd = "find -L %s -type f -ls | %s" % (feSrcDir, grep)
        commandComplete = subprocess.run(cmd,
                                         executable=PeekPlatformConfig.config.bashLocation,
                                         stdout=PIPE, stderr=PIPE, shell=True)

        if commandComplete.returncode:
            for line in commandComplete.stdout.splitlines():
                logger.error(line)
            for line in commandComplete.stderr.splitlines():
                logger.error(line)
            raise Exception("Frontend compile diff check failed")

        logger.debug("Frontend compile diff check ran ok")

        newHash = commandComplete.stdout
        fileHash = ""

        if os.path.isfile(self._hashFileName):
            with open(self._hashFileName, 'rb') as f:
                fileHash = f.read()

        fileHashLines = set(fileHash.splitlines())
        newHashLines = set(newHash.splitlines())
        changes = False

        for line in fileHashLines - newHashLines:
            changes = True
            logger.debug("Removed %s" % line)

        for line in newHashLines - fileHashLines:
            changes = True
            logger.debug("Added %s" % line)

        if changes:
            with open(self._hashFileName, 'wb') as f:
                f.write(newHash)

        return changes

    def _compileFrontend(self, feSrcDir: str) -> None:
        """ Compile the frontend

        this runs `ng build`

        We need to use a pty otherwise webpack doesn't run.

        """

        if not self._recompileRequiredCheck(feSrcDir):
            logger.info("Frondend has not changed, recompile not required.")
            return

        logger.info("Rebuilding frontend distribution")

        try:
            parser = PtyOutParser(loggingStartMarker="Hash: ")
            spawnPty("cd %s && ng build" % feSrcDir, parser)
            logger.info("Frontend distribution rebuild complete.")

        except Exception as e:
            logSpawnException(e)
            os.remove(self._hashFileName)

            # Update the detail of the exception and raise it
            e.message = "The angular frontend failed to build."
            raise


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, syncFileHook, srcDir: str, dstDir: str):
        self._syncFileHook = syncFileHook
        self._srcDir = srcDir
        self._dstDir = dstDir

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent) or event.src_path.endswith("__"):
            return
        pass

    def on_deleted(self, event):
        if not isinstance(event, FileDeletedEvent) or event.src_path.endswith("__"):
            return
        pass

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent) or event.src_path.endswith("__"):
            return

        srcFilePath = event.src_path
        dstFilePath = self._dstDir + event.src_path[len(self._srcDir):]
        shutil.copy2(srcFilePath, dstFilePath)
        self._syncFileHook(dstFilePath)

    def on_moved(self, event):
        if not isinstance(event, FileMovedEvent) or event.src_path.endswith("__"):
            return
