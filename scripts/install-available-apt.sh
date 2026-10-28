#!/bin/sh
# Install Debian runtime dependencies and available distro-packaged emulators.
# This is intentionally filtered: one unavailable package never makes the full image fail.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update

base="ca-certificates python3 file x11-utils xauth xdg-utils procps libvulkan1 vulkan-tools mesa-vulkan-drivers libgl1 libegl1 libgl1-mesa-dri libgtk-3-0t64 libgtk-3-0 libasound2t64 libasound2 libpulse0 pulseaudio-utils libx11-6 libxrandr2 libxi6 libxinerama1 libxcursor1 libxkbcommon0 libxkbcommon-x11-0 libwayland-client0 libudev1 libsdl2-2.0-0 libsdl3-0 libqt6core6t64 libqt6gui6t64 libqt6widgets6t64 libqt6svg6 libfuse2t64 libfuse2"
optional="ppsspp-qt ppsspp rpcs3 pcsx2 pcsx2-qt dolphin-emu cemu xemu mgba-qt mgba mupen64plus-ui-console mupen64plus-audio-sdl mupen64plus-input-sdl mupen64plus-rsp-hle mupen64plus-video-rice mupen64plus-video-glide64mk2 libretro-mgba libretro-mupen64plus bsnes mesen melonds wine wine64 winetricks"

available_base=""
for package in $base; do
  if apt-cache show "$package" >/dev/null 2>&1; then
    available_base="$available_base $package"
  fi
done
# shellcheck disable=SC2086
apt-get install -y --no-install-recommends $available_base

available_optional=""
for package in $optional; do
  if apt-cache show "$package" >/dev/null 2>&1; then
    available_optional="$available_optional $package"
  fi
done
if [ -n "$available_optional" ]; then
  # shellcheck disable=SC2086
  if ! apt-get install -y --no-install-recommends $available_optional; then
    echo "WARN: pacote opcional combinado falhou; tentando instalar individualmente." >&2
    for package in $available_optional; do
      apt-get install -y --no-install-recommends "$package" || echo "WARN: pacote opcional indisponível: $package" >&2
    done
  fi
fi

apt-get clean
rm -rf /var/lib/apt/lists/*
