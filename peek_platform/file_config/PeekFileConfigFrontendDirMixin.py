import logging
import os

from jsoncfg.value_mappers import require_bool

logger = logging.getLogger(__name__)


class PeekFileConfigFrontendDirMixin:
    # --- Platform Logging

    _frontendProjectDir = None

    @property
    def feDistDir(self) -> str:
        """ Frontend Dist Directory

        The directory of the dist folder in the frontend project

        """
        # EG "/home/peek/project/peek_client_fe/dist"
        default = os.path.join(self._frontendProjectDir, 'dist')
        # with self._cfg as c:
        #     c.frontend.distDirComment = (
        #         "The directory where the peek_????_fe project"
        #         " will generate it's build files")
        #     dir = c.frontend.distDir(default, require_string)
        dir = default
        if not os.path.exists(dir):
            logger.info("Frontend DIST folder does not yest exist : %s", dir)

        return dir

    @property
    def feSrcDir(self) -> str:
        """ Frontend Source Directory

        The directory of the source folder in the frontend project

        """
        # EG "/home/peek/project/peek_client_fe/src"
        default = os.path.join(self._frontendProjectDir, 'src')
        # with self._cfg as c:
        #     c.frontend.srcDirComment = (
        #         "The directory where the peek_????_fe project"
        #         " src directory is located.\n"
        #         "This is where the plugin dirs will be linked into and where the build will"
        #         " be kicked off from")
        #     dir = c.frontend.srcDir(default, require_string)
        dir = default

        if not os.path.isdir(dir):
            logger.error("Frontend SRC folder does not yest exist : %s", dir)

        return dir

    @property
    def feBuildEnabled(self) -> bool:
        """ Frontend Build Enabled

        :return True If peek should automatically try to build the frontend.

        """
        with self._cfg as c:
            return c.frontend.buildEnabled(True, require_bool)
