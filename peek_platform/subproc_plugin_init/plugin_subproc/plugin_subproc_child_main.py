import json
import logging
import sys
from base64 import b64decode

from setproctitle import setproctitle
from twisted.internet import reactor
from twisted.internet._posixstdio import StandardIO
from vortex.VortexFactory import VortexFactory

from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_state_protocol import (
    PluginSubprocChildStateProtocol,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_vortex_protocol import (
    PluginSubprocChildVortexProtocol,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_vortex_uuid_protocol import (
    PluginSubprocChildVortexUuidProtocol,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    PLUGIN_STATE_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    PLUGIN_STATE_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_MSG_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_MSG_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_UUID_FROM_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_constants import (
    VORTEX_UUID_TO_CHILD_FD,
)
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_platform_config_tuple import (
    PluginSubprocPlatformConfigTuple,
)


"""
from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_platform_config_tuple import PluginSubprocPlatformConfigTuple
from base64 import b64encode
import json

x=PluginSubprocPlatformConfigTuple(serviceName="peek-office-service", pluginName="peek_core_search")
b64encode(json.dumps(x.toJsonDict()).encode())

b'eyJfY3QiOiJydCIsIl9jIjoicGVla19wbGF0Zm9ybS5QbHVnaW5TdWJwcm9jUGxhdGZvcm1Db25maWdUdXBsZSIsInBsdWdpbk5hbWUiOiJwZWVrX2NvcmVfc2VhcmNoIiwic2VydmljZU5hbWUiOiJwZWVrLW9mZmljZS1zZXJ2aWNlIn0='
"""

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    base64Tuple = sys.argv[1]

    platformConfigTuple = PluginSubprocPlatformConfigTuple().fromJsonDict(
        json.loads(b64decode(base64Tuple))
    )
    logger = logging.getLogger(
        "subproc plugin main %s %s"
        % (platformConfigTuple.serviceName, platformConfigTuple.subprocessGroup)
    )

    setproctitle(
        "%s %s"
        % (platformConfigTuple.serviceName, platformConfigTuple.subprocessGroup)
    )

    from peek_platform.subproc_plugin_init.plugin_subproc.plugin_subproc_child_vortex import (
        PluginSubprocChildVortex,
    )

    vortex = PluginSubprocChildVortex(
        vortexName=platformConfigTuple.serviceName
    )

    # Create the protocol used to send vortex messages
    sendVortexToParentProtocol = PluginSubprocChildVortexProtocol(vortex)
    StandardIO(
        sendVortexToParentProtocol,
        stdin=VORTEX_MSG_TO_CHILD_FD,
        stdout=VORTEX_MSG_FROM_CHILD_FD,
    )

    try:
        # If we run this directly from the commandline, FD3 and FD4 don't exist
        # Just log the problem
        # This is the vortex UUID update protocol
        StandardIO(
            PluginSubprocChildVortexUuidProtocol(vortex),
            stdin=VORTEX_UUID_TO_CHILD_FD,
            stdout=VORTEX_UUID_FROM_CHILD_FD,
        )

        # This is the plugin load, start, stop, unload protocol
        StandardIO(
            PluginSubprocChildStateProtocol(
                platformConfigTuple.serviceName,
                platformConfigTuple.subprocessGroup,
            ),
            stdin=PLUGIN_STATE_TO_CHILD_FD,
            stdout=PLUGIN_STATE_FROM_CHILD_FD,
        )

    except Exception as e:
        logger.error("Failed to connect to FD3 and FD4")
        logger.exception(e)

    vortex.setStdoutProtocol(sendVortexToParentProtocol)
    VortexFactory.addCustomServerVortex(vortex)

    reactor.run()
