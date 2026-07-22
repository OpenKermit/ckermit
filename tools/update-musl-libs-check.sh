#!/bin/sh
#
# Compare the zlib/OpenSSL/ncurses versions pinned in
# tools/build-musl-libs.sh against upstream, and update the
# *_VERSION and *_SHA256 lines in place for anything newer. Run
# from the repository root. Requires curl, gh, GNU sed, sort -V,
# and sha256sum.
#
# OpenSSL only takes a patch-level bump within the currently pinned
# branch (e.g. 3.5.x).  OpenSSL's release strategy gives its branches
# different support lengths, so moving to a new branch is a
# deliberate choice, not a mechanical version bump. A newer branch
# is reported below but not applied.
#
# zlib and ncurses each have a single active release line, so their
# absolute latest version is used.
#
# Usage: tools/update-musl-libs-check.sh <summary-output-file>
# The summary file gets a one-line-per-library report, meant for
# both a CI job summary and a pull request body.

set -e

SCRIPT=tools/build-musl-libs.sh
SUMMARY=${1:?"usage: $0 <summary-output-file>"}
: > "$SUMMARY"

current_version() {
    sed -n "s/^$1=//p" "$SCRIPT"
}

# Downloads the given URL and prints its sha256. Used both to pin a
# new version's checksum and, incidentally, to prove the tarball is
# actually fetchable before it's committed.
sha256_of() {
    curl -sSfL "$1" | sha256sum | cut -d' ' -f1
}

update_pin() {
    lib=$1 old=$2 new=$3 url=$4
    if [ "$old" = "$new" ]; then
        echo "* $lib: up to date ($old)" >> "$SUMMARY"
        return
    fi
    sha256=$(sha256_of "$url")
    sed -i "s/^${lib}_VERSION=.*/${lib}_VERSION=$new/" "$SCRIPT"
    sed -i "s/^${lib}_SHA256=.*/${lib}_SHA256=$sha256/" "$SCRIPT"
    echo "* $lib: $old -> $new" >> "$SUMMARY"
}

# Prints numeric (non-alpha/beta/rc) OpenSSL tags whose name starts
# with "openssl-$1", one per line, with that prefix stripped.
openssl_tags() {
    gh api --paginate "repos/openssl/openssl/git/matching-refs/tags/openssl-$1" \
        --jq '.[].ref' \
        | grep -oE 'openssl-[0-9]+\.[0-9]+\.[0-9]+$' \
        | sed 's/^openssl-//'
}

echo "## musl library pin check" >> "$SUMMARY"

# --- zlib: single active release line, GitHub Releases ---
ZLIB_OLD=$(current_version ZLIB_VERSION)
ZLIB_NEW=$(gh api repos/madler/zlib/releases/latest \
    --jq '.tag_name | ltrimstr("v")')
update_pin ZLIB "$ZLIB_OLD" "$ZLIB_NEW" \
    "https://github.com/madler/zlib/releases/download/v$ZLIB_NEW/zlib-$ZLIB_NEW.tar.gz"

# --- OpenSSL: patch-level bump within the pinned branch only ---
OPENSSL_OLD=$(current_version OPENSSL_VERSION)
OPENSSL_BRANCH=$(echo "$OPENSSL_OLD" | cut -d. -f1,2)
OPENSSL_NEW=$(openssl_tags "$OPENSSL_BRANCH." | sort -V | tail -1)
[ -z "$OPENSSL_NEW" ] && OPENSSL_NEW=$OPENSSL_OLD
update_pin OPENSSL "$OPENSSL_OLD" "$OPENSSL_NEW" \
    "https://www.openssl.org/source/openssl-$OPENSSL_NEW.tar.gz"

LATEST_BRANCH=$(openssl_tags "3." | cut -d. -f1,2 | sort -Vu | tail -1)
if [ -n "$LATEST_BRANCH" ] && [ "$LATEST_BRANCH" != "$OPENSSL_BRANCH" ]; then
    echo "* Note: OpenSSL branch $LATEST_BRANCH exists upstream" \
        "(this script tracks $OPENSSL_BRANCH). Moving to a new" \
        "branch is a manual decision; check its support status at" \
        "https://openssl-library.org/policies/releasestrat/ first." \
        >> "$SUMMARY"
fi

# --- ncurses: single active release line, GNU FTP directory listing ---
NCURSES_OLD=$(current_version NCURSES_VERSION)
NCURSES_NEW=$(curl -sSfL https://ftp.gnu.org/gnu/ncurses/ \
    | grep -oE 'ncurses-[0-9]+\.[0-9]+\.tar\.gz' \
    | sed 's/ncurses-//; s/\.tar\.gz//' \
    | sort -Vu | tail -1)
update_pin NCURSES "$NCURSES_OLD" "$NCURSES_NEW" \
    "https://ftp.gnu.org/gnu/ncurses/ncurses-$NCURSES_NEW.tar.gz"
