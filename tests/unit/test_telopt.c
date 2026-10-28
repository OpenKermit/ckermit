/*
  Unit tests for telopt_index(), telopt_ok() and telopt() in ckctel.c.
  These functions replace the TELOPT_INDEX(), TELOPT_OK() and TELOPT()
  macros in builds with NOTOMACROS.  The makefile compiles ckctel.c with
  -DNOTOMACROS for this test.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#define NOTOMACROS
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcker.h"
#include "ckcnet.h"
#include "ckctel.h"

/* Each option and the name that telopts[] holds for it. */
static struct {
    int opt;
    char * name;
} options[] = {
    { TELOPT_BINARY, "BINARY" },
    { TELOPT_STDERR, "stderr" },
    { TELOPT_PRAGMA_LOGON, "pragma-logon" },
    { TELOPT_SSPI_LOGON, "sspi-logon" },
    { TELOPT_PRAGMA_HEARTBEAT, "pragma-heartbeat" },
    { TELOPT_IBM_SAK, "ibm-sak" }
};

START_TEST(test_index_distinct)
{
    int i, j;
    int n = sizeof(options) / sizeof(options[0]);

    for (i = 0; i < n; i++) {
        int x = telopt_index(options[i].opt);
        ck_assert_int_ge(x, 0);
        ck_assert_int_lt(x, NTELOPTS);
        for (j = 0; j < i; j++)
          ck_assert_int_ne(x, telopt_index(options[j].opt));
    }
}
END_TEST

START_TEST(test_names)
{
    int i;
    int n = sizeof(options) / sizeof(options[0]);

    for (i = 0; i < n; i++) {
        ck_assert(telopt_ok(options[i].opt));
        ck_assert_str_eq(telopt(options[i].opt), options[i].name);
    }
}
END_TEST

START_TEST(test_unknown)
{
    ck_assert(!telopt_ok(TELOPT_STDERR + 1));
    ck_assert(!telopt_ok(TELOPT_IBM_SAK + 1));
    ck_assert_int_eq(telopt_index(TELOPT_STDERR + 1), NTELOPTS);
    ck_assert_int_eq(telopt_index(255), NTELOPTS);
}
END_TEST

static Suite *
telopt_suite(void)
{
    Suite * s = suite_create("telopt");
    TCase * tc = tcase_create("core");
    tcase_add_test(tc, test_index_distinct);
    tcase_add_test(tc, test_names);
    tcase_add_test(tc, test_unknown);
    suite_add_tcase(s, tc);
    return s;
}

int
main(int argc, char ** argv)
{
    int failed;
    SRunner * sr = srunner_create(telopt_suite());
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (failed == 0) ? 0 : 1;
}
