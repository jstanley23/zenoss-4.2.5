from __future__ import absolute_import

import sys

supports_exec = True

if sys.platform.startswith("java"):
    _billiard = None
else:
    try:
        import _billiard                                # noqa
    except ImportError:
        import _multiprocessing as _billiard            # noqa
        supports_exec = False
    Connection = _billiard.Connection

    PipeConnection = getattr(_billiard, "PipeConnection", None)
    win32 = getattr(_billiard, "win32", None)


def ensure_SemLock():
    try:
        from _billiard import SemLock                   # noqa
    except ImportError:
        try:
            from _multiprocessing import SemLock        # noqa
        except ImportError:
            raise ImportError("""\
This platform lacks a functioning sem_open implementation, therefore,
the required synchronization primitives needed will not function,
see issue 3770.""")
