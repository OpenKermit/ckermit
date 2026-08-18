#!/usr/bin/env python3
"""
hybridfat.py -- read/write files in the FAT16 volume of a Victor 9000 hybrid
FreeDOS disk image.

The hybrid image (see ~/projects/myfreedos/docs/victor/VICTOR_HYBRID_DISK_STRUCTURE.md)
is neither a Victor disk nor an IBM disk:

    sector 0        Victor drive label (for the Victor ROM's IPL vector)
    sectors 1-128   stage 1 boot loader
    sector 129      IBM-style FAT16 BPB, with hidden_sectors = 129
    sector 130+     FAT1, FAT2, root directory, data

Neither mtools nor vtg_image_util can read it: mtools looks for a BPB at
sector 0 or in an MBR partition table, and vtg_image_util expects Victor
virtual volumes.  So this file does the FAT16 by hand, taking the volume base
from the BPB's own hidden_sectors field rather than assuming 129.

    hybridfat.py info  <img>
    hybridfat.py list  <img>
    hybridfat.py put   <img> <hostfile> [DOSNAME]   (overwrites if present)
    hybridfat.py get   <img> <DOSNAME> [hostfile]
    hybridfat.py del   <img> <DOSNAME>

Root directory only -- this port stages everything in the root, and a
subdirectory walker is code with no caller.
"""

import os
import struct
import sys
import time

SECSIZE = 512
ATTR_LFN = 0x0F
ATTR_DIR = 0x10
ATTR_VOL = 0x08


class Fat16(object):
    def __init__(self, path, writable=False):
        self.path = path
        self.f = open(path, 'r+b' if writable else 'rb')
        self.base = self._find_bpb()
        self._read_bpb()

    # The BPB is at hidden_sectors, and hidden_sectors is *in* the BPB, so
    # the only way in is to try the candidates and check for consistency.
    # 129 is the hybrid layout; 0 is a plain floppy/IBM image.
    def _find_bpb(self):
        for cand in (129, 0):
            self.f.seek(cand * SECSIZE)
            b = self.f.read(SECSIZE)
            if len(b) < SECSIZE:
                continue
            if b[510:512] != b'\x55\xaa':
                continue
            bps = struct.unpack('<H', b[11:13])[0]
            hidden = struct.unpack('<I', b[28:32])[0]
            if bps == SECSIZE and hidden == cand:
                return cand
        raise SystemExit("%s: no FAT16 BPB at sector 129 or 0 "
                         "(is this a hybrid image?)" % self.path)

    def _read_bpb(self):
        self.f.seek(self.base * SECSIZE)
        b = self.f.read(SECSIZE)
        self.oem = b[3:11].decode('latin1').rstrip()
        self.bps = struct.unpack('<H', b[11:13])[0]
        self.spc = b[13]
        self.rsvd = struct.unpack('<H', b[14:16])[0]
        self.nfats = b[16]
        self.rootent = struct.unpack('<H', b[17:19])[0]
        tot16 = struct.unpack('<H', b[19:21])[0]
        self.spf = struct.unpack('<H', b[22:24])[0]
        tot32 = struct.unpack('<I', b[32:36])[0]
        self.total = tot16 if tot16 else tot32
        self.vollab = b[43:54].decode('latin1').rstrip()
        self.fstype = b[54:62].decode('latin1').rstrip()

        self.fat1 = self.base + self.rsvd
        self.root = self.fat1 + self.nfats * self.spf
        self.rootsecs = (self.rootent * 32 + self.bps - 1) // self.bps
        self.data = self.root + self.rootsecs
        datasecs = self.total - self.rsvd - self.nfats * self.spf - self.rootsecs
        self.nclusters = datasecs // self.spc          # count of usable clusters
        self.clsize = self.spc * self.bps

    # ---- raw sector access -------------------------------------------------

    def rdsec(self, sec, n=1):
        self.f.seek(sec * self.bps)
        return self.f.read(n * self.bps)

    def wrsec(self, sec, data):
        self.f.seek(sec * self.bps)
        self.f.write(data)

    # ---- FAT ---------------------------------------------------------------

    def read_fat(self):
        return bytearray(self.rdsec(self.fat1, self.spf))

    def write_fat(self, fat):
        for i in range(self.nfats):
            self.wrsec(self.fat1 + i * self.spf, bytes(fat))

    def chain(self, fat, first):
        out = []
        c = first
        while 2 <= c < 0xFFF8:
            out.append(c)
            if len(out) > self.nclusters:
                raise SystemExit("FAT chain loop starting at cluster %d" % first)
            c = struct.unpack_from('<H', fat, c * 2)[0]
        return out

    def free_clusters(self, fat, n):
        out = []
        for c in range(2, self.nclusters + 2):
            if struct.unpack_from('<H', fat, c * 2)[0] == 0:
                out.append(c)
                if len(out) == n:
                    return out
        raise SystemExit("not enough free space: need %d clusters, found %d"
                         % (n, len(out)))

    def count_free(self, fat):
        return sum(1 for c in range(2, self.nclusters + 2)
                   if struct.unpack_from('<H', fat, c * 2)[0] == 0)

    def cluster_sector(self, c):
        return self.data + (c - 2) * self.spc

    # ---- root directory ----------------------------------------------------

    def read_root(self):
        return bytearray(self.rdsec(self.root, self.rootsecs))

    def write_root(self, rd):
        self.wrsec(self.root, bytes(rd))

    def entries(self, rd):
        """Yield (index, raw32) for live 8.3 entries."""
        for i in range(self.rootent):
            e = rd[i * 32:i * 32 + 32]
            if e[0] == 0:
                return
            if e[0] == 0xE5 or (e[11] & ATTR_LFN) == ATTR_LFN:
                continue
            yield i, e

    @staticmethod
    def fatname(name):
        name = name.upper()
        if '.' in name:
            b, e = name.split('.', 1)
        else:
            b, e = name, ''
        if len(b) > 8 or len(e) > 3:
            raise SystemExit("%s is not an 8.3 name" % name)
        return (b.ljust(8) + e.ljust(3)).encode('ascii')

    @staticmethod
    def dosname(raw):
        b = raw[0:8].decode('latin1').rstrip()
        e = raw[8:11].decode('latin1').rstrip()
        return b + ('.' + e if e else '')

    def find(self, rd, name):
        want = self.fatname(name)
        for i, e in self.entries(rd):
            if e[0:11] == want:
                return i
        return None

    def free_entry(self, rd):
        for i in range(self.rootent):
            if rd[i * 32] in (0x00, 0xE5):
                return i
        raise SystemExit("root directory is full (%d entries)" % self.rootent)


