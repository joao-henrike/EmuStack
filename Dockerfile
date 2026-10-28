# Debian Official Image index digest, observed on Docker Hub on 2026-10-28.
# Override only after reviewing a new official digest and updating the lock/docs.
ARG DEBIAN_BASE_IMAGE=debian:trixie-slim@sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31
ARG APT_SNAPSHOT_TIMESTAMP=
# Build stage: best-effort Linux build of pinned official KytyPS5 source.
FROM ${DEBIAN_BASE_IMAGE} AS kyty-builder
ARG APT_SNAPSHOT_TIMESTAMP
ARG BUILD_KYTYPS5=1
ARG KYTYPS5_REF=KytyPS5-2026-10-26-f90a8b1
ARG KYTYPS5_EXPECTED_SHORT=f90a8b1
RUN mkdir -p /out/kytyps5
RUN set -eu; \
    if [ -n "$APT_SNAPSHOT_TIMESTAMP" ]; then \
      case "$APT_SNAPSHOT_TIMESTAMP" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) ;; *) echo "Invalid APT_SNAPSHOT_TIMESTAMP" >&2; exit 2;; esac; \
      rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; \
      printf 'Types: deb\nURIs: https://snapshot.debian.org/archive/debian/%s/\nSuites: trixie trixie-updates\nComponents: main\nCheck-Valid-Until: no\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: https://snapshot.debian.org/archive/debian-security/%s/\nSuites: trixie-security\nComponents: main\nCheck-Valid-Until: no\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' "$APT_SNAPSHOT_TIMESTAMP" "$APT_SNAPSHOT_TIMESTAMP" > /etc/apt/sources.list.d/emustack-snapshot.sources; \
    fi; \
    if [ "$BUILD_KYTYPS5" = "1" ]; then \
      if apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git cmake ninja-build clang lld glslang-tools python3 pkg-config \
        qt6-base-dev libvulkan-dev libgl1-mesa-dev libx11-dev libxcursor-dev libxext-dev \
        libxfixes-dev libxi-dev libxrandr-dev libxss-dev libxtst-dev libxkbcommon-dev \
        libasound2-dev libpulse-dev libudev-dev libdbus-1-dev libwayland-dev wayland-protocols \
        && git clone --depth 1 --branch "$KYTYPS5_REF" https://github.com/KytyPS5/KytyPS5.git /src/kytyps5 \
        && test "$(git -C /src/kytyps5 rev-parse --short=7 HEAD)" = "$KYTYPS5_EXPECTED_SHORT" \
        && git -C /src/kytyps5 submodule update --init --recursive \
        && cmake -S /src/kytyps5 -B /src/kytyps5/_Build/linux -G Ninja \
          -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
          -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/cmake \
        && cmake --build /src/kytyps5/_Build/linux --target launcher --parallel 2 \
        && cmake --install /src/kytyps5/_Build/linux --prefix /out/kytyps5; then \
        echo "KytyPS5 source build completed"; \
      else \
        echo "WARN: KytyPS5 source build failed; continuing with other emulators."; \
      fi; \
    else echo "INFO: KytyPS5 source build disabled by BUILD_KYTYPS5=0"; fi

FROM ${DEBIAN_BASE_IMAGE} AS runtime
ARG APT_SNAPSHOT_TIMESTAMP
ARG PUID=1000
ARG PGID=1000
ARG INSTALL_UPSTREAM=1
ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/emu \
    APPIMAGE_EXTRACT_AND_RUN=1 \
    QT_X11_NO_MITSHM=1 \
    SDL_VIDEODRIVER=x11 \
    EMUSTACK_GAMES_DIR=/games \
    EMUSTACK_BIN_DIR=/opt/emustack/installed \
    EMUSTACK_USER_BIN_DIR=/custom-emulators \
    EMUSTACK_INSTALL_REPORT=/opt/emustack/install-report.json \
    EMUSTACK_LOG_DIR=/home/emu/.local/state/emustack/logs \
    EMUSTACK_SYSTEMS_PATH=/opt/emustack/console-systems.json \
    EMUSTACK_CEMU_MLC_PATH=/home/emu/.local/share/Cemu/mlc01 \
    EMUSTACK_XEMU_CONFIG=/home/emu/.config/xemu/xemu.toml
