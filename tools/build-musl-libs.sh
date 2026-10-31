#!/bin/sh
#
# Build static OpenSSL, zlib, ncurses, and check against musl libc
# for the linux+ssl+musl and linux+musl makefile targets. check
# provides the unit test framework for "make check".
#
# This builds all four from source against musl-gcc into a private
# prefix. That prefix is then passed to those targets via
# KSSLINC/KSSLLIB (linux+ssl+musl only) and KNCURSESINC, e.g.:
#
#   tools/build-musl-libs.sh .ci-cache/musl-libs
#   make linux+ssl+musl \
#     KSSLINC="-I$(pwd)/.ci-cache/musl-libs/include" \
#     KSSLLIB="-L$(pwd)/.ci-cache/musl-libs/lib" \
#     KNCURSESINC="-I$(pwd)/.ci-cache/musl-libs/include/ncurses"
#
# An optional second argument cross-builds for armhf or i386 instead
# of the host architecture:
#
#   tools/build-musl-libs.sh .ci-cache/musl-libs armhf
#   tools/build-musl-libs.sh .ci-cache/musl-libs i386
#
# Cross-compiling for armhf requires gcc-arm-linux-gnueabihf, plus
# musl-tools and linux-libc-dev installed for the armhf architecture
# (via dpkg --add-architecture armhf).
#
# musl-tools:armhf installs a musl-gcc wrapper that defaults to calling
# cc. Setting REALGCC=arm-linux-gnueabihf-gcc directs musl-gcc to the
# cross compiler.
#
# The i386 target is for the linux+musl makefile target and builds
# only ncurses and check.  It compiles for the i486 instruction set
# (-march=i486).  It requires gcc-i686-linux-gnu and musl-tools:i386.
# tools/i386-musl-container.sh provides both.  musl-tools:i386
# installs a musl-gcc wrapper that calls i686-linux-gnu-gcc.
#
# ncurses carries built-in fallback entries for common terminal types
# on every target.  Generating them requires a host C compiler (cc).
#
# Idempotent: does nothing if the target's libraries already exist in
# <prefix>/lib, so CI can cache the prefix directory across runs.

set -e

PREFIX=${1:?"usage: $0 <prefix-dir> [armhf|i386]"}
TARGET=${2:-native}

ZLIB_VERSION=1.3.2
ZLIB_URL="https://github.com/madler/zlib/releases/download/\
v$ZLIB_VERSION/zlib-$ZLIB_VERSION.tar.gz"
ZLIB_SHA256=bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16

OPENSSL_VERSION=3.5.9
OPENSSL_URL="https://www.openssl.org/source/openssl-$OPENSSL_VERSION.tar.gz"
OPENSSL_SHA256=603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a

NCURSES_VERSION=6.6
NCURSES_URL="https://ftp.gnu.org/gnu/ncurses/ncurses-$NCURSES_VERSION.tar.gz"
NCURSES_SHA256=355b4cbbed880b0381a04c46617b7656e362585d52e9cf84a67e2009b749ff11

CHECK_VERSION=0.15.2
CHECK_URL="https://github.com/libcheck/check/releases/download/\
$CHECK_VERSION/check-$CHECK_VERSION.tar.gz"
CHECK_SHA256=a8de4e0bacfb4d76dd1c618ded263523b53b85d92a146d8835eb1a52932fa20a

# Terminal types compiled into ncurses as fallback entries.
NCURSES_FALLBACKS=ansi,dumb,linux,putty,rxvt,screen,screen-256color,\
tmux,tmux-256color,vt100,vt102,vt220,xterm,xterm-256color

case "$TARGET" in
    native|armhf) WANT_SSL=yes ;;
    i386) WANT_SSL=no ;;
    *) echo "unknown target '$TARGET'; expected 'armhf', 'i386'," \
        "or no second argument" >&2
       exit 1 ;;
esac

if [ -f "$PREFIX/lib/libncurses.a" ] && [ -f "$PREFIX/lib/libcheck.a" ] \
    && { [ "$WANT_SSL" = no ] || { [ -f "$PREFIX/lib/libssl.a" ] \
    && [ -f "$PREFIX/lib/libz.a" ]; }; }; then
    echo "musl libraries already built in $PREFIX, skipping."
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

