#!/bin/sh
set -eu
cat >&2 <<'EOF'
Uninstall is intentionally disabled in this pre-alpha snapshot because the
mutating installer is not yet enabled. No production files should have been
installed by this repository version.
EOF
exit 1
