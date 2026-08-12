IF EXIST STEPJC.OUT DEL STEPJC.OUT
CKBULK --nobulz --nodisplay -l /dev/seriala -b 9600 -r > STEPJC.OUT
