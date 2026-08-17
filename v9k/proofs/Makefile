# v9k/proofs -- build and run the standing correctness proofs.
#
# Host programs (the Mac), not the target.  "make" both builds and RUNS
# them, and fails if any test fails: a proof that is only compiled has not
# proved anything, and the failure mode these guard against is silent.
#
#     make            build and run all
#     make vcrc16     build and run one
#     make clean

CC      = cc
CFLAGS  = -O2 -Wall

PROOFS  = vcrc16 vburst vttinl vwindow

.PHONY: all clean $(PROOFS)

all: $(PROOFS)

# Each target rebuilds if stale, then runs.  The recipe is phony on purpose
# so that "make" always re-runs the checks rather than reporting the
# binaries up to date -- these take milliseconds and the whole point is the
# result, not the artifact.
$(PROOFS): %: %.bin
	@echo "=== $@ ==="
	@./$<

%.bin: %.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(PROOFS:=.bin) $(PROOFS)
