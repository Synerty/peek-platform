import json
import logging
import os
import shutil
import subprocess
from collections import namedtuple
from subprocess import PIPE

from jsoncfg.value_mappers import require_string, require_bool

from peek_platform import PeekPlatformConfig
from peek_platform.file_config.PeekFileConfigFrontendDirMixin import \
    PeekFileConfigFrontendDirMixin
from peek_platform.file_config.PeekFileConfigOsMixin import PeekFileConfigOsMixin
from peek_platform.util.PtyUtil import PtyOutParser, spawnPty, logSpawnException
from peek_plugin_base.PluginPackageFileConfig import PluginPackageFileConfig

logger = logging.getLogger(__name__)

PluginDetail = namedtuple("PluginDetail",
                          ["pluginRootDir",
                           "pluginName",
                           "pluginTitle",
                           "angularFrontendDir",
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
        loadChildren: "%s/%s#default"
    }"""


class PluginFrontendInstallerABC(object):
    """ Peek App Frontend Installer Mixin

    This class is used for the client and server.

    This class contains the logic for:
        * Linking in the frontend angular components to the frontend project
        * Compiling the frontend project

    :TODO: Use find/sort to generate a string of the files when this was last run.
        Only run it again if anything has changed.

    """

    def __init__(self, platformService: str):
        assert platformService in ("server", "client")
        self._platformService = platformService

    def buildFrontend(self) -> None:

        from peek_platform.plugin.PluginLoaderABC import PluginLoaderABC
        assert isinstance(self, PluginLoaderABC)

        from peek_platform import PeekPlatformConfig
        if not isinstance(PeekPlatformConfig.config, PeekFileConfigFrontendDirMixin):
            raise Exception("The file config must inherit the"
                            " PeekFileConfigFrontendDirMixin")

        from peek_platform import PeekPlatformConfig
        if not isinstance(PeekPlatformConfig.config, PeekFileConfigOsMixin):
            raise Exception("The file config must inherit the"
                            " PeekFileConfigOsMixin")

        from peek_platform import PeekPlatformConfig

        feSrcDir = PeekPlatformConfig.config.feSrcDir
        feAppDir = os.path.join(feSrcDir, 'app')
        feAssetsDir = os.path.join(feSrcDir, 'app', 'assets')
        feNodeModulesDir = os.path.join(os.path.dirname(feSrcDir), 'node_modules')

        self._hashFileName = os.path.join(os.path.dirname(feSrcDir), ".lastHash")

        pluginDetails = self._loadPluginConfigs()

        # Write files that link the plugins into Peek.
        self._writePluginRouteLazyLoads(feAppDir, pluginDetails)
        self._writePluginRootModules(feAppDir, pluginDetails)
        self._writePluginRootServices(feAppDir, pluginDetails)
        self._writePluginHomeLinks(feAppDir, pluginDetails)
        self._writePluginTitleBarLinks(feAppDir, pluginDetails)

        # This link probably isn't nessesary any more
        self._copyOverAssets(feAssetsDir, pluginDetails)

        # This link probably isn't nessesary any more
        self._relinkPluginDirs(feAppDir, pluginDetails)

        # Linking into the node_modules allows plugins to import code from each other.
        self._relinkPluginDirs(feNodeModulesDir, pluginDetails)

        if not PeekPlatformConfig.config.feBuildEnabled:
            logger.warning("Frontend build disabled by config file, Not Building.")
            return

        self._compileFrontend(feSrcDir)

    def _loadPluginConfigs(self) -> [PluginDetail]:
        pluginDetails = []

        for plugin in self._loadedPlugins.values():
            assert isinstance(plugin.packageCfg, PluginPackageFileConfig)
            pluginPackageConfig = plugin.packageCfg.config

            jsonCfgNode = pluginPackageConfig[self._platformService]

            enabled = (jsonCfgNode.enableAngularFrontend(True, require_bool))

            if not enabled:
                continue

            angularFrontendDir = (jsonCfgNode.angularFrontendDir(require_string))
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
                             angularFrontendDir=angularFrontendDir,
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

    def _copyOverAssets(self, assetDir: str,
                              pluginDetails: [PluginDetail]) -> None:
        """ Copy Over Assets
        
        This method finds the images in each plugin and copies them over to the assets
        dir. Assets are included in the ng build.
        
        :param assetDir: The location of the assets directory within the frontend.
        :param pluginDetails: config details of the plugin
        """
        excludeDirs = ()
        includeExts = ('.png', '.jpg', 'jpeg', '.mp3')

        for pluginDetail in pluginDetails:
            pluginName= pluginDetail.pluginName
            pluginFrontendDir = pluginDetail.angularFrontendDir

            srcDir = os.path.join(pluginDetail.pluginRootDir,
                                  pluginDetail.angularFrontendDir)

            # First, delete the existing files
            if os.path.exists(os.path.join(assetDir, pluginFrontendDir)):
                shutil.rmtree(os.path.join(assetDir, pluginFrontendDir))

            for (path, directories, filenames) in os.walk(srcDir):
                if [e for e in excludeDirs if e in path]:
                    continue

                for filename in filenames:
                    if not [e for e in includeExts if filename.endswith(e)]:
                        continue

                    absPath = os.path.join(path, filename)
                    relPath = os.path.join(path[len(srcDir) + 1:], filename)
                    newPath = os.path.join(assetDir, pluginName, relPath)

                    imgAssetDirName = os.path.dirname(newPath)
                    if not os.path.exists(imgAssetDirName):
                        os.makedirs(imgAssetDirName, mode=0o755, exist_ok=True)

                    shutil.copy(absPath, newPath)

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
            links, indent=4, separators=(', ', ': '))

        self._writeFileIfRequired(feAppDir, 'plugin-home-links.ts', contents)

    def _writePluginTitleBarLinks(self, feAppDir: str,
                                  pluginDetails: [PluginDetail]) -> None:
        """
        export const titleBarLinks = [
            {
                text: "Noop",
                left: false,
                resourcePath: "/peek_plugin_noop/home_icon.png"
            }
        ];
        """

        links = []
        for pluginDetail in pluginDetails:
            if not (pluginDetail.angularMainModule and pluginDetail.showPluginInTitleBar):
                continue

            links.append(dict(text=pluginDetail.titleBarText,
                              left=pluginDetail.titleBarLeft,
                              resourcePath="/%s" % pluginDetail.pluginName))

        contents = "// This file is auto generated, the git version is blank and .gitignored\n"
        contents += "export const titleBarLinks = %s;\n" % json.dumps(
            links, indent=4, separators=(', ', ': '))

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
                                pluginDetails: [PluginDetail]) -> None:

        imports = []
        modules = []
        for pluginDetail in pluginDetails:
            if not pluginDetail.angularRootModule:
                continue
            imports.append('import {%s} from "%s/%s";'
                           % (pluginDetail.angularRootModule["class"],
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
                                 pluginDetails: [PluginDetail]) -> None:

        imports = []
        services = []
        for pluginDetail in pluginDetails:
            if not pluginDetail.angularRootService:
                continue
            imports.append('import {%s} from "%s/%s";'
                           % (pluginDetail.angularRootService["class"],
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

    def _relinkPluginDirs(self, targetDir: str, pluginDetails: [PluginDetail]) -> None:
        # Remove all the old symlinks

        for item in os.listdir(targetDir):
            path = os.path.join(targetDir, item)
            if item.startswith("peek_plugin_"):  # and os.path.islink(path):
                os.remove(path)

        for pluginDetail in pluginDetails:
            srcDir = os.path.join(pluginDetail.pluginRootDir,
                                  pluginDetail.angularFrontendDir)
            linkPath = os.path.join(targetDir, pluginDetail.pluginName)
            os.symlink(srcDir, linkPath, target_is_directory=True)

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
