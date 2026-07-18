#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
label="com.ky776.commercial-insight-social"
plist="$HOME/Library/LaunchAgents/$label.plist"
hour=${SOCIAL_JOB_HOUR:-8}
minute=${SOCIAL_JOB_MINUTE:-30}

case "$hour:$minute" in
  *[!0-9:]*|:*|*:) printf '%s\n' 'Hour and minute must be integers.' >&2; exit 1 ;;
esac
if [ "$hour" -lt 0 ] || [ "$hour" -gt 23 ] || [ "$minute" -lt 0 ] || [ "$minute" -gt 59 ]; then
  printf '%s\n' 'Hour must be 0-23 and minute must be 0-59.' >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$repo_root/local/logs"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>$repo_root/scripts/run_daily_social.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$repo_root</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$hour</integer>
    <key>Minute</key><integer>$minute</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$repo_root/local/logs/social-collector.log</string>
  <key>StandardErrorPath</key>
  <string>$repo_root/local/logs/social-collector-error.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$plist"

printf 'Installed %s at %02d:%02d daily\n' "$label" "$hour" "$minute"
printf 'Configuration: %s\n' "$repo_root/config/social_watchlist.json"
printf 'Logs: %s\n' "$repo_root/local/logs"
