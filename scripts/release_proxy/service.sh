#!/usr/bin/env bash
# Start, stop or inspect the authenticated GitHub proxy on the relay host.
# All state stays inside the directory that holds this script.
set -u

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${PYTHON:-}" ]; then
    for candidate in /public/home/lihj/miniforge3/bin/python3 /usr/bin/python3 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
            PYTHON="$candidate"
            break
        fi
    done
fi
if [ -z "${PYTHON:-}" ]; then
    echo "no python3 >= 3.8 found" >&2
    exit 1
fi
PIDFILE="$BASE/proxy.pid"
CONFIG="$BASE/config.json"
LAUNCHER_LOG="$BASE/launcher.log"

is_running() {
    [ -f "$PIDFILE" ] || return 1
    local pid
    pid="$(cat "$PIDFILE" 2>/dev/null)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

start() {
    if is_running; then
        echo "running pid=$(cat "$PIDFILE")"
        return 0
    fi
    rm -f "$PIDFILE"
    if [ ! -f "$CONFIG" ]; then
        echo "missing config: $CONFIG" >&2
        return 1
    fi
    nohup "$PYTHON" "$BASE/github_proxy_server.py" --config "$CONFIG" --pid-file "$PIDFILE" \
        >>"$LAUNCHER_LOG" 2>&1 &
    local attempt
    for attempt in $(seq 1 40); do
        sleep 0.25
        if is_running; then
            echo "started pid=$(cat "$PIDFILE")"
            return 0
        fi
    done
    echo "failed to start" >&2
    tail -n 20 "$LAUNCHER_LOG" >&2 2>/dev/null
    return 1
}

stop() {
    if ! is_running; then
        echo "not running"
        rm -f "$PIDFILE"
        return 0
    fi
    local pid
    pid="$(cat "$PIDFILE")"
    kill "$pid" 2>/dev/null
    local attempt
    for attempt in $(seq 1 40); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PIDFILE"
    echo "stopped pid=$pid"
}

status() {
    if is_running; then
        echo "running pid=$(cat "$PIDFILE")"
        return 0
    fi
    echo "stopped"
    return 1
}

ensure() {
    is_running || start >/dev/null 2>&1
    is_running
}

case "${1:-status}" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status) status ;;
    ensure) ensure ;;
    *)
        echo "usage: $0 {start|stop|restart|status|ensure}" >&2
        exit 2
        ;;
esac
