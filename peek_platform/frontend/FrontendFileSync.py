import logging
import os
import shutil

from typing import Callable
from watchdog.events import FileSystemEventHandler, FileMovedEvent, FileModifiedEvent, \
    FileDeletedEvent, FileCreatedEvent
from watchdog.observers import Observer as WatchdogObserver

logger = logging.getLogger(__name__)

# Quiten the file watchdog
logging.getLogger("watchdog.observers.inotify_buffer").setLevel(logging.INFO)

SyncFileHookCallable = Callable[[str, bytes], bytes]


class FrontendFileSync:
    """ Peek App Frontend File Sync

    This class is used to syncronise the frontend files from the plugins into the 
        frontend build dirs.

    """

    def __init__(self, syncFileHookCallable: SyncFileHookCallable):
        self._syncFileHookCallable = syncFileHookCallable
        self._dirSyncMap = list()
        self._fileWatchdogObserver = None

    def addSyncMapping(self, srcDir, dstDir):
        self._dirSyncMap.append((srcDir, dstDir))

    def startFileSyncWatcher(self):

        self._fileWatchdogObserver = WatchdogObserver()

        for srcDir, dstDir in self._dirSyncMap:
            self._fileWatchdogObserver.schedule(
                _FileChangeHandler(self._syncFileHookCallable, srcDir, dstDir),
                srcDir, recursive=True)

        self._fileWatchdogObserver.start()

    def stopFileSyncWatcher(self):
        self._fileWatchdogObserver.stop()
        self._fileWatchdogObserver.join()
        self._fileWatchdogObserver = None

    def syncFiles(self):

        for srcDir, dstDir in self._dirSyncMap:
            # Create lists of files relative to the dstDir and srcDir
            existingFiles = set(self._listFiles(dstDir))
            srcFiles = set(self._listFiles(srcDir))

            for srcFile in srcFiles:
                srcFilePath = os.path.join(srcDir, srcFile)
                dstFilePath = os.path.join(dstDir, srcFile)

                dstFileDir = os.path.dirname(dstFilePath)
                os.makedirs(dstFileDir, exist_ok=True)
                self._fileCopier(srcFilePath, dstFilePath)

            for obsoleteFile in existingFiles - srcFiles:
                obsoleteFile = os.path.join(dstDir, obsoleteFile)

                if os.path.islink(obsoleteFile):
                    os.remove(obsoleteFile)

                elif os.path.isdir(obsoleteFile):
                    shutil.rmtree(obsoleteFile)

                else:
                    os.remove(obsoleteFile)

    def _writeFileIfRequired(self, dir, fileName, contents):
        fullFilePath = os.path.join(dir, fileName)

        # Since writing the file again changes the date/time,
        # this messes with the self._recompileRequiredCheck
        if os.path.isfile(fullFilePath):
            with open(fullFilePath, 'r') as f:
                if contents == f.read():
                    logger.debug("%s is up to date", fileName)
                    return

        logger.debug("Writing new %s", fileName)

        with open(fullFilePath, 'w') as f:
            f.write(contents)

    def _fileCopier(self, src, dst):
        with open(src, 'rb') as f:
            contents = f.read()

        contents = self._syncFileHookCallable(dst, contents)

        # If the contents hasn't change, don't write it
        if os.path.isfile(dst):
            with open(dst, 'rb') as f:
                if f.read() == contents:
                    return

        with open(dst, 'wb') as f:
            f.write(contents)

    def _listFiles(self, dir):
        paths = []
        for (path, directories, filenames) in os.walk(dir):

            for filename in filenames:
                paths.append(os.path.join(path[len(dir) + 1:], filename))

        return paths


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, syncFileHook, srcDir: str, dstDir: str):
        self._syncFileHook = syncFileHook
        self._srcDir = srcDir
        self._dstDir = dstDir

    def _makeDestPath(self, srcFilePath: str) -> str:
        return self._dstDir + srcFilePath[len(self._srcDir):]

    def _updateFileContents(self, srcFilePath):
        dstFilePath = self._makeDestPath(srcFilePath)

        # Copy files this way to ensure we only make one file event on the dest side.
        # tns in particular reloads on every file event.

        # This used to be done by copying the file,
        #   then _syncFileHook would modify it in place

        with open(srcFilePath, 'rb') as f:
            contents = f.read()

        contents = self._syncFileHook(dstFilePath, contents)

        # If the contents hasn't change, don't write it
        if os.path.isfile(dstFilePath):
            with open(dstFilePath, 'rb') as f:
                if f.read() == contents:
                    return

        logger.debug("Syncing %s -> %s", srcFilePath[len(self._srcDir) + 1:],
                     self._dstDir)

        with open(dstFilePath, 'wb') as f:
            f.write(contents)

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent) or event.src_path.endswith("__"):
            return

        self._updateFileContents(event.src_path)

    def on_deleted(self, event):
        if not isinstance(event, FileDeletedEvent) or event.src_path.endswith("__"):
            return

        dstFilePath = self._makeDestPath(event.src_path)

        if os.path.exists(dstFilePath):
            os.remove(dstFilePath)

        logger.debug("Removing %s -> %s", event.src_path[len(self._srcDir) + 1:],
                     self._dstDir)

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent) or event.src_path.endswith("__"):
            return

        self._updateFileContents(event.src_path)

    def on_moved(self, event):
        if (not isinstance(event, FileMovedEvent)
            or event.src_path.endswith("__")
            or event.dest_path.endswith("__")):
            return

        self._updateFileContents(event.dest_path)

        oldDestFilePath = self._makeDestPath(event.src_path)
        if os.path.exists(oldDestFilePath):
            os.remove(oldDestFilePath)
