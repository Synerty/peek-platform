from typing import Union

from vortex.PayloadEnvelope import VortexMsgList
from vortex.Tuple import Tuple
from vortex.Tuple import TupleField
from vortex.Tuple import addTupleType


@addTupleType
class PluginSubprocVortexMsgTuple(Tuple):
    __tablename__ = "PluginSubprocVortexMsgTuple"
    __tupleType__ = "peek_platform." + __tablename__

    # The vortexUuid to send the message to
    vortexUuid: str = TupleField()

    # Call arguments
    vortexMsgs: Union[VortexMsgList, bytes] = TupleField()

    priority: int = TupleField()
