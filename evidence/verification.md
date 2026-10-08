# Verification evidence

Observed results belong to the run and commit shown below. Pending rows are not claims of completed verification. Private keys, secret values and raw matched secrets must not be included in this public repository.

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

The initial image required remediation. This failed run does not establish that a later image is clean or that either website has been deployed. Record the later passing run and its immutable digest below.

## Successful releases

| Environment | Workflow link | Source commit | Image digest | Observed `/health` result |
| --- | --- | --- | --- | --- |
| QA | Pending | Pending | Pending | Pending |
| Initial production before repository rename | [Run 37818426096](https://github.com/Y-Just-Y/is373_Test/actions/runs/37818426096) | `c147a53683f6251ad41898f2df1baa962dc5c55d` | `sha256:78b351bdb1351e88d6261d543892966b23d478bbd8a14900b00956f728fe086e` | Workflow verified `production` and the expected full revision over HTTPS |
| Production under the renamed repository/image | Pending | Pending | Pending | Pending |

The initial production run completed successfully at 17:42:00 UTC on 2026-10-08. Tests, secret scanning, restricted container checks, vulnerability scanning, anonymous image pull and deployment all passed. The retained image report contains **zero HIGH and zero CRITICAL findings**. The registry image name was subsequently changed to `ghcr.io/y-just-y/is373_test`; a new successful run is required to verify the renamed release path.

Copy the source commit and `sha256` digest from each successful workflow's deployment summary. Verify that `https://dev.lwdgyasteri.com/health` reports `environment: qa` and that `https://lwdgyasteri.com/health` reports `environment: production`. Both responses must report the expected full source commit.

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

## SSH and host controls: pending

Use the host commands in [`deploy/README.md`](../deploy/README.md) after the administrator key and sudo have been verified. Save only redacted results here.

| Setting or test | Expected result | Observed result |
| --- | --- | --- |
| CI SSH options | `BatchMode=yes`, `IdentitiesOnly=yes`, `StrictHostKeyChecking=yes` | Verified in successful production run 37818426096 |
| Pinned SSH host key | CI agrees with the established Ed25519 host-key baseline | Baseline used trust on first use, then was confirmed over authenticated SSH; production CI host checking passed |
| Administrator key and sudo | New `is373_Test` SSH connection and sudo work | Administrator access verified during account migration; complete command output pending |
| Root/password SSH | Disabled after replacement administrator access is proved | Pending |
| CI command restriction | Deployment request accepted; arbitrary `id` command denied | Pending |
| Public listening services | SSH 22 and reverse proxy 80/443; app ports remain inside separate internal Docker networks | Pending |
| Containers | Separate QA and production; nonroot, read-only, no capabilities or privilege escalation | Pending |
| HTTPS | Valid certificates and expected environment/revision on both hostnames | Pending |
| Fail2ban and updates | Active SSH jail; configured update and maintenance timers | Pending |

To check the CI restriction, use the dedicated CI key against `lab-deploy` and request `id`; the helper must deny it. Do not deliberately trigger repeated SSH authentication failures from the administrator's only working connection.

Redaction format for public evidence:

```text
SSH user: lab-deploy
SSH port: 22
Host: [redacted]
Private key: [redacted; stored only in GitHub environment secrets]
Pinned host key: [fingerprint only; trust-on-first-use baseline confirmed over authenticated SSH]
StrictHostKeyChecking: yes
Arbitrary command result: [actual denial and exit status]
```

Documentation and files under `evidence/` are excluded from push-triggered releases, so recording results does not rebuild or redeploy the website.
