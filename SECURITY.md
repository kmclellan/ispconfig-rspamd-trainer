# Security policy

No production version is supported yet; this project is pre-alpha.

Report security issues privately to the maintainer rather than opening a public
issue when disclosure could expose email, credentials, local privilege
boundaries, or deployment details. Use GitHub private vulnerability reporting
when it is enabled.

The ISPConfig web process is intentionally separated from mail operations by a
local Unix-socket broker. Do not solve permission problems by making that
socket world-writable, running the UI as root, granting generic sudo, or
exposing the broker over TCP.

Never include real email content, mailbox addresses, passwords, tokens, or
production configuration in bug reports or fixtures.
