# victorow.mak -- Build C-Kermit for the Victor 9000 / Sirius 1 with Open Watcom
#
# This is THE build for the port: Open Watcom V2 wcc/wlink, LARGE model --
# far code and far data.
#
#   make -f victorow.mak            build objects and link
#   make -f victorow.mak sizes      report segment sizes and DGROUP usage
#   make -f victorow.mak clean
#
# WHY THIS TOOLCHAIN
#   The port was also built by ia16-elf-gcc + newlib in the medium model
#   until 2026-08-05.  That toolchain has no compact/large/huge model: every
#   "char *" is a near pointer, so every string literal lived in the one 64K
#   DGROUP.  It cost the interactive "C-Kermit>" parser (PORTING.md SS9c) and
#   it left about 2K of heap for a transfer, because malloc() came out of the
#   same segment.  The large model plus -zc fixes both -- DGROUP 39,424
#   against gcc's 52,728, and a far heap -- so the gcc build was retired.
#   PORTING.md SS9d and SS16e keep the measurements.
#
# CONFIGURATION
#   Feature configuration is ckvictor.h and only ckvictor.h, force-included
#   ahead of every module (-fi=).  Do not add -D options here.

WATCOM  = /opt/open-watcom-v2/rel
WBIN    = $(WATCOM)/arml64
CC      = $(WBIN)/wcc
LINK    = $(WBIN)/wlink

# -ml   large model: far code AND far data.  The whole point of this build.
# -0    8088/8086 instruction set only.  The Victor is an 8088.
# -os   optimize for size.  This is a 64K-DGROUP, 128K-of-RAM machine.
# -zq   quiet.
# -zc   place string literals in the code segment rather than in DGROUP.
#       In the large model all pointers are far, so this is free; it is the
#       single biggest reason this toolchain and not the other.  Set ZC= on
#       the command line to measure the difference.
# -bt=dos  target MS-DOS.
# -zt<n>  put data objects of n bytes or more in FAR segments instead of
#       DGROUP.  This is the other half of -zc and it is worth even more,
#       because it moves the keyword TABLES, not just the strings they
#       point at.  Measured, full build with the interactive parser on
#       (XFLAGS=-dKEEP_ICP), DGROUP of 65536:
#
#           default threshold   60,768      fits, 4,768 bytes to spare
#           -zt1024             42,528
#           -zt128              19,376
#
#       Left empty by default: the serial-only milestone does not need the
#       room, and far data costs a segment load per access on an 8088.
#       Turn it on with ZT=-zt128 when the parser goes back in.
ZT      =
ZC      = -zc
MODEL   = -ml
# -fr=/dev/null   throw away the .err files.  wcc writes one per module that
#       produced a diagnostic, in ADDITION to printing it; they are the same
#       text and they litter the source directory.
CFLAGS  = $(MODEL) -0 -os -zq $(ZC) $(ZT) -bt=dos -fr=/dev/null \
	  -i=victorow -i=victor -i=$(WATCOM)/h -fi=ckvictor.h $(XFLAGS)

EXE     = ckermitw.exe

# Portable protocol core -- unmodified upstream, this is the part we keep.
COMMON  = ckcmai.obj ckclib.obj ckcfns.obj ckcfn2.obj ckcfn3.obj ckcpro.obj

# Command parser and user interface.
UI      = ckucmd.obj ckuusr.obj ckuus2.obj ckuus3.obj ckuus4.obj \
	  ckuus5.obj ckuus6.obj ckuus7.obj ckuusx.obj ckuusy.obj

# Platform I/O.  Stock upstream Unix modules -- this is the port.
PLATFORM = ckutio.obj ckufio.obj ckusig.obj

# Compiled to ~0 bytes by NOCSETS / NOUNICODE / NONET, but kept in the
# link so the handful of symbols the mainline references still resolve.
EMPTY   = ckuxla.obj ckcuni.obj ckcnet.obj ckctel.obj

# Victor-specific glue -- the only non-upstream C file.
VICTOR  = ckvictor.obj

# NOT LINKED: binmode.obj.  Recording this because it looks like exactly the
# right answer and it does not work here.
#
# ckufio.c is the UNIX file module -- zopeni() is a bare fopen(name,"r") and
# zopeno() only ever builds "w" or "a", neither consulting the "binary" flag,
# because on Unix there is nothing to consult it for.  On DOS that silently
# corrupted every binary transfer in both directions (PORTING.md SS16h).  The
# runtime's default translation mode is what decides it, and Open Watcom
# ships binmode.obj to set that mode to O_BINARY before main().
#
# Measured on Victor MS-DOS 3.1 (.probe/vfmode.c, .probe/vfmodefp.c): it sets
# _fmode correctly in a small test program -- with the object the toolchain
# ships in $(WATCOM)/lib286/dos, which is the SMALL model build, AND with the
# large-model build of the same source, and with or without the FP emulator
# linked -- and leaves _fmode at 0100 in CKERMITW.EXE either way.  The record
# is in the XI table, cstart runs every priority, and _TEXT is one segment, so
# none of the obvious explanations hold.  Why is not known.
#
# ckvictor.c registers the initializer itself instead, as a FAR record
# (rtn_type 1) where binmode.obj uses the near form.  That works, and it has a
# witness flag so the debug log says whether it ran.  See ckvictor.c's section
# 1d and PORTING.md SS16h; the other half of the pair is "#undef NLCHAR" for
# VICTOR9K in ckcdeb.h, and neither half is correct alone.

