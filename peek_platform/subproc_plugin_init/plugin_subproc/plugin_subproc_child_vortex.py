import logging
import uuid
from typing import List
from typing import Optional
from typing import Union

from twisted.internet._posixstdio import StandardIO
from twisted.internet.defer import inlineCallbacks
from vortex.PayloadEnvelope import VortexMsgList
from vortex.VortexABC import VortexABC
from vortex.VortexABC import VortexInfo


logger = logging.getLogger("child_vortex")


class PluginSubprocChildVortex(VortexABC):
    def __init__(self, vortexName: str):
        self._localVortexInfo = VortexInfo(vortexName, uuid.uuid4())
        self._remoteVortexInfos = []
        self._remoteVortexUuidsSet = set()
        self._sendVortexToParentProtocol = None

    def setStdoutProtocol(self, sendVortexToParentProtocol: StandardIO):
        self._sendVortexToParentProtocol = sendVortexToParentProtocol

    @property
    def localVortexInfo(self) -> VortexInfo:
        return self._localVortexInfo

    @property
    def remoteVortexInfo(self) -> List[VortexInfo]:
        return self._remoteVortexInfos

    @property
    def requiresBase64Encoding(self) -> bool:
        return False

    @inlineCallbacks
    def sendVortexMsg(
        self,
        vortexMsgs: Union[VortexMsgList, bytes],
        vortexUuid: Optional[str] = None,
    ):
        if vortexUuid not in self._remoteVortexUuidsSet:
            logger.debug(
                "Remote client vortex with UUID %s doesn't exist", vortexUuid
            )
            return

        if not isinstance(vortexMsgs, list):
            vortexMsgs = [vortexMsgs]

        yield self._sendVortexToParentProtocol.sendVortexMsg(
            vortexMsgs=vortexMsgs, vortexUuid=vortexUuid
        )

    def ensureRemoteVortexIsRegistered(self, vortexUuid: str, vortexName: str):
        if vortexUuid in self._remoteVortexUuidsSet:
            return

        self._remoteVortexInfos.append(
            VortexInfo(name=vortexName, uuid=vortexUuid)
        )
        self._remoteVortexUuidsSet.add(vortexUuid)

    def updateRemoteVortexUuids(self, vortexInfos: list[VortexInfo]):
        self._remoteVortexInfos = vortexInfos
        self._remoteVortexUuidsSet = set([vi.uuid for vi in vortexInfos])
