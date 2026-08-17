/*
  Unit tests for the address-family-independent helpers in ckcnet.c.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcnet.h"
#include "ck_ssl.h"

/*
  ckgetfqhostname() calls debug(), which needs these two.  See the identical
  stubs in test_lib.c/test_strings.c, needed for the same reason.
*/
int deblog = 0;
int fp_digits = 6;
int matchdot = 0;
int dodebug(int a, char *b, char *c, CK_OFF_T d) {
    return 0;
}

/*
  test_net links a --gc-sections build of ckcnet.c so that only the functions
  under test are in the binary.  The rest of ckcnet.c calls out to globals and
  functions that live in modules this test doesn't need or link against.

  On most architectures --gc-sections drops that unreached code along with the
  external references it carries.  PowerPC64 (ELFv2 ABI) keeps every TOC entry
  for a translation unit in one section that is not itself subject to garbage
  collection, so the linker still demands these symbols even though nothing in
  the final binary calls them.  Defining them here satisfies the linker on
  every architecture without pulling in the rest of C-Kermit or OpenSSL.
*/
CK_TTYFD_T ttyfd = -1;
int streaming = 0;
int ttchk(void) {
    return -1;
}

#ifdef CK_SSL
int tls_http_active_flag = 0;
int ssl_debug_flag = 0;
SSL *tls_http_con = NULL;
BIO *bio_err = NULL;

int SSL_shutdown(SSL *s) {
    return 0;
}
int SSL_write(SSL *ssl, const void *buf, int num) {
    return -1;
}
int SSL_get_error(const SSL *s, int ret_code) {
    return 0;
}
int SSL_pending(const SSL *s) {
    return 0;
}
int SSL_read(SSL *ssl, void *buf, int num) {
    return -1;
}
int BIO_printf(BIO *bio, const char *format, ...) {
    return 0;
}
#endif /* CK_SSL */

START_TEST(test_straddr_v4)
{
    struct sockaddr_in sin;
    char buf[64];

    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_addr.s_addr = inet_addr("192.0.2.1");
    sin.sin_port = htons(23);

    ck_assert_int_eq(
        ck_straddr((struct sockaddr *)&sin, sizeof(sin), buf, sizeof(buf)),
        0);
    ck_assert_str_eq(buf, "192.0.2.1");
}
END_TEST

START_TEST(test_straddr_bad_args)
{
    struct sockaddr_in sin;
    char buf[64];

    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_addr.s_addr = inet_addr("192.0.2.1");

    ck_assert_int_eq(ck_straddr((struct sockaddr *)&sin, sizeof(sin),
                                 NULL, 0), -1);
    ck_assert_int_eq(ck_straddr(NULL, 0, buf, sizeof(buf)), -1);
}
END_TEST

START_TEST(test_port_v4)
{
    struct sockaddr_in sin;

    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_port = htons(23);

    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin), 23);

    ck_setport((struct sockaddr *)&sin, 2000);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin), 2000);
    ck_assert_uint_eq(ntohs(sin.sin_port), 2000);
}
END_TEST

START_TEST(test_port_v4_overflow)
{
    struct sockaddr_in sin;

    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;

    /* sin_port is 16 bits: the top of its range must round-trip... */
    ck_setport((struct sockaddr *)&sin, 65535);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin), 65535);

    /* ...and a port that doesn't fit truncates to the low 16 bits
       rather than erroring, since ck_setport() has no error return.
       70000 = 65536 + 4464, so only 4464 survives. */
    ck_setport((struct sockaddr *)&sin, 70000);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin), 4464);
}
END_TEST

START_TEST(test_port_null)
{
    ck_assert_uint_eq(ck_getport(NULL), 0);
    ck_setport(NULL, 23);              /* must not crash */
}
END_TEST

#ifdef CK_VSOCK
START_TEST(test_straddr_vsock)
{
    struct sockaddr_vm svm;
    char buf[64];

    memset(&svm, 0, sizeof(svm));
    svm.svm_family = AF_VSOCK;
    svm.svm_cid = 1;
    svm.svm_port = 9600;

    ck_assert_int_eq(
        ck_straddr((struct sockaddr *)&svm, sizeof(svm), buf, sizeof(buf)),
        0);
    ck_assert_str_eq(buf, "1:9600");
}
END_TEST

