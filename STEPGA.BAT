ECHO OFF
REM Leg GA -- the control half of the efficacy pair, second attempt.
REM CKFCMID is the shipping tree with the water marks at 1024/896 -- a
REM NARROW BAND, not a low mark, which is the change from SS16ak's DA/DB.
REM 256/64 paused the sender hard enough to trip the protocol; 128 bytes of
REM drain is about 62 ms and should not.
IF EXIST RCVGA.DAT DEL RCVGA.DAT
CKFCMID -l /dev/seriala -b 38400 --noflow -r > STEPGA.OUT
