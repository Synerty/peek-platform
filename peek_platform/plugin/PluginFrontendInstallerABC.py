import logging
import os
import subprocess
from collections import namedtuple
from subprocess import PIPE

from jsoncfg.value_mappers import require_string

from peek_platform import PeekPlatformConfig
from peek_platform.WindowsPatch import isWindows
from peek_platform.file_config.PeekFileConfigFrontendDirMixin import \
    PeekFileConfigFrontendDirMixin
from peek_platform.file_config.PeekFileConfigOsMixin import PeekFileConfigOsMixin
from peek_platform.util.PtyUtil import PtyOutParser, spawnPty, logSpawnException
from peek_plugin_base.PluginPackageFileConfig import PluginPackageFileConfig

logger = logging.getLogger(__name__)

PluginDetail = namedtuple("PluginDetail",
                          ["pluginRootDir", "pluginName", "angularFrontendDir",
                           "angularMainModule"])


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

    @property
    def pluginFrontendTitleUrls(self):
        """ Plugin Admin Name Urls

        @:returns a list of tuples (pluginName, pluginTitle, pluginUrl)
        """
        data = []
        for plugin in list(self._loadedPlugins.values()):
            data.append((plugin.name, plugin.title, "/%s" % plugin.name))

        return data

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

        self._hashFileName = os.path.join(os.path.dirname(feSrcDir), ".lastHash")

        pluginDetails = self._loadPluginConfigs()

        self._writePluginRouteLazyLoads(feSrcDir, pluginDetails)
        self._relinkPluginDirs(feSrcDir, pluginDetails)
        self._compileFrontend(feSrcDir)

    def _loadPluginConfigs(self) -> [PluginDetail]:
        pluginDetails = []

        for plugin in self._loadedPlugins.values():
            assert isinstance(plugin.packageCfg, PluginPackageFileConfig)
            pluginPackageConfig = plugin.packageCfg.config

            angularFrontendDir = (pluginPackageConfig[self._platformService]
                                  .angularFrontendDir(require_string))

            angularMainModule = (pluginPackageConfig[self._platformService]
                                 .angularMainModule(require_string))

            pluginDetails.append(
                PluginDetail(pluginRootDir=plugin.rootDir,
                             pluginName=plugin.name,
                             angularFrontendDir=angularFrontendDir,
                             angularMainModule=angularMainModule)
            )

        return pluginDetails

    def _writePluginRouteLazyLoads(self, feSrcDir: str,
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
            routes.append(
                """
                {
                    path: '%s',
                    loadChildren: "%s/%s#default"
                }
                """ % (pluginDetail.pluginName,
                       pluginDetail.pluginName,
                       pluginDetail.angularMainModule))

        pluginRoutesTs = os.path.join(feSrcDir, 'PluginRoutes.ts')

        routeData = "// This file is auto generated, the git version is blank and .gitignored\n"
        routeData += "export const pluginRoutes = [\n"
        routeData += ",\n".join(routes)
        routeData += "];\n"

        # Since writing the file again changes the date/time,
        # this messes with the self._recompileRequiredCheck
        with open(pluginRoutesTs, 'r') as f:
            if routeData == f.read():
                logger.debug("PluginRoutes.ts is up to date")
                return

        logger.debug("Writing new PluginRoutes.ts")
        with open(pluginRoutesTs, 'w') as f:
            f.write(routeData)

    def _relinkPluginDirs(self, feSrcDir: str, pluginDetails: [PluginDetail]) -> None:
        # Remove all the old symlinks

        for item in os.listdir(feSrcDir):
            path = os.path.join(feSrcDir, item)
            if item.startswith("peek_plugin_") and os.path.islink(path):
                os.remove(path)

        for pluginDetail in pluginDetails:
            srcDir = os.path.join(pluginDetail.pluginRootDir,
                                  pluginDetail.angularFrontendDir)
            linkPath = os.path.join(feSrcDir, pluginDetail.pluginName)
            os.symlink(srcDir, linkPath, target_is_directory=True)

    def _recompileRequiredCheck(self, feSrcDir: str) -> bool:
        """ Recompile Check

        This command lists the details of the source dir to see if a recompile is needed

        The find command outputs the following

        543101    0 -rw-r--r--   1 peek     sudo            0 Nov 29 17:27 ./src/app/environment/environment.component.css
        543403    4 drwxr-xr-x   2 peek     sudo         4096 Dec  2 17:37 ./src/app/environment/env-worker
        543446    4 -rw-r--r--   1 peek     sudo         1531 Dec  2 17:37 ./src/app/environment/env-worker/env-worker.component.html

        """
        ignore = (".git", ".idea", "dist")
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
