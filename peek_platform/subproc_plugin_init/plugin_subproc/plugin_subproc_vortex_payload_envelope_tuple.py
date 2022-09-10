from vortex.PayloadEnvelope import PayloadEnvelope
from vortex.Tuple import Tuple
from vortex.Tuple import TupleField
from vortex.Tuple import addTupleType


@addTupleType
class PluginSubprocVortexPayloadEnvelopeTuple(Tuple):
    __tablename__ = "PluginSubprocVortexPayloadEnvelopeTuple"
    __tupleType__ = "peek_platform." + __tablename__

    # Subprocess fields
    # The uuid of the vortex this message was received from
    vortexUuid: str = TupleField()
    vortexName: str = TupleField()

    # Call arguments
    payloadEnvelope: PayloadEnvelope = TupleField()
