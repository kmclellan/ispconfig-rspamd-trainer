#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MODE=install
STAGE_ROOT=

case "${1:-}" in
  --check)
    [ "$#" -eq 1 ] || { echo "usage: $0 [--check | --stage DIR]" >&2; exit 2; }
    MODE=check
    ;;
  --stage)
    [ "$#" -eq 2 ] || { echo "usage: $0 [--check | --stage DIR]" >&2; exit 2; }
    MODE=stage
    STAGE_ROOT=$2
    ;;
  "")
    [ "$#" -eq 0 ] || { echo "usage: $0 [--check | --stage DIR]" >&2; exit 2; }
    ;;
  *)
    echo "usage: $0 [--check | --stage DIR]" >&2
    exit 2
    ;;
esac

if [ "$MODE" = stage ]; then
  command -v python3 >/dev/null 2>&1 || {
    echo "error: python3 is required for staging" >&2
    exit 1
  }
  mkdir -p "$STAGE_ROOT"
  PYTHONPATH="$SCRIPT_DIR/src" python3 -m ispconfig_rspamd_trainer.install_layout \
    --root "$STAGE_ROOT" \
    --source "$SCRIPT_DIR"
  echo "staged install layout at $STAGE_ROOT"
  exit 0
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
check_cmd rspamadm
check_cmd doveconf
check_cmd redis-cli
check_cmd php
check_cmd sievec

if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
  echo "ok: Python 3.10+"
else
  echo "unsupported: Python 3.10+ is required" >&2
  fail=1
fi

if [ -f /usr/local/ispconfig/server/lib/config.inc.php ] &&
   [ -f /usr/local/ispconfig/interface/lib/config.inc.php ]; then
  version=$(php -r "require '/usr/local/ispconfig/server/lib/config.inc.php'; echo defined('ISPC_APP_VERSION') ? ISPC_APP_VERSION : '';" 2>/dev/null || true)
  case "$version" in
    3.3.*)
      echo "ok: ISPConfig $version"
      ;;
    *)
      echo "unsupported: ISPConfig 3.3.x required (found: ${version:-unknown})" >&2
      fail=1
      ;;
  esac
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

for helper in bin/assign_module.php bin/unassign_module.php bin/export_mailboxes.php; do
  if php -l "$SCRIPT_DIR/$helper" >/dev/null 2>&1; then
    echo "ok: $helper"
  else
    echo "invalid: $helper" >&2
    fail=1
  fi
done

if command -v sievec >/dev/null 2>&1; then
  sieve_tmp="$(mktemp -d)"
  sieve_ok=1
  for sieve_script in "$SCRIPT_DIR"/dovecot/sieve/*.sieve; do
    if ! sievec -P sieve_imapsieve -P sieve_extprograms       -x '+vnd.dovecot.pipe +vnd.dovecot.environment'       "$sieve_script" "$sieve_tmp/$(basename "$sieve_script").svbin" >/dev/null 2>&1; then
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

if command -v doveconf >/dev/null 2>&1; then
  imap_exec=$(doveconf service/imap/executable 2>/dev/null | sed 's/^[^=]*=[[:space:]]*//' || true)
  pop3_exec=$(doveconf service/pop3/executable 2>/dev/null | sed 's/^[^=]*=[[:space:]]*//' || true)
  printf 'info: Dovecot IMAP executable chain: %s\n' "${imap_exec:-unknown}"
  printf 'info: Dovecot POP3 executable chain: %s\n' "${pop3_exec:-unknown}"
  if [ -n "$imap_exec" ] && [ "$imap_exec" != "imap" ]; then
    echo "notice: existing IMAP post-login chain must be preserved/merged"
  fi
  if [ -n "$pop3_exec" ] && [ "$pop3_exec" != "pop3" ]; then
    echo "notice: existing POP3 post-login chain must be preserved/merged"
  fi
fi

if command -v rspamadm >/dev/null 2>&1; then
  if rspamadm configtest >/dev/null 2>&1; then
    echo "ok: Rspamd configuration syntax"
  else
    echo "invalid: rspamadm configtest failed" >&2
    fail=1
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
snapshot. Use --check for target preflight or --stage DIR to inspect/test the
complete filesystem payload. Production activation will be enabled only after
Debian 13 / ISPConfig 3.3.x / Dovecot 2.4 integration validation.
EOF
exit 1
