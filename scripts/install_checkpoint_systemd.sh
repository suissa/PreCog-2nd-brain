#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 /absolute/path/to/PreCog-2nd-brain" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
repo_dir="$(cd "$1" && pwd)"
[[ -f "$repo_dir/scripts/checkpoint_promotion_audit.py" ]] || {
  echo "Could not find scripts/checkpoint_promotion_audit.py under: $repo_dir" >&2
  exit 1
}
[[ "$repo_dir" != *$'\n'* ]] || {
  echo "Repository path must not contain newline characters." >&2
  exit 1
}
command -v systemctl >/dev/null || {
  echo "systemctl is required; this installer targets systemd user services." >&2
  exit 1
}

config_dir="$HOME/.config/precog"
unit_dir="$HOME/.config/systemd/user"
mkdir -p "$config_dir" "$unit_dir"
chmod 700 "$config_dir"

env_file="$config_dir/checkpoint.env"
if [[ ! -e "$env_file" ]]; then
  umask 077
  cat > "$env_file" <<EOF
PRECOG_REPO_DIR=$repo_dir
DATABASE_URL=
PRECOG_CHECKPOINT_DIR=$HOME/.local/state/precog/checkpoints
PRECOG_PUBLIC_KEY_DIR=$HOME/.config/precog/public-keys
PRECOG_PRIVATE_KEY_FILE=$HOME/.config/precog/private/signing.pem
PRECOG_PUBLIC_KEY_ID=key-1
PRECOG_AUDIT_INCIDENT_LOG=$HOME/.local/state/precog/audit-incidents.jsonl
PRECOG_MAX_CHECKPOINT_AGE_SECONDS=129600
EOF
  chmod 600 "$env_file"
  echo "Created configuration template: $env_file"
else
  echo "Preserving existing configuration: $env_file"
  echo "Ensure PRECOG_REPO_DIR points to: $repo_dir"
fi

cat > "$unit_dir/precog-checkpoint-create.service" <<'EOF'
[Unit]
Description=Create a signed PreCog promotion-audit checkpoint
After=network-online.target

[Service]
Type=oneshot
EnvironmentFile=%h/.config/precog/checkpoint.env
ExecStart=/usr/bin/bash -c 'cd "$PRECOG_REPO_DIR" && exec python3 scripts/checkpoint_promotion_audit.py create'
EOF

cat > "$unit_dir/precog-checkpoint-create.timer" <<'EOF'
[Unit]
Description=Schedule signed PreCog audit checkpoints hourly

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=60
Unit=precog-checkpoint-create.service

[Install]
WantedBy=timers.target
EOF

cat > "$unit_dir/precog-checkpoint-verify.service" <<'EOF'
[Unit]
Description=Verify PreCog audit checkpoint integrity and freshness
After=network-online.target

[Service]
Type=oneshot
EnvironmentFile=%h/.config/precog/checkpoint.env
ExecStart=/usr/bin/bash -c 'cd "$PRECOG_REPO_DIR" && exec python3 scripts/checkpoint_promotion_audit.py verify'
EOF

cat > "$unit_dir/precog-checkpoint-verify.timer" <<'EOF'
[Unit]
Description=Schedule PreCog audit checkpoint verification

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true
RandomizedDelaySec=30
Unit=precog-checkpoint-verify.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now precog-checkpoint-create.timer precog-checkpoint-verify.timer

cat <<EOF
Timers installed and enabled for the current user.

Next:
  1. Edit $env_file and set DATABASE_URL and valid key/checkpoint paths.
  2. Ensure Python dependencies are installed in the execution environment.
  3. Test manually:
     systemctl --user start precog-checkpoint-create.service
     systemctl --user start precog-checkpoint-verify.service
  4. Inspect:
     systemctl --user list-timers 'precog-checkpoint-*'
     journalctl --user -u precog-checkpoint-create.service -u precog-checkpoint-verify.service

The installer does not enable lingering. Timers may stop running after logout unless user lingering is already enabled.
EOF