START_TEST(test_straddr_vsock_buffer_too_small)
{
    struct sockaddr_vm svm;
    char buf[4];                       /* not enough room for "1:9600" */

    memset(&svm, 0, sizeof(svm));
    svm.svm_family = AF_VSOCK;
    svm.svm_cid = 1;
    svm.svm_port = 9600;

    ck_assert_int_eq(
        ck_straddr((struct sockaddr *)&svm, sizeof(svm), buf, sizeof(buf)),
        -1);
}
END_TEST

START_TEST(test_port_vsock)
{
    struct sockaddr_vm svm;

    memset(&svm, 0, sizeof(svm));
    svm.svm_family = AF_VSOCK;
    svm.svm_port = 9600;

    /* Unlike TCP/IPv6, VSOCK ports are not byte-swapped. */
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&svm), 9600);

    /* Verify a 32-bit VSOCK port above 65535 is preserved. */
    ck_setport((struct sockaddr *)&svm, 4294967295U);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&svm), 4294967295U);
    ck_assert_uint_eq(svm.svm_port, 4294967295U);
}
END_TEST
#endif /* CK_VSOCK */

#ifdef CK_IPV6
START_TEST(test_straddr_v6)
{
    struct sockaddr_in6 sin6;
    char buf[64];

    memset(&sin6, 0, sizeof(sin6));
    sin6.sin6_family = AF_INET6;
    ck_assert_int_eq(inet_pton(AF_INET6, "2001:db8::1", &sin6.sin6_addr), 1);
    sin6.sin6_port = htons(23);

    ck_assert_int_eq(
        ck_straddr((struct sockaddr *)&sin6, sizeof(sin6), buf, sizeof(buf)),
        0);
    ck_assert_str_eq(buf, "2001:db8::1");
}
END_TEST

START_TEST(test_port_v6)
{
    struct sockaddr_in6 sin6;

    memset(&sin6, 0, sizeof(sin6));
    sin6.sin6_family = AF_INET6;
    sin6.sin6_port = htons(23);

    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin6), 23);

    ck_setport((struct sockaddr *)&sin6, 2000);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin6), 2000);
    ck_assert_uint_eq(ntohs(sin6.sin6_port), 2000);
}
END_TEST

START_TEST(test_port_v6_overflow)
{
    struct sockaddr_in6 sin6;

    memset(&sin6, 0, sizeof(sin6));
    sin6.sin6_family = AF_INET6;

    /* sin6_port is 16 bits, same as sin_port; see test_port_v4_overflow. */
    ck_setport((struct sockaddr *)&sin6, 65535);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin6), 65535);

    ck_setport((struct sockaddr *)&sin6, 70000);
    ck_assert_uint_eq(ck_getport((struct sockaddr *)&sin6), 4464);
}
END_TEST

/*
  ck_scopeaddr6() tests need one interface name guaranteed to exist
  and resolve on the test target. The loopback interface is always
  present, but its name isn't portable: Linux calls it "lo", BSD and
  macOS call it "lo0". test_loopback_ifname() finds whichever one
  actually resolves via if_nametoindex(), so the tests below build
  their zone-qualified literals from that name instead of a literal
  "lo".
*/
static const char *
test_loopback_ifname(void)
{
    static char name[IFNAMSIZ];
    static int done = 0;

    if (!done) {
        if (if_nametoindex("lo0") != 0)
          strncpy(name, "lo0", sizeof(name) - 1);
        else if (if_nametoindex("lo") != 0)
          strncpy(name, "lo", sizeof(name) - 1);
        done = 1;
    }
    return name;
}

START_TEST(test_scopeaddr6_no_zone)
{
    struct in6_addr addr, expect;
    unsigned int scope = 999;           /* poison, must come back 0 */

    ck_assert_int_eq(inet_pton(AF_INET6, "2001:db8::1", &expect), 1);
    ck_assert_int_eq(ck_scopeaddr6("2001:db8::1", &addr, &scope), 1);
    ck_assert_int_eq(memcmp(&addr, &expect, sizeof(addr)), 0);
    ck_assert_uint_eq(scope, 0);
}
END_TEST

