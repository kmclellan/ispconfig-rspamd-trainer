# Repository agent instructions

Read `README.md`, `SECURITY.md`, `PROVENANCE.md`,
`docs/ARCHITECTURE.md`, `docs/PRIVACY.md`, and
`docs/THREAT-MODEL.md` before security-sensitive changes.

## Development safety

- Run normal Git/edit/build/test work as the repository owner, never root.
- Use privilege only for narrowly scoped installer/system validation that truly
  requires it.
- Never commit credentials, real mail, mailbox addresses, production
  domains/IPs, private paths, database dumps, or service secrets.
- Inspect `git status` before editing and preserve unrelated work.

## Invariants

1. ISPConfig PHP never gets arbitrary shell, filesystem, `rspamc`, Redis,
   Maildir, or systemd access.
2. Broker operations are fixed and strictly validated.
3. No API accepts arbitrary commands, executables, service names, or paths.
4. Ham is not copied into a retained training corpus.
5. Inbox is never globally assumed to be ham.
6. POP3/mixed mailboxes do not use aged-Inbox learning automatically.
7. Dedicated spam corpora require explicit administrator designation.
8. Message content/addresses/passwords do not enter persistent state or logs.
9. ISPConfig core files are not patched.
10. Unsupported dependency/version drift fails closed.

## Validation

```sh
python3 -m unittest discover -s tests -v
find ispconfig -name '*.php' -print0 | xargs -0 -n1 php -l
sh -n install.sh uninstall.sh
```

Public history must use a GitHub privacy-preserving noreply address and must be
checked for secrets/private infrastructure before publication.
