#!/bin/sh
set -eu

MODE=install
if [ "${1:-}" = "--check" ]; then
  MODE=check
elif [ "$#" -ne 0 ]; then
  echo "usage: $0 [--check]" >&2
  exit 2
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "error: installer/preflight must run as root" >&2
  exit 1
fi

fail=0
check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'ok: %s\n' "$1"
  else
    printf 'missing: %s\n' "$1" >&2
    fail=1
  fi
}

echo "ISPConfig Rspamd Trainer preflight"
check_cmd python3
check_cmd systemctl
check_cmd rspamd
check_cmd rspamc
check_cmd doveconf
check_cmd redis-cli
check_cmd php

if [ -f /usr/local/ispconfig/server/lib/config.inc.php ]; then
  echo "ok: ISPConfig installation detected"
else
  echo "missing: supported ISPConfig installation" >&2
  fail=1
fi

if [ "$MODE" = check ]; then
  exit "$fail"
fi

if [ "$fail" -ne 0 ]; then
  echo "error: prerequisites are incomplete; refusing installation" >&2
  exit 1
fi

cat >&2 <<'EOF'
error: mutating installation is intentionally disabled in this pre-alpha
snapshot. Use --check only. The production installer will be enabled after
ISPConfig 3.3.x/Debian 13 integration tests.
EOF
exit 1
