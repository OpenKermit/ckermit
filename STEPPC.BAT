ECHO OFF
REM Leg PC -- see s16aePC.ksc on the host for what this leg tests
REM and how to read it.  All four legs run the shipping CKERMITW.EXE:
REM the Victor-side prefixing setting is read only by the packet BUILDER
REM (ckcfns.c:1798, 2904), so on a receive it cannot affect the wire and
REM a Victor-side control build has nothing left to control.
REM
REM Own fixture per leg, so no leg can collide with or be mistaken for
REM another: receives as RCVPC.DAT.  The redirect is how the v9k:
REM counters reach a file at all (SS16u).
CKERMITW -l /dev/seriala -b 38400 -r > STEPPC.OUT
