#!/usr/bin/python3 -I
"""Root-owned fixed deployment helper; no shell, mounts or configuration from CI."""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time

BASE = Path("/opt/lwdgy-security-lab")
IMAGE_PREFIX = "ghcr.io/y-just-y/is373_test@"
# Only root-owned saved state may reference the pre-rename registry for rollback.
LEGACY_IMAGE_PREFIX = "ghcr.io/y-just-y/lwdgy-security-lab@"
REQUEST = re.compile(r"deploy (qa|production) (sha256:[a-f0-9]{64}) ([a-f0-9]{40})")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "DOCKER_CONFIG": str(BASE / "docker-config")}


def parse_request(command):
    match = REQUEST.fullmatch(command)
    if not match:
        raise ValueError("Denied: invalid deploy request")
    return match.groups()


def trusted(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError(f"Untrusted deployment path: {path}")


def run(args, *, capture=False):
    return subprocess.run(args, env=ENV, cwd=BASE, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          timeout=300).stdout


def compose(*args):
    return run(["/usr/bin/docker", "compose", "--project-name", "lwdgy-security-lab",
                "--env-file", str(BASE / "images.env"), "--file", str(BASE / "compose.yaml"), *args], capture=True)


def atomic(path, content):
    with tempfile.NamedTemporaryFile(mode="w", dir=BASE, delete=False) as handle:
        os.chmod(handle.name, 0o600)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def validate_state(state):
    if not isinstance(state, dict) or set(state) - {"qa", "production"}:
        raise ValueError("Invalid saved state")
    for environment, release in state.items():
        if not isinstance(release, dict) or set(release) != {"image", "commit"}:
            raise ValueError("Invalid saved release")
        image = release["image"]
        prefix = next((candidate for candidate in (IMAGE_PREFIX, LEGACY_IMAGE_PREFIX)
                       if isinstance(image, str) and image.startswith(candidate)), None)
        if prefix is None:
            raise ValueError("Invalid saved image repository")
        parse_request(f"deploy {environment} {image.removeprefix(prefix)} {release['commit']}")
    return state


def write_images(state):
    lines = []
    for environment, release in sorted(state.items()):
        prefix = environment.upper()
        lines += [f"{prefix}_IMAGE={release['image']}", f"{prefix}_COMMIT={release['commit']}"]
    atomic(BASE / "images.env", "\n".join(lines) + "\n")


def health(environment, commit):
    service = f"app-{environment}"
    # Inside the app: checks readiness and declared environment/revision.
    code = ("import json,urllib.request; "
            "h=json.load(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)); "
            f"assert h['status']=='ok' and h['environment']=={environment!r} and h['revision']=={commit!r}")
    for _ in range(12):
        try:
            compose("exec", "--no-TTY", service, "python", "-c", code)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            time.sleep(5)
    raise RuntimeError(f"Health verification failed for {environment}")


def external_health(environment, commit):
    host = "dev.lwdgyasteri.com" if environment == "qa" else "lwdgyasteri.com"
    for _ in range(12):
        try:
            body = run(["/usr/bin/curl", "--fail", "--silent", "--show-error", "--max-time", "8",
                        "--resolve", f"{host}:443:127.0.0.1", f"https://{host}/health"], capture=True)
            result = json.loads(body)
            if result.get("status") == "ok" and result.get("environment") == environment and result.get("revision") == commit:
                return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        time.sleep(5)
    raise RuntimeError("HTTPS router/certificate/revision verification failed")


def acquire_lock(lock, timeout=300):
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Deployment lock is still busy after the allowed wait") from None
            time.sleep(min(0.25, remaining))


def deploy(environment, digest, commit):
    for path in [BASE, BASE / "compose.yaml", BASE / "traefik.yaml", BASE / "dynamic",
                 BASE / "dynamic/routes.yaml", BASE / "images.env", BASE / "state.json", BASE / "docker-config"]:
        trusted(path)
    with (BASE / "deploy.lock").open("a") as lock:
        acquire_lock(lock)
        old_state = validate_state(json.loads((BASE / "state.json").read_text()))
        image = IMAGE_PREFIX + digest
        run(["/usr/bin/docker", "pull", image])
        revision = run(["/usr/bin/docker", "image", "inspect", "--format",
                        '{{index .Config.Labels "org.opencontainers.image.revision"}}', image], capture=True).strip()
        if revision != commit:
            raise ValueError("Image revision label does not match requested commit")
        new_state = {**old_state, environment: {"image": image, "commit": commit}}
        write_images(new_state)
        try:
            compose("--profile", environment, "up", "--detach", "--no-deps", f"app-{environment}")
            health(environment, commit)
            external_health(environment, commit)
            atomic(BASE / "state.json", json.dumps(new_state, indent=2) + "\n")
        except Exception:
            print("Deployment failed; restoring previous release.", file=sys.stderr)
            write_images(old_state)
            if environment in old_state:
                compose("--profile", environment, "up", "--detach", "--no-deps", f"app-{environment}")
                health(environment, old_state[environment]["commit"])
                external_health(environment, old_state[environment]["commit"])
                print("Rollback verified.", file=sys.stderr)
            else:
                compose("--profile", environment, "stop", f"app-{environment}")
                compose("--profile", environment, "rm", "--force", f"app-{environment}")
                print("Initial failed release removed; proxy remains available.", file=sys.stderr)
            raise
        print(f"Deployed {environment}: {commit} {digest}")


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise ValueError("Root helper takes no command-line arguments")
    command = sys.stdin.buffer.readline(257)
    if not command.endswith(b"\n") or len(command) > 256 or sys.stdin.buffer.read(1):
        raise ValueError("Denied: invalid request framing")
    deploy(*parse_request(command[:-1].decode("ascii")))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
