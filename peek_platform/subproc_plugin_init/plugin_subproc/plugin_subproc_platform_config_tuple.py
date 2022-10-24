from vortex.Tuple import Tuple
from vortex.Tuple import TupleField
from vortex.Tuple import addTupleType


@addTupleType
class PluginSubprocPlatformConfigTuple(Tuple):
    __tablename__ = "PluginSubprocPlatformConfigTuple"
    __tupleType__ = "peek_platform." + __tablename__

    serviceName: str = TupleField()
    subprocessGroup: str = TupleField()
