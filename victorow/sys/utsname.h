/*  S Y S / U T S N A M E . H  --  uname() for the Open Watcom build  */

/*
  Open Watcom's DOS runtime has no uname().  newlib does, which is why the
  ia16-elf-gcc build never needed this file.

  Two modules want it, and both use it the same way -- as the last resort
  for "what is this machine called?":

    ckutio.c   getlocalipaddrs()/ttgtpn area: os name for the version banner
    ckuusx.c   getlocalname(): the \v(host) value, after gethostname() fails

  A Victor is a single machine with no network and no hostname, so the
  implementation in ckvictor.c fills the fields in from constants and
  returns 0.  The field widths follow the traditional SVR4 layout; the
  struct is a static in each caller, so keeping it small matters -- 9
  characters is the classic value and is more than "Victor" needs.

  Reached via -i=victorow.  See PORTING.md.
*/

#ifndef _SYS_UTSNAME_H
#define _SYS_UTSNAME_H

#ifdef __cplusplus
extern "C" {
#endif

#define _UTSNAME_LENGTH 9

struct utsname {
    char sysname[_UTSNAME_LENGTH];      /* Operating system name        */
    char nodename[_UTSNAME_LENGTH];     /* Network node name            */
    char release[_UTSNAME_LENGTH];      /* OS release                   */
    char version[_UTSNAME_LENGTH];      /* OS version                   */
    char machine[_UTSNAME_LENGTH];      /* Hardware type                */
};

int uname(struct utsname * __name);

#ifdef __cplusplus
}
#endif

#endif /* _SYS_UTSNAME_H */
