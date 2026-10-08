# Verification evidence

Results below were observed on 2026-10-08 and belong to the specified runs and commits. Private keys, passwords, secret values and raw matched secrets are excluded from this public repository.

## Vulnerability gate: verified

[Workflow run 37818014999](https://github.com/Y-Just-Y/is373_Test/actions/runs/37818014999) ran on `main` at commit `62a6406aebeee1123d221129682ccc96c6d6d49e` on 2026-10-08. It completed at 17:38:13 UTC with a **failure** conclusion.

| Check | Observed result |
| --- | --- |
| Application and deployment unit tests | Passed |
| Server script syntax | Passed |
| Working-tree secret scan | Passed |
| Docker build | Passed |
| Container health and restricted runtime | Passed |
| HIGH/CRITICAL image vulnerability scan | Failed |
| Image publication | Skipped |
| Deployment | Skipped |

The image scan downloaded the vulnerability database successfully and completed package analysis. Its retained `image-scan-37818014999-1` artifact reported **48 HIGH package findings and zero CRITICAL findings**: 44 in Debian 13.7 packages and four in Python packages. This was a vulnerability finding result, rather than a database download failure. The gate retained the report and stopped the release before publication or deployment.

The initial image was remediated before the successful releases recorded below. The vulnerability gate remained enabled.

## Successful releases

| Environment | Workflow link | Source commit | Image digest | Observed `/health` result |
| --- | --- | --- | --- | --- |
| QA | [Run 37819341646](https://github.com/Y-Just-Y/is373_Test/actions/runs/37819341646) | [`c2dda8c0e8cc62ad6950b3d80ccaab651f9280b8`](https://github.com/Y-Just-Y/is373_Test/commit/c2dda8c0e8cc62ad6950b3d80ccaab651f9280b8) | `sha256:684f0771a079e399baa64cd1cb9cc90fd7d05d2250cc832676e66eece405b878` | Workflow verified `qa` and the expected full revision over HTTPS |
| Initial production before repository rename | [Run 37818426096](https://github.com/Y-Just-Y/is373_Test/actions/runs/37818426096) | `c147a53683f6251ad41898f2df1baa962dc5c55d` | `sha256:78b351bdb1351e88d6261d543892966b23d478bbd8a14900b00956f728fe086e` | Workflow verified `production` and the expected full revision over HTTPS |
| Production | [Run 37819881976](https://github.com/Y-Just-Y/is373_Test/actions/runs/37819881976) | [`0cb3adfb09e5a539080ca6736c6fb0eeb2644997`](https://github.com/Y-Just-Y/is373_Test/commit/0cb3adfb09e5a539080ca6736c6fb0eeb2644997) | `sha256:b1cc4a191976f1ea2a7ac36213dd1a1de82df38b02f080689c2650a2b833ea5d` | Workflow verified `production` and the expected full revision over HTTPS |

The initial production run completed successfully at 17:42:00 UTC on 2026-10-08. Tests, secret scanning, restricted container checks, vulnerability scanning, anonymous image pull and deployment all passed. Its retained image report contains **zero HIGH and zero CRITICAL findings**.

QA run 37819341646 completed successfully at 17:49:13 UTC using the public registry image `ghcr.io/y-just-y/is373_test`. All three jobs passed, including anonymous digest pull and HTTPS verification. Its retained image report contains **zero HIGH and zero CRITICAL findings**.

[PR #1](https://github.com/Y-Just-Y/is373_Test/pull/1) promoted `qa` to `main` at 17:52:10 UTC. Production run 37819881976 deployed the merge commit at 17:53:19 UTC and completed successfully at 17:53:22 UTC. Its retained image report contains **zero HIGH and zero CRITICAL findings**. Both branches tested, built, scanned and anonymously pulled their own exact source commit before deployment; their image digests differ.

The QA HTTPS health check reported `environment: qa` with revision `c2dda8c0e8cc62ad6950b3d80ccaab651f9280b8`. Production reported `environment: production` with revision `0cb3adfb09e5a539080ca6736c6fb0eeb2644997`. TLS verification remained enabled.

## Visible QA-to-production promotion

| Stage | Screenshot | Observed page |
| --- | --- | --- |
| QA first | [QA Release 2](qa-release-2.png) | `dev.lwdgyasteri.com`, QA environment, Release 2, revision `c2dda8c0e8cc` |
| Production baseline while QA was updated | [Before promotion](production-before-promotion.png) | Captured at 17:49 UTC: `lwdgyasteri.com`, Production environment, Release 1, revision `c147a53683f6` |
| Production after PR #1 promotion | [Production Release 2](production-release-2.png) | `lwdgyasteri.com`, Production environment, Release 2, revision `0cb3adfb09e5` |

The baseline shows that publishing Release 2 to QA did not update production. Production changed after the QA-to-main promotion and successful production pipeline.

## Reverse proxy vulnerability scan

The [Traefik scan summary](proxy-scan.txt) records the pinned proxy image `traefik:v3.7.14@sha256:575fa15b135078fe5e50aa847987d96dbddd7b093c172429618404df73f3fa7c`. Trivy 0.75.0 scanned it at 17:52:19 UTC and returned exit 0 with **zero HIGH and zero CRITICAL findings**. This is a point-in-time result for those severities and the database used.

## Failed unit test blocks build and deployment: verified

The manual workflow input creates a deliberate wrong assertion about the application's actual QA setting. Run it on `qa`:

```sh
gh workflow run pipeline.yml --repo Y-Just-Y/is373_Test \
  --ref qa -f demonstrate_test_failure=true
gh run list --repo Y-Just-Y/is373_Test --branch qa \
  --event workflow_dispatch --limit 5
```

After the run finishes, record its link and job conclusions. The expected evidence is a failing **Tests and secret scan** job at **Demonstrate that a failed unit test blocks deployment**, with **Build and scan the image** and **Deploy the verified digest** both **skipped**. A local simulated failure is not a substitute for this GitHub run.

| Workflow link | Tests | Image | Deployment |
| --- | --- | --- | --- |
| [Run 37818318467](https://github.com/Y-Just-Y/is373_Test/actions/runs/37818318467) | Failed at the intentional unit test | Skipped | Skipped |

This QA run used commit `62a6406aebeee1123d221129682ccc96c6d6d49e` and completed at 17:40:10 UTC on 2026-10-08. The application and deployment tests passed first; the deliberate incorrect environment assertion then failed. GitHub skipped both downstream jobs, confirming that a failing test prevented image build and deployment.

For a normal release, leave `demonstrate_test_failure` cleared or explicitly set it to `false`. The demonstration does not modify application code or the running containers.

## SSH and host controls

The [redacted server inspection](server-security.txt), captured at 17:54:56 UTC, records Ubuntu 24.04.5, active kernel `6.8.0-146-generic`, SSH settings, firewall rules, account permissions, timers and final container restrictions. Administrator access and command-denial tests were verified separately during setup; the [SSH denial record](ssh-denials.txt) contains redacted root/password results.

| Setting or test | Expected result | Observed result |
| --- | --- | --- |
| CI SSH options | `BatchMode=yes`, `IdentitiesOnly=yes`, `StrictHostKeyChecking=yes` | Verified in successful production run 37819881976 and QA run 37819341646 |
| Pinned SSH host key | CI agrees with the established Ed25519 host-key baseline | Baseline used trust on first use, then was confirmed over authenticated SSH; production CI host checking passed |
| Administrator key and sudo | New `is373_Test` SSH connection and sudo work | Verified during account migration; server inspection records the account and sudo rights |
| Root/password SSH | Key-only access; root and password login disabled | Effective settings verified; root and password login tests denied with SSH exit 255 |
| CI command restriction | Deployment request accepted; arbitrary `id` command denied | Successful CI deployments accepted; arbitrary `id` denied with exit 2 |
| Public listening services | SSH 22 and reverse proxy 80/443; app ports remain inside separate internal Docker networks | Server inspection verified 22/80/443 are the only all-interface listening ports; Docker uses its Unix socket. External nine-port check also passed |
| Containers | Separate QA and production; nonroot, read-only, no capabilities or privilege escalation | Final inspection verified both app containers healthy as UID `10001:10001`, root filesystem read-only, `CapDrop=ALL`, `no-new-privileges`, no published ports, and distinct internal networks; proxy also healthy |
| HTTPS | Valid certificates and expected environment/revision on both hostnames | Production run 37819881976 and QA run 37819341646 passed verified HTTPS and revision checks |
| Fail2ban and updates | Active SSH jail; configured update and maintenance timers | Jail threshold 3 failures/600 seconds, ban 86400 seconds; active update 02:00 and conditional reboot 03:30 timers in America/New_York |

The [external port check](external-port-check.txt), captured at 17:55:42 UTC, reached TCP 22, 80 and 443. TCP 2375, 2376, 3000, 8080, 8082 and 8443 were closed or filtered. This tested the nine listed ports; it was not a scan of every possible port.

To check the CI restriction, use the dedicated CI key against `lab-deploy` and request `id`; the helper must deny it. Do not deliberately trigger repeated SSH authentication failures from the administrator's only working connection.

Redaction format for public evidence:

```text
SSH user: lab-deploy
SSH port: 22
Host: [redacted]
Private key: [redacted; stored only in GitHub repository Actions secrets]
Pinned host key: [fingerprint only; trust-on-first-use baseline confirmed over authenticated SSH]
StrictHostKeyChecking: yes
Arbitrary command result: denied; exit status 2
```

Documentation and files under `evidence/` are excluded from push-triggered releases, so recording results does not rebuild or redeploy the website.
