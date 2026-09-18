# Dovecot integration

IMAPSieve integration is intentionally not auto-generated yet.

The production installer will generate/version-check Dovecot 2.4 configuration
only after target ISPConfig 3.3.x has been installed and its effective layout
has been validated.

Intended semantics:

- move into Junk -> learn spam;
- move out of Junk -> learn ham;
- do not retain an extra ham copy.

Do not paste historical Dovecot 2.3 configuration into Debian 13/Dovecot 2.4.
