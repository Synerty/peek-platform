import os
from abc import ABCMeta
from typing import Optional

from jsoncfg.value_mappers import require_bool
from jsoncfg.value_mappers import require_string, require_integer


class PeekFileConfigPeekServerClientMixin(metaclass=ABCMeta):

    ### SERVER SECTION ###
    @property
    def peekServerHttpPort(self) -> int:
        with self._cfg as c:
            return c.peekServer.httpPort(8011, require_integer)

    @property
    def peekServerVortexTcpPort(self) -> int:
        with self._cfg as c:
            return c.peekServer.tcpVortexPort(8012, require_integer)

    @property
    def peekServerHost(self) -> str:
        with self._cfg as c:
            return c.peekServer.host("127.0.0.1", require_string)

    @property
    def peekServerSSL(self) -> int:
        with self._cfg as c:
            return c.peekServer.ssl(False, require_bool)

    @property
    def peekServerSSLEnableMutualTLS(self) -> int:
        with self._cfg as c:
            return c.peekServer.sslEnableMutualTLS(False, require_bool)

    @property
    def peekServerSSLClientBundleFilePath(self) -> Optional[str]:
        default = os.path.join(
            self._homePath, "peek-platform-ssl-client-bundle.pem"
        )
        with self._cfg as c:
            file = c.peekServer.sslClientBundleFilePath(default, require_string)
            if os.path.exists(file):
                return file
            return None

    @property
    def peekServerSSLClientMutualTLSCertificateAuthorityBundleFilePath(
        self,
    ) -> Optional[str]:
        default = os.path.join(
            self._homePath, "peek-platform-ssl-client-mtls-bundle.pem"
        )
        with self._cfg as c:
            file = c.peekServer.sslClientMutualTLSCertificateAuthorityBundleFilePath(
                default, require_string
            )
            if os.path.exists(file):
                return file
            return None
