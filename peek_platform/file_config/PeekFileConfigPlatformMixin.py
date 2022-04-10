import logging
import os
import time
from abc import ABCMeta
import random
from typing import Optional

from jsoncfg.value_mappers import (
    require_string,
    RequireType,
    require_list,
    require_bool,
    require_integer,
)

from peek_platform.file_config.PeekFileConfigABC import PEEK_AGENT_SERVICE
from peek_platform.file_config.PeekFileConfigABC import PEEK_FIELD_SERVICE
from peek_platform.file_config.PeekFileConfigABC import PEEK_LOGIC_SERVICE
from peek_platform.file_config.PeekFileConfigABC import PEEK_OFFICE_SERVICE
from peek_platform.file_config.PeekFileConfigABC import PEEK_WORKER_SERVICE

logger = logging.getLogger(__name__)


class PeekFileConfigPlatformMixin(metaclass=ABCMeta):
    # --- Platform Logging

    @property
    def loggingDebugMemoryMask(self) -> int:
        with self._cfg as c:
            return c.logging.debugMemoryMask(0, require_integer)

    @property
    def loggingLevel(self) -> str:
        with self._cfg as c:
            lvl = c.logging.level("INFO", require_string)
            if lvl in logging._nameToLevel:
                return lvl

            logger.warning(
                "Logging level %s is not valid, defauling to INFO", lvl
            )
            return "INFO"

    @property
    def logToStdout(self) -> str:
        with self._cfg as c:
            return c.logging.logToStdout(False, require_bool)

    @property
    def daysToKeep(self) -> int:
        with self._cfg as c:
            val = c.logging.daysToKeep(14, require_integer)

            # As of v3.1+ cleanup the old log file properties
            for prop in ("rotateSizeMb", "rotationsToKeep"):
                if prop in c.logging:
                    logging = {}
                    logging.update(iter(c.logging))
                    del logging[prop]
                    c.logging = logging

            return val

    @property
    def loggingLogToSyslogHost(self) -> Optional[str]:
        with self._cfg as c:
            return c.logging.syslog.logToSysloyHost(None)

    @property
    def loggingLogToSyslogPort(self) -> int:
        with self._cfg as c:
            return c.logging.syslog.logToSysloyPort(514, require_integer)

    @property
    def loggingLogToSyslogFacility(self) -> str:
        with self._cfg as c:
            return c.logging.syslog.logToSysloyProtocol("user", require_string)

    @property
    def twistedThreadPoolSize(self) -> int:
        with self._cfg as c:
            count = c.twisted.threadPoolSize(500, require_integer)

        # Ensure the thread count is high
        if count < 50:
            logger.info("Upgrading thread count from %s to %s", count, 500)
            count = 500
            with self._cfg as c:
                c.twisted.threadPoolSize = count

        return count

    @property
    def autoPackageUpdate(self):
        with self._cfg as c:
            return c.platform.autoPackageUpdate(True, require_bool)

    # --- Platform Tmp Path
    @property
    def tmpPath(self):
        default = os.path.join(self._homePath, "tmp")
        with self._cfg as c:
            return self._chkDir(c.disk.tmp(default, require_string))

    # --- Platform Software Path
    @property
    def platformSoftwarePath(self):
        default = os.path.join(self._homePath, "platform_software")
        with self._cfg as c:
            return self._chkDir(
                c.platform.softwarePath(default, require_string)
            )

    # --- Platform Version
    @property
    def platformVersion(self):
        with self._cfg as c:
            return c.platform.version("0.0.0", require_string)

    @platformVersion.setter
    def platformVersion(self, value):
        with self._cfg as c:
            c.platform.version = value

    # --- Plugin Software Path
    @property
    def pluginSoftwarePath(self):
        default = os.path.join(self._homePath, "plugin_software")
        with self._cfg as c:
            return self._chkDir(c.plugin.softwarePath(default, require_string))

    # --- Plugin Data Path
    def pluginDataPath(self, pluginName):
        default = os.path.join(self._homePath, "plugin_data")

        with self._cfg as c:
            pluginData = c.plugin.dataPath(default, require_string)

        return self._chkDir(os.path.join(pluginData, pluginName))

    # --- Plugin Software Version
    def pluginVersion(self, pluginName):
        """Plugin Version

        The last version that we know about
        """
        with self._cfg as c:
            return c.plugin[pluginName].version(
                None, RequireType(type(None), str)
            )

    def setPluginVersion(self, pluginName, version):
        with self._cfg as c:
            c.plugin[pluginName].version = version

    # --- Plugins Installed
    @property
    def pluginsEnabled(self):
        with self._cfg as c:
            return c.plugin.enabled([], require_list)

    @pluginsEnabled.setter
    def pluginsEnabled(self, value):
        with self._cfg as c:
            c.plugin.enabled = value

    # --- Manhole
    @property
    def manholeEnabled(self) -> str:
        with self._cfg as c:
            return c.logging.manhole.enabled(True, require_bool)

    @property
    def manholePort(self) -> int:
        from peek_platform import PeekPlatformConfig

        port = {
            PEEK_LOGIC_SERVICE: 2201,
            PEEK_WORKER_SERVICE: 2202,
            PEEK_AGENT_SERVICE: 2203,
            PEEK_FIELD_SERVICE: 2204,
            PEEK_OFFICE_SERVICE: 2205,
        }[PeekPlatformConfig.componentName]
        with self._cfg as c:
            return c.logging.manhole.port(port, require_integer)

    @property
    def manholePassword(self) -> str:
        default = str(random.getrandbits(int(time.time() * 10**6 % 100000)))[
            :32
        ]
        with self._cfg as c:
            return c.logging.manhole.password(default, require_string)

    @property
    def manholePublicKeyFile(self) -> str:
        return self._ensureMaholeKeysExist()[0]

    @property
    def manholePrivateKeyFile(self) -> str:
        return self._ensureMaholeKeysExist()[1]

    def _ensureMaholeKeysExist(self) -> (str, str):
        with self._cfg as c:
            privateDefault = os.path.join(self._homePath, "manhole-key")
            priFile = c.logging.manhole.privateKeyFile(
                privateDefault, require_string
            )

            publicDefault = os.path.join(self._homePath, "manhole-key.pub")
            pubFile = c.logging.manhole.publicKeyFile(
                publicDefault, require_string
            )

            if not os.path.exists(priFile) or not os.path.exists(pubFile):
                self._manholeCreateKeys(priFile, pubFile)

            return pubFile, priFile

    def _manholeCreateKeys(self, priFile, pubFile):
        logger.info("(Re)Creating Manhole SSH Server Keys")

        from cryptography.hazmat.primitives import (
            serialization as crypto_serialization,
        )
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import (
            default_backend as crypto_default_backend,
        )

        key = rsa.generate_private_key(
            backend=crypto_default_backend(),
            public_exponent=65537,
            key_size=2048,
        )
        privateKey = key.private_bytes(
            crypto_serialization.Encoding.PEM,
            crypto_serialization.PrivateFormat.TraditionalOpenSSL,
            crypto_serialization.NoEncryption(),
        ).decode()
        publicKey = (
            key.public_key()
            .public_bytes(
                crypto_serialization.Encoding.OpenSSH,
                crypto_serialization.PublicFormat.OpenSSH,
            )
            .decode()
        )

        from peek_platform import PeekPlatformConfig

        publicKey += " Peek %s Manhole" % PeekPlatformConfig.componentName

        with open(pubFile, "w") as f:
            f.write(publicKey)

        with open(priFile, "w") as f:
            f.write(privateKey)
