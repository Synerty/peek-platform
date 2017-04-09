import logging
import os
import shutil
from collections import namedtuple
from typing import Callable, Optional

from twisted.internet import reactor
from watchdog.events import FileSystemEventHandler, FileMovedEvent, FileModifiedEvent, \
    FileDeletedEvent, FileCreatedEvent
from watchdog.observers import Observer as WatchdogObserver

logger = logging.getLogger(__name__)

# Quiten the file watchdog
logging.getLogger("watchdog.observers.inotify_buffer").setLevel(logging.INFO)

SyncFileHookCallable = Callable[[str, bytes], bytes]

FileSyncCfg = namedtuple('FileSyncCfg',
                         ['srcDir', 'dstDir', 'parentMustExist',
                          'deleteExtraDstFiles',
                          'preSyncCallback', 'postSyncCallback'])


class FrontendFileSync:
    """ Peek App Frontend File Sync

    This class is used to syncronise the frontend files from the plugins into the 
        frontend build dirs.

    """

    def __init__(self, syncFileHookCallable: SyncFileHookCallable):
        self._syncFileHookCallable = syncFileHookCallable
        self._dirSyncMap = list()
        self._fileWatchdogObserver = None

    def addSyncMapping(self, srcDir, dstDir,
                       parentMustExist=False,
                       deleteExtraDstFiles=True,
                       preSyncCallback: Optional[Callable[[], None]] = None,
                       postSyncCallback: Optional[Callable[[], None]] = None):
        self._dirSyncMap.append(
            FileSyncCfg(srcDir, dstDir, parentMustExist,
                        deleteExtraDstFiles,
                        preSyncCallback, postSyncCallback)
        )

    def startFileSyncWatcher(self):

        self._fileWatchdogObserver = WatchdogObserver()

        for cfg in self._dirSyncMap:
            self._fileWatchdogObserver.schedule(
                _FileChangeHandler(self._syncFileHookCallable, cfg),
                cfg.srcDir, recursive=True)

        self._fileWatchdogObserver.start()

        reactor.addSystemEventTrigger('before', 'shutdown', self.stopFileSyncWatcher)
        logger.debug("Started frontend file watchers")

    def stopFileSyncWatcher(self):
        self._fileWatchdogObserver.stop()
        self._fileWatchdogObserver.join()
        self._fileWatchdogObserver = None
        logger.debug("Stopped frontend file watchers")

    def syncFiles(self):

        for cfg in self._dirSyncMap:
            parentDstDir = os.path.dirname(cfg.dstDir)
            if cfg.parentMustExist and not os.path.isdir(parentDstDir):
                logger.debug("Skipping sink, parent doesn't exist. dstDir=%s", cfg.dstDir)
                continue

            if cfg.preSyncCallback:
                cfg.preSyncCallback()

            # Create lists of files relative to the dstDir and srcDir
            existingFiles = set(self._listFiles(cfg.dstDir))
            srcFiles = set(self._listFiles(cfg.srcDir))

            for srcFile in srcFiles:
                srcFilePath = os.path.join(cfg.srcDir, srcFile)
                dstFilePath = os.path.join(cfg.dstDir, srcFile)

                dstFileDir = os.path.dirname(dstFilePath)
                os.makedirs(dstFileDir, exist_ok=True)
                self._fileCopier(srcFilePath, dstFilePath)

            if cfg.deleteExtraDstFiles:
                for obsoleteFile in existingFiles - srcFiles:
                    obsoleteFile = os.path.join(cfg.dstDir, obsoleteFile)

                    if os.path.islink(obsoleteFile):
                        os.remove(obsoleteFile)

                    elif os.path.isdir(obsoleteFile):
                        shutil.rmtree(obsoleteFile)

                    else:
                        os.remove(obsoleteFile)

            if cfg.postSyncCallback:
                cfg.postSyncCallback()

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
        ignoreFiles = set('.lastHash')
        paths = []
        for (path, directories, filenames) in os.walk(dir):

            for filename in filenames:
                if filename in ignoreFiles:
                    continue
                paths.append(os.path.join(path[len(dir) + 1:], filename))

        return paths


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(self, syncFileHook, cfg: FileSyncCfg):
        self._syncFileHook = syncFileHook
        self._srcDir = cfg.srcDir
        self._dstDir = cfg.dstDir
        self._cfg = cfg

    def _makeDestPath(self, srcFilePath: str) -> str:
        return self._dstDir + srcFilePath[len(self._srcDir):]

    def _updateFileContents(self, srcFilePath):
        parentDstDir = os.path.dirname(self._dstDir)
        if self._cfg.parentMustExist and not os.path.isdir(parentDstDir):
            logger.debug("Skipping sink, parent doesn't exist. dstDir=%s", self._dstDir)
            return

        if self._cfg.preSyncCallback:
            self._cfg.preSyncCallback()

        # if the file had vanished, then do nothing
        if not os.path.exists(srcFilePath):
            return

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

        if self._cfg.postSyncCallback:
            self._cfg.postSyncCallback()

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