# TARGET_CC compiles ncurses and check, plus zlib when built.
#
# musl-gcc passes -nostdinc and points only at musl headers.  Those
# do not include the Linux kernel UAPI headers (linux/*.h, asm/*.h)
# that OpenSSL secure memory requires.  Debian's linux-libc-dev
# installs them under /usr/include regardless of libc.  MUSLCC pulls
# them in after the musl headers with -idirafter, so musl headers
# take priority over glibc for anything both provide.  Only OpenSSL
# compiles with MUSLCC.
case "$TARGET" in
    armhf)
        KERNEL_HDR_TRIPLE=arm-linux-gnueabihf
        export REALGCC=arm-linux-gnueabihf-gcc
        export AR=arm-linux-gnueabihf-ar
        export RANLIB=arm-linux-gnueabihf-ranlib
        OPENSSL_TARGET=linux-armv4
        AUTOCONF_HOST_FLAG="--host=arm-linux-gnueabihf"
        TARGET_CC=musl-gcc
        ;;
    i386)
        AUTOCONF_HOST_FLAG="--host=i686-linux-musl"
        TARGET_CC="musl-gcc -march=i486"
        ;;
    *)
        KERNEL_HDR_TRIPLE="$(uname -m)-linux-gnu"
        OPENSSL_TARGET="linux-$(uname -m)"
        AUTOCONF_HOST_FLAG=""
        TARGET_CC=musl-gcc
        ;;
esac

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

if [ "$WANT_SSL" = yes ]; then
    cd "$WORK"
    fetch "$ZLIB_URL" "$ZLIB_SHA256" zlib.tar.gz
    tar xzf zlib.tar.gz
    cd "zlib-$ZLIB_VERSION"
    CC="$TARGET_CC" ./configure --prefix="$PREFIX" --static
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
    # Build and install only the libraries and headers. The openssl
    # CLI binary is not needed. Linking that binary during armhf
    # cross-compilation pulls in the cross toolchain's glibc-linked
    # libatomic.so, which fails to resolve in a musl static link.
    CC="$MUSLCC" ./Configure "$OPENSSL_TARGET" \
        no-shared no-module no-tests no-zstd no-docs \
        --prefix="$PREFIX" --libdir=lib --openssldir="$PREFIX/ssl"
    make -j"$(nproc)" build_libs
    # install_ssldirs installs apps/CA.pl and apps/tsget.pl, which are
    # generated scripts. build_libs does not generate them. Generate
    # them directly by name to avoid building the rest of
    # build_programs.
    make apps/CA.pl apps/tsget.pl
    make install_dev install_ssldirs
fi

# --with-terminfo-dirs/--with-default-terminfo-dir point the library
# at the target system's terminfo database (the usual system
# paths) rather than bundling one.
#
# --with-fallbacks compiles the NCURSES_FALLBACKS entries into the
# library.  ncurses consults them only after the terminfo database
# lookup fails.  An entry in the target system's database takes
# precedence over the built-in entry for the same type.  The built-in
# entries come from misc/terminfo.src in the ncurses source.
#
# Generating the fallback source runs tic and infocmp on the build
# host.  The generated C initializes ncurses' internal TERMTYPE2
# structures.  So tic and infocmp come from the same ncurses source,
# built for the host with cc and the same configure options.
#
# "install.libs install.includes" (not the default "install" target)
# skips installing that terminfo database, which needs root to write
# under /usr/share/terminfo and which we don't want anyway, since
# nothing here should touch the build host's terminfo files.
NCURSES_OPTS="--without-shared --without-debug --without-ada \
--without-manpages --without-tests --without-cxx-binding \
--enable-widec=no \
--with-terminfo-dirs=/usr/share/terminfo:/etc/terminfo:/lib/terminfo \
--with-default-terminfo-dir=/usr/share/terminfo"

cd "$WORK"
fetch "$NCURSES_URL" "$NCURSES_SHA256" ncurses.tar.gz
mkdir ncurses-host
tar xzf ncurses.tar.gz -C ncurses-host
cd "ncurses-host/ncurses-$NCURSES_VERSION"
CC=cc AR=ar RANLIB=ranlib ./configure \
    --prefix="$WORK/ncurses-host-prefix" $NCURSES_OPTS
make -j"$(nproc)" AR=ar RANLIB=ranlib
HOST_PROGS="$WORK/ncurses-host/ncurses-$NCURSES_VERSION/progs"

cd "$WORK"
tar xzf ncurses.tar.gz
cd "ncurses-$NCURSES_VERSION"
CC="$TARGET_CC" ./configure $AUTOCONF_HOST_FLAG \
    --prefix="$PREFIX" $NCURSES_OPTS \
    --without-progs \
    --with-fallbacks="$NCURSES_FALLBACKS" \
    --with-tic-path="$HOST_PROGS/tic" \
    --with-infocmp-path="$HOST_PROGS/infocmp"
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
CC="$TARGET_CC" ./configure $AUTOCONF_HOST_FLAG \
    --prefix="$PREFIX" \
    --disable-shared \
    --disable-build-docs \
    --disable-subunit
make -j"$(nproc)"
make install

if [ "$WANT_SSL" = yes ]; then
    echo "musl OpenSSL $OPENSSL_VERSION, zlib $ZLIB_VERSION, ncurses" \
        "$NCURSES_VERSION, and check $CHECK_VERSION installed to $PREFIX"
else
    echo "musl ncurses $NCURSES_VERSION and check $CHECK_VERSION" \
        "installed to $PREFIX"
fi
