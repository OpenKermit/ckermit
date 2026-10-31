#!/bin/sh
#
# Run a command in a Debian container that holds the i386 musl
# toolchain.  CI builds the i386 static binary (linux+musl for the
# i486 instruction set) with it.
#
# Usage: tools/i386-musl-container.sh <command> [args...]
#
# For example:
#
#   tools/i386-musl-container.sh \
#     tools/build-musl-libs.sh .ci-cache/musl-libs i386
#   tools/i386-musl-container.sh make linux+musl KFLAGS=-march=i486 \
#     KNCURSESINC="-I$PWD/.ci-cache/musl-libs/include \
#       -I$PWD/.ci-cache/musl-libs/include/ncurses" \
#     KNCURSESLIB="-L$PWD/.ci-cache/musl-libs/lib"
#   tools/check-i486-insns.sh wermit
#
# The first call builds a local Docker image named ckermit-i386-musl.
# The command runs as the calling user, in the current directory.
# That directory is mounted at the same path inside the container.
# PKG_CONFIG_PATH passes through from the caller.
#
# musl-tools:i386 provides a musl-gcc wrapper that calls
# i686-linux-gnu-gcc from gcc-i686-linux-gnu.  That compiler links
# libgcc from libgcc-14-dev-i386-cross.  Its 64-bit integer division
# helpers use only i486 instructions.  musl:i386 provides the dynamic
# loader that the "make check" unit test binaries use.  gcc and
# libc6-dev build host programs such as ncurses' tic.
#
# tools/check-i486-insns.sh verifies the finished binary.

set -e

if [ $# -eq 0 ]; then
    echo "usage: $0 <command> [args...]" >&2
    exit 2
fi

IMAGE=ckermit-i386-musl

if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    docker build -t "$IMAGE" - <<'EOF'
FROM debian:trixie
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gcc gcc-i686-linux-gnu libc6-dev make \
        pkg-config musl-tools:i386 \
    && rm -rf /var/lib/apt/lists/*
EOF
fi

exec docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -e PKG_CONFIG_PATH -v "$PWD:$PWD" -w "$PWD" "$IMAGE" "$@"
