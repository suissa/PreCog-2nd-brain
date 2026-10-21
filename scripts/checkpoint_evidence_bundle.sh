#!/usr/bin/env bash
# Capture redacted, host-level evidence for checkpoint scheduler acceptance.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: checkpoint_evidence_bundle.sh [--output DIR]

Captures read-only systemd timer/service state and recent journal evidence.
The bundle is local evidence only: it does not install, enable, start, stop,
or modify systemd units. Sensitive-looking values are redacted before writing.
EOF
}

output=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a directory" >&2; exit 2; }
      output="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

command -v systemctl >/dev/null || { echo "systemctl is required" >&2; exit 1; }
command -v journalctl >/dev/null || { echo "journalctl is required" >&2; exit 1; }

if [[ -z "$output" ]]; then
  output="evidence/checkpoint-$(date -u +%Y%m%dT%H%M%SZ)"
fi

umask 077
mkdir -p "$output"

redact() {
  sed -E \
    -e 's#(postgres(ql)?://)[^[:space:]]+@#\1[REDACTED]@#g' \
    -e 's#([A-Za-z_]*(PASSWORD|SECRET|TOKEN|PRIVATE_KEY)[A-Za-z_]*[[:space:]]*[=:][[:space:]]*)[^[:space:]]+#\1[REDACTED]#Ig' \
    -e 's#(Authorization:[[:space:]]*(Bearer|Basic)[[:space:]]+)[^[:space:]]+#\1[REDACTED]#Ig'
}

capture() {
  local name="$1"
  shift
  if "$@" 2>&1 | redact > "$output/$name"; then
    return 0
  fi
  printf 'COMMAND_FAILED: %q\n' "$*" | redact > "$output/$name"
  return 1
}

cat > "$output/manifest.txt" <<EOF
PreCog checkpoint operational evidence
captured_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
host=$(hostname -s 2>/dev/null || echo unknown)
user=$(id -un 2>/dev/null || echo unknown)
repository=${PWD}

This bundle contains redacted operational evidence. It is not an audit-history
integrity proof and must not be treated as deployment authorization.
EOF

failed=0
capture timers.txt systemctl --user list-timers --all 'precog-checkpoint-*.timer' || failed=1
capture create_timer.txt systemctl --user show precog-checkpoint-create.timer --property=Id,LoadState,ActiveState,Unit,TriggerUSec,NextElapseUSecRealtime || failed=1
capture verify_timer.txt systemctl --user show precog-checkpoint-verify.timer --property=Id,LoadState,ActiveState,Unit,TriggerUSec,NextElapseUSecRealtime || failed=1
capture create_service.txt systemctl --user show precog-checkpoint-create.service --property=Id,LoadState,ActiveState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp || failed=1
capture verify_service.txt systemctl --user show precog-checkpoint-verify.service --property=Id,LoadState,ActiveState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp || failed=1
capture journal.txt journalctl --user -u precog-checkpoint-create.service -u precog-checkpoint-verify.service --no-pager -n 100 || failed=1

sha256sum "$output"/* > "$output/SHA256SUMS"
printf 'Evidence bundle: %s\n' "$output"
if [[ "$failed" -ne 0 ]]; then
  echo 'One or more evidence commands failed; bundle is partial.' >&2
  exit 1
fi
echo 'Evidence capture completed successfully.'
