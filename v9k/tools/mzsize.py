#!/usr/bin/env python3
#
# mzsize.py -- report what an MS-DOS MZ image will need at load time.
#
# PORTING.md 16a's method, made repeatable.  The number that decides whether
# a build loads on the Victor is NOT the file size: it is the load module
# (file size minus the MZ header and minus any overlay/debug tail) plus
# minalloc, the paragraphs DOS must add for .bss and the stack.  Compare the
# total against the largest block DOS will hand out.
#
# QUOTE THE REQUIREMENT, NOT THE SPARE.  A Victor takes RAM in 128K
# increments from 128K to 896K, so "spare" is a fact about one machine while
# the requirement is the same everywhere.  Use -a 0 to print it alone.
#
# The default below is the 896K bench machine.  SS16x measured what Victor
# MS-DOS 3.1 actually hands out, with v9k/probes/vmem.c, and the model is
#
#     free = installed RAM - 92,720
#
# because this DOS loads high: 11,584 bytes below the program and 81,136
# above, identical at 256K and at 896K.  That gives 169,424 free at 256K
# (where CKERMITW does NOT load), 300,496 at 384K, 431,568 at 512K and
# 824,784 at 896K.
#
# The 396,224 this script used to default to was WRONG -- it came from a
# FreeDOS measurement filed under an MS-DOS 3.1 heading in SS16a, and it
# understated MS-DOS 3.1 by better than 2x.  See SS16x before reintroducing
# it anywhere.
#
#   python3 v9k/tools/mzsize.py ckermitw.exe [...]      # vs the 896K bench
#   python3 v9k/tools/mzsize.py -a 0 ckermitw.exe       # requirement only
#   python3 v9k/tools/mzsize.py -a 300496 ckermitw.exe  # vs a 384K machine
#
# MZ header fields used, all little-endian words:
#   0x02  bytes in last page      0x04  pages of 512
#   0x08  header size, paragraphs 0x0A  minalloc, paragraphs

import sys, os

# Largest block Victor MS-DOS 3.1 offers on the 896K bench machine.  See the
# header: a fact about that machine, not a property of the Victor.
AVAIL = 824784                          # measured, PORTING.md 16x

# free = installed RAM - 92,720 (11,584 below the program, 81,136 above)
V9K_DOS_OVERHEAD = 92720

def report(path, avail=None):
    if avail is None:
        avail = AVAIL
    with open(path, 'rb') as f:
        h = f.read(0x20)
    if h[:2] not in (b'MZ', b'ZM'):
        print("%-24s not an MZ image" % os.path.basename(path))
        return
    w = lambda o: h[o] | (h[o+1] << 8)
    lastpage, pages, hdrparas, minalloc = w(2), w(4), w(8), w(0x0a)
    total = (pages - 1) * 512 + (lastpage if lastpage else 512)
    image = total - hdrparas * 16        # the load module proper
    need  = image + minalloc * 16
    verdict = ""
    if avail:
        verdict = ("FITS, %d spare" % (avail - need) if need <= avail
                   else "OVER by %d" % (need - avail))
    print("%-24s file %8d  image %8d  + minalloc %7d  = needs %8d (%dK)  %s"
          % (os.path.basename(path), os.path.getsize(path), image,
             minalloc * 16, need, need // 1024, verdict))

    # The number that governs how widely this build can run.  A Victor comes
    # in 128K increments to 896K; print the smallest one that can load it.
    #
    # DERIVED, not measured.  Only 256K and 896K have ever been read off a
    # machine (SS16x), and MAME misreports 512K and 640K on victor9k -- both
    # claim 759,248 free, which is impossible at 640K.  So treat this line
    # as the model's answer and not as a fact about any particular Victor.
    fits = [k for k in range(128, 897, 128)
            if k * 1024 - V9K_DOS_OVERHEAD >= need]
    if fits:
        k = fits[0]
        print("%-24s smallest Victor: %dK (%d free, %d spare) [derived]"
              % ("", k, k * 1024 - V9K_DOS_OVERHEAD,
                 k * 1024 - V9K_DOS_OVERHEAD - need))
    else:
        print("%-24s smallest Victor: none -- will not load on any Victor"
              % "")

args  = sys.argv[1:]
avail = None
if args and args[0] in ('-a', '--avail'):
    avail = int(args[1]); args = args[2:]
if avail:
    print("checking against %d bytes free" % avail)
for p in args:
    report(p, avail)
