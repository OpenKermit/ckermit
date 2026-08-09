/*
  vmem.c -- what will this Victor actually give a program?

  PORTING.md SS16a measured "the largest block DOS offers" once, on a 896K
  machine, and the resulting 396,224 then travelled through the tree as if
  it were a property of the Victor.  It is not.  A Victor takes RAM in 128K
  increments from 128K to 896K, and the free block depends on the machine,
  the DOS and what CONFIG.SYS loaded.  This prints it, so the question can
  be asked of any configuration instead of assumed from one.

  INT 21h AH=4Ah (resize memory block) with BX = FFFFh always fails, and
  the failure is the measurement: DOS returns in BX the largest number of
  paragraphs it COULD have given.  ES must be our own PSP-owned block,
  which is what _psp is.  This is the same call SS16a used and the reason
  the parser build's "Allocation of DOS memory failed" was diagnosable.

  Reports the free block, then the total the program already occupies, so
  the two together say what the machine had before DOS loaded.

  Build (host container, Open Watcom):
    wcc -ml -0 -os -zq -bt=dos -fr=/dev/null vmem.c
    wlink system dos name vmem.exe file vmem.obj

  INT 21h only, per rule 6.  Nothing here is Victor-specific; it is only
  interesting on a Victor because nobody had run it on a small one.
*/

#include <dos.h>
#include <stdio.h>

extern unsigned _psp;

int
main()
{
    union REGS  r;
    struct SREGS s;
    unsigned long paras;

    segread(&s);

    /*
      Ask for an impossible resize of our own block.  Carry comes back set
      and BX holds the maximum available, in paragraphs.  Counting our own
      block, because DOS reports what the block could grow to.
    */
    r.h.ah = 0x4a;
    r.x.bx = 0xffff;
    s.es   = _psp;
    intdosx(&r, &r, &s);

    paras = (unsigned long)r.x.bx;
    printf("v9k mem: largest block = %lu paragraphs = %lu bytes (%luK)\n",
           paras, paras * 16UL, (paras * 16UL) / 1024UL);

    /*
      The PSP segment itself says where DOS started handing memory out,
      which is the size of DOS plus its drivers plus the shell's resident
      part.  Machine total is then roughly psp*16 + the block above, and
      "roughly" because the transient shell above us is not counted.
    */
    printf("v9k mem: psp = %04X, so DOS+drivers below us = %lu bytes (%luK)\n",
           _psp, (unsigned long)_psp * 16UL,
           ((unsigned long)_psp * 16UL) / 1024UL);

    return(0);
}
