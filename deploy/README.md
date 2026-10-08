# One-Droplet lab deployment

These files deploy the lab on a new Ubuntu 24.04 Droplet. Public DNS records must point `lwdgyasteri.com` and `dev.lwdgyasteri.com` (DNS is case-insensitive) at the new Droplet. Remove stale AAAA records unless the new IPv6 address is configured. DigitalOcean's cloud firewall should permit inbound TCP 22, 80 and 443 only, plus outbound traffic.

The trusted server files live in `/opt/lwdgy-security-lab`, owned by root. Traefik 3.7.14 is pinned by its official multi-platform digest. It uses fixed file routes with separate internal QA and production networks and has no Docker socket mount or dashboard. Only Traefik publishes ports. Each app runs as UID 10001 with a read-only filesystem, no Linux capabilities and no new privileges. Certificates persist in `acme/acme.json`, mode 0600, owned by Traefik's numeric identity. App images come from the public `ghcr.io/y-just-y/is373_test` package by digest; no registry credentials are needed.

## Bootstrap and access proof

1. Generate separate Ed25519 administrator and CI keypairs locally. Keep private keys out of this repository. Attach the administrator public key when creating the Droplet. Verify the server's Ed25519 host-key fingerprint through the DigitalOcean console before connecting or configuring `DEPLOY_KNOWN_HOSTS`; do not trust an unverified `ssh-keyscan` result.
2. Copy the reviewed `deploy/` directory and the two **public** keys to `/root` on the new Droplet. In the existing root SSH session, use the actual public-key filenames and a real certificate contact email:

   ```sh
   bash /root/deploy/bootstrap.sh /root/is373_Test.pub /root/lab-deploy.pub you@example.com
   ```

   The bootstrap checks the OS and existing UFW rules. It stops if it finds firewall allowances beyond SSH/HTTP/HTTPS; review any reported rule before proceeding. It installs Docker from its official apt repository, prepares the root-owned deploy helpers, enables fail2ban and schedules updates. It starts only Traefik; absent application containers may return 502 until the first successful deployments. Root SSH is preserved during this stage.
3. Keep the root session open. From a **second local terminal**, prove the new administrator SSH key and sudo access:

   ```sh
   ssh -i /absolute/path/is373_Test is373_Test@DROPLET_IP
   sudo -n id
   ```

   The owner-authorized `is373_Test` identity has full, passwordless sudo; its login password is locked. Protect this private key as administrator access. `lab-deploy` has no Docker-group membership, no shell access, and can sudo only the no-argument deploy helper.
4. From that verified administrator SSH session, finalize access controls:

   ```sh
   sudo --preserve-env=SSH_CONNECTION /usr/local/sbin/lwdgy-lab-finalize-ssh --verified-login-and-sudo
   ```

   This requires `SUDO_USER=is373_Test` and an SSH session. It validates `sshd -t` and effective settings before reloading SSH. It then requires key authentication, disables passwords and root login, allows only the two lab accounts, disables SSH forwarding and fixes the CI forced command. Open a third administrator connection and test a root connection is denied before closing the original sessions.

## Restricted deployment

Set GitHub secrets `DROPLET_HOST`, `DEPLOY_SSH_KEY` and `DEPLOY_KNOWN_HOSTS` to the new host, the dedicated CI private key, and the verified host-key line. Use protected QA and production environments with the workflow in this repository. The sole accepted SSH command is:

```text
deploy qa sha256:<64 lowercase hex> <40 lowercase commit>
deploy production sha256:<64 lowercase hex> <40 lowercase commit>
```

The wrapper validates the **entire** original command and sends it as data to a fixed root helper. The helper takes no CLI arguments, validates the request again, constructs the fixed image repository, pulls anonymously and verifies its OCI revision label. It never executes CI text as a shell command. Root-owned Compose routes, networks, mounts and runtime settings cannot be supplied by CI. A server lock serializes deployments; deploying QA recreates only QA, and deploying production recreates only production.

The helper verifies `/health` inside the target container and over HTTPS through the correct router, including environment and full commit. TLS verification remains enabled. A failed release restores and verifies the previous target release; an initial failed release is stopped and removed. Release state is committed only after checks pass. A rollback failure exits with an error and requires administrator attention.

## Host checks and maintenance

In the administrator session:

```sh
sudo ufw status numbered
sudo ss -lntp
sudo fail2ban-client status sshd
sudo sshd -T | awk '$1 == "permitrootlogin" || $1 == "passwordauthentication" || $1 == "authenticationmethods" || $1 == "allowusers" {print}'
sudo -l -U lab-deploy
sudo docker compose --env-file /opt/lwdgy-security-lab/images.env -f /opt/lwdgy-security-lab/compose.yaml ps
sudo systemctl list-timers apt-daily.timer apt-daily-upgrade.timer lwdgy-lab-reboot.timer --no-pager
curl --fail https://dev.lwdgyasteri.com/health
curl --fail https://lwdgyasteri.com/health
```

There should be no public app port, Docker API port 2375/2376, or Traefik dashboard port. Docker-published ports bypass UFW, so the checked-in Compose file intentionally publishes only 80 and 443. Fail2ban bans an SSH source for 86,400 seconds after 3 failures within 600 seconds. Test denial using the CI key (`ssh ... lab-deploy@HOST id` must fail); do not deliberately trigger bans from the administrator's only working connection.

Ubuntu security updates run daily at **02:00 America/New_York**, with package-list refresh at 01:50. Automatic reboot inside unattended-upgrades is disabled. A separate maintenance timer runs at **03:30 America/New_York**, and reboots only when `/var/run/reboot-required` exists and package updates/deployment are idle. Missed windows are not replayed immediately after boot. Review logs with `sudo journalctl -u apt-daily-upgrade.service -u lwdgy-lab-reboot.service` and `/var/log/unattended-upgrades/`. Docker package and Traefik image updates need a deliberate review; pinned container images do not update themselves.

## Local verification

```sh
bash -n deploy/bootstrap.sh deploy/finalize-ssh.sh deploy/reboot-if-required.sh
python3 -m unittest discover -s deploy -p 'test_*.py' -v
docker compose -f deploy/compose.yaml config --quiet
```

The helper tests exercise injection denial, framing, filesystem trust, revision mismatch and rollback while mocking Docker. Health tests use the actual application response body, verify the environment/revision contract, and check that the HTTPS targets and router domains agree. They do not claim a remote deployment or TLS issuance has happened. Perform the host and HTTPS checks above after setup.

## Primary references

- [Docker Engine installation on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) — official repository installation and Docker/UFW boundary.
- [Traefik file provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/) — fixed dynamic routes without a Docker socket.
- [Traefik ACME resolver](https://doc.traefik.io/traefik/reference/install-configuration/tls/certificate-resolvers/acme/) — HTTP challenge and persistent certificate storage.
- [Official Traefik 3.7.14 image metadata](https://github.com/docker-library/repo-info/blob/master/repos/traefik/remote/3.7.14.md) — multi-platform digest verified 2026-10-08.
- [Ubuntu automatic security updates](https://documentation.ubuntu.com/security/security-updates/) — drop-in configuration and update behavior.
