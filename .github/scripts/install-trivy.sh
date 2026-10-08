#!/usr/bin/env bash
set -euo pipefail

# Fixed official release; SHA-256 matches the trusted installer in the storefront.
version=0.75.0
checksum=c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f
destination=${1:?Pass an installation directory}
[[ "$(uname -s)-$(uname -m)" == Linux-x86_64 ]] || {
  echo 'This CI installer requires Linux x86_64.' >&2
  exit 1
}
mkdir -p "$destination"
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT
curl --fail --silent --show-error --location --retry 3 \
  "https://github.com/aquasecurity/trivy/releases/download/v${version}/trivy_${version}_Linux-64bit.tar.gz" \
  --output "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check -
tar -xzf "$archive" -C "$destination" trivy
"$destination/trivy" version
