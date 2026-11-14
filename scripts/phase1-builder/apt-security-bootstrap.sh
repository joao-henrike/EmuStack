#!/bin/sh
# Bootstrap APT safely on the pinned Debian Trixie base.
# CVE-2026-109518 affects APT 3.0.3; Trixie is fixed in 3.0.4.
set -eu
export DEBIAN_FRONTEND=noninteractive

MIN_APT_VERSION="3.0.4"

# The initial APT binary may be vulnerable. Disable automatic retries before
# refreshing indexes or downloading the fixed APT package.
apt-get -o Acquire::Retries=0 update

candidate="$(apt-cache policy apt | awk '/Candidate:/ { print $2; exit }')"
if [ -z "$candidate" ] || [ "$candidate" = "(none)" ]; then
  echo "ERROR: no APT candidate is available from the configured Debian repositories." >&2
  exit 2
fi
if ! dpkg --compare-versions "$candidate" ge "$MIN_APT_VERSION"; then
  echo "ERROR: APT candidate $candidate is older than required $MIN_APT_VERSION." >&2
  echo "Use a newer Debian security snapshot; refusing to continue with vulnerable APT." >&2
  exit 2
fi

apt-get -o Acquire::Retries=0 install -y --no-install-recommends apt
installed="$(dpkg-query -W -f='${Version}' apt)"
if ! dpkg --compare-versions "$installed" ge "$MIN_APT_VERSION"; then
  echo "ERROR: installed APT $installed is older than required $MIN_APT_VERSION." >&2
  exit 2
fi

# Apply all available stable/security upgrades before adding runtime packages.
apt-get upgrade -y --no-install-recommends

installed="$(dpkg-query -W -f='${Version}' apt)"
if ! dpkg --compare-versions "$installed" ge "$MIN_APT_VERSION"; then
  echo "ERROR: APT version regressed after package upgrade: $installed." >&2
  exit 2
fi
echo "APT security bootstrap OK: $installed (minimum $MIN_APT_VERSION)"
