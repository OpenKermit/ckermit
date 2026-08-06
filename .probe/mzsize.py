#!/usr/bin/env python3
#
# mzsize.py -- report what an MS-DOS MZ image will need at load time.
#
# PORTING.md 16a's method, made repeatable.  The number that decides whether
# a build loads on the Victor is NOT the file size: it is the load module
# (file size minus the MZ header and minus any overlay/debug tail) plus
# minalloc, the paragraphs DOS must add for .bss and the stack.  Compare the
# total against the largest block DOS will hand out, measured there at
# 396,224 bytes (387K) with -ramsize 896K.
#
#   python3 .probe/mzsize.py ckermitw.exe [...]
#
# MZ header fields used, all little-endian words:
#   0x02  bytes in last page      0x04  pages of 512
#   0x08  header size, paragraphs 0x0A  minalloc, paragraphs

import sys, os

AVAIL = 396224                          # measured, PORTING.md 16a

def report(path):
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
    print("%-24s file %8d  image %8d  + minalloc %7d  = needs %8d (%dK)  %s"
          % (os.path.basename(path), os.path.getsize(path), image,
             minalloc * 16, need, need // 1024,
             "FITS, %d spare" % (AVAIL - need) if need <= AVAIL
             else "OVER by %d" % (need - AVAIL)))

for p in sys.argv[1:]:
    report(p)
