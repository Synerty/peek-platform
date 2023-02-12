import os
from abc import ABCMeta
from typing import Optional

from jsoncfg.value_mappers import require_bool
from jsoncfg.value_mappers import require_string, require_integer

from peek_platform.file_config.PeekFileConfigPlatformMixin import (
    PeekFileConfigPlatformMixin,
)
from peek_plugin_base.PeekPlatformServerInfoHookABC import (
    PeekPlatformServerInfoHookABC,
)


class PeekFileConfigDataExchangeClientMixin(PeekPlatformServerInfoHookABC):
    def __init__(self, config: PeekFileConfigPlatformMixin):
        self._config = config

    ### SERVER SECTION ###
    @property
    def peekServerHttpPort(self) -> int:
        with self._config._cfg as c:
            return c.dataExchange.httpPort(8011, require_integer)

    @property
    def peekServerHost(self) -> str:
        with self._config._cfg as c:
            return c.dataExchange.host("localhost", require_string)

    @property
    def peekServerSSL(self) -> bool:
        return self.peekServerUseSSL

    @property
    def peekServerUseSSL(self) -> bool:
        with self._config._cfg as c:
            return c.dataExchange.useSsl(False, require_bool)

    @property
    def peekServerSSLEnableMutualTLS(self) -> int:
        with self._config._cfg as c:
            return c.dataExchange.sslEnableMutualTLS(False, require_bool)

    @property
    def peekServerSSLClientBundleFilePath(self) -> Optional[str]:
        default = os.path.join(self._config._homePath, "key-cert-cachain.pem")
        with self._config._cfg as c:
            file = c.dataExchange.sslClientBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None

    @property
    def peekServerSSLClientMutualTLSCertificateAuthorityBundleFilePath(
        self,
    ) -> Optional[str]:
        default = os.path.join(self._config._homePath, "root-cas.pem")
        with self._config._cfg as c:
            file = c.dataExchange.sslClientMutualTLSCertificateAuthorityBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None

    @property
    def peekServerSSLMutualTLSTrustedPeerCertificateBundleFilePath(
        self,
    ) -> Optional[str]:
        default = os.path.join(self._config._homePath, "certs-of-peers.pem")
        with self._config._cfg as c:
            file = (
                c.dataExchange.sslMutualTLSTrustedPeerCertificateBundleFilePath(
                    default, require_string
                )
            )
            if os.path.exists(file):
                return file
            return None
