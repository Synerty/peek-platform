import json
import logging
from typing import List, Callable, Optional

import os
import shutil
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from jsoncfg.value_mappers import require_bool

from peek_platform.file_config.PeekFileConfigFrontendDirMixin import \
    PeekFileConfigFrontendDirMixin
from peek_platform.file_config.PeekFileConfigOsMixin import PeekFileConfigOsMixin
from peek_platform.frontend.FrontendFileSync import FrontendFileSync
from peek_plugin_base.PluginPackageFileConfig import PluginPackageFileConfig

logger = logging.getLogger(__name__)

# Quiten the file watchdog
logging.getLogger("watchdog.observers.inotify_buffer").setLevel(logging.INFO)

PluginDetail = namedtuple("PluginDetail",
                          ["pluginRootDir",
                           "pluginName",
                           "pluginTitle",
                           "appDir",
                           "appModule",
                           "moduleDir",
                           "assetDir",
                           "rootModules",
                           "rootServices",
                           "icon",
                           "showHomeLink",
                           "showInTitleBar",
                           "titleBarLeft",
                           "titleBarText"])

_routesTemplate = """
    {
        path: '%s',
        loadChildren: "%s/%s"
    }"""


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
        assert platformService in ("peek-mobile", "peek-admin", "peek-desktop"), (
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

        self.fileSync = FrontendFileSync(lambda f, c: self._syncFileHook(f, c))
        self._dirSyncMap = list()
        self._fileWatchdogObserver = None

    def _loadPluginConfigs(self) -> [PluginDetail]:
        pluginDetails = []

        for plugin in self._loadedPlugins:
            assert isinstance(plugin.packageCfg, PluginPackageFileConfig)
            pluginPackageConfig = plugin.packageCfg.config

            jsonCfgNode = pluginPackageConfig[self._platformService.replace('peek-', '')]

            enabled = (jsonCfgNode.enableAngularFrontend(True, require_bool))

            if not enabled:
                continue

            appDir = jsonCfgNode.appDir(None)
            moduleDir = jsonCfgNode.moduleDir(None)
            assetDir = jsonCfgNode.assetDir(None)
            appModule = jsonCfgNode.appModule(None)

            showHomeLink = jsonCfgNode.showHomeLink(True)
            showInTitleBar = jsonCfgNode.showInTitleBar(False)
            titleBarLeft = jsonCfgNode.titleBarLeft(False)
            titleBarText = jsonCfgNode.titleBarText(None)

            def checkThing(name, data):
                sub = (name, plugin.name)
                if data:
                    assert data["file"], "%s.file is missing for %s" % sub
                    assert data["class"], "%s.class is missing for %s" % sub

                if not data.get("persistent"):
                    data["persistent"] = False

            # Root Modules
            rootModules = jsonCfgNode.rootModules([])
            for rootModule in rootModules:
                checkThing("rootModules", rootModule)

            # Root Services
            rootServices = jsonCfgNode.rootServices([])
            for rootService in rootServices:
                checkThing("rootServices", rootService)

            icon = (jsonCfgNode.icon(None))

            pluginDetails.append(
                PluginDetail(pluginRootDir=plugin.rootDir,
                             pluginName=plugin.name,
                             pluginTitle=plugin.title,
                             appDir=appDir,
                             moduleDir=moduleDir,
                             assetDir=assetDir,
                             appModule=appModule,
                             rootModules=rootModules,
                             rootServices=rootServices,
                             icon=icon,
                             showHomeLink=showHomeLink,
                             showInTitleBar=showInTitleBar,
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
            if not (pluginDetail.appModule and pluginDetail.showHomeLink):
                continue

            links.append(dict(name=pluginDetail.pluginName,
                              title=pluginDetail.pluginTitle,
                              resourcePath="/%s" % pluginDetail.pluginName,
                              pluginIconPath=pluginDetail.icon))

        contents = "// This file is auto generated, the git version is blank and .gitignored\n"
        contents += "export const homeLinks = %s;\n" % json.dumps(
            links, sort_keys=True, indent=4, separators=(', ', ': '))

        self._writeFileIfRequired(feAppDir, 'plugin-home-links.ts', contents)

    def _writePluginTitleBarLinks(self, feAppDir: str,
                                  pluginDetails: [PluginDetail]) -> None:
        """
        
        import {TitleBarLink} from "@synerty/peek-mobile-util";

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
            if not (pluginDetail.appModule and pluginDetail.showInTitleBar):
                continue

            links.append(dict(plugin=pluginDetail.pluginName,
                              text=pluginDetail.titleBarText,
                              left=pluginDetail.titleBarLeft,
                              resourcePath="/%s" % pluginDetail.pluginName,
                              badgeCount=None))

        contents = "// This file is auto generated, the git version is blank and .gitignored\n\n"
        contents += "import {TitleBarLink} from '@synerty/peek-mobile-util';\n\n"
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
            if not pluginDetail.appModule:
                continue
            routes.append(_routesTemplate
                          % (pluginDetail.pluginName,
                             pluginDetail.pluginName,
                             pluginDetail.appModule))

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += "export const pluginRoutes = ["
        routeData += ",".join(routes)
        routeData += "\n];\n"

        self._writeFileIfRequired(feAppDir, 'plugin-routes.ts', routeData)

    def _writePluginRootModules(self, feAppDir: str,
                                pluginDetails: [PluginDetail]) -> None:

        # initiliase the arrays, and put in the persisten service module
        imports = ['''import {PluginRootServicePersistentLoadModule} 
                        from "./plugin-root-services";''']
        modules = ['PluginRootServicePersistentLoadModule']

        for pluginDetail in pluginDetails:
            for rootModule in pluginDetail.rootModules:
                imports.append('import {%s} from "@peek/%s/%s";'
                               % (rootModule["class"],
                                  pluginDetail.pluginName,
                                  rootModule["file"]))
                modules.append(rootModule["class"])

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += '\n'.join(imports) + '\n'
        routeData += "export const pluginRootModules = [\n\t"
        routeData += ",\n\t".join(modules)
        routeData += "\n];\n"

        self._writeFileIfRequired(feAppDir, 'plugin-root-modules.ts', routeData)

    def _writePluginRootServices(self, feAppDir: str,
                                 pluginDetails: [PluginDetail]) -> None:

        imports = []
        services = []
        persistentServices = []
        for pluginDetail in pluginDetails:
            for rootService in pluginDetail.rootServices:
                imports.append('import {%s} from "@peek/%s/%s";'
                               % (rootService["class"],
                                  pluginDetail.pluginName,
                                  rootService["file"]))
                services.append(rootService["class"])
                if rootService["persistent"]:
                    persistentServices.append(rootService["class"])

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += '\n'.join(imports) + '\n'
        routeData += "export const pluginRootServices = [\n\t"
        routeData += ",\n\t".join(services)
        routeData += "\n];\n"

        routeData += '''
        import {NgModule} from "@angular/core";

        @NgModule({
        
        })
        export class PluginRootServicePersistentLoadModule {
            constructor(%s){
        
            }
        
        }
        ''' % ', '.join(['private _%s:%s' % (s, s) for s in persistentServices])

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
                         attrName: str,
                         preSyncCallback: Optional[Callable[[], None]] = None,
                         postSyncCallback: Optional[Callable[[], None]] = None,
                         keepExtraDstJsAndMapFiles=False,
                         excludeFilesRegex=()) -> None:

        if not os.path.exists(targetDir):
            os.mkdir(targetDir)  # The parent must exist

        # Make a note of the existing items
        currentItems = set()
        createdItems = set()
        for item in os.listdir(targetDir):
            if item.startswith("peek_plugin_"):
                currentItems.add(item)

        for pluginDetail in pluginDetails:
            frontendDir = getattr(pluginDetail, attrName, None)
            if not frontendDir:
                continue

            srcDir = os.path.join(pluginDetail.pluginRootDir, frontendDir)
            if not os.path.exists(srcDir):
                logger.warning("%s FE dir %s doesn't exist",
                               pluginDetail.pluginName, frontendDir)
                continue

            createdItems.add(pluginDetail.pluginName)

            linkPath = os.path.join(targetDir, pluginDetail.pluginName)
            self.fileSync.addSyncMapping(srcDir, linkPath,
                                         keepExtraDstJsAndMapFiles=keepExtraDstJsAndMapFiles,
                                         preSyncCallback=preSyncCallback,
                                         postSyncCallback=postSyncCallback,
                                         excludeFilesRegex=excludeFilesRegex)

        # Delete the items that we didn't create
        for item in currentItems - createdItems:
            path = os.path.join(targetDir, item)
            if os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    @abstractmethod
    def _syncFileHook(self, fileName: str, contents: bytes) -> bytes:
        """ Sync File Hook
        
        see FrontendFileSync._syncFileHook
        
        """
        pass

    def _updatePackageJson(self, targetJson: str,
                           pluginDetails: [PluginDetail]) -> None:

        serviceName = "@peek"

        # Remove all the old symlinks

        with open(targetJson, 'r') as f:
            jsonData = json.load(f)

        dependencies = jsonData["dependencies"]
        for key in list(dependencies):
            if key.startswith(serviceName):
                del dependencies[key]

        for pluginDetail in pluginDetails:
            if not pluginDetail.moduleDir:
                continue

            moduleDir = os.path.join(pluginDetail.pluginRootDir,
                                     pluginDetail.moduleDir)

            name = "%s/%s" % (serviceName, pluginDetail.pluginName)
            dependencies[name] = "file:///" + moduleDir.replace("\\", '/')

        contents = json.dumps(jsonData, sort_keys=True, indent=2,
                              separators=(',', ': '))

        self._writeFileIfRequired(os.path.dirname(targetJson),
                                  os.path.basename(targetJson),
                                  contents)

    def _recompileRequiredCheck(self, feBuildDir: str, hashFileName: str) -> bool:
        """ Recompile Check

        This command lists the details of the source dir to see if a recompile is needed

        The find command outputs the following

        543101    0 -rw-r--r--   1 peek     sudo            0 Nov 29 17:27 ./src/app/environment/environment.component.css
        543403    4 drwxr-xr-x   2 peek     sudo         4096 Dec  2 17:37 ./src/app/environment/env-worker
        543446    4 -rw-r--r--   1 peek     sudo         1531 Dec  2 17:37 ./src/app/environment/env-worker/env-worker.component.html

        """

        excludeFilesEndWith = (".git", ".idea", '.lastHash')
        excludeFilesStartWith = ()

        def dirCheck(path):
            s = os.path.sep
            excludePathContains = ('__pycache__', 'node_modules', 'platforms', 'dist')

            # Always include the node_modules/@peek module dir
            if path.endswith(s + "@peek") or (s + "@peek" + s) in path:
                return True

            for exPath in excludePathContains:
                # EG "C:\thing\node_modules"
                if path.endswith(s + exPath):
                    return False

                # EG "C:\thing\node_modules\thing"
                if (s + exPath + s) in path:
                    return False

            return True

        fileList = []

        for (path, directories, filenames) in os.walk(feBuildDir):
            if not dirCheck(path):
                continue

            for filename in filenames:
                if [e for e in excludeFilesEndWith if filename.endswith(e)]:
                    continue

                if [e for e in excludeFilesStartWith if filename.startswith(e)]:
                    continue

                fullPath = os.path.join(path, filename)
                relPath = fullPath[len(feBuildDir) + 1:]
                stat = os.stat(fullPath)
                fileList.append('%s %s %s' % (relPath, stat.st_size, stat.st_mtime))

        newHash = '\n'.join(fileList)
        fileHash = ""

        if os.path.isfile(hashFileName):
            with open(hashFileName, 'r') as f:
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
            with open(hashFileName, 'w') as f:
                f.write(newHash)

        return changes
