#!/usr/bin/env bash
# Install the crontab entries that keep the relay proxy alive.
set -eu

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARK="operon-github-proxy"
LINE1="@reboot $BASE/service.sh ensure >/dev/null 2>&1 # $MARK"
LINE2="*/5 * * * * $BASE/service.sh ensure >/dev/null 2>&1 # $MARK"

current="$(crontab -l 2>/dev/null || true)"
if printf '%s\n' "$current" | grep -F "# $MARK" >/dev/null 2>&1; then
    echo "cron already installed"
    exit 0
fi

{
    printf '%s\n' "$current"
    printf '%s\n' "$LINE1"
    printf '%s\n' "$LINE2"
} | crontab -

echo "cron installed"
