import logging
import os

from jsoncfg.value_mappers import require_bool

logger = logging.getLogger(__name__)


class PeekFileConfigFrontendDirMixin:
    # --- Platform Logging


    @property
    def feNativescriptBuildPrepareEnabled(self) -> bool:
        """ Frontend Build Enabled

        :return True If peek should automatically try to build the frontend.

        """
        with self._cfg as c:
            return c.frontend.nativescriptBuildPrepareEnabled(True, require_bool)


    @property
    def feWebBuildPrepareEnabled(self) -> bool:
        """ Frontend Build Enabled

        :return True If peek should automatically try to build the frontend.

        """
        with self._cfg as c:
            return c.frontend.webBuildPrepareEnabled(True, require_bool)



    @property
    def feWebBuildEnabled(self) -> bool:
        """ Frontend Build Enabled

        :return True If peek should automatically try to build the frontend.

        """
        with self._cfg as c:
            return c.frontend.webBuildEnabled(True, require_bool)