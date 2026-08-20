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

PROOFS  = vcrc16 vburst vttinl vwindow vznewn

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

# vznewn checks a function that SHIPS, so it must not hold its own copy of
# it -- the standing complaint in README and NEXT_SESSION.md is that these
# proofs transcribe what they check and then keep passing after it moves.
# This extracts v9k_backupname() out of ckvictor.c at build time, so the
# thing under test is the thing that ships, by construction.  The rule
# fails loudly rather than emitting an empty header: a proof compiled
# against nothing passes.
vznewn.bin: vznewn_gen.h

vznewn_gen.h: ../../ckvictor.c
	@echo "/* GENERATED from ckvictor.c by v9k/proofs/Makefile -- do not edit. */" > $@
	@awk '{L[NR]=$$0} \
	      /^v9k_backupname\(char \* buf, int size\)$$/{s=NR-2} \
	      END{ if(!s){print "EXTRACT FAILED" > "/dev/stderr"; exit 1} \
	           for(i=s;i<=NR;i++){print L[i]; if(L[i]=="}") exit} }' $< >> $@
	@grep -q "v9k_backupname" $@ || (echo "vznewn_gen.h: extraction failed" && rm -f $@ && false)
	@grep -c . $@ | xargs printf "vznewn_gen.h: %s lines extracted from ckvictor.c\n"

clean:
	rm -f $(PROOFS:=.bin) $(PROOFS) vznewn_gen.h
