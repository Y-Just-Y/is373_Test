#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && -f /var/run/reboot-required ]] || exit 0
exec 9>/opt/lwdgy-security-lab/deploy.lock
if ! flock -n 9; then echo 'Deployment active; defer reboot until next maintenance window.'; exit 0; fi
if systemctl is-active --quiet apt-daily.service || systemctl is-active --quiet apt-daily-upgrade.service || fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock >/dev/null 2>&1; then
  echo 'Package update active; defer reboot until next maintenance window.'
  exit 0
fi
echo 'Ubuntu requested a reboot; rebooting in the 03:30 New York maintenance window.'
systemctl reboot
