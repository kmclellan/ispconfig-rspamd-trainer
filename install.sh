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
check_cmd sievec

if [ -f /usr/local/ispconfig/server/lib/config.inc.php ] && [ -f /usr/local/ispconfig/interface/lib/config.inc.php ]; then
  echo "ok: ISPConfig installation detected"
else
  echo "missing: supported ISPConfig installation" >&2
  fail=1
fi

if php -r 'exit(extension_loaded("mysqli") ? 0 : 1);' >/dev/null 2>&1; then
  echo "ok: PHP mysqli extension"
else
  echo "missing: PHP mysqli extension required for automatic module assignment" >&2
  fail=1
fi

for helper in bin/assign_module.php bin/unassign_module.php; do
  if php -l "$helper" >/dev/null 2>&1; then
    echo "ok: $helper"
  else
    echo "invalid: $helper" >&2
    fail=1
  fi
done

if command -v sievec >/dev/null 2>&1; then
  sieve_tmp="$(mktemp -d)"
  sieve_ok=1
  for sieve_script in dovecot/sieve/*.sieve; do
    if ! sievec -P sieve_imapsieve -P sieve_extprograms \
      -x '+vnd.dovecot.pipe +vnd.dovecot.environment' \
      "$sieve_script" "$sieve_tmp/$(basename "$sieve_script").svbin" >/dev/null 2>&1; then
      echo "invalid: $sieve_script (required IMAPSieve/extprogram capabilities unavailable or syntax error)" >&2
      sieve_ok=0
      fail=1
    fi
  done
  rm -rf "$sieve_tmp"
  if [ "$sieve_ok" -eq 1 ]; then
    echo "ok: Dovecot IMAPSieve feedback scripts"
  fi
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
