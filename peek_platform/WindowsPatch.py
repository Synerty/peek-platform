import logging
import os
import platform

logger = logging.getLogger(__name__)

isWindows = platform.system() is "Windows"


def createHardLink(src, dst):
    import ctypes
    flags = 1 if src is not None and os.path.isdir(src) else 0
    if not ctypes.windll.kernel32.CreateHardLinkA(dst, src, flags):
        raise OSError


def createSymbolicLink(src, dst):
    import ctypes
    flags = 1 if src is not None and os.path.isdir(src) else 0
    if not ctypes.windll.kernel32.CreateSymbolicLinkA(dst, src, flags):
        raise OSError


if isWindows:
    logger.info("Replacing os.link/os.symlink functions.")
    os.link = createHardLink
    os.symlink = createSymbolicLink