START_TEST(test_scopeaddr6_named_zone)
{
    struct in6_addr addr;
    unsigned int scope = 0;
    const char *ifname = test_loopback_ifname();
    unsigned int idx = if_nametoindex(ifname);
    char in[64];

    ck_assert_uint_ne(idx, 0);   /* loopback must exist to test this */
    snprintf(in, sizeof(in), "fe80::1%%%s", ifname);
    ck_assert_int_eq(ck_scopeaddr6(in, &addr, &scope), 1);
    ck_assert_uint_eq(scope, idx);
}
END_TEST

START_TEST(test_scopeaddr6_numeric_zone)
{
    struct in6_addr addr;
    unsigned int scope = 0;
    unsigned int idx = if_nametoindex(test_loopback_ifname());
    char in[64];

    ck_assert_uint_ne(idx, 0);
    snprintf(in, sizeof(in), "fe80::1%%%u", idx);
    ck_assert_int_eq(ck_scopeaddr6(in, &addr, &scope), 1);
    ck_assert_uint_eq(scope, idx);
}
END_TEST

START_TEST(test_scopeaddr6_bad_address)
{
    struct in6_addr addr;
    unsigned int scope = 0;

    ck_assert_int_eq(ck_scopeaddr6("not-an-address", &addr, &scope), 0);
    ck_assert_int_eq(ck_scopeaddr6("not-an-address%lo", &addr, &scope), 0);
}
END_TEST

START_TEST(test_scopeaddr6_nonexistent_named_zone)
{
    struct in6_addr addr;
    unsigned int scope = 0;

    ck_assert_int_eq(
        ck_scopeaddr6("fe80::1%zzz_bogus_iface_9999", &addr, &scope), 0);
}
END_TEST

START_TEST(test_scopeaddr6_nonexistent_numeric_zone)
{
    struct in6_addr addr;
    unsigned int scope = 0;

    /* Numeric index does not match any active interface. */
    ck_assert_int_eq(ck_scopeaddr6("fe80::1%4000000000", &addr, &scope), 0);
}
END_TEST

START_TEST(test_scopeaddr6_bare_trailing_percent)
{
    struct in6_addr addr;
    unsigned int scope = 0;

    /* Trailing percent symbol without zone name is invalid. */
    ck_assert_int_eq(ck_scopeaddr6("fe80::1%", &addr, &scope), 0);
}
END_TEST

START_TEST(test_scopeaddr6_numeric_zone_overflow)
{
    struct in6_addr addr;
    unsigned int scope = 0;

    /* Exceeding UINT_MAX numeric scope ID must fail. */
    ck_assert_int_eq(
        ck_scopeaddr6("fe80::1%999999999999999", &addr, &scope), 0);
}
END_TEST

/*
  Test parsing of max-length (45 character) IPv6 literal. Verify exact
  parsed byte match to detect truncation.
*/
START_TEST(test_scopeaddr6_max_length_address)
{
    static const char * a45 =
        "0000:0000:0000:0000:0000:ffff:255.255.255.255";
    struct in6_addr addr, expect;
    unsigned int scope = 0;
    const char *ifname = test_loopback_ifname();
    unsigned int idx = if_nametoindex(ifname);
    char in[80];

    ck_assert_uint_eq(strlen(a45), (size_t)(INET6_ADDRSTRLEN - 1));
    ck_assert_uint_ne(idx, 0);
    ck_assert_int_eq(inet_pton(AF_INET6, a45, &expect), 1);

    snprintf(in, sizeof(in), "%s%%%s", a45, ifname);
    ck_assert_int_eq(ck_scopeaddr6(in, &addr, &scope), 1);
    ck_assert_int_eq(memcmp(&addr, &expect, sizeof(addr)), 0);
    ck_assert_uint_eq(scope, idx);
}
END_TEST

/*
  Test zone name of max length (15 characters) that is not an active
  interface.
*/
START_TEST(test_scopeaddr6_max_length_zone_not_truncated)
{
    struct in6_addr addr;
    unsigned int scope = 0;
    static const char * zone15 = "loXXXXXXXXXXXXX"; /* "lo" + 13 chars */

    ck_assert_uint_eq(strlen(zone15), (size_t)(IFNAMSIZ - 1));
    ck_assert_int_eq(ck_scopeaddr6("fe80::1%loXXXXXXXXXXXXX", &addr, &scope),
                      0);
}
END_TEST

