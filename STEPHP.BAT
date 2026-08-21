ECHO OFF
REM Leg HP (pass 3) -- the -d MECHANISM run into A:\ that SS16ba asked
REM for.  9600.  NOT a throughput leg: -d costs ~25 ms per received byte
REM (SS16k) and its clock means nothing.
REM
REM THE BINARY IS CKHPDBG.EXE, NOT CKBB.EXE, AND THAT IS THE WHOLE POINT.
REM CKBB.EXE is built NODEBUG, so it REJECTS -d -- which is what happened
REM on 21 August, because pass 2 named the flag and never built or staged
REM a binary carrying it.  CLAUDE.md hard rule: a sheet that names a -d
REM flag must also name the staged binary that carries it, or the flag is
REM a suggestion.  CKHPDBG.EXE is -dKEEP_DEBUG from HEAD, 314,168 bytes,
REM needs 320,920 (313K), smallest Victor 512K.
REM
REM Expect deb=1 on this leg and ONLY this leg.  The log is large.
IF EXIST RCVHP.DAT DEL RCVHP.DAT
IF EXIST STEPHP.OUT DEL STEPHP.OUT
IF EXIST HP.LOG DEL HP.LOG
IF EXIST DEBUG.LOG DEL DEBUG.LOG
CKHPDBG.EXE --nodisplay -l /dev/seriala -b 9600 -d -r > STEPHP.OUT
REN DEBUG.LOG HP.LOG