WORKDIR /opt/emustack
COPY catalog.json /opt/emustack/catalog.json
COPY console-systems.json /opt/emustack/console-systems.json
COPY environments.json /opt/emustack/environments.json
COPY console_agent.py /opt/emustack/console_agent.py
COPY console_modes.py /opt/emustack/console_modes.py
COPY release-lock.json /opt/emustack/release-lock.json
COPY emustack.py /opt/emustack/emustack.py
COPY webapp.py /opt/emustack/webapp.py
COPY README.md /opt/emustack/README.md
COPY game-sources.json /opt/emustack/game-sources.json
COPY docs/ /opt/emustack/docs/
COPY web/ /opt/emustack/web/
COPY scripts/install-available-apt.sh /tmp/install-available-apt.sh
COPY scripts/install-upstream.py /opt/emustack/scripts/install-upstream.py
COPY --from=kyty-builder /out/kytyps5 /opt/emustack/installed/kytyps5
RUN if [ -n "$APT_SNAPSHOT_TIMESTAMP" ]; then \
      case "$APT_SNAPSHOT_TIMESTAMP" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) ;; *) echo "Invalid APT_SNAPSHOT_TIMESTAMP" >&2; exit 2;; esac; \
      rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; \
      printf 'Types: deb\nURIs: https://snapshot.debian.org/archive/debian/%s/\nSuites: trixie trixie-updates\nComponents: main\nCheck-Valid-Until: no\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: https://snapshot.debian.org/archive/debian-security/%s/\nSuites: trixie-security\nComponents: main\nCheck-Valid-Until: no\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' "$APT_SNAPSHOT_TIMESTAMP" "$APT_SNAPSHOT_TIMESTAMP" > /etc/apt/sources.list.d/emustack-snapshot.sources; \
    fi \
    && chmod +x /tmp/install-available-apt.sh /opt/emustack/emustack.py /opt/emustack/console_agent.py /opt/emustack/scripts/install-upstream.py \
    && /tmp/install-available-apt.sh \
    && mkdir -p /opt/emustack/installed /opt/emustack/dropin /games /bios /saves /home/emu/.config /home/emu/.cache \
    && if [ "$INSTALL_UPSTREAM" = "1" ]; then \
         python3 /opt/emustack/scripts/install-upstream.py \
           --target /opt/emustack/installed --catalog /opt/emustack/catalog.json \
           --report /opt/emustack/install-report.json --lock /opt/emustack/release-lock.json; \
       else \
         python3 /opt/emustack/scripts/install-upstream.py --skip-network \
           --target /opt/emustack/installed --catalog /opt/emustack/catalog.json \
           --report /opt/emustack/install-report.json --lock /opt/emustack/release-lock.json; \
       fi \
    && if ! getent group "${PGID}" >/dev/null; then groupadd -g "${PGID}" emu; fi \
    && if ! getent passwd "${PUID}" >/dev/null; then useradd -m -u "${PUID}" -g "${PGID}" -s /bin/bash emu; fi \
    && chown -R "${PUID}:${PGID}" /home/emu /opt/emustack/installed /games /bios /saves \
    && ln -sf /opt/emustack/emustack.py /usr/local/bin/emustack \
    && rm -f /tmp/install-available-apt.sh \
    && rm -rf /var/lib/apt/lists/*
USER ${PUID}:${PGID}
ENV PATH="/opt/emustack/installed/kytyps5:/opt/emustack/installed:/home/emu/.local/bin:/usr/local/bin:/usr/bin:/bin" \
    EMUSTACK_WEB_DOCS_DIR=/opt/emustack/docs \
    EMUSTACK_SOURCES_PATH=/opt/emustack/game-sources.json \
    XDG_CONFIG_HOME=/home/emu/.config \
    XDG_CACHE_HOME=/home/emu/.cache
ENTRYPOINT ["python3", "/opt/emustack/emustack.py"]
CMD ["list"]
