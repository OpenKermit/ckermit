#!/bin/sh
#
# Check that a 32-bit x86 binary uses only instructions an i486
# executes.  Exits 0 if the binary passes, 1 if it uses a later
# instruction, and 2 on a usage or objdump error.
#
# Usage: tools/check-i486-insns.sh <binary>
#
# objdump disassembles every executable section.  These fail the
# check:
#
#   - CMOVcc, FCMOVcc, FCOMI and FUCOMI (i686).
#   - Long NOPs (0F 1F) and ENDBR32 (0F 1E).  An i486 does not decode
#     either opcode.
#   - CMPXCHG8B, RDTSC, RDMSR, WRMSR and RDPMC (Pentium).
#   - CPUID.  Early i486 steppings lack it.
#   - SYSENTER, SYSEXIT, SYSCALL and SYSRET.
#   - MMX, SSE and AVX instructions, and any use of their registers.
#   - POPCNT, LZCNT, TZCNT, MOVBE, CRC32, RDRAND and RDSEED.
#
# UD2 passes.  It exists to trap, and an i486 raises the same
# invalid-opcode exception for it.  PAUSE (F3 90) passes.  An i486
# executes it as a NOP.

if [ $# -ne 1 ]; then
    echo "usage: $0 <binary>" >&2
    exit 2
fi

BIN=$1
OUT=$(mktemp)
trap 'rm -f "$OUT"' EXIT

if ! objdump -d --no-show-raw-insn "$BIN" > "$OUT"; then
    echo "$0: objdump failed on $BIN" >&2
    exit 2
fi

# objdump prints each instruction as "  addr:<TAB>mnemonic operands".
# Prefixes such as "lock", "rep", "cs" and "data16" precede the
# mnemonic.  The awk program drops them, then tests the mnemonic and
# operands.  It prints each offending instruction with its function.
awk '
BEGIN {
    prefix = "^(lock|rep|repz|repnz|repe|repne|cs|ds|es|fs|gs|ss|" \
        "data16|addr16|addr32|notrack|bnd)$"
}
/^[0-9a-f]+ <.*>:$/ { fn = $2; next }
/^ *[0-9a-f]+:\t/ {
    sub(/^ *[0-9a-f]+:\t/, "")
    insn = $0
    n = split(insn, w, /[ \t]+/)
    i = 1
    while (i < n && w[i] ~ prefix)
        i++
    m = w[i]
    bad = 0
    if (m ~ /^(cmov|fcmov)/) bad = 1
    else if (m ~ /^f(u)?comip?$/) bad = 1
    else if (m ~ /^nop[wl]$/) bad = 1
    else if (m ~ /^endbr(32|64)$/) bad = 1
    else if (m ~ /^(cmpxchg8b|rdtsc|rdtscp|rdmsr|wrmsr|rdpmc|cpuid)$/) bad = 1
    else if (m ~ /^(sysenter|sysexit|syscall|sysret)$/) bad = 1
    else if (m ~ /^(popcnt|lzcnt|tzcnt|movbe|crc32|rdrand|rdseed)$/) bad = 1
    else if (m ~ /^(emms|femms|ldmxcsr|stmxcsr|fxsave|fxrstor|fisttp)/) bad = 1
    else if (m ~ /^([lms]fence|clflush|movnti|prefetch)/) bad = 1
    else if (insn ~ /%(mm[0-7]|[xyz]mm[0-9]+|k[0-7])([^0-9]|$)/) bad = 1
    if (bad) {
        print fn " " insn
        found = 1
    }
}
END { exit found ? 1 : 0 }
' "$OUT"
status=$?

if [ $status -ne 0 ]; then
    echo "$BIN uses instructions an i486 does not execute." >&2
    exit 1
fi
echo "$BIN uses only i486 instructions."
