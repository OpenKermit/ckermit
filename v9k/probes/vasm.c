/* vasm.c -- which hand-written-ISR mechanism does Open Watcom give us?
   PORTING.md SS16t.  Compile only; the point is the wdis output. */
static volatile unsigned char x;

void __interrupt __far isr_c(void)      /* 1. what ckvictor.c uses today */
{
    x++;
}

void __interrupt __far isr_mixed(void)  /* 2. __interrupt with _asm body */
{
    _asm {
        mov al,1
        mov byte ptr x,al
    }
}
