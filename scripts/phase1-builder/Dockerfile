# Opt-in source builder, separate from EmuStack's normal Compose runtime.
# Debian Trixie digest matches the main Dockerfile (review on base image upgrades).
FROM debian:trixie-slim@sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31
ENV DEBIAN_FRONTEND=noninteractive HOME=/tmp XDG_CACHE_HOME=/tmp/.cache \
    GIT_OPTIONAL_LOCKS=0 PYTHONDONTWRITEBYTECODE=1
RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates git python3 cmake ninja-build clang lld build-essential pkg-config \
      glslang-tools qt6-base-dev qt6-base-private-dev qt6-multimedia-dev qt6-svg-dev \
      extra-cmake-modules libsdl2-dev libsdl3-dev libsdl3-ttf-dev \
      libarchive-dev libenet-dev libzstd-dev libfaad-dev libpcap0.8-dev \
      libcurl4-openssl-dev libfontconfig1-dev libglew-dev \
      libx11-dev libxext-dev libwayland-dev libxkbcommon-dev \
      libxcursor-dev libxi-dev libxss-dev libxtst-dev libxrandr-dev libxfixes-dev \
      libudev-dev libevdev-dev libasound2-dev libpulse-dev libopenal-dev \
      libssl-dev libvulkan-dev libpng-dev libgl1-mesa-dev libdbus-1-dev \
      wayland-protocols zlib1g-dev libedit-dev libjack-dev libsndio-dev \
      libegl1-mesa-dev libgtk-3-dev; \
    rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
# No COPY: source is mounted read-only and only project data is writable.
CMD ["python3", "scripts/emulator-manager.py", "status"]
