#!/bin/bash
# Runs the morning email draft routine via Claude Code.
# Invoke manually: bash run.sh
# Or let cron call it: crontab -e, then add the cron line below.
#
# Cron (7 AM PT / 15:00 UTC):
#   0 15 * * * /bin/bash /path/to/Email-Draft-Routine/run.sh >> /var/log/email-routine.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "Email Draft Routine — $(date)"
echo "========================================"

cd "$SCRIPT_DIR"

claude --print "Run the morning email draft routine exactly as described in CLAUDE.md."

echo "========================================"
echo "Done — $(date)"
echo "========================================"
