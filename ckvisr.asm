;;  ckvisr.asm -- the uPD7201 receive interrupt handler, written by hand.
;;
;;  PORTING.md SS16t.  This is the second implementation of the handler in
;;  ckvictor.c SS1e; the C one is still there and still builds, and
;;  XFLAGS=-dV9K_CISR selects it.  Read the C one first -- every comment
;;  explaining WHY the sequence is what it is lives there, and this file
;;  deliberately does not repeat them.  What follows is only why it is in
;;  assembly at all, and what is different.
;;
;;  WHY.  At 38400 a byte arrives every 260us.  The C handler is marginal
;;  against that, and the measurement that says so is SS16t's A/B: taking
;;  36 instructions out of the overrun path cut rxlost 822 -> 483 and the
;;  longest burst 401 -> 204, back to back in one bench session.  Handler
;;  cost translates directly into bytes lost, so the overhead is the bug.
;;
;;  In the C handler that overhead is 52 of 185 instructions, and none of
;;  it does any work:
;;
;;    * 24 stack operations.  Open Watcom's __interrupt saves all twelve
;;      registers and there is no way to ask it not to -- confirmed by
;;      compiling it three ways (v9k/probes/vasm.c): __interrupt with a C body
;;      and with an _asm body emit the identical twelve-push prologue, and
;;      a #pragma aux written in assembly cannot be used at all, because
;;      its code is inlined at call sites and taking its address emits a
;;      reference to a symbol nothing defines.  msxv90.asm, which is this
;;      same chip on this same machine and works at 38400, saves five.
;;    * 14 "mov ax,DGROUP / mov ds,ax" pairs.  The C handler reaches the
;;      chip through a far pointer built by MK_FP, so Watcom rebuilds DS
;;      for every port access and rebuilds it again for every counter
;;      update in between.  On a 5MHz 8088 the bottleneck is instruction
;;      fetch at about 4 clocks a byte, so those 70 bytes cost about 56us
;;      of the 260us budget, and the stack traffic about 67us more.
;;
;;  WHAT IS DIFFERENT, and there are only two things.
;;
;;    1. ONE segment register covers both chips.  The 7201 is at E004:0-3
;;       and the 8259 at E000:0-1, which are 0xE0040-43 and 0xE0000-01 in
;;       linear terms -- 0x40 apart, both inside one 64K segment.  So ES
;;       is loaded once with E000h and every port access is ES-relative
;;       with no reload: channel A control is 42h, channel A data 40h,
;;       channel B 43h/41h, the 8259 command port 0.  The C handler cannot
;;       express this because V9K_SEG_7201 and V9K_SEG_8259 are separate
;;       constants in separate far pointers.
;;    2. No burst table.  SS16s added a per-burst table to the overrun
;;       path believing it was rare; it is rare only while the receiver is
;;       keeping up, and inside a burst the overrun path IS the per-byte
;;       path.  It cost 2.5x the loss rate.  The counters it was built
;;       from -- lostevt, lostmax, losttag, lostat, lostend -- are all
;;       still maintained here, so a run of this handler prints the same
;;       lines a V9K_LEANLOST C build does and the two are comparable.
;;
;;  Everything else is a faithful transcription of v9k_ser_isr(), in the
;;  same order, with the same tests.  If the two ever disagree the C one
;;  is the specification.
;;
;;  REGISTERS.  AX, BX, DX, DS, ES -- five, the same five msxv90.asm saves.
;;  CX, SI, DI and BP are not touched, so they are not saved.  The frame is
;;  10 bytes plus the return address; there is no stack switch, which is
;;  the same deliberate choice SS1e made for the C handler and for the same
;;  reason (MS-DOS 3.1's own ISRs switch, but this one calls nothing and
;;  cannot recurse).
;;
;;  IT HAS NOT RUN ON A VICTOR.  Neither had SS16q's or SS16s's
;;  instruments when they were written.  The overrun path in particular
;;  cannot be exercised under MAME at any rate the emulator can drive, so
;;  what a 9600 emulator run proves is that the clean path receives every
;;  byte and the machine survives -- which is most of this file, and is
;;  worth doing before a drive to the bench.

        .8086

