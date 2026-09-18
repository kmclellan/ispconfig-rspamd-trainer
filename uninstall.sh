#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

usage() {
  echo "usage: $0 [--stage-root DIR --plan | --stage-root DIR --apply [--allow-modified]]" >&2
}

if [ "$#" -eq 0 ]; then
  cat >&2 <<'EOF'
Uninstall of a live system is intentionally disabled in this pre-alpha
snapshot. Use --stage-root DIR --plan/--apply only against a disposable staged
filesystem root. Production uninstall will be enabled only after Debian 13
integration validates module unassignment, systemd shutdown, Dovecot rollback,
state/config preservation and reboot recovery.
EOF
  exit 1
fi

[ "${1:-}" = "--stage-root" ] || { usage; exit 2; }
[ "$#" -ge 3 ] || { usage; exit 2; }
ROOT=$2
shift 2

case "${1:-}" in
  --plan)
    [ "$#" -eq 1 ] || { usage; exit 2; }
    PYTHONPATH="$SCRIPT_DIR/src" exec python3 -m ispconfig_rspamd_trainer.lifecycle \
      --root "$ROOT" plan-uninstall
    ;;
  --apply)
    shift
    if [ "$#" -eq 0 ]; then
      PYTHONPATH="$SCRIPT_DIR/src" exec python3 -m ispconfig_rspamd_trainer.lifecycle \
        --root "$ROOT" apply-uninstall
    elif [ "$#" -eq 1 ] && [ "$1" = "--allow-modified" ]; then
      PYTHONPATH="$SCRIPT_DIR/src" exec python3 -m ispconfig_rspamd_trainer.lifecycle \
        --root "$ROOT" apply-uninstall --allow-modified
    else
      usage
      exit 2
    fi
    ;;
  *)
    usage
    exit 2
    ;;
esac
