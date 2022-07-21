import logging
import shutil
from collections import namedtuple
from pathlib import Path
from typing import List

from vortex.DeferUtil import deferToThreadWrapWithLogger

from peek_platform.build_common.BuilderOsCmd import runCommand
from peek_platform.build_common.BuilderOsCmd import runNgBuild
from peek_platform.build_frontend.FrontendBuilderABC import FrontendBuilderABC
from peek_platform.build_frontend.WebBuilder import WebBuilder

logger = logging.getLogger(__name__)

PatchItem = namedtuple("PatchItem", ["target", "patch"])


class EdnarWebBuilder(WebBuilder):
    def __init__(
        self,
        frontendProjectDir: str,
        platformService: str,
        jsonCfg,
        loadedPlugins: List,
        officeAppSrcDir: str,
    ):
        self._officeAppSrcDir = officeAppSrcDir
        FrontendBuilderABC.__init__(
            self,
            frontendProjectDir,
            platformService,
            self._buildType(platformService),
            jsonCfg,
            loadedPlugins,
        )

        self.isField = "field" in platformService
        self.isOffice = "office" in platformService
        self.isAdmin = "admin" in platformService

    @deferToThreadWrapWithLogger(logger, checkMainThread=False)
    def build(self):
        if not self.isOffice:
            return

        # npm install
        nodeModuleFolder = Path(self._frontendProjectDir) / Path(
            "./node_modules"
        )
        if nodeModuleFolder.is_dir() and not nodeModuleFolder.exists():
            runCommand(self._frontendProjectDir, "npm install".split())

        # copy over @_peek and @peek
        for folder in ["@_peek", "@peek"]:
            peekModuleFolder = Path(self._officeAppSrcDir) / Path(folder)

            shutil.copytree(
                peekModuleFolder,
                Path(self._frontendProjectDir) / Path(f"./{folder}"),
                dirs_exist_ok=True,
            )
        # apply patches
        #  patch src/@peek/peek_core_device/device-enrolment.service.ts \
        # patch/device-enrolment.service.ts.diff

        # patch src/@peek/peek_plugin_diagram/_private/branch/PrivateDiagramBranchContext.ts \
        # patch/PrivateDiagramBranchContext.ts.diff

        # patch src/@_peek/peek_plugin_enmac_diagram/pofDiagram.module.ts \
        #  patch/pofDiagram.module.ts.diff
        for patchItem in [
            PatchItem(
                target="@peek/peek_core_device/device-enrolment.service" ".ts",
                patch="patch/device-enrolment.service.ts.diff",
            ),
            PatchItem(
                target="@peek/peek_plugin_diagram/_private/branch"
                "/PrivateDiagramBranchContext.ts",
                patch="patch/PrivateDiagramBranchContext.ts.diff",
            ),
            PatchItem(
                target="@_peek/peek_plugin_enmac_diagram/pofDiagram"
                ".module.ts",
                patch="patch/pofDiagram.module.ts.diff",
            ),
        ]:
            command = f"patch {patchItem.target} {patchItem.patch}"
            runCommand(self._frontendProjectDir, command.split())

        # ng build --prod --output-hashing none --base-href ./
        runNgBuild(
            self._frontendProjectDir,
            ngBuildArgs="ng build --prod --output-hashing none --base-href "
            "./".split(),
        )
