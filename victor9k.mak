# victor9k.mak -- Build C-Kermit for the Victor 9000 / Sirius 1
#
# Serial-only C-Kermit for Victor MS-DOS on the 8088, built with
# ia16-elf-gcc against a newlib-based C runtime.
#
#   make -f victor9k.mak            build objects
#   make -f victor9k.mak sizes      report .text/.data/.bss and DGROUP usage
#   make -f victor9k.mak clean
#
# The entire feature configuration lives in ckvictor.h, which is force-
# included ahead of every source file.  Do not add -D options here; put
# them in ckvictor.h next to the comment explaining why they are needed.
#
# MEMORY MODEL
#   -mcmodel=medium gives far code (multiple code segments, up to 1MB) and
#   NEAR data.  ia16-elf-gcc has no compact/large/huge model, so there is
#   exactly one 64K data group and everything static, plus the heap and the
#   stack, lives in it.  "make sizes" exists to keep that honest.

CC      = ia16-elf-gcc

# -Ivictor supplies <sys/termios.h>.  The stock ia16 newlib ships
# <termios.h> as a dangling include of a sys/termios.h that does not exist,
# and defines no termios functions; ours is the uPD7201 driver's control
# surface.  See victor/sys/termios.h and PORTING.md.
# -mnewlib-nano-stdio selects newlib's reduced printf/scanf.  This is not a
# nicety: it is worth 14,272 bytes of DGROUP, and without it the program does
# not link (near data 66,272 against a 65,536-byte limit).  It must be on for
# BOTH compiling and linking, so it lives in CFLAGS and LDFLAGS both.
NANOSTDIO = -mnewlib-nano-stdio

CFLAGS  = -mcmodel=medium -Os -Ivictor -include ckvictor.h $(NANOSTDIO) $(XFLAGS)
LDFLAGS = -mcmodel=medium $(NANOSTDIO)

EXE     = ckermit.exe

# Portable protocol core -- unmodified upstream, this is the part we keep.
COMMON  = ckcmai.o ckclib.o ckcfns.o ckcfn2.o ckcfn3.o ckcpro.o

# Command parser and user interface.
UI      = ckucmd.o ckuusr.o ckuus2.o ckuus3.o ckuus4.o \
	  ckuus5.o ckuus6.o ckuus7.o ckuusx.o ckuusy.o

# Platform I/O.  ckutio.c and ckufio.c are the stock Unix modules: they
# compile clean for ia16 and reach the hardware through newlib.
PLATFORM = ckutio.o ckufio.o ckusig.o

# Compiled to ~0 bytes by NOCSETS / NOUNICODE / NONET, but kept in the
# link so the handful of symbols the mainline references still resolve.
EMPTY   = ckuxla.o ckcuni.o ckcnet.o ckctel.o

# Victor-specific glue -- the only non-upstream C file.
VICTOR  = ckvictor.o

OBJS    = $(COMMON) $(UI) $(PLATFORM) $(EMPTY) $(VICTOR)

all: $(EXE)

# The MS-DOS .EXE.  dos-m-c0.o (startup), dos-mm.ld (linker script) and
# libdos-m.a (INT 21h syscalls) all come in automatically from the medium
# multilib -- ia16-elf-gcc knows how to make a DOS binary and needs no help.
#
# The map is not optional.  DGROUP is the binding constraint and the linker
# is the only thing that knows the real total: "make sizes" measures the
# OBJECTS, and libc adds roughly 26KB of near data on top of them.  Read
# __heap_end_minimum out of the map to see what is actually left.
$(EXE): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS) -Wl,-Map=$(EXE).map
	@echo "--- near data (DGROUP), from the linker, including libc ---"
	@n=$$((`grep -m1 __heap_end_minimum $(EXE).map | awk '{print $$1}'`)); \
	 echo "  end of .bss = $$n of 65536 ($$((n*100/65536))%)"; \
	 echo "  left for heap + stack = $$((65536-n))"; \
	 test $$n -lt 65536 || { echo "  *** DGROUP OVERFLOW ***"; exit 1; }

# The protocol state machine is generated from ckcpro.w by wart.
# wart is a host tool, so build it with the host compiler.
wart: ckwart.c
	cc -DSIGTYP=void -o wart ckwart.c

ckcpro.c: ckcpro.w wart
	./wart ckcpro.w ckcpro.c

ckcpro.o: ckcpro.c

# Every object depends on the force-included configuration header and on the
# headers we supply under victor/.  Without this, editing ckvictor.h -- which
# is where the ENTIRE feature and size configuration lives -- rebuilds nothing
# and "make" cheerfully reports success over stale objects.  That happened,
# and it briefly hid a warning count.  Coarse-grained on purpose: these three
# headers change rarely and a full rebuild is a couple of minutes.
CONFIG_H = ckvictor.h victor/sys/termios.h victor/sys/ioctl.h

$(OBJS): $(CONFIG_H)

.c.o:
	$(CC) $(CFLAGS) -c $< -o $@

# Report the number that actually decides whether this port is viable.
sizes: $(OBJS)
	@echo "--- per module ---"
	@ia16-elf-size $(OBJS)
	@echo "--- totals ---"
# NOTE: ia16-elf-size reports Berkeley format, where .rodata is counted in the
# "text" column.  That is actively misleading here: .rodata is NEAR data and
# lives in DGROUP, because this toolchain has no large data model.  Believing
# the text column is what hid a 33KB DGROUP overrun until link time (see
# PORTING.md SS9c), so this target uses -A and adds .rodata where it belongs.
	@ia16-elf-size -A $(OBJS) | awk \
	  '/^\.rodata/{r+=$$2} /^\.data/{d+=$$2} /^\.bss/{b+=$$2} /^\.fartext/{f+=$$2} \
	   END {printf "far code (.fartext) = %7d   (1MB limit -- not a concern)\n", f; \
	        printf "\nNEAR DATA -- all of this is in the one 64K DGROUP:\n"; \
	        printf "  .rodata           = %7d   <- string literals ARE near\n", r; \
	        printf "  .data             = %7d\n", d; \
	        printf "  .bss              = %7d\n", b; \
	        printf "  objects subtotal  = %7d of 65536 (%.1f%%)\n", r+d+b, (r+d+b)*100/65536; \
	        printf "\nlibc adds roughly 12KB more of near data on top of this.\n"; \
	        printf "For the real number, link and read __heap_end_minimum from\n"; \
	        printf "$(EXE).map -- \"make $(EXE)\" prints it.\n"}'
	@echo "--- largest static objects ---"
	@ia16-elf-nm --size-sort -S --radix=d $(OBJS) 2>/dev/null | \
	  awk '$$3 ~ /^[bBdD]$$/ && $$2+0 > 500 {printf "%-7d %-3s %s\n", $$2,$$3,$$4}' | \
	  sort -rn | head -12

clean:
	rm -f *.o wart ckcpro.c

.PHONY: all sizes clean
