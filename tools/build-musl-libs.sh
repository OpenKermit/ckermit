#!/bin/sh
#
# Build static OpenSSL, zlib, ncurses, and check against musl libc
# for the linux+ssl+musl and linux+musl makefile targets. check
# provides the unit test framework for "make check".
#
# This builds all four from source against musl-gcc into a private
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
# An optional second argument cross-builds for armhf instead of the
# host architecture:
#
#   tools/build-musl-libs.sh .ci-cache/musl-libs armhf
#
# Cross-compiling for armhf requires gcc-arm-linux-gnueabihf, plus
# musl-tools and linux-libc-dev installed for the armhf architecture
# (via dpkg --add-architecture armhf).
#
# musl-tools:armhf installs a musl-gcc wrapper that defaults to calling
# cc. Setting REALGCC=arm-linux-gnueabihf-gcc directs musl-gcc to the
# cross compiler.
#
# Idempotent: does nothing if <prefix>/lib/libssl.a already exists,
# so CI can cache the prefix directory across runs.

set -e

PREFIX=${1:?"usage: $0 <prefix-dir> [armhf]"}
TARGET=${2:-native}

ZLIB_VERSION=1.3.2
ZLIB_URL="https://github.com/madler/zlib/releases/download/\
v$ZLIB_VERSION/zlib-$ZLIB_VERSION.tar.gz"
ZLIB_SHA256=bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16

OPENSSL_VERSION=3.5.8
OPENSSL_URL="https://www.openssl.org/source/openssl-$OPENSSL_VERSION.tar.gz"
OPENSSL_SHA256=a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2

NCURSES_VERSION=6.6
NCURSES_URL="https://ftp.gnu.org/gnu/ncurses/ncurses-$NCURSES_VERSION.tar.gz"
NCURSES_SHA256=355b4cbbed880b0381a04c46617b7656e362585d52e9cf84a67e2009b749ff11

CHECK_VERSION=0.15.2
CHECK_URL="https://github.com/libcheck/check/releases/download/\
$CHECK_VERSION/check-$CHECK_VERSION.tar.gz"
CHECK_SHA256=a8de4e0bacfb4d76dd1c618ded263523b53b85d92a146d8835eb1a52932fa20a

if [ -f "$PREFIX/lib/libssl.a" ] && [ -f "$PREFIX/lib/libz.a" ] \
    && [ -f "$PREFIX/lib/libncurses.a" ] \
    && [ -f "$PREFIX/lib/libcheck.a" ]; then
    echo "musl OpenSSL/zlib/ncurses/check already built in $PREFIX," \
        "skipping."
    exit 0
fi

case "$TARGET" in
    native|armhf) ;;
    *) echo "unknown target '$TARGET'; expected 'armhf' or no" \
        "second argument" >&2
       exit 1 ;;
esac

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

# musl-gcc passes -nostdinc and points only at musl headers, which do
# not include the Linux kernel UAPI headers (linux/*.h, asm/*.h) that
# OpenSSL secure memory requires. Debian's linux-libc-dev installs
# those under /usr/include regardless of libc.
#
# Pull them in after musl headers with -idirafter so musl headers
# take priority over glibc for anything both provide.
if [ "$TARGET" = armhf ]; then
    KERNEL_HDR_TRIPLE=arm-linux-gnueabihf
    export REALGCC=arm-linux-gnueabihf-gcc
    export AR=arm-linux-gnueabihf-ar
    export RANLIB=arm-linux-gnueabihf-ranlib
    OPENSSL_TARGET=linux-armv4
    AUTOCONF_HOST_FLAG="--host=arm-linux-gnueabihf"
else
    KERNEL_HDR_TRIPLE="$(uname -m)-linux-gnu"
    OPENSSL_TARGET="linux-$(uname -m)"
    AUTOCONF_HOST_FLAG=""
fi

MUSLCC="musl-gcc -idirafter /usr/include -idirafter \
/usr/include/$KERNEL_HDR_TRIPLE"

# On AArch64, GCC defaults to -moutline-atomics. That emits calls into
# libgcc helpers that reference the glibc-internal __getauxval symbol,
# which musl does not provide. Disabling outline atomics avoids the
# helper calls.
#
# This flag is specific to AArch64 and is omitted for armhf cross builds.
if [ "$TARGET" = native ] && [ "$(uname -m)" = "aarch64" ]; then
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
#
# Build and install only the libraries and headers. The openssl CLI
# binary is not needed. Linking that binary during armhf cross-compilation
# pulls in the cross toolchain's glibc-linked libatomic.so, which fails
# to resolve in a musl static link.
CC="$MUSLCC" ./Configure "$OPENSSL_TARGET" \
    no-shared no-module no-tests no-zstd no-docs \
    --prefix="$PREFIX" --libdir=lib --openssldir="$PREFIX/ssl"
make -j"$(nproc)" build_libs
# install_ssldirs installs apps/CA.pl and apps/tsget.pl, which are
# generated scripts. build_libs does not generate them. Generate them
# directly by name to avoid building the rest of build_programs.
make apps/CA.pl apps/tsget.pl
make install_dev install_ssldirs

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
CC=musl-gcc ./configure $AUTOCONF_HOST_FLAG \
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

# --disable-build-docs skips documentation that requires texinfo.
#
# --disable-shared builds only the static library libcheck.a.
#
# The configure script enables subunit support if /usr/include/subunit
# is present on the build host. Disabling subunit avoids an unresolved
# dependency, as libsubunit is not built here.
#
# "make check" locates this build when PKG_CONFIG_PATH includes
# $PREFIX/lib/pkgconfig.
cd "$WORK"
fetch "$CHECK_URL" "$CHECK_SHA256" check.tar.gz
tar xzf check.tar.gz
cd "check-$CHECK_VERSION"
CC=musl-gcc ./configure $AUTOCONF_HOST_FLAG \
    --prefix="$PREFIX" \
    --disable-shared \
    --disable-build-docs \
    --disable-subunit
make -j"$(nproc)"
make install

echo "musl OpenSSL $OPENSSL_VERSION, zlib $ZLIB_VERSION, ncurses" \
    "$NCURSES_VERSION, and check $CHECK_VERSION installed to $PREFIX"
