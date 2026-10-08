# LWDGY Security Lab

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
docker build --pull -t lwdgy-security-lab:local .
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
  -p 127.0.0.1:8080:8080 -e APP_ENV=qa -e RELEASE_COMMIT=local \
  lwdgy-security-lab:local
```

## Release flow

Open a pull request to `qa` for testing. A push to `qa` deploys QA after all checks pass. After verifying QA, promote the change with a pull request from `qa` to `main`; merging it runs the same checks and deploys production. Configure branch protection to require the **Tests and secret scan** and **Build and scan the image** checks.

The workflow runs application tests and a secret scan before building. It starts the built image with reduced privileges, checks its health, and scans for HIGH and CRITICAL vulnerabilities. A failed test, build, scan, image publication, or anonymous registry pull prevents deployment. Pull requests run checks without deployment credentials.

For evidence of the failure gate, run the workflow manually on `qa` with **demonstrate_test_failure** selected. It deliberately makes a wrong assertion about the application's QA setting: the tests job fails, and the image and deployment jobs are skipped. Leave the option cleared for normal releases. Pushes that change only `README.md`, `deploy/README.md`, or `evidence/` do not trigger a release.

The workflow publishes `ghcr.io/y-just-y/lwdgy-security-lab:sha-<commit>-<run>-<attempt>`. The unique tag records the full source commit. Deployment uses the immutable `sha256` digest of that exact scanned image. No `latest` tag is used. The GHCR package must be **public**; the workflow verifies that the digest can be pulled anonymously before deployment. After the first publication, set the package visibility to public and rerun the workflow if the initial anonymous pull fails.

GitHub Actions are pinned to full commit SHAs. Trivy 0.75.0 is downloaded from its [official release](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0) and checked against a fixed SHA-256 before execution. Scan reports are retained as workflow artifacts.

## SSH and server setup

Create GitHub environments named `qa` and `production`. Set these secrets in each environment:

| Secret | Value |
| --- | --- |
| `DROPLET_HOST` | Droplet IP address or SSH hostname |
| `DEPLOY_SSH_KEY` | Dedicated deployment private key |
| `DEPLOY_KNOWN_HOSTS` | Exact host/IP and SSH public host key line, verified using the Droplet console |

Keep private keys and environment files out of Git. Restrict access to the environments and workflow changes. The matching public key on the server belongs to `lab-deploy` and is restricted to the deployment helper. It accepts only `deploy <qa|production> <sha256:digest> <commit>` and uses a fixed registry image name. QA and production use separate containers and environment configuration.

SSH uses port 22, `BatchMode=yes`, `IdentitiesOnly=yes`, and `StrictHostKeyChecking=yes`. Obtain and verify the host fingerprint through the Droplet console before adding `DEPLOY_KNOWN_HOSTS`; do not trust an unverified `ssh-keyscan` result. Workflow summaries show redacted SSH settings, the deployed digest, the commit, and the target URL. The server pulls the public image without storing registry credentials.

Server installation and hardening commands are in [`deploy/README.md`](deploy/README.md). Run privileged setup from the server console or the administrator's SSH session. Keep that session open until the replacement SSH account works. Only the reverse proxy should expose HTTP/HTTPS; application ports bind to loopback.

## Evidence

Add actual run links and observed results after provisioning and deployment. These placeholders do not claim a successful run.

| Requirement | Verified evidence |
| --- | --- |
| Successful QA workflow | Pending: workflow run link, source SHA, digest |
| Successful production workflow | Pending: workflow run link, source SHA, digest |
| Failed test blocks deployment | Pending: failing test run with image/deploy jobs skipped |
| QA and production remain separate | Pending: both `/health` responses and container status |
| HTTPS and restricted SSH | Pending: certificate check and redacted SSH verification |
| Vulnerability and secret scans | Pending: successful workflow artifacts |

To rebuild a release, rerun the workflow on the intended `qa` or `main` commit. Each attempt gets its own tag; the reported digest and health revision identify what reached the server.
