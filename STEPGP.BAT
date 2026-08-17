ECHO OFF
REM Leg GP -- PORTING.md SS16al.  THE CONTROL SS16aj's run sheet should have
REM had: CKPRE is HEAD BEFORE section 1f, md5 537486a8, the binary the whole
REM project measured through SS16ai.  Adjacent to GQ, same fixture, same
REM rate.  The pair answers whether section 1f costs 11% of a 38400 receive
REM or whether SS16ak's three legs were simply a slower sitting than SS16ah.
REM
REM IF EXIST/DEL makes this leg RE-RUNNABLE.  SET FILE COLLISION is BACKUP
REM and BACKUP cannot work on FAT; a stale target refuses the file and the
REM leg comes back "S, F, A, then Z with data D" and no data packets.  That
REM voided both legs of the 9 August re-run.
IF EXIST RCVGP.DAT DEL RCVGP.DAT
CKPRE -l /dev/seriala -b 38400 -r > STEPGP.OUT
