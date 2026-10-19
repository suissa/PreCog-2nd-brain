#!/usr/bin/env bash
# Explicit, read-only acceptance checks for the installed user-level systemd units.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: checkpoint_systemd_acceptance.sh [--run-jobs]

Default mode checks that systemd sees both timers and that their units are
loaded. --run-jobs additionally executes the create and verify oneshot services.
It does not install, enable, disable, or modify units.
EOF
}

run_jobs=0
case "${1:-}" in
  "") ;;
  --run-jobs) run_jobs=1 ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }

command -v systemctl >/dev/null || {
  echo "systemctl is required" >&2
  exit 1
}

for timer in precog-checkpoint-create.timer precog-checkpoint-verify.timer; do
  systemctl --user is-enabled --quiet "$timer" || {
    echo "Acceptance failed: $timer is not enabled for this user" >&2
    exit 1
  }
  systemctl --user is-active --quiet "$timer" || {
    echo "Acceptance failed: $timer is not active for this user" >&2
    exit 1
  }
  systemctl --user show "$timer" --property=LoadState --value | grep -qx loaded || {
    echo "Acceptance failed: $timer is not loaded" >&2
    exit 1
  }
done

echo "PASS: both user timers are enabled, active, and loaded"

if [[ "$run_jobs" -eq 1 ]]; then
  for service in precog-checkpoint-create.service precog-checkpoint-verify.service; do
    echo "Running $service"
    systemctl --user start "$service"
    systemctl --user is-active --quiet "$service" && {
      echo "Acceptance failed: $service unexpectedly remains active" >&2
      exit 1
    }
    result="$(systemctl --user show "$service" --property=Result --value)"
    [[ "$result" == success ]] || {
      echo "Acceptance failed: $service result is '$result'" >&2
      exit 1
    }
    echo "PASS: $service completed successfully"
  done
fi

echo "Acceptance checks passed."
