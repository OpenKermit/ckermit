/*  P W D . H  --  <pwd.h> for the Open Watcom build of the Victor port  */

/*
  MS-DOS has no password database, and the Open Watcom DOS runtime does not
  pretend otherwise: there is no <pwd.h> at all.  newlib ships one, which is
  why the ia16-elf-gcc build never needed this file.

  ckufio.c includes <pwd.h> unconditionally under UNIX and calls getpwnam(),
  getpwuid() and, for the fields, p->pw_name / pw_uid / pw_dir / pw_shell.
  Those calls are all on fallback paths -- whoami() and tilde_expand() --
  that ask "who is the user and where is their home directory?".  The stubs
  in ckvictor.c return NULL, which makes C-Kermit fall through to the
  environment (USER, HOME) exactly as it does on a Unix system where the
  lookup fails.  So the struct below only has to be *shaped* right; nothing
  ever reads an instance of it.

  Reached via -i=victorow.  See PORTING.md.
*/

#ifndef _PWD_H
#define _PWD_H

#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

struct passwd {
    char  * pw_name;                    /* User name                    */
    char  * pw_passwd;                  /* Encrypted password           */
    uid_t   pw_uid;                     /* User id                      */
    gid_t   pw_gid;                     /* Group id                     */
    char  * pw_gecos;                   /* Real name and so on          */
    char  * pw_dir;                     /* Home directory               */
    char  * pw_shell;                   /* Login shell                  */
};

/*
  Prototypes are spelled the way ckufio.c's own _PROTOTYP() declarations
  spell them (see ckufio.c ~line 507 and following): getpwnam() takes a
  "const char *" and getpwuid() takes PWID_T, which ckcdeb.h resolves to
  uid_t.  A disagreement here is a compile error in ckufio.c, not here.
*/
struct passwd * getpwnam(const char * __name);
struct passwd * getpwuid(uid_t __uid);
struct passwd * getpwent(void);
void            setpwent(void);
void            endpwent(void);

#ifdef __cplusplus
}
#endif

#endif /* _PWD_H */
