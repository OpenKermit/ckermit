/*
  Unit test for ck_hostaddr() in ckcnet.c.

  ck_copyhostent() allocates h_addr_list entries with h_length bytes
  (4 for AF_INET).

  This test uses an oversized source buffer filled with a sentinel
  pattern past the 4-byte address. If ck_hostaddr() reads past 4
  bytes, sentinel bytes leak into the return value and the test fails.
*/
#include <check.h>
#include <netdb.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcnet.h"
#include "ck_ssl.h"

/* ck_copyhostent() calls debug(), which requires these stubs. */
int deblog = 0;
int fp_digits = 6;
int matchdot = 0;
int dodebug(int a, const char *b, const char *c, CK_OFF_T d) {
    return 0;
}

START_TEST(test_ck_hostaddr_no_overread)
{
    struct hostent host;
    char * addr_list[2];
    unsigned char real_bytes[4] = { 10, 20, 30, 40 };
    /* Storage is wider than unsigned long so an overread reaches
       into the sentinel bytes. */
    unsigned char storage[16];
    unsigned long expected = 0L;
    unsigned long result;

    memset(storage, 0xAA, sizeof(storage));    /* Sentinel fill. */
    memcpy(storage, real_bytes, sizeof(real_bytes));

    memset(&host, 0, sizeof(host));
    host.h_addrtype = AF_INET;
    host.h_length = (short) sizeof(real_bytes);
    addr_list[0] = (char *) storage;
    addr_list[1] = NULL;
    host.h_addr_list = addr_list;

    /* Expected result matches the 4-byte address without assuming
       host byte order. */
    memcpy(&expected, real_bytes, sizeof(real_bytes));

    result = ck_hostaddr(&host, 0);

    ck_assert_msg(result == expected,
                  "ck_hostaddr() returned 0x%lx, expected 0x%lx: "
                  "sentinel bytes may have leaked into the result",
                  result, expected);
}
END_TEST

Suite *hostaddr_suite(void)
{
    Suite *s;
    TCase *tc_core;

    s = suite_create("Kermit ck_hostaddr() Unit Tests");
    tc_core = tcase_create("Core");

    tcase_add_test(tc_core, test_ck_hostaddr_no_overread);

    suite_add_tcase(s, tc_core);
    return s;
}

/* ckcfnp.h prototypes main with (int, char **). */
int
main(int argc, char ** argv)
{
    int number_failed;
    Suite *s;
    SRunner *sr;

    s = hostaddr_suite();
    sr = srunner_create(s);

    srunner_run_all(sr, CK_NORMAL);
    number_failed = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (number_failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
