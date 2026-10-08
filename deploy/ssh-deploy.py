#!/usr/bin/python3 -I
"""Forced SSH entry point. Never execute the original command as shell text."""
import os
import re
import subprocess
import sys

REQUEST = re.compile(r"deploy (qa|production) (sha256:[a-f0-9]{64}) ([a-f0-9]{40})")


def main():
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    if not REQUEST.fullmatch(command):
        print("Denied: expected deploy qa|production sha256:<64hex> <40hex>.", file=sys.stderr)
        return 2
    return subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/local/sbin/lwdgy-lab-deploy"],
        input=command + "\n", text=True,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