START_TEST(test_scopeaddr6_address_too_long)
{
    struct in6_addr addr;
    unsigned int scope = 0;
    /* Address exceeding INET6_ADDRSTRLEN-1 must be rejected. */
    static char a46[] =
        "0000:0000:0000:0000:0000:ffff:255.255.255.2550";
    /* Oversized buffer must be rejected. */
    char huge[500];

    ck_assert_uint_eq(strlen(a46), (size_t)INET6_ADDRSTRLEN);
    ck_assert_int_eq(ck_scopeaddr6(a46, &addr, &scope), 0);

    memset(huge, 'f', sizeof(huge) - 1);
    huge[sizeof(huge) - 1] = '\0';
    ck_assert_int_eq(ck_scopeaddr6(huge, &addr, &scope), 0);
}
END_TEST

START_TEST(test_scopeaddr6_zone_too_long)
{
    struct in6_addr addr;
    unsigned int scope = 0;
    /* Zone name exceeding IFNAMSIZ-1 must be rejected. */
    static char in16[] = "fe80::1%loXXXXXXXXXXXXXX"; /* 16-char zone */

    ck_assert_int_eq(ck_scopeaddr6(in16, &addr, &scope), 0);
}
END_TEST

START_TEST(test_scopeaddr6_bad_args)
{
    struct in6_addr addr;
    unsigned int scope = 0;

    ck_assert_int_eq(ck_scopeaddr6(NULL, &addr, &scope), 0);
    ck_assert_int_eq(ck_scopeaddr6("fe80::1", NULL, &scope), 0);
    ck_assert_int_eq(ck_scopeaddr6("fe80::1", &addr, NULL), 0);
}
END_TEST
#endif /* CK_IPV6 */

START_TEST(test_splithostport_plain_host)
{
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("example.com", host, sizeof(host),
                          port, sizeof(port)),
        0);
    ck_assert_str_eq(host, "example.com");
    ck_assert_str_eq(port, "");
}
END_TEST

START_TEST(test_splithostport_host_port)
{
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("example.com:23", host, sizeof(host),
                          port, sizeof(port)),
        1);
    ck_assert_str_eq(host, "example.com");
    ck_assert_str_eq(port, "23");
}
END_TEST

START_TEST(test_splithostport_bare_v6_literal_no_brackets)
{
    /* Zero brackets, two colons must be a bare IPv6 literal, not
       "host:port".  A real IPv6 address always has at least two
       colons, and the plain host:port syntax never allowed more than
       one, so this can't be anything else. */
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("::1", host, sizeof(host), port, sizeof(port)),
        0);
    ck_assert_str_eq(host, "::1");
    ck_assert_str_eq(port, "");
}
END_TEST

START_TEST(test_splithostport_bare_v6_literal_full_form)
{
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("2001:db8::1", host, sizeof(host),
                          port, sizeof(port)),
        0);
    ck_assert_str_eq(host, "2001:db8::1");
    ck_assert_str_eq(port, "");
}
END_TEST

START_TEST(test_splithostport_bracket_no_port)
{
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("[::1]", host, sizeof(host), port, sizeof(port)),
        0);
    ck_assert_str_eq(host, "::1");
    ck_assert_str_eq(port, "");
}
END_TEST

START_TEST(test_splithostport_bracket_with_port)
{
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("[::1]:23", host, sizeof(host), port, sizeof(port)),
        1);
    ck_assert_str_eq(host, "::1");
    ck_assert_str_eq(port, "23");
}
END_TEST

START_TEST(test_splithostport_bracket_v6_literal_with_port)
{
    char host[64], port[64];

    ck_assert_int_eq(
        ck_splithostport("[2001:db8::1]:23", host, sizeof(host),
                          port, sizeof(port)),
        1);
    ck_assert_str_eq(host, "2001:db8::1");
    ck_assert_str_eq(port, "23");
}
END_TEST