def dos_stamp(mtime):
    t = time.localtime(mtime)
    year = max(1980, t.tm_year)
    date = ((year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    tm = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    return date, tm


def cmd_info(img):
    v = Fat16(img)
    fat = v.read_fat()
    free = v.count_free(fat)
    print("image        %s (%d bytes)" % (img, os.path.getsize(img)))
    print("BPB sector   %d  (hidden_sectors, OEM '%s')" % (v.base, v.oem))
    print("volume       %s  %s" % (v.vollab or '(none)', v.fstype))
    print("geometry     %d B/sec, %d sec/clus (%d B), %d FATs x %d sec"
          % (v.bps, v.spc, v.clsize, v.nfats, v.spf))
    print("layout       FAT1 %d  root %d (%d ent)  data %d"
          % (v.fat1, v.root, v.rootent, v.data))
    print("clusters     %d total, %d free" % (v.nclusters, free))
    print("free         %d bytes (%.1f%%)"
          % (free * v.clsize, 100.0 * free / v.nclusters))


def cmd_list(img):
    v = Fat16(img)
    rd = v.read_root()
    n = 0
    used = 0
    for i, e in v.entries(rd):
        if e[11] & ATTR_VOL:
            continue
        size = struct.unpack('<I', e[28:32])[0]
        clus = struct.unpack('<H', e[26:28])[0]
        date = struct.unpack('<H', e[24:26])[0]
        tm = struct.unpack('<H', e[22:24])[0]
        y = 1980 + (date >> 9)
        stamp = "%04d-%02d-%02d %02d:%02d" % (y, (date >> 5) & 15, date & 31,
                                              tm >> 11, (tm >> 5) & 63)
        print("%-12s %10d  clus %-6d %s%s"
              % (v.dosname(e), size, clus, stamp,
                 "  <DIR>" if e[11] & ATTR_DIR else ""))
        n += 1
        used += size
    print("%d file(s), %d bytes" % (n, used))


def cmd_put(img, host, dosname=None):
    if dosname is None:
        dosname = os.path.basename(host).upper()
    with open(host, 'rb') as h:
        data = h.read()
    v = Fat16(img, writable=True)
    fat = v.read_fat()
    rd = v.read_root()

    # Overwrite: free the old chain and reuse the entry slot.
    idx = v.find(rd, dosname)
    if idx is not None:
        old = struct.unpack('<H', rd[idx * 32 + 26:idx * 32 + 28])[0]
        if old >= 2:
            for c in v.chain(fat, old):
                struct.pack_into('<H', fat, c * 2, 0)
        print("replacing existing %s" % dosname)
    else:
        idx = v.free_entry(rd)

    need = (len(data) + v.clsize - 1) // v.clsize
    clusters = v.free_clusters(fat, need) if need else []

    for i, c in enumerate(clusters):
        chunk = data[i * v.clsize:(i + 1) * v.clsize]
        chunk += b'\x00' * (v.clsize - len(chunk))
        v.wrsec(v.cluster_sector(c), chunk)
        nxt = clusters[i + 1] if i + 1 < len(clusters) else 0xFFFF
        struct.pack_into('<H', fat, c * 2, nxt)

    date, tm = dos_stamp(os.path.getmtime(host))
    e = bytearray(32)
    e[0:11] = v.fatname(dosname)
    e[11] = 0x20                                   # archive
    struct.pack_into('<H', e, 22, tm)
    struct.pack_into('<H', e, 24, date)
    struct.pack_into('<H', e, 26, clusters[0] if clusters else 0)
    struct.pack_into('<I', e, 28, len(data))
    rd[idx * 32:idx * 32 + 32] = e

    v.write_fat(fat)
    v.write_root(rd)
    v.f.flush()
    os.fsync(v.f.fileno())
    print("%s -> %s: %d bytes, %d cluster(s) from %d, entry %d"
          % (host, dosname, len(data), need,
             clusters[0] if clusters else 0, idx))


def cmd_get(img, dosname, host=None):
    if host is None:
        host = dosname
    v = Fat16(img)
    rd = v.read_root()
    idx = v.find(rd, dosname)
    if idx is None:
        raise SystemExit("%s not found" % dosname)
    e = rd[idx * 32:idx * 32 + 32]
    size = struct.unpack('<I', e[28:32])[0]
    first = struct.unpack('<H', e[26:28])[0]
    fat = v.read_fat()
    out = bytearray()
    if first >= 2:
        for c in v.chain(fat, first):
            out += v.rdsec(v.cluster_sector(c), v.spc)
    with open(host, 'wb') as h:
        h.write(bytes(out[:size]))
    print("%s -> %s: %d bytes" % (dosname, host, size))


def cmd_del(img, dosname):
    v = Fat16(img, writable=True)
    fat = v.read_fat()
    rd = v.read_root()
    idx = v.find(rd, dosname)
    if idx is None:
        raise SystemExit("%s not found" % dosname)
    first = struct.unpack('<H', rd[idx * 32 + 26:idx * 32 + 28])[0]
    if first >= 2:
        for c in v.chain(fat, first):
            struct.pack_into('<H', fat, c * 2, 0)
    rd[idx * 32] = 0xE5
    v.write_fat(fat)
    v.write_root(rd)
    v.f.flush()
    os.fsync(v.f.fileno())
    print("deleted %s" % dosname)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, img = argv[1], argv[2]
    rest = argv[3:]
    try:
        if cmd == 'info':
            cmd_info(img)
        elif cmd in ('list', 'dir'):
            cmd_list(img)
        elif cmd == 'put':
            cmd_put(img, *rest)
        elif cmd == 'get':
            cmd_get(img, *rest)
        elif cmd in ('del', 'rm'):
            cmd_del(img, *rest)
        else:
            print(__doc__)
            return 1
    except TypeError:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
