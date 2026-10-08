#!/usr/bin/env bash
# Run only on the new Ubuntu 24.04 lab Droplet, after reviewing these files.
set -euo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && $# == 3 ]] || { echo 'Usage: sudo bash bootstrap.sh ADMIN_PUBLIC_KEY CI_PUBLIC_KEY ACME_EMAIL' >&2; exit 2; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo 'Ubuntu 24.04 required.' >&2; exit 2; }
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
BASE=/opt/lwdgy-security-lab
ADMIN_KEY=$1
DEPLOY_KEY=$2
ACME_EMAIL=$3
[[ $ACME_EMAIL =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || { echo 'A real ACME contact email is required.' >&2; exit 2; }
for file in "$ADMIN_KEY" "$DEPLOY_KEY"; do
  [[ -f $file && ! -L $file && $(wc -l < "$file") -le 1 ]] || { echo 'Expected a single public key file.' >&2; exit 2; }
  key=$(cat -- "$file")
  [[ $key != *$'\n'* ]] || exit 2
  [[ $key =~ ^ssh-ed25519[[:blank:]][A-Za-z0-9+/]+={0,3}([[:blank:]].*)?$ ]] || { echo 'Only a plain Ed25519 public key is accepted.' >&2; exit 2; }
  ssh-keygen -lf "$file" >/dev/null
done
[[ $(awk '{print $1 " " $2}' "$ADMIN_KEY") != $(awk '{print $1 " " $2}' "$DEPLOY_KEY") ]] || { echo 'Admin and CI must use different keys.' >&2; exit 2; }
for file in compose.yaml traefik.yaml routes.yaml ssh-deploy.py release-helper.py finalize-ssh.sh reboot-if-required.sh; do
  [[ -f $HERE/$file && ! -L $HERE/$file ]] || { echo "Missing trusted installer asset: $file" >&2; exit 2; }
done
# Never silently remove preexisting firewall holes. Fresh Droplet should have none.
if command -v ufw >/dev/null; then
  ufw status numbered
  rules=$(ufw show added | awk '/^ufw /')
  while IFS= read -r rule; do
    [[ -z $rule || $rule =~ ^ufw\ allow\ (OpenSSH|22/tcp|80/tcp|443/tcp)$ ]] || { echo "Review unexpected existing UFW rule before bootstrap: $rule" >&2; exit 1; }
  done <<< "$rules"
fi
# The official Docker apt repository; never pipe a remote installer into a shell.
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl python3 sudo ufw fail2ban unattended-upgrades update-notifier-common psmisc
install -d -m 0755 /etc/apt/keyrings
curl --fail --silent --show-error https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<DOCKER_APT
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER_APT
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# Docker remains root-only; neither account is added to the docker group.
for account in lab-admin lab-deploy; do
  if ! id "$account" >/dev/null 2>&1; then useradd --create-home --shell /bin/bash "$account"; fi
  passwd -l "$account"
done
usermod -G sudo lab-admin
usermod -G "" lab-deploy
# Administrator has full sudo by explicit owner request; CI has one fixed helper.
ADMIN_RULE=$(mktemp)
printf '%s\n' 'lab-admin ALL=(ALL:ALL) NOPASSWD: ALL' > "$ADMIN_RULE"
visudo -cf "$ADMIN_RULE"
install -o root -g root -m 0440 "$ADMIN_RULE" /etc/sudoers.d/lwdgy-lab-admin
rm -f "$ADMIN_RULE"
install -d -o lab-admin -g lab-admin -m 0700 /home/lab-admin/.ssh
awk '{print $1 " " $2}' "$ADMIN_KEY" > /home/lab-admin/.ssh/authorized_keys
chown lab-admin:lab-admin /home/lab-admin/.ssh/authorized_keys
chmod 0600 /home/lab-admin/.ssh/authorized_keys
# Root owns the CI home/key, preventing the CI identity from replacing restrictions.
chown root:root /home/lab-deploy
chmod 0755 /home/lab-deploy
install -d -o root -g lab-deploy -m 0750 /home/lab-deploy/.ssh
printf 'restrict,command="/usr/local/libexec/lwdgy-lab/ssh-deploy" %s\n' "$(awk '{print $1 " " $2}' "$DEPLOY_KEY")" > /home/lab-deploy/.ssh/authorized_keys
chown root:lab-deploy /home/lab-deploy/.ssh/authorized_keys
chmod 0640 /home/lab-deploy/.ssh/authorized_keys
install -d -o root -g root -m 0755 /usr/local/libexec/lwdgy-lab
install -o root -g root -m 0755 "$HERE/ssh-deploy.py" /usr/local/libexec/lwdgy-lab/ssh-deploy
install -o root -g root -m 0755 "$HERE/release-helper.py" /usr/local/sbin/lwdgy-lab-deploy
install -o root -g root -m 0755 "$HERE/finalize-ssh.sh" /usr/local/sbin/lwdgy-lab-finalize-ssh
install -o root -g root -m 0755 "$HERE/reboot-if-required.sh" /usr/local/sbin/lwdgy-lab-reboot-if-required
RULE=$(mktemp)
# "" in sudoers means no command-line arguments are allowed.
printf '%s\n' 'lab-deploy ALL=(root) NOPASSWD: /usr/local/sbin/lwdgy-lab-deploy ""' > "$RULE"
visudo -cf "$RULE"
install -o root -g root -m 0440 "$RULE" /etc/sudoers.d/lwdgy-lab-deploy
rm -f "$RULE"
visudo -c
install -d -o root -g root -m 0755 "$BASE" "$BASE/dynamic"
install -d -o root -g root -m 0700 "$BASE/docker-config"
install -o root -g root -m 0644 "$HERE/compose.yaml" "$BASE/compose.yaml"
install -o root -g root -m 0644 "$HERE/routes.yaml" "$BASE/dynamic/routes.yaml"
python3 - "$HERE/traefik.yaml" "$BASE/traefik.yaml" "$ACME_EMAIL" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[2]).write_text(Path(sys.argv[1]).read_text().replace('ACME_EMAIL_REPLACED_BY_BOOTSTRAP', sys.argv[3]))
PY
chown root:root "$BASE/traefik.yaml"
chmod 0644 "$BASE/traefik.yaml"
install -d -o 10000 -g 10000 -m 0700 "$BASE/acme"
if [[ ! -e $BASE/acme/acme.json ]]; then install -o 10000 -g 10000 -m 0600 /dev/null "$BASE/acme/acme.json"; fi
chown 10000:10000 "$BASE/acme/acme.json"
chmod 0600 "$BASE/acme/acme.json"
if [[ ! -e $BASE/state.json ]]; then printf '{}\n' > "$BASE/state.json"; fi
if [[ ! -e $BASE/images.env ]]; then touch "$BASE/images.env"; fi
chown root:root "$BASE/state.json" "$BASE/images.env"
chmod 0600 "$BASE/state.json" "$BASE/images.env"
cat > /etc/fail2ban/jail.d/lwdgy-lab.local <<'JAIL'
[sshd]
enabled = true
backend = systemd
port = 22
maxretry = 3
findtime = 600
bantime = 86400
banaction = ufw
JAIL
# Daily security upgrades at 02:00, with a separate conditional 03:30 reboot.
timedatectl set-timezone America/New_York
cat > /etc/apt/apt.conf.d/99lwdgy-lab-security <<'APT'
#clear Unattended-Upgrade::Allowed-Origins;
Unattended-Upgrade::Allowed-Origins { "${distro_id}:${distro_codename}-security"; };
Unattended-Upgrade::Automatic-Reboot "false";
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT
install -d -m 0755 /etc/systemd/system/apt-daily.timer.d /etc/systemd/system/apt-daily-upgrade.timer.d
cat > /etc/systemd/system/apt-daily.timer.d/lwdgy-lab.conf <<'TIMER'
[Timer]
OnCalendar=
OnCalendar=*-*-* 01:50:00 America/New_York
RandomizedDelaySec=0
Persistent=false
TIMER
cat > /etc/systemd/system/apt-daily-upgrade.timer.d/lwdgy-lab.conf <<'TIMER'
[Timer]
OnCalendar=
OnCalendar=*-*-* 02:00:00 America/New_York
RandomizedDelaySec=0
Persistent=false
TIMER
cat > /etc/systemd/system/lwdgy-lab-reboot.service <<'SERVICE'
[Unit]
Description=Reboot lab only when Ubuntu requests it in maintenance window
ConditionPathExists=/var/run/reboot-required
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/lwdgy-lab-reboot-if-required
SERVICE
cat > /etc/systemd/system/lwdgy-lab-reboot.timer <<'TIMER'
[Unit]
Description=03:30 New York lab maintenance window
[Timer]
OnCalendar=*-*-* 03:30:00 America/New_York
RandomizedDelaySec=0
Persistent=false
[Install]
WantedBy=timers.target
TIMER
systemctl daemon-reload
systemctl enable --now apt-daily.timer apt-daily-upgrade.timer lwdgy-lab-reboot.timer
systemctl restart apt-daily.timer apt-daily-upgrade.timer
# Preserve SSH until successful new-account access proof; hardening is separate.
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban
fail2ban-client reload
cd "$BASE"
env -i PATH="$PATH" DOCKER_CONFIG="$BASE/docker-config" docker compose --env-file "$BASE/images.env" -f "$BASE/compose.yaml" up --detach proxy
printf '\nBootstrap ready. Keep this root session open.\n'
printf '%s\n' 'Open a second terminal: ssh -i ADMIN_PRIVATE_KEY lab-admin@DROPLET_IP' 'Then verify: sudo -n id' 'Only from that verified SSH session: sudo /usr/local/sbin/lwdgy-lab-finalize-ssh --verified-login-and-sudo'
ufw status numbered
fail2ban-client status sshd
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer lwdgy-lab-reboot.timer --no-pager