START_TEST(test_splithostport_unterminated_bracket)
{
    char host[64], port[64];

    /* Must fail safely (-1), not crash, and must not leave stale data
       in the output buffers. */
    ck_assert_int_eq(
        ck_splithostport("[::1", host, sizeof(host), port, sizeof(port)),
        -1);
    ck_assert_str_eq(host, "");
    ck_assert_str_eq(port, "");
}
END_TEST

START_TEST(test_splithostport_bad_args)
{
    char host[64];

    ck_assert_int_eq(ck_splithostport(NULL, host, sizeof(host), NULL, 0), -1);
    ck_assert_int_eq(ck_splithostport("example.com", NULL, 0, NULL, 0), -1);
}
END_TEST

/*
  Test bracketaddr formatting for IPv6 addresses.
*/
START_TEST(test_bracketaddr_plain_host)
{
    char buf[64] = "example.com";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"example.com");
}
END_TEST

START_TEST(test_bracketaddr_ipv4)
{
    char buf[64] = "192.0.2.1";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"192.0.2.1");
}
END_TEST

START_TEST(test_bracketaddr_one_colon_untouched)
{
    /* Single colon is not an IPv6 literal; leave untouched. */
    char buf[64] = "example.com:23";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"example.com:23");
}
END_TEST

START_TEST(test_bracketaddr_bare_v6)
{
    char buf[64] = "::1";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"[::1]");
}
END_TEST

START_TEST(test_bracketaddr_bare_v6_with_zone)
{
    char buf[64] = "fe80::1%eth0";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"[fe80::1%eth0]");
}
END_TEST

START_TEST(test_bracketaddr_already_bracketed_untouched)
{
    char buf[64] = "[::1]";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"[::1]");
}
END_TEST

START_TEST(test_bracketaddr_too_long_untouched)
{
    /* Insufficient space for bracket characters; leave untouched. */
    char buf[5] = "::1";
    ck_bracketaddr(buf,sizeof(buf));
    ck_assert_str_eq(buf,"::1");
}
END_TEST

START_TEST(test_bracketaddr_bad_args)
{
    char buf[64] = "::1";
    ck_bracketaddr(NULL,sizeof(buf));
    ck_bracketaddr(buf,0);
    ck_assert_str_eq(buf,"::1");
}
END_TEST

#ifdef CK_VSOCK
START_TEST(test_vsock_addr_numeric)
{
    unsigned int cid = 999, port = 999;

    ck_assert_int_eq(ck_parse_vsock_addr("1:9600", &cid, &port), 0);
    ck_assert_uint_eq(cid, 1);
    ck_assert_uint_eq(port, 9600);
}
END_TEST

START_TEST(test_vsock_addr_symbolic_cid)
{
    unsigned int cid, port;

    ck_assert_int_eq(ck_parse_vsock_addr("local:9600", &cid, &port), 0);
    ck_assert_uint_eq(cid, VMADDR_CID_LOCAL);
    ck_assert_uint_eq(port, 9600);

    ck_assert_int_eq(ck_parse_vsock_addr("HOST:1649", &cid, &port), 0);
    ck_assert_uint_eq(cid, VMADDR_CID_HOST);
    ck_assert_uint_eq(port, 1649);

    ck_assert_int_eq(ck_parse_vsock_addr("Hypervisor:1", &cid, &port), 0);
    ck_assert_uint_eq(cid, VMADDR_CID_HYPERVISOR);
    ck_assert_uint_eq(port, 1);

    ck_assert_int_eq(ck_parse_vsock_addr("any:1", &cid, &port), 0);
    ck_assert_uint_eq(cid, (unsigned int)VMADDR_CID_ANY);
    ck_assert_uint_eq(port, 1);
}
END_TEST

START_TEST(test_vsock_addr_extreme_values)
{
    unsigned int cid, port;

    ck_assert_int_eq(ck_parse_vsock_addr("0:0", &cid, &port), 0);
    ck_assert_uint_eq(cid, 0);
    ck_assert_uint_eq(port, 0);

    ck_assert_int_eq(
        ck_parse_vsock_addr("4294967295:4294967295", &cid, &port), 0);
    ck_assert_uint_eq(cid, 4294967295U);
    ck_assert_uint_eq(port, 4294967295U);
}
END_TEST

