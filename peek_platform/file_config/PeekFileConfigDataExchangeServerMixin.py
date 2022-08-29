import os
from typing import Optional

from jsoncfg.value_mappers import require_bool
from jsoncfg.value_mappers import require_integer
from jsoncfg.value_mappers import require_string

from peek_platform.file_config.PeekFileConfigPlatformMixin import (
    PeekFileConfigPlatformMixin,
)


class PeekFileConfigDataExchangeServerMixin:
    def __init__(
        self, config: PeekFileConfigPlatformMixin, name: str, defaultPort: int
    ):
        self._config = config
        self._name = name
        self._defaultPort = defaultPort

    @property
    def sitePort(self) -> int:
        with self._config._cfg as c:
            return c.httpServer[self._name].sitePort(
                self._defaultPort, require_integer
            )

    @property
    def useSsl(self) -> bool:
        with self._config._cfg as c:
            return c.httpServer[self._name].useSsl(False, require_bool)

    @property
    def sslEnableMutualTLS(self) -> Optional[bool]:
        with self._config._cfg as c:
            return c.httpServer[self._name].sslEnableMutualTLS(
                False, require_bool
            )

    @property
    def sslBundleFilePath(self) -> Optional[str]:
        default = os.path.join(self._config._homePath, "key-cert-cachain.pem")
        with self._config._cfg as c:
            file = c.httpServer[self._name].sslBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None

    @property
    def sslMutualTLSCertificateAuthorityBundleFilePath(self) -> Optional[str]:
        default = os.path.join(
            self._config._homePath,
            f"root-cas.pem",
        )
        with self._config._cfg as c:
            file = c.httpServer[
                self._name
            ].sslMutualTLSCertificateAuthorityBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None

    @property
    def sslMutualTLSTrustedPeerCertificateBundleFilePath(
        self,
    ) -> Optional[str]:
        default = os.path.join(
            self._config._homePath,
            "certs-of-peers.pem",
        )
        with self._config._cfg as c:
            file = c.httpServer[
                self._name
            ].sslMutualTLSTrustedPeerCertificateBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None
