/*
  fakeshadow.c: LD_PRELOAD library that lets an IKSD log in one user
  without root access.

  FAKESHADOW_USER names the user.  FAKESHADOW_PASS is the password.
  FAKESHADOW_HOME, when set, is the user's home directory.

  getpwnam() returns the user's entry with pw_dir set to
  FAKESHADOW_HOME.  FAKESHADOW_ALIAS, when set, is a second name for
  the same entry.  getpwnam() returns other entries unchanged.

  fopen() and fopen64() open FAKESHADOW_IKSDCONF, when set, in place of
  /etc/iksd.conf.  So a test can give an IKSD a configuration file.

  getspnam() returns an entry for that user, or for FAKESHADOW_ALIAS,
  that holds crypt(FAKESHADOW_PASS) with a fixed SHA-512 salt.  It
  returns NULL for any other name.

  pam_authenticate() asks for the password through the application's
  conversation function and accepts the user when the answer matches.
  pam_acct_mgmt() accepts that user.  Both refuse any other user.

  Build: cc -shared -fPIC -o fakeshadow.so fakeshadow.c -lcrypt -lpam -ldl
*/
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pwd.h>
#include <shadow.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <crypt.h>
#include <security/pam_appl.h>

/* Return the path to open in place of path. */
static const char *
conf_path(const char *path)
{
    const char *conf = getenv("FAKESHADOW_IKSDCONF");

    if (conf && path && strcmp(path, "/etc/iksd.conf") == 0)
        return conf;
    return path;
}

FILE *
fopen(const char *path, const char *mode)
{
    static FILE *(*real)(const char *, const char *);

    if (!real)
        real = (FILE *(*)(const char *, const char *))dlsym(RTLD_NEXT,
                                                            "fopen");
    return real ? real(conf_path(path), mode) : NULL;
}

FILE *
fopen64(const char *path, const char *mode)
{
    static FILE *(*real)(const char *, const char *);

    if (!real)
        real = (FILE *(*)(const char *, const char *))dlsym(RTLD_NEXT,
                                                            "fopen64");
    return real ? real(conf_path(path), mode) : NULL;
}

struct passwd *
getpwnam(const char *name)
{
    static struct passwd pw;
    static struct passwd *(*real)(const char *);
    const char *user = getenv("FAKESHADOW_USER");
    const char *home = getenv("FAKESHADOW_HOME");
    const char *alias = getenv("FAKESHADOW_ALIAS");
    struct passwd *p;

    if (!real)
        real = (struct passwd *(*)(const char *))dlsym(RTLD_NEXT,
                                                      "getpwnam");
    if (!real)
        return NULL;
    if (name && user && home && alias && strcmp(name, alias) == 0) {
        if (!(p = real(user)))
            return NULL;
        pw = *p;
        pw.pw_name = (char *)alias;
        pw.pw_dir = (char *)home;
        return &pw;
    }
    p = real(name);
    if (!p || !user || !home || strcmp(name, user) != 0)
        return p;
    pw = *p;
    pw.pw_dir = (char *)home;
    return &pw;
}

struct spwd *
getspnam(const char *name)
{
    static struct spwd sp;
    const char *user = getenv("FAKESHADOW_USER");
    const char *pass = getenv("FAKESHADOW_PASS");
    const char *alias = getenv("FAKESHADOW_ALIAS");
    char *hash;

    if (!name || !user || !pass)
        return NULL;
    if (strcmp(name, user) != 0 && (!alias || strcmp(name, alias) != 0))
        return NULL;
    hash = crypt(pass, "$6$ckermittest$");
    if (!hash)
        return NULL;
    memset(&sp, 0, sizeof(sp));
    sp.sp_namp = (char *)name;
    sp.sp_pwdp = hash;
    sp.sp_lstchg = -1;
    sp.sp_min = -1;
    sp.sp_max = -1;
    sp.sp_warn = -1;
    sp.sp_inact = -1;
    sp.sp_expire = -1;
    return &sp;
}

/* Return 1 if the PAM user is FAKESHADOW_USER. */
static int
pam_user_ok(pam_handle_t *pamh)
{
    const void *item = NULL;
    const char *user = getenv("FAKESHADOW_USER");

    if (!user || pam_get_item(pamh, PAM_USER, &item) != PAM_SUCCESS ||
        !item)
        return 0;
    return strcmp((const char *)item, user) == 0;
}

int
pam_authenticate(pam_handle_t *pamh, int flags)
{
    const void *item = NULL;
    const struct pam_conv *conv;
    struct pam_message msg;
    const struct pam_message *msgp = &msg;
    struct pam_response *resp = NULL;
    const char *pass = getenv("FAKESHADOW_PASS");
    int ok;

    (void)flags;
    if (!pass || !pam_user_ok(pamh))
        return PAM_AUTH_ERR;
    if (pam_get_item(pamh, PAM_CONV, &item) != PAM_SUCCESS || !item)
        return PAM_AUTH_ERR;
    conv = (const struct pam_conv *)item;
    msg.msg_style = PAM_PROMPT_ECHO_OFF;
    msg.msg = "Password: ";
    if (conv->conv(1, &msgp, &resp, conv->appdata_ptr) != PAM_SUCCESS ||
        !resp)
        return PAM_AUTH_ERR;
    ok = resp[0].resp && strcmp(resp[0].resp, pass) == 0;
    free(resp[0].resp);
    free(resp);
    return ok ? PAM_SUCCESS : PAM_AUTH_ERR;
}

int
pam_acct_mgmt(pam_handle_t *pamh, int flags)
{
    (void)flags;
    return pam_user_ok(pamh) ? PAM_SUCCESS : PAM_PERM_DENIED;
}
