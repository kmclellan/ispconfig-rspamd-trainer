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

## Existing options reviewed

- Rspamd WebUI/controller: keep and reuse for engine internals.
- `jnorell/train-spam-scanner` (BSD-2-Clause): useful prior art for
  ISPConfig/Dovecot training, but not used as this project's architecture.
- `darix/dovecot-sieve-antispam-rspamd`: useful conceptual reference; source
  is not copied because repository licensing was unclear during review.
- `ispconfig-theme-customizer` (MIT): useful example of an additive ISPConfig
  module/installer with no core patches.

See `docs/EXISTING-PROJECTS.md` and `PROVENANCE.md`.

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