OBJS    = $(COMMON) $(UI) $(PLATFORM) $(EMPTY) $(VICTOR)

all: $(EXE) report

# wlink picks the startup module and the model's libraries out of the
# LIBRARY records wcc embeds in each object, so "system dos" is all the
# help it needs.  The map is not optional: DGROUP is the binding
# constraint and the linker is the only thing that knows the real total.
#
# STACK.  wlink's default for "system dos" is 2,048 bytes, and until now that
# is what this port had -- inherited, never chosen.  Against it: ckufio.c's
# traverse() recurses at 98 bytes per level, and the two largest non-recursive
# frames measured are docmd() at 1152 and zcopy() at 1114, so a directory walk
# a few levels deep that lands inside docmd() is already most of 2K.  The
# stack lives in DGROUP (hard rule 4) and there were 26,096 bytes free there,
# so 8K costs nothing this build needs for anything else.  PORTING.md SS15
# argued for this and deliberately did not bundle it with another change.
#
# This is a linker option, not a feature, which is why it is here and not in
# ckvictor.h -- there is no #define that sets it.
STACK   = 8k

$(EXE): $(OBJS)
	$(LINK) system dos name $(EXE) option map=$(EXE).map,quiet \
	  option stack=$(STACK) file { $(OBJS) }

# The protocol state machine is generated from ckcpro.w by wart.
# wart is a host tool, so build it with the host compiler.
wart: ckwart.c
	cc -DSIGTYP=void -o wart ckwart.c

ckcpro.c: ckcpro.w wart
	./wart ckcpro.w ckcpro.c

ckcpro.obj: ckcpro.c

# Every object depends on the force-included configuration header and on
# the headers we supply under victor/ and victorow/.  Without this, editing
# ckvictor.h rebuilds nothing.
CONFIG_H = ckvictor.h victor/sys/termios.h victor/sys/ioctl.h \
	   victorow/termios.h victorow/pwd.h victorow/sys/utsname.h

$(OBJS): $(CONFIG_H)

%.obj: %.c
	$(CC) $(CFLAGS) -fo=$@ $<

# Report the numbers that actually decide whether this port is viable.
#
# This reads the LINKER's map rather than the objects: the interesting
# figure is not how much data there is but how much of it is NEAR, and only
# the linker knows which segments ended up in DGROUP.  Everything in the
# DGROUP column shares one 64K segment with the stack; everything in the far
# column does not.
#
# Note on the heap: in the compact, large and huge models Watcom's malloc()
# allocates from the FAR heap, so C-Kermit's DYNAMIC packet buffers do not
# come out of DGROUP at all.  What bounds them is the 387K the machine
# offers, not this segment.
#
# "sizes" and "report" are the same thing, and both are .PHONY so that they
# print even when the .EXE is already up to date.  "sizes" used to be a
# target with no recipe depending on $(EXE), which meant that on an unchanged
# tree it said "Nothing to be done" and reported no number at all -- unhelpful
# for a rule that asks you to report DGROUP after every change.
sizes: report

report: $(EXE)
	@echo "--- DGROUP, from the linker, including libc ---"
	@hx() { printf "%d" "0x$$1"; }; \
	 tot=`hx \`awk '/^DGROUP /{print $$3}' $(EXE).map\``; \
	 for s in CONST CONST2 _DATA _BSS STACK; do \
	   v=`awk -v s=$$s '$$1==s{print $$5}' $(EXE).map`; \
	   [ -n "$$v" ] && printf "    %-8s %8d\n" $$s `hx $$v`; \
	 done; \
	 echo "  DGROUP total = $$tot of 65536 (`expr $$tot \* 100 / 65536`%)"; \
	 echo "  left in the segment for the near heap = `expr 65536 - $$tot`"; \
	 test $$tot -lt 65536 || { echo "  *** DGROUP OVERFLOW ***"; exit 1; }
	@echo "--- far segments (outside DGROUP, no 64K limit) ---"
	@awk '$$2=="CODE"{c+=1} $$2=="FAR_DATA"{f+=1} \
	      END{}' $(EXE).map; \
	 awk 'function h(x){r=0;n=split(tolower(x),a,"");for(i=1;i<=n;i++)\
	        {c=index("0123456789abcdef",a[i]);r=r*16+c-1} return r} \
	      $$2=="CODE"    {code+=h($$5)} \
	      $$2=="FAR_DATA"{fdat+=h($$5)} \
	      END {printf "    far code     %8d\n    far data     %8d\n", code, fdat}' \
	   $(EXE).map
	@ls -l $(EXE) | awk '{printf "  %s = %d bytes\n", "$(EXE)", $$5}'

clean:
	rm -f *.obj wart $(EXE) $(EXE).map

.PHONY: all sizes report clean
