import logging
import subprocess

from peek_platform.WindowsPatch import isWindows
from peek_platform.util.PtyUtil import PtyOutParser, spawnPty, logSpawnException
from typing import List

logger = logging.getLogger(__name__)


def runNgBuild(feBuildDir: str):
    try:
        if isWindows:
            return __runNodeCmdWin(feBuildDir, ["ng", "build"])
        return __runNodeCmdLin(feBuildDir, ["ng", "build"])

    finally:
        logger.info("Frontend distribution rebuild complete.")

def runTsc(feDir: str):
    try:
        if isWindows:
            return __runNodeCmdWin(feDir, ["tsc"])
        return __runNodeCmdLin(feDir, ["tsc"])

    finally:
        logger.info("Frontend plugin module compile complete.")


def __runNodeCmdWin(feBuildDir: str, cmds: List[str]):
    proc = subprocess.Popen(cmds,
                            cwd=feBuildDir,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            shell=True)

    outs, errs = proc.communicate(timeout=20)

    if proc.returncode in (0,):
        for line in (outs + errs).decode().splitlines():
            print(".")
    else:
        for line in (outs + errs).decode().splitlines():
            print(line)

    raise Exception("ng build in %s failed" % feBuildDir)


def __runNodeCmdLin(feBuildDir: str, cmds: List[str]):
    try:
        parser = PtyOutParser(loggingStartMarker="Hash: ")
        spawnPty("cd %s && %s" % (feBuildDir, ' '.join(cmds)), parser)

    except Exception as e:
        logSpawnException(e)
        raise
