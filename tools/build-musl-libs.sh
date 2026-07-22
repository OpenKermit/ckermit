#!/bin/sh
#
# Build static OpenSSL, zlib, and ncurses against musl libc for the
# linux+ssl+musl and linux+musl makefile targets.
#
# This builds all three from source against musl-gcc into a private
# prefix. That prefix is then passed to those targets via
# KSSLINC/KSSLLIB (or KZLIBINC/KZLIBLIB for linux+musl, which has no
# OpenSSL) and KNCURSESINC, e.g.:
#
#   tools/build-musl-libs.sh .ci-cache/musl-libs
#   make linux+ssl+musl \
#     KSSLINC="-I$(pwd)/.ci-cache/musl-libs/include" \
#     KSSLLIB="-L$(pwd)/.ci-cache/musl-libs/lib" \
#     KNCURSESINC="-I$(pwd)/.ci-cache/musl-libs/include/ncurses"
#
# Idempotent: does nothing if <prefix>/lib/libssl.a already exists,
# so CI can cache the prefix directory across runs.

set -e

PREFIX=${1:?"usage: $0 <prefix-dir>"}

ZLIB_VERSION=1.3.1
ZLIB_URL="https://github.com/madler/zlib/releases/download/\
v$ZLIB_VERSION/zlib-$ZLIB_VERSION.tar.gz"
ZLIB_SHA256=9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23

OPENSSL_VERSION=3.5.6
OPENSSL_URL="https://www.openssl.org/source/openssl-$OPENSSL_VERSION.tar.gz"
OPENSSL_SHA256=deae7c80cba99c4b4f940ecadb3c3338b13cb77418409238e57d7f31f2a3b736

NCURSES_VERSION=6.5
NCURSES_URL="https://ftp.gnu.org/gnu/ncurses/ncurses-$NCURSES_VERSION.tar.gz"
NCURSES_SHA256=136d91bc269a9a5785e5f9e980bc76ab57428f604ce3e5a5a90cebc767971cc6

if [ -f "$PREFIX/lib/libssl.a" ] && [ -f "$PREFIX/lib/libz.a" ] \
    && [ -f "$PREFIX/lib/libncurses.a" ]; then
    echo "musl OpenSSL/zlib/ncurses already built in $PREFIX, skipping."
    exit 0
fi

if ! command -v musl-gcc > /dev/null 2>&1; then
    echo "musl-gcc not found; install musl-tools first." >&2
    exit 1
fi

PREFIX=$(mkdir -p "$PREFIX" && cd "$PREFIX" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

fetch() {
    url=$1
    sha256=$2
    out=$3
    curl -sSL -o "$out" "$url"
    echo "$sha256  $out" | sha256sum -c -
}

# musl-gcc's specs file passes -nostdinc and points only at musl's
# own headers, which don't include the Linux kernel's UAPI headers
# (linux/*.h, asm/*.h) that OpenSSL's secure-memory code needs.
# Debian's linux-libc-dev package installs those under /usr/include
# regardless of libc, so pull them in after musl's own headers with
# -idirafter (not -I), so musl's headers still take priority over
# glibc's for anything both provide.
MUSLCC="musl-gcc -idirafter /usr/include -idirafter \
/usr/include/$(uname -m)-linux-gnu"

# On arm64, GCC defaults to -moutline-atomics, which means any atomic op is
# compiled as a call into a libgcc.a helper that picks LSE or LL/SC atomics at
# runtime. That helper's init routine calls the glibc-internal __getauxval
# symbol, which musl does not provide, so any link that pulls in an atomic op
# fails with "undefined reference to `__getauxval'". This is unrelated to
# no-shared/no-module above: it hits the final apps/openssl link too, not just
# provider modules. Disabling outline atomics avoids the libgcc helper
# entirely.

if [ "$(uname -m)" = "aarch64" ]; then
    MUSLCC="$MUSLCC -mno-outline-atomics"
fi

cd "$WORK"
fetch "$ZLIB_URL" "$ZLIB_SHA256" zlib.tar.gz
tar xzf zlib.tar.gz
cd "zlib-$ZLIB_VERSION"
CC=musl-gcc ./configure --prefix="$PREFIX" --static
make -j"$(nproc)" libz.a
make install

cd "$WORK"
fetch "$OPENSSL_URL" "$OPENSSL_SHA256" openssl.tar.gz
tar xzf openssl.tar.gz
cd "openssl-$OPENSSL_VERSION"
# no-shared alone still builds the provider modules (legacy, etc.)
# as loadable .so files. Linking those pulls in libgcc.a's LSE
# atomics runtime check, which calls the glibc-internal
# __getauxval symbol that musl does not provide, so the link
# fails on arm64. no-module builds the providers directly into
# libcrypto.a instead, which also fits a static build better.
CC="$MUSLCC" ./Configure linux-"$(uname -m)" \
    no-shared no-module no-tests no-zstd no-docs \
    --prefix="$PREFIX" --libdir=lib --openssldir="$PREFIX/ssl"
make -j"$(nproc)" build_sw
make install_sw install_ssldirs

# --with-terminfo-dirs/--with-default-terminfo-dir point the library
# at the target system's terminfo database (the usual system
# paths) rather than bundling one.  Like any other curses program,
# static or not, the resulting binary still needs a terminfo database
# present at runtime, just not baked into the binary itself.
#
# "install.libs install.includes" (not the default "install" target)
# skips installing that terminfo database, which needs root to write
# under /usr/share/terminfo and which we don't want anyway, since
# nothing here should touch the build host's terminfo files.
cd "$WORK"
fetch "$NCURSES_URL" "$NCURSES_SHA256" ncurses.tar.gz
tar xzf ncurses.tar.gz
cd "ncurses-$NCURSES_VERSION"
CC=musl-gcc ./configure \
    --prefix="$PREFIX" \
    --without-shared \
    --without-debug \
    --without-ada \
    --without-manpages \
    --without-progs \
    --without-tests \
    --without-cxx-binding \
    --enable-widec=no \
    --with-terminfo-dirs=/usr/share/terminfo:/etc/terminfo:/lib/terminfo \
    --with-default-terminfo-dir=/usr/share/terminfo
make -j"$(nproc)"
make install.libs install.includes

echo "musl OpenSSL $OPENSSL_VERSION, zlib $ZLIB_VERSION, and ncurses" \
    "$NCURSES_VERSION installed to $PREFIX"
