import os

from peek_platform.frontend.FrontendBuilderABC import FrontendBuilderABC


class WebBuilder(FrontendBuilderABC):
    def __init__(self, serviceName:str, jsonCfg):
        self._serviceName = serviceName
        self._jsonCfg = jsonCfg


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