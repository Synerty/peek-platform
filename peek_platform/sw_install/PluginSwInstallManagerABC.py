"""
 *
 *  Copyright Synerty Pty Ltd 2013
 *
 *  This software is proprietary, you are not free to copy
 *  or redistribute this code in any format.
 *
 *  All rights to this software are reserved by 
 *  Synerty Pty Ltd
 *
"""
import logging
import os
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from abc import ABCMeta, abstractmethod
from typing import Optional

from pytmpdir.Directory import Directory
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks
from txhttputil.downloader.HttpFileDownloader import HttpFileDownloader
from vortex.Payload import deferToThreadWrap

from peek_platform import PeekPlatformConfig
from peek_platform.file_config.PeekFileConfigPlatformMixin import \
    PeekFileConfigPlatformMixin
from peek_platform.util.PtyUtil import spawnPty, logSpawnException

logger = logging.getLogger(__name__)

PLUGIN_PACKAGE_JSON = "plugin_package.json"


class PluginSwInstallManagerABC(metaclass=ABCMeta):
    """ Plugin Software Install Manager ABC

    This class handles the downloading and installing of platform plugin updates.

    """

    def __init__(self):
        pass

    @classmethod
    def makePipArgs(cls, fileName: str) -> [str]:
        """ Make PIP Args

        This method creates the install arg list for pip, it's used for
        testing and installing

        :param fileName: The full fileName of the package to install
        :return: The list of arguments to pass to pip
        """

        # Create and return the pip args
        return ['install',  # Install the packages
                '--force-reinstall',  # Reinstall if they already exist
                '--no-cache-dir',  # Don't use the local pip cache
                '--no-index',  # Work offline, don't use pypi
                fileName
                ]

    @inlineCallbacks
    def update(self, pluginName: str, targetVersion: str) -> Optional[str]:
        """ Update

        This method is called when this service detects that a newer version of a plugin
        is availible.

        :param pluginName: The name of the plugin to update
        :param targetVersion: The version to update to.
        :return: The version updated to.
        """

        logger.info("Updating %s to %s", pluginName, targetVersion)

        from peek_platform import PeekPlatformConfig

        url = ('http://%(ip)s:%(port)s/peek_server.sw_install.plugin.download?'
               ) % {"ip": PeekPlatformConfig.config.peekServerHost,
                    "port": PeekPlatformConfig.config.peekServerPort}

        args = {"name": pluginName}
        if targetVersion:
            args["version"] = str(targetVersion)

        url += urllib.parse.urlencode(args)

        try:

            file = yield HttpFileDownloader(url).run()

            if os.path.getsize(file.name) == 0:
                logger.warning(
                    "Peek server doesn't have any updates for plugin %s, version %s",
                    pluginName, targetVersion)
                return

            yield self.installAndReload(pluginName, targetVersion, file.name)

        except Exception as e:
            logger.exception(e)
            raise

        defer.returnValue(targetVersion)

    @deferToThreadWrap
    def installAndReload(self, pluginName: str, targetVersion: str,
                         fullTarPath: str) -> None:

        assert isinstance(PeekPlatformConfig.config, PeekFileConfigPlatformMixin)

        if not tarfile.is_tarfile(fullTarPath):
            raise Exception("Plugin update %s download is not a tar file" % pluginName)

        directory = Directory()
        tarfile.open(fullTarPath).extractall(directory.path)
        directory.scan()

        # CHECK 1
        pkgInfoFile = self._getFileForFileName("PKG-INFO", directory)

        # CHECK 2
        pkgVersion = None
        with pkgInfoFile.open() as f:
            for line in f:
                if line.startswith("Version: "):
                    pkgVersion = line.split(':')[1].strip()

        if not pkgVersion:
            raise Exception("Unable to determine package version")

        if pkgVersion != targetVersion:
            raise Exception("Plugin %s trget version is %s actual version is %s"
                            % (pluginName, targetVersion, pkgVersion))

        self._pipInstall(fullTarPath)

        PeekPlatformConfig.config.setPluginVersion(pluginName, targetVersion)

        ####
        # FIXME : This will always enabled the Plugin and overwrite config changes
        PeekPlatformConfig.config.pluginsEnabled = list(set(
            PeekPlatformConfig.config.pluginsEnabled + [pluginName]))

        # RELOAD PLUGIN
        reactor.callLater(0, self.notifyOfPluginVersionUpdate, pluginName, targetVersion)

    def _pipInstall(self, fileName: str) -> None:
        """ Pip Install Plugin

        Runs the PIP install for the packages provided in the directory

        :param fileName: The full path and filename of the package to install
        :return: None

        """

        pipExec = os.path.join(os.path.dirname(sys.executable), "pip")

        pipArgs = [sys.executable, pipExec] + self.makePipArgs(fileName)

        # # The platform update is tested for dependencies when it's first uploaded
        # # PIP has a bug, when you have updated packages for several dependent files
        # #   and try to install them all at once, some of the packages don't update.
        # pipArgs += ['--no-deps']

        pipArgs = ' '.join(pipArgs)

        try:
            spawnPty(pipArgs)
            logger.info("Peek plugin update complete.")

        except Exception as e:
            logSpawnException(e)

            # Update the detail of the exception and raise it
            e.message = "Failed to install new plugin package."
            raise

    @abstractmethod
    def notifyOfPluginVersionUpdate(self, pluginName: str, targetVersion: str) -> None:
        """ Notify of Plugin Version Update

        This method is called when a package update has comleted, it notifies the
        service (implementer).

        :param pluginName: The name of the plugin being updated
        :param targetVersion" The version being updated to
        """
        pass
