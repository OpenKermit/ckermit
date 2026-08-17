ECHO OFF
REM Leg FZ -- PORTING.md SS16aj.  THE CONTROL, and it is the pre-change
REM binary: HEAD without section 1f, rebuilt and md5-identical to the
REM SS16ai shipping build (537486a8).  Same fixture, same rate, same run
REM sheet as leg FA.  Any difference between FZ and FA is section 1f.
CKPRE -l /dev/seriala -b 9600 -r > STEPFZ.OUT
