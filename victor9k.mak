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
CFLAGS  = -mcmodel=medium -Os -Ivictor -include ckvictor.h $(XFLAGS)
LDFLAGS = -mcmodel=medium

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

all: $(OBJS)

# The protocol state machine is generated from ckcpro.w by wart.
# wart is a host tool, so build it with the host compiler.
wart: ckwart.c
	cc -DSIGTYP=void -o wart ckwart.c

ckcpro.c: ckcpro.w wart
	./wart ckcpro.w ckcpro.c

ckcpro.o: ckcpro.c

.c.o:
	$(CC) $(CFLAGS) -c $< -o $@

# Report the number that actually decides whether this port is viable.
sizes: $(OBJS)
	@echo "--- per module ---"
	@ia16-elf-size $(OBJS)
	@echo "--- totals ---"
	@ia16-elf-size $(OBJS) | awk 'NR>1 {t+=$$1; d+=$$2; b+=$$3} \
	  END {printf "text = %6d  (far code, 1MB limit -- not a concern)\n", t; \
	       printf "data = %6d\n", d; printf "bss  = %6d\n", b; \
	       printf "STATIC DGROUP = %d of 65536 (%.1f%%)\n", d+b, (d+b)*100/65536; \
	       printf "remaining for heap + stack + libc: %d\n", 65536-(d+b)}'
	@echo "--- largest static objects ---"
	@ia16-elf-nm --size-sort -S --radix=d $(OBJS) 2>/dev/null | \
	  awk '$$3 ~ /^[bBdD]$$/ && $$2+0 > 500 {printf "%-7d %-3s %s\n", $$2,$$3,$$4}' | \
	  sort -rn | head -12

clean:
	rm -f *.o wart ckcpro.c

.PHONY: all sizes clean
