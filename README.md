# ISPConfig Rspamd Trainer

[![CI](https://github.com/kmclellan/ispconfig-rspamd-trainer/actions/workflows/ci.yml/badge.svg)](https://github.com/kmclellan/ispconfig-rspamd-trainer/actions/workflows/ci.yml)

`ispconfig-rspamd-trainer` is a privacy-aware automatic Rspamd training
service for ISPConfig mail servers. It combines a constrained local trainer, a
small ISPConfig administration module, Dovecot/IMAPSieve feedback, and
conservative per-mailbox automation.

**Status:** pre-alpha. Do not deploy to production yet.

## Goals

- Automatic by default, conservative by default.
- No retained ham corpus.
- Explicit administrator confirmation for dedicated spam corpora.
- No ISPConfig core patches.
- Least privilege: ISPConfig PHP talks only to a fixed local Unix-socket broker.
- Detailed human- and AI-readable installation and recovery documentation.

## Mailbox modes

- **Automatic (recommended):** new mailboxes initially do no aged-Inbox
  learning. Once IMAP use is observed and recent POP3 use is absent, the
  mailbox may become eligible.
- **IMAP:** explicitly permit aged-Inbox learning.
- **POP3/mixed:** never use Inbox as a ham source.
- **Off:** disable aged-Inbox learning.

Initial safe defaults are a 30-day Inbox age threshold and a 90-day POP3
look-back window. Any newly observed POP3 activity suspends automatic
aged-Inbox learning.

Aged Inbox messages are learned in place and never copied or retained by this
project.

## Dedicated spam sources

An administrator may designate an ISPConfig mailbox as a trusted spam corpus
only after confirming that every non-Ham message in it is known spam.

Intended queue semantics:

- root `new/` and `cur/`: trusted spam queue;
- `.Trained/cur/`: successfully processed spam archive;
- `.Ham/new/` and `.Ham/cur/`: transient explicit ham queue.

Ham queue messages are deleted only after confirmed successful learning.

## Architecture

```text
ISPConfig admin module
        |
        | fixed JSON over local Unix socket
        v
restricted broker + SQLite policy/state
        |
        +---- trainer one-shot/timer
        |       +---- Dovecot/Maildir metadata
        |       +---- local Rspamd controller
        |       +---- Redis-backed Bayes
        |
        +---- aggregate status
```

Rspamd's own WebUI remains the detailed engine/history interface; this project
should link to it rather than duplicate it.

## Privacy

Persistent project state may contain mailbox identity, policy, aggregate
counts, run status, last IMAP/POP3 observation timestamps, and non-content
deduplication markers.

It must not contain message bodies, subjects, sender/recipient addresses,
mailbox passwords, client IPs, or copied ham. See `docs/PRIVACY.md`.

## Reused open-source components and prior art

This project deliberately reuses small, well-isolated pieces where that is
safer than reinventing them:

- The MIT-licensed ISPConfig admin module assignment/unassignment helpers from
  `ispconfig-theme-customizer` are adapted in `bin/`. They automatically
  add `rspamd_trainer` to administrator module lists and clean it up safely on
  uninstall, including stale `startmodule` values.
- `jnorell/train-spam-scanner` (BSD-2-Clause) is used as design/API prior art
  for Rspamd controller password files, controller endpoint/classifier
  selection, per-user delivery context, and immediate IMAPSieve feedback.
  Those parts are independently implemented in Python/current Dovecot 2.4
  configuration; its Bash trainer/cron/bindfs architecture is not copied.
- Rspamd's own WebUI/controller remains the engine UI/API rather than being
  reimplemented here.
- `darix/dovecot-sieve-antispam-rspamd` remains conceptual reference only;
  source is not copied because its repository licence was unclear during
  review.

See `THIRD_PARTY_NOTICES.md`, `docs/EXISTING-PROJECTS.md`, and
`PROVENANCE.md`.

## Immediate IMAP feedback

Current Dovecot 2.4 templates are included for:

- move into Junk -> learn spam;
- move out of Junk -> learn ham;
- move from Junk to Trash/Deleted/Junk/Spam -> **do not** learn ham.

The Sieve scripts pipe each message transiently to
`ispconfig-rspamd-feedback`. The message is supplied on stdin and is not
retained by the project. Controller endpoint/password-file/classifier settings
live in the protected `rspamd.ini`, not in Sieve or shell scripts.

These files are present and tested as source, but activation remains disabled
until the Debian 13 target's Dovecot 2.4 configuration is validated.


## Development

Routine development must not run as root.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -v
```

Supported public baseline is Python 3.10+. The current source is intentionally
also parseable on Python 3.9 so it can be developed on older migration hosts.

PHP syntax:

```sh
find ispconfig -name '*.php' -print0 | xargs -0 -n1 php -l
```

Shell syntax:

```sh
sh -n install.sh uninstall.sh
```

## Installation

The intended production path is eventually:

```sh
sudo ./install.sh
```

For now only the non-mutating preflight is enabled:

```sh
sudo ./install.sh --check
```

The mutating path intentionally refuses to run until Debian 13 / ISPConfig
3.3.x integration testing is complete.

## Licence

MIT. See `LICENSE`.