;;  All four segments, in the order wcc emits them, and not just the two
;;  this file happens to address.  "mov ax,DGROUP" assembles to the group
;;  BASE, and the base is the first segment in the group -- so declaring a
;;  subset here would build a group whose base is _DATA while the C half of
;;  the program is using CONST, and DS would be wrong by however much CONST
;;  and CONST2 occupy.  That is a silent, data-dependent corruption of every
;;  variable this handler touches, so it is spelled out rather than trusted.
;;  Compare "mov ax,DGROUP:CONST" in wdis output from ckvictor.obj.
DGROUP  GROUP   CONST,CONST2,_DATA,_BSS

;;  The chips, as offsets inside segment E000h.  See note 1 above.
V9K_SEG_IO      EQU     0E000h
V9K_7201_BIAS   EQU     40h             ; add to a 7201 channel offset
V9K_CTLA_OFF    EQU     42h             ; channel A control, biased
V9K_8259_CMD    EQU     0               ; OCW2, where the EOI goes

;;  Commands and status bits -- ckvictor.c SS1e has the datasheet notes.
V9K_CMD_EOI     EQU     38h             ; 7201 end of interrupt
V9K_CMD_ERRRST  EQU     30h             ; 7201 error reset
V9K_IRQ1_EOI    EQU     61h             ; 8259 specific EOI for IRQ1
V9K_RR0_RXRDY   EQU     01h
V9K_RR1_OVERRUN EQU     20h

;;  Ring geometry.  MUST match V9K_RXBUFSIZ in ckvictor.h; there is a
;;  compile-time check for that in ckvictor.c next to the ring itself.
V9K_RXMASK      EQU     0FFFh           ; V9K_RXBUFSIZ - 1, 4096 - 1
V9K_RXSTALL     EQU     256
V9K_LOSTGAP     EQU     16
V9K_BELL        EQU     07h

        EXTRN   _v9k_off_ctl   : WORD
        EXTRN   _v9k_off_dat   : WORD
        EXTRN   _v9k_off_oth   : WORD
        EXTRN   _v9k_rxbuf     : BYTE
        EXTRN   _v9k_rxhead    : WORD
        EXTRN   _v9k_rxtail    : WORD
        EXTRN   _v9k_rxlost    : WORD
        EXTRN   _v9k_rxfull    : WORD
        EXTRN   _v9k_rxpeak    : WORD
        EXTRN   _v9k_rxstall   : WORD
        EXTRN   _v9k_rxbytes   : DWORD
        EXTRN   _v9k_peakat    : DWORD
        EXTRN   _v9k_stallat   : DWORD
        EXTRN   _v9k_peaktag   : BYTE
        EXTRN   _v9k_peakfd    : WORD
        EXTRN   _v9k_wtag      : BYTE
        EXTRN   _v9k_wtagfd    : WORD
        EXTRN   _v9k_lostevt   : WORD
        EXTRN   _v9k_lostrun   : WORD
        EXTRN   _v9k_lostmax   : WORD
        EXTRN   _v9k_lostat    : DWORD
        EXTRN   _v9k_lostend   : DWORD
        EXTRN   _v9k_losttag   : BYTE
        EXTRN   _v9k_lostfd    : WORD
        EXTRN   _v9k_isrnorx   : WORD
        EXTRN   _v9k_isrothrx  : WORD
        EXTRN   _v9k_norxrr0   : BYTE
        EXTRN   _v9k_norxoth   : BYTE
        EXTRN   _v9k_norxseen  : BYTE

CONST   SEGMENT WORD PUBLIC USE16 'DATA'
CONST   ENDS
CONST2  SEGMENT WORD PUBLIC USE16 'DATA'
CONST2  ENDS
_DATA   SEGMENT WORD PUBLIC USE16 'DATA'
_DATA   ENDS
_BSS    SEGMENT WORD PUBLIC USE16 'BSS'
_BSS    ENDS

