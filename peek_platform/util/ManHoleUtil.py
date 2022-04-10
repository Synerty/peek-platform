import logging
import os.path

from twisted.conch.checkers import InMemorySSHKeyDB
from twisted.conch.checkers import SSHPublicKeyChecker
from twisted.conch.manhole import ColoredManhole
from twisted.conch.manhole_ssh import ConchFactory
from twisted.conch.manhole_ssh import TerminalRealm
from twisted.conch.ssh.keys import Key
from twisted.cred.portal import Portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.internet import reactor

logger = logging.getLogger(__name__)


def start_manhole(
    port: int,
    manholeUserPassword: str,
    serverKeyPubPath: str,
    serverKeyPriPath: str,
):
    logger.info("Starting manhole server on port %s", port)

    def get_manhole(_):
        return ColoredManhole(globals())

    passwdChecker = InMemoryUsernamePasswordDatabaseDontUse(
        manhole=manholeUserPassword.encode()
    )

    checkers = [passwdChecker]

    usersPubKeyPath = os.path.expanduser("~/.ssh/id_rsa.pub")
    if os.path.exists(usersPubKeyPath):
        checkers.append(
            SSHPublicKeyChecker(
                InMemorySSHKeyDB({b"manhole": [Key.fromFile(usersPubKeyPath)]})
            )
        )

    realm = TerminalRealm()
    realm.chainedProtocolFactory.protocolFactory = get_manhole
    portal = Portal(realm, checkers=checkers)

    factory = ConchFactory(portal)
    factory.publicKeys[b"ssh-rsa"] = Key.fromFile(serverKeyPubPath)
    factory.privateKeys[b"ssh-rsa"] = Key.fromFile(serverKeyPriPath)

    reactorSocket = reactor.listenTCP(port, factory, interface="127.0.0.1")

    # Stop the manhole server when the reactor stops.4
    reactor.addSystemEventTrigger(
        "before", "shutdown", reactorSocket.stopListening
    )
