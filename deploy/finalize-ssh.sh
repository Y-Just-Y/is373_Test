#!/usr/bin/env bash
# Invoke only through sudo inside the newly verified is373_Test SSH session.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
[[ $EUID == 0 && $# == 1 && $1 == --verified-login-and-sudo && ${SUDO_USER:-} == is373_Test && -n ${SSH_CONNECTION:-} ]] || {
  echo 'Requires sudo from the verified is373_Test SSH session and explicit --verified-login-and-sudo.' >&2
  exit 2
}
id is373_Test >/dev/null
[[ -s /home/is373_Test/.ssh/authorized_keys ]] || exit 2
CONFIG=/etc/ssh/sshd_config.d/00-lwdgy-lab.conf
TEMP=$(mktemp)
cat > "$TEMP" <<'SSH'
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AuthenticationMethods publickey
AllowUsers is373_Test lab-deploy
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
PermitUserEnvironment no

Match User lab-deploy
    ForceCommand /usr/local/libexec/lwdgy-lab/ssh-deploy
    DisableForwarding yes
    PermitTTY no
SSH
# OpenSSH uses the first matching global setting; the 00 drop-in comes before cloud-init.
if [[ -e $CONFIG ]]; then cp -p "$CONFIG" "$CONFIG.previous"; fi
install -o root -g root -m 0644 "$TEMP" "$CONFIG"
rm -f "$TEMP"
rollback_config() {
  if [[ -e $CONFIG.previous ]]; then mv "$CONFIG.previous" "$CONFIG"; else rm -f "$CONFIG"; fi
}
if ! /usr/sbin/sshd -t; then rollback_config; exit 1; fi
EFFECTIVE=$(/usr/sbin/sshd -T)
for expected in 'permitrootlogin no' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'authenticationmethods publickey'; do
  if ! printf '%s\n' "$EFFECTIVE" | grep -qx "$expected"; then
    echo "Effective SSH config mismatch: $expected. Kept prior configuration." >&2
    rollback_config
    exit 1
  fi
done
CI_CONFIG=$(/usr/sbin/sshd -T -C user=lab-deploy,host=localhost,addr=127.0.0.1)
for expected in 'forcecommand /usr/local/libexec/lwdgy-lab/ssh-deploy' 'disableforwarding yes' 'permittty no'; do
  if ! printf '%s\n' "$CI_CONFIG" | grep -qx "$expected"; then
    echo "CI SSH restriction mismatch: $expected. Kept prior configuration." >&2
    rollback_config
    exit 1
  fi
done
systemctl reload ssh
rm -f "$CONFIG.previous"
printf '%s\n' 'SSH hardened. Keep current sessions open until a third is373_Test SSH connection succeeds and a root SSH connection is denied.'
/usr/sbin/sshd -T | awk '$1 == "permitrootlogin" || $1 == "passwordauthentication" || $1 == "authenticationmethods" || $1 == "allowusers" {print}'