CKVISR_TEXT     SEGMENT BYTE PUBLIC USE16 'CODE'
        ASSUME  CS:CKVISR_TEXT, DS:DGROUP

        PUBLIC  v9k_ser_isr_asm_

v9k_ser_isr_asm_ PROC FAR

        push    ax
        push    bx
        push    dx
        push    ds
        push    es

        mov     ax,DGROUP
        mov     ds,ax
        mov     ax,V9K_SEG_IO
        mov     es,ax

;;  Service the chip.  RR0, then RR1, then both end-of-interrupts, exactly
;;  as the C handler does and in the same order: the EOIs go out before any
;;  decision is taken, so no path can leave the 8259 with IRQ1 in service.
        mov     bx,_v9k_off_ctl
        add     bx,V9K_7201_BIAS
        mov     al,es:[bx]                      ; AL = RR0
        mov     byte ptr es:[bx],1              ; point at RR1 ...
        mov     ah,es:[bx]                      ; AH = RR1, pointer resets
        mov     byte ptr es:[V9K_CTLA_OFF],V9K_CMD_EOI
        mov     byte ptr es:[V9K_8259_CMD],V9K_IRQ1_EOI

        test    al,V9K_RR0_RXRDY                ; anything for us?
        jnz     v9k_haverx
        jmp     v9k_norx

v9k_haverx:
        test    ah,V9K_RR1_OVERRUN              ; latched -- clear or wedge
        jnz     v9k_overrun
        jmp     v9k_getbyte

;; ---------------------------------------------------------------------
;;  The overrun path.  Rare while we are keeping up, and the per-byte path
;;  once we are not -- which is why nothing beyond the original counters
;;  is allowed in here.  See note 2 at the top.
;; ---------------------------------------------------------------------
v9k_overrun:
        mov     byte ptr es:[bx],V9K_CMD_ERRRST
        inc     word ptr _v9k_rxlost

;;  New burst, or a continuation?  A loss opens a new one when more than
;;  V9K_LOSTGAP bytes have arrived cleanly since the last.  The first-loss
;;  arm has to stay: lostend is still 0 then and the subtraction would be
;;  measuring against nothing.
        cmp     word ptr _v9k_lostevt,0
        je      v9k_newburst
        mov     ax,word ptr _v9k_rxbytes
        mov     dx,word ptr _v9k_rxbytes+2
        sub     ax,word ptr _v9k_lostend
        sbb     dx,word ptr _v9k_lostend+2
        or      dx,dx                           ; > 64K apart is certainly
        jnz     v9k_newburst                    ; a new burst
        cmp     ax,V9K_LOSTGAP
        jbe     v9k_sameburst

v9k_newburst:
        cmp     word ptr _v9k_lostevt,0
        jne     v9k_nb1
        mov     dl,byte ptr _v9k_wtag           ; section 0e, latched HERE
        mov     byte ptr _v9k_losttag,dl
        mov     dx,word ptr _v9k_wtagfd
        mov     word ptr _v9k_lostfd,dx
        mov     dx,word ptr _v9k_rxbytes
        mov     word ptr _v9k_lostat,dx
        mov     dx,word ptr _v9k_rxbytes+2
        mov     word ptr _v9k_lostat+2,dx
v9k_nb1:
        inc     word ptr _v9k_lostevt
        mov     word ptr _v9k_lostrun,1
        jmp     v9k_burstdone

v9k_sameburst:
        inc     word ptr _v9k_lostrun

v9k_burstdone:
        mov     ax,word ptr _v9k_lostrun
        cmp     ax,word ptr _v9k_lostmax
        jbe     v9k_nomax
        mov     word ptr _v9k_lostmax,ax
v9k_nomax:
        mov     ax,word ptr _v9k_rxbytes
        mov     dx,word ptr _v9k_rxbytes+2
        mov     word ptr _v9k_lostend,ax
        mov     word ptr _v9k_lostend+2,dx

