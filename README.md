# IS373 Test

Production: [lwdgyasteri.com](https://lwdgyasteri.com) · QA: [dev.lwdgyasteri.com](https://dev.lwdgyasteri.com)

A small Python website for a secure CI/CD lab. It uses the Python standard library and Docker, with separate QA and production containers behind an HTTPS reverse proxy.

| Branch | Environment | URL |
| --- | --- | --- |
| `qa` | QA | https://dev.lwdgyasteri.com |
| `main` | Production | https://lwdgyasteri.com |

## Run and test

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s deploy -p 'test_*.py' -v
APP_ENV=qa RELEASE_COMMIT=local python3 app/main.py
```

The website listens on port 8080. `GET /health` reports the environment and source revision.

```sh
docker build --pull -t is373-test:local .
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
  -p 127.0.0.1:8080:8080 -e APP_ENV=qa -e RELEASE_COMMIT=local \
  is373-test:local
```

## Release flow

Open a pull request to `qa` for testing. A push to `qa` deploys QA after all checks pass. After verifying QA, promote the change with a pull request from `qa` to `main`; merging it runs the same checks and deploys production. Configure branch protection to require the **Tests and secret scan** and **Build and scan the image** checks.

Each branch builds and scans its own exact commit. QA verifies the source commit; production verifies the merge commit after promotion. Each deployment uses its own verified image digest.

The workflow runs application tests and a secret scan before building. It starts the built image with reduced privileges, checks its health, and scans for HIGH and CRITICAL vulnerabilities. A failed test, build, scan, image publication, or anonymous registry pull prevents deployment. Pull requests run checks without deployment credentials.

For evidence of the failure gate, run the workflow manually on `qa` with **demonstrate_test_failure** selected. It deliberately makes a wrong assertion about the application's QA setting: the tests job fails, and the image and deployment jobs are skipped. Leave the option cleared for normal releases. Pushes that change only `README.md`, `deploy/README.md`, or `evidence/` do not trigger a release.

The workflow publishes `ghcr.io/y-just-y/is373_test:sha-<commit>-<run>-<attempt>`. The unique tag records the full source commit. Deployment uses the immutable `sha256` digest of that exact scanned image. No `latest` tag is used. The GHCR package must be **public**; the workflow verifies that the digest can be pulled anonymously before deployment. After the first publication, set the package visibility to public and rerun the workflow if the initial anonymous pull fails.

GitHub Actions are pinned to full commit SHAs. Trivy 0.75.0 is downloaded from its [official release](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0) and checked against a fixed SHA-256 before execution. Scan reports are retained as workflow artifacts.

## SSH and server setup

GitHub environments named `qa` and `production` identify the deployment targets. This lab configures the following repository-level Actions secrets, inherited by both environments:

| Secret | Value |
| --- | --- |
| `DROPLET_HOST` | Droplet IP address or SSH hostname |
| `DEPLOY_SSH_KEY` | Dedicated deployment private key |
| `DEPLOY_KNOWN_HOSTS` | Exact host/IP and pinned SSH public host key line |

Keep private keys and environment files out of Git. Restrict access to the environments and workflow changes. The matching public key on the server belongs to `lab-deploy` and is restricted to the deployment helper. It accepts only `deploy <qa|production> <sha256:digest> <commit>` and uses a fixed registry image name. QA and production use separate containers and environment configuration.

SSH uses port 22, `BatchMode=yes`, `IdentitiesOnly=yes`, and `StrictHostKeyChecking=yes`. This lab established its host-key baseline using trust on first use, then confirmed the pinned key over authenticated SSH. CI requires that same pinned key. Workflow summaries show redacted SSH settings, the deployed digest, the commit, and the target URL. The server pulls the public image without storing registry credentials.

Server installation and hardening commands are in [`deploy/README.md`](deploy/README.md). Administrative SSH access uses `is373_Test`; CI uses the restricted `lab-deploy` account. Run privileged setup from the administrator's SSH session. Only the reverse proxy publishes HTTP/HTTPS ports; QA and production application ports are reachable through separate internal Docker networks and are not published on the host.

## Test Evidence

The [verification record](evidence/verification.md) contains exact commits, image digests and job outcomes. The [redacted server inspection](evidence/server-security.txt) records the host controls.

| Requirement | Verified evidence |
| --- | --- |
| Successful QA workflow | [Run 37819341646](https://github.com/Y-Just-Y/is373_Test/actions/runs/37819341646): renamed image deployed, HTTPS verified, commit `c2dda8c0e8cc` |
| Successful production workflow | [Run 37819881976](https://github.com/Y-Just-Y/is373_Test/actions/runs/37819881976): [PR #1](https://github.com/Y-Just-Y/is373_Test/pull/1) promoted QA; merge commit `0cb3adfb09e5` deployed and HTTPS verified |
| Failed test blocks deployment | [Run 37818318467](https://github.com/Y-Just-Y/is373_Test/actions/runs/37818318467): intentional unit test failed; image/deploy jobs skipped |
| QA and production remain separate | [QA Release 2](evidence/qa-release-2.png), [production before promotion](evidence/production-before-promotion.png), and [production after promotion](evidence/production-release-2.png); separate internal networks |
| HTTPS and restricted SSH | QA and initial production HTTPS checks passed; root/password SSH denied with exit 255; arbitrary CI command denied with exit 2 |
| Vulnerability and secret scans | QA and production runs passed secret scans; both image reports and the [Traefik proxy scan](evidence/proxy-scan.txt) report zero HIGH/CRITICAL findings |
| Failed vulnerability scan blocks release | [Run 37818014999](https://github.com/Y-Just-Y/is373_Test/actions/runs/37818014999): image scan failed; publication and deployment skipped |

To rebuild a release, rerun the workflow on the intended `qa` or `main` commit. Each attempt gets its own tag; the reported digest and health revision identify what reached the server.
