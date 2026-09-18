# Threat model

Protected assets include user email confidentiality, ISPConfig admin sessions,
Rspamd controller credentials, Redis/statistical state, Maildir integrity, and
the root/systemd boundary.

Main threats are command/path injection, privilege escalation from PHP,
accidental ham retention, unsafe POP3 classification, destructive moves after
failed learning, duplicate/concurrent training, broker exposure, and silent
breakage after dependency upgrades.

Required controls: fixed broker operations, local socket permissions, no
arbitrary paths/commands, deny-by-default policies, serialization, move/delete
only after confirmed learning success, fail-closed version checks, and
privacy-safe logs.