;;  Mark the gap with a BELL, as 3.13 does, so the packet keeps its length
;;  and ttinl() still finds the next SOH where it expects it.  Counted in
;;  rxbytes, because it occupies a position in the stream.
        mov     bx,word ptr _v9k_rxhead
        mov     ax,bx
        inc     ax
        and     ax,V9K_RXMASK
        cmp     ax,word ptr _v9k_rxtail
        je      v9k_getbyte
        mov     byte ptr _v9k_rxbuf[bx],V9K_BELL
        mov     word ptr _v9k_rxhead,ax
        add     word ptr _v9k_rxbytes,1
        adc     word ptr _v9k_rxbytes+2,0

;; ---------------------------------------------------------------------
;;  The byte itself, and the ring.  Dropping the NEWEST byte when the ring
;;  is full is deliberate -- the oldest bytes are the front of a packet
;;  Kermit is about to read.
;; ---------------------------------------------------------------------
v9k_getbyte:
        mov     bx,_v9k_off_dat
        add     bx,V9K_7201_BIAS
        mov     al,es:[bx]                      ; AL = the received byte

        mov     bx,word ptr _v9k_rxhead
        mov     dx,bx
        inc     dx
        and     dx,V9K_RXMASK
        cmp     dx,word ptr _v9k_rxtail
        je      v9k_ringfull

        mov     byte ptr _v9k_rxbuf[bx],al
        mov     word ptr _v9k_rxhead,dx
        add     word ptr _v9k_rxbytes,1
        adc     word ptr _v9k_rxbytes+2,0

;;  Occupancy after us, which is what rxpeak and the stall counter read.
        mov     ax,dx
        sub     ax,word ptr _v9k_rxtail
        and     ax,V9K_RXMASK

        cmp     ax,word ptr _v9k_rxpeak
        jbe     v9k_nopeak
        mov     word ptr _v9k_rxpeak,ax
        mov     dl,byte ptr _v9k_wtag           ; section 0e: and who was
        mov     byte ptr _v9k_peaktag,dl        ; holding us up
        mov     dx,word ptr _v9k_wtagfd
        mov     word ptr _v9k_peakfd,dx
        mov     dx,word ptr _v9k_rxbytes
        mov     word ptr _v9k_peakat,dx
        mov     dx,word ptr _v9k_rxbytes+2
        mov     word ptr _v9k_peakat+2,dx
v9k_nopeak:
        cmp     ax,V9K_RXSTALL                  ; crossed it going up
        jne     v9k_done
        cmp     word ptr _v9k_rxstall,0
        jne     v9k_bumpstall
        mov     dx,word ptr _v9k_rxbytes
        mov     word ptr _v9k_stallat,dx
        mov     dx,word ptr _v9k_rxbytes+2
        mov     word ptr _v9k_stallat+2,dx
v9k_bumpstall:
        inc     word ptr _v9k_rxstall
        jmp     v9k_done

v9k_ringfull:
        inc     word ptr _v9k_rxfull            ; this byte is gone

v9k_done:
        pop     es
        pop     ds
        pop     dx
        pop     bx
        pop     ax
        iret

;; ---------------------------------------------------------------------
;;  An entry with nothing waiting on our channel.  SS16t measured this at
;;  zero, twice, at two rates -- so nothing else shares IRQ1 and the other
;;  half of the 7201 is not stealing slots.  Kept because it costs nothing
;;  unless it happens and it makes every future run say so again.  AL still
;;  holds RR0 here, which is why the test above jumps rather than falls.
;; ---------------------------------------------------------------------
v9k_norx:
        mov     bx,_v9k_off_oth
        add     bx,V9K_7201_BIAS
        mov     byte ptr es:[bx],0              ; null command: point at RR0
        mov     ah,es:[bx]
        inc     word ptr _v9k_isrnorx
        test    ah,V9K_RR0_RXRDY
        jz      v9k_nrx1
        inc     word ptr _v9k_isrothrx
v9k_nrx1:
        cmp     byte ptr _v9k_norxseen,0
        jne     v9k_done
        mov     byte ptr _v9k_norxseen,1
        mov     byte ptr _v9k_norxrr0,al
        mov     byte ptr _v9k_norxoth,ah
        jmp     v9k_done

v9k_ser_isr_asm_ ENDP

CKVISR_TEXT     ENDS

        END
