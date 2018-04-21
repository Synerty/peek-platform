#!/usr/bin/env python
"""
 * run_peek_client_build_only.py
 *
 *  Copyright Synerty Pty Ltd 2013
 *
 *  This software is proprietary, you are not free to copy
 *  or redistribute this code in any format.
 *
 *  All rights to this software are reserved by
 *  Synerty Pty Ltd
 *
"""
import sys

import win32serviceutil


def restartPeekWinSvc(serviceName: str) -> None:
    import os
    os.spawnlp(os.P_NOWAIT, '_restart_peek_winsvc', '_restart_peek_winsvc', serviceName)


def main():
    if len(sys.argv) != 2:
        raise Exception("Expected one argument, peek serivce name, eg 'peek_server'")

    serviceName = sys.argv[1]

    win32serviceutil.RestartService(serviceName)


if __name__ == '__main__':
    main()
