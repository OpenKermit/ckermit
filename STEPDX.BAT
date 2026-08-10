ECHO OFF
REM Leg DX -- the Victor OBEYING a real XOFF, which no leg has ever done.
REM The Victor sends; the host receives with "set flow xon/xoff", so its
REM tty will XOFF us when its buffer fills.  Pass is byte-exact with
REM stuck=0.  xoff>0 is the reading that says we obeyed one; xoff=0 means
REM the host never needed to send one, which is a null and not a failure.
CKERMITW -l /dev/seriala -b 38400 --xonxoff -s TRANS.DAT > STEPDX.OUT