START_TEST(test_vsock_addr_overflow)
{
    unsigned int cid, port;

    /* One past UINT_MAX must be rejected, not silently wrap. */
    ck_assert_int_eq(
        ck_parse_vsock_addr("4294967296:1", &cid, &port), -1);
    ck_assert_int_eq(
        ck_parse_vsock_addr("1:4294967296", &cid, &port), -1);
}
END_TEST

START_TEST(test_vsock_addr_missing_colon)
{
    unsigned int cid, port;

    ck_assert_int_eq(ck_parse_vsock_addr("1", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("", &cid, &port), -1);
}
END_TEST

START_TEST(test_vsock_addr_extra_colon)
{
    unsigned int cid, port;

    ck_assert_int_eq(ck_parse_vsock_addr("1:9600:1", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1:2:3:4", &cid, &port), -1);
}
END_TEST

START_TEST(test_vsock_addr_empty_field)
{
    unsigned int cid, port;

    ck_assert_int_eq(ck_parse_vsock_addr(":9600", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1:", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr(":", &cid, &port), -1);
}
END_TEST

START_TEST(test_vsock_addr_non_numeric)
{
    unsigned int cid, port;

    ck_assert_int_eq(ck_parse_vsock_addr("abc:9600", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1:abc", &cid, &port), -1);
    /* Not a recognized symbolic name, and not numeric either. */
    ck_assert_int_eq(ck_parse_vsock_addr("bogus:9600", &cid, &port), -1);
    /* Leading/trailing junk on an otherwise-numeric field. */
    ck_assert_int_eq(ck_parse_vsock_addr("1x:9600", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1:9600x", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("-1:9600", &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1: 9600", &cid, &port), -1);
}
END_TEST

START_TEST(test_vsock_addr_bad_args)
{
    unsigned int cid = 111, port = 222;

    ck_assert_int_eq(ck_parse_vsock_addr(NULL, &cid, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1:9600", NULL, &port), -1);
    ck_assert_int_eq(ck_parse_vsock_addr("1:9600", &cid, NULL), -1);
    /* Failure must not touch the output arguments. */
    ck_assert_uint_eq(cid, 111);
    ck_assert_uint_eq(port, 222);
}
END_TEST
#endif /* CK_VSOCK */

/*
  ckgetfqhostname() does forward-then-reverse DNS resolution, so this
  relies on loopback names being set up the ordinary way (::1 and
  127.0.0.1 both reverse-resolving to "localhost", via /etc/hosts on
  any normal POSIX system) rather than on a specific DNS server.
*/
START_TEST(test_getfqhostname_v4_literal)
{
    ck_assert_str_eq(ckgetfqhostname("127.0.0.1"), "localhost");
}
END_TEST

#ifdef CK_IPV6
START_TEST(test_getfqhostname_v6_literal)
{
    ck_assert_str_eq(ckgetfqhostname("::1"), "localhost");
}
END_TEST

/*
  Before the fix accompanying this test, ckgetfqhostname() only
  recognized a *bare* IPv6 literal (inet_pton() directly on the
  whole string); it never tried ck_splithostport(), so a bracketed
  literal like "[::1]" fell through to the legacy "find the first
  colon" rule, which finds the colon *inside* the brackets and
  truncates the hostname to "[".  Forward resolution then fails
  silently and the function returns its input essentially unchanged
  ("[::1]", not "localhost").
*/
START_TEST(test_getfqhostname_v6_bracketed_no_port)
{
    ck_assert_str_eq(ckgetfqhostname("[::1]"), "localhost");
}
END_TEST

START_TEST(test_getfqhostname_v6_bracketed_with_port)
{
    ck_assert_str_eq(ckgetfqhostname("[::1]:23"), "localhost:23");
}
END_TEST

START_TEST(test_getfqhostname_v6_unterminated_bracket_safe)
{
    /* Must fail safely (return the input essentially unchanged), not
       crash, on malformed bracket syntax. */
    ck_assert_str_eq(ckgetfqhostname("[::1"), "[::1");
}
END_TEST
#endif /* CK_IPV6 */

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s = suite_create("Kermit Network Address Helper Unit Tests");
    TCase * tc = tcase_create("core");

    tcase_add_test(tc, test_straddr_v4);
    tcase_add_test(tc, test_straddr_bad_args);
    tcase_add_test(tc, test_port_v4);
    tcase_add_test(tc, test_port_v4_overflow);
    tcase_add_test(tc, test_port_null);
#ifdef CK_VSOCK
    tcase_add_test(tc, test_straddr_vsock);
    tcase_add_test(tc, test_straddr_vsock_buffer_too_small);
    tcase_add_test(tc, test_port_vsock);
#endif /* CK_VSOCK */
#ifdef CK_IPV6
    tcase_add_test(tc, test_straddr_v6);
    tcase_add_test(tc, test_port_v6);
    tcase_add_test(tc, test_port_v6_overflow);
    tcase_add_test(tc, test_scopeaddr6_no_zone);
    tcase_add_test(tc, test_scopeaddr6_named_zone);
    tcase_add_test(tc, test_scopeaddr6_numeric_zone);
    tcase_add_test(tc, test_scopeaddr6_bad_address);
    tcase_add_test(tc, test_scopeaddr6_nonexistent_named_zone);
    tcase_add_test(tc, test_scopeaddr6_nonexistent_numeric_zone);
    tcase_add_test(tc, test_scopeaddr6_bare_trailing_percent);
    tcase_add_test(tc, test_scopeaddr6_numeric_zone_overflow);
    tcase_add_test(tc, test_scopeaddr6_max_length_address);
    tcase_add_test(tc, test_scopeaddr6_max_length_zone_not_truncated);
    tcase_add_test(tc, test_scopeaddr6_address_too_long);
    tcase_add_test(tc, test_scopeaddr6_zone_too_long);
    tcase_add_test(tc, test_scopeaddr6_bad_args);
#endif /* CK_IPV6 */
    tcase_add_test(tc, test_splithostport_plain_host);
    tcase_add_test(tc, test_splithostport_host_port);
    tcase_add_test(tc, test_splithostport_bare_v6_literal_no_brackets);
    tcase_add_test(tc, test_splithostport_bare_v6_literal_full_form);
    tcase_add_test(tc, test_splithostport_bracket_no_port);
    tcase_add_test(tc, test_splithostport_bracket_with_port);
    tcase_add_test(tc, test_splithostport_bracket_v6_literal_with_port);
    tcase_add_test(tc, test_splithostport_unterminated_bracket);
    tcase_add_test(tc, test_splithostport_bad_args);
    tcase_add_test(tc, test_bracketaddr_plain_host);
    tcase_add_test(tc, test_bracketaddr_ipv4);
    tcase_add_test(tc, test_bracketaddr_one_colon_untouched);
    tcase_add_test(tc, test_bracketaddr_bare_v6);
    tcase_add_test(tc, test_bracketaddr_bare_v6_with_zone);
    tcase_add_test(tc, test_bracketaddr_already_bracketed_untouched);
    tcase_add_test(tc, test_bracketaddr_too_long_untouched);
    tcase_add_test(tc, test_bracketaddr_bad_args);
#ifdef CK_VSOCK
    tcase_add_test(tc, test_vsock_addr_numeric);
    tcase_add_test(tc, test_vsock_addr_symbolic_cid);
    tcase_add_test(tc, test_vsock_addr_extreme_values);
    tcase_add_test(tc, test_vsock_addr_overflow);
    tcase_add_test(tc, test_vsock_addr_missing_colon);
    tcase_add_test(tc, test_vsock_addr_extra_colon);
    tcase_add_test(tc, test_vsock_addr_empty_field);
    tcase_add_test(tc, test_vsock_addr_non_numeric);
    tcase_add_test(tc, test_vsock_addr_bad_args);
#endif /* CK_VSOCK */
    tcase_add_test(tc, test_getfqhostname_v4_literal);
#ifdef CK_IPV6
    tcase_add_test(tc, test_getfqhostname_v6_literal);
    tcase_add_test(tc, test_getfqhostname_v6_bracketed_no_port);
    tcase_add_test(tc, test_getfqhostname_v6_bracketed_with_port);
    tcase_add_test(tc, test_getfqhostname_v6_unterminated_bracket_safe);
#endif /* CK_IPV6 */
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
