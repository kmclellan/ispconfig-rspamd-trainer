# ISPConfig compatibility

Initial target: ISPConfig 3.3.x on Debian 13.

The project must detect the installed version, avoid core-file modifications,
use additive interface modules/custom drop-ins, identify mailboxes by stable
ISPConfig identity where possible, and fail closed on untested major/minor
versions.

Multi-server ISPConfig orchestration is deferred for v1.
