Lock file support
=================

The ZODB lock_file module provides support for creating file system
locks.  These are locks that are implemented with lock files and
OS-provided locking facilities.  To create a lock, instantiate a
LockFile object with a file name:

    >>> import zc.lockfile
    >>> lock = zc.lockfile.LockFile('lock')

If we try to lock the same name, we'll get a lock error:

    >>> import zope.testing.loggingsupport
    >>> handler = zope.testing.loggingsupport.InstalledHandler('zc.lockfile')
    >>> try:
    ...     zc.lockfile.LockFile('lock')
    ... except zc.lockfile.LockError:
    ...     print "Can't lock file"
    Can't lock file

    >>> for record in handler.records:
    ...     print record.levelname, record.getMessage()
    ERROR Error locking file lock; pid=UNKNOWN

To release the lock, use it's close method:

    >>> lock.close()

The lock file is not removed.  It is left behind:

    >>> import os
    >>> os.path.exists('lock')
    True

Of course, now that we've released the lock, we can created it again:

    >>> lock = zc.lockfile.LockFile('lock')
    >>> lock.close()

.. Cleanup

    >>> import os
    >>> os.remove('lock')

