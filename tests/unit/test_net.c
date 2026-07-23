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

START_TEST(test_port_null)
{
    ck_assert_uint_eq(ck_getport(NULL), 0);
    ck_setport(NULL, 23);              /* must not crash */
}
END_TEST

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
    tcase_add_test(tc, test_port_null);
#ifdef CK_IPV6
    tcase_add_test(tc, test_straddr_v6);
    tcase_add_test(tc, test_port_v6);
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
