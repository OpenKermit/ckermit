#include <check.h>
#include <stdlib.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckclib.h"

int deblog = 0;
int fp_digits = 6;
int matchdot = 0;
int dodebug(int a, char *b, char *c, CK_OFF_T d) {
    return 0;
}

START_TEST(test_ckstrncpy)
{
    char dest[20];
    int r;

    // Normal copy
    r = ckstrncpy(dest, "hello", sizeof(dest));
    ck_assert_int_eq(r, 5);
    ck_assert_str_eq(dest, "hello");

    // Truncated copy
    r = ckstrncpy(dest, "hello world", 6);
    ck_assert_int_eq(r, 5);
    ck_assert_str_eq(dest, "hello");

    // Length <= 0
    dest[0] = 'X';
    r = ckstrncpy(dest, "hello", 0);
    ck_assert_int_eq(r, 0);
    ck_assert_str_eq(dest, "");

    // NULL inputs
    r = ckstrncpy(NULL, "hello", 5);
    ck_assert_int_eq(r, 0);

    r = ckstrncpy(dest, NULL, 5);
    ck_assert_int_eq(r, 0);
    ck_assert_str_eq(dest, "");
}
END_TEST

START_TEST(test_ckstrncat)
{
    char dest[20] = "hello";
    int r;

    // Normal concatenation
    r = ckstrncat(dest, " world", sizeof(dest));
    ck_assert_int_eq(r, 6);
    ck_assert_str_eq(dest, "hello world");

    // Truncated concatenation: dest is 5 chars, total size 8,
    // leaving space for 2 chars + NUL
    ckstrncpy(dest, "hello", sizeof(dest));
    r = ckstrncat(dest, " world", 8);
    ck_assert_int_eq(r, 2);
    ck_assert_str_eq(dest, "hello w");

    // NULL inputs
    r = ckstrncat(NULL, " world", sizeof(dest));
    ck_assert_int_eq(r, 0);

    r = ckstrncat(dest, NULL, sizeof(dest));
    ck_assert_int_eq(r, 0);
}
END_TEST

START_TEST(test_cklower_ckupper)
{
    char str1[] = "Hello World 123!";
    char str2[] = "Hello World 123!";

    cklower(str1);
    ck_assert_str_eq(str1, "hello world 123!");

    ckupper(str2);
    ck_assert_str_eq(str2, "HELLO WORLD 123!");
}
END_TEST

START_TEST(test_chartostr)
{
    ck_assert_str_eq(chartostr(0), "NUL");
    ck_assert_str_eq(chartostr(127), "DEL");
    ck_assert_str_eq(chartostr('A'), "A");
}
END_TEST

START_TEST(test_ckstrcmp)
{
    // Case-sensitive (c != 0)
    ck_assert(ckstrcmp("abc", "abc", -1, 1) == 0);
    ck_assert(ckstrcmp("abc", "abd", -1, 1) < 0);
    ck_assert(ckstrcmp("abd", "abc", -1, 1) > 0);
    ck_assert(ckstrcmp("abc", "ABC", -1, 1) != 0);

    // Case-insensitive (c == 0)
    ck_assert(ckstrcmp("abc", "ABC", -1, 0) == 0);
    ck_assert(ckstrcmp("abc", "AbC", -1, 0) == 0);

    // Length limit (n)
    ck_assert(ckstrcmp("abc", "abd", 2, 1) == 0);
    ck_assert(ckstrcmp("abc", "abd", 3, 1) < 0);

    // NULL pointers are treated as ""
    ck_assert(ckstrcmp(NULL, NULL, -1, 1) == 0);
    ck_assert(ckstrcmp(NULL, "abc", -1, 1) < 0);
    ck_assert(ckstrcmp("abc", NULL, -1, 1) > 0);
}
END_TEST

START_TEST(test_cksplit)
{
    struct stringarray *q;

    // Split basic string with space separator
    q = cksplit(1, 0, "hello world", " ", "ALL", 0, 0, 0, 0);
    ck_assert_int_eq(q->a_size, 2);
    ck_assert_str_eq(q->a_head[1], "hello");
    ck_assert_str_eq(q->a_head[2], "world");

    // Test collapse vs no collapse adjacent separators (n4)
    // Collapse: "hello  world" -> 2 elements
    q = cksplit(1, 0, "hello  world", " ", "ALL", 0, 0, 0, 0);
    ck_assert_int_eq(q->a_size, 2);

    // No collapse (n4 = 1): 3 elements returned, middle is empty
    q = cksplit(1, 0, "hello  world", " ", "ALL", 0, 0, 1, 0);
    ck_assert_int_eq(q->a_size, 3);
    ck_assert_str_eq(q->a_head[1], "hello");
    ck_assert_str_eq(q->a_head[2], "");
    ck_assert_str_eq(q->a_head[3], "world");

    // Test get single word (fc = 0)
    // Get 1st word
    q = cksplit(0, 1, "hello world", " ", "ALL", 0, 0, 0, 0);
    ck_assert_int_eq(q->a_size, 1);
    ck_assert_str_eq(q->a_head[1], "hello");

    // Get 2nd word
    q = cksplit(0, 2, "hello world", " ", "ALL", 0, 0, 0, 0);
    ck_assert_int_eq(q->a_size, 1);
    ck_assert_str_eq(q->a_head[1], "world");
}
END_TEST

START_TEST(test_dquote)
{
    char buf[30];
    int r;

    // Spaces present, enough buffer: should quote with double quotes
    ckstrncpy(buf, "hello world", sizeof(buf));
    r = dquote(buf, sizeof(buf), 0);
    ck_assert_int_eq(r, 13);
    ck_assert_str_eq(buf, "\"hello world\"");

    // Spaces present, enough buffer, flag=1: should quote with braces
    ckstrncpy(buf, "hello world", sizeof(buf));
    r = dquote(buf, sizeof(buf), 1);
    ck_assert_int_eq(r, 13);
    ck_assert_str_eq(buf, "{hello world}");

    // Spaces present, NOT enough buffer (len <= k + 2)
    // "hello world" has length 11, k+2 = 13.
    // If len = 12: should not quote and return k = 11.
    ckstrncpy(buf, "hello world", sizeof(buf));
    r = dquote(buf, 12, 0);
    ck_assert_int_eq(r, 11);
    ck_assert_str_eq(buf, "hello world");

    // No spaces: should not quote, but returns k+2 = 7
    ckstrncpy(buf, "hello", sizeof(buf));
    r = dquote(buf, sizeof(buf), 0);
    ck_assert_int_eq(r, 7);
    ck_assert_str_eq(buf, "hello");

    // NULL input
    r = dquote(NULL, 10, 0);
    ck_assert_int_eq(r, 0);
}
END_TEST

START_TEST(test_untabify)
{
    char dest[100];
    int r;

    // Basic string without tabs
    r = untabify("hello", dest, sizeof(dest));
    ck_assert_int_eq(r, 0);
    ck_assert_str_eq(dest, "hello");

    // Tab at start
    r = untabify("\tworld", dest, sizeof(dest));
    ck_assert_int_eq(r, 0);
    ck_assert_str_eq(dest, "        world"); // 8 spaces + "world"

    // Tab in middle
    r = untabify("a\tb", dest, sizeof(dest));
    ck_assert_int_eq(r, 0);
    ck_assert_str_eq(dest, "a       b"); // "a" + 7 spaces + "b"

    // String exceeding max limit (causes truncation)
    r = untabify("hello", dest, 5);
    ck_assert_int_eq(r, -1);
    ck_assert_str_eq(dest, "hell");
}
END_TEST

START_TEST(test_ckoptsubst)
{
    char buf[20];
    char opts[40];
    int r;

    // %s placeholder: value substituted in place
    ckstrncpy(opts, "-e %s", sizeof(opts));
    r = ckoptsubst(opts, "file.txt", buf, sizeof(buf));
    ck_assert_int_eq(r, 1);
    ck_assert_str_eq(buf, "-e file.txt");

    // %s in the middle, with a trailing suffix preserved
    ckstrncpy(opts, "-e %s --readonly", sizeof(opts));
    r = ckoptsubst(opts, "f", buf, sizeof(buf));
    ck_assert_int_eq(r, 1);
    ck_assert_str_eq(buf, "-e f --readonly");

    // No %s placeholder: value appended after a space
    ckstrncpy(opts, "-e", sizeof(opts));
    r = ckoptsubst(opts, "file.txt", buf, sizeof(buf));
    ck_assert_int_eq(r, 1);
    ck_assert_str_eq(buf, "-e file.txt");

    // Empty opts: value appended after a leading space
    ckstrncpy(opts, "", sizeof(opts));
    r = ckoptsubst(opts, "file.txt", buf, sizeof(buf));
    ck_assert_int_eq(r, 1);
    ck_assert_str_eq(buf, " file.txt");

    // Value itself contains %n / %s: must NOT be interpreted as a
    // format string -- this is the vulnerability being regression
    // tested.  It should be copied verbatim.
    ckstrncpy(opts, "-e %s", sizeof(opts));
    r = ckoptsubst(opts, "%n%s%x", buf, sizeof(buf));
    ck_assert_int_eq(r, 1);
    ck_assert_str_eq(buf, "-e %n%s%x");

    // opts containing stray %n must not be interpreted either --
    // it should pass through literally in the non-%s portions.
    ckstrncpy(opts, "%n-%s", sizeof(opts));
    r = ckoptsubst(opts, "f", buf, sizeof(buf));
    ck_assert_int_eq(r, 1);
    ck_assert_str_eq(buf, "%n-f");

    // Combined length too long for buf: buf must be left untouched,
    // and opts must not be corrupted by the failed attempt.
    ckstrncpy(buf, "UNTOUCHED", sizeof(buf));
    ckstrncpy(opts, "this-is-a-long-option %s", sizeof(opts));
    r = ckoptsubst(opts, "also-a-fairly-long-value", buf, sizeof(buf));
    ck_assert_int_eq(r, 0);
    ck_assert_str_eq(buf, "UNTOUCHED");
    ck_assert_str_eq(opts, "this-is-a-long-option %s");
}
END_TEST

Suite *strings_suite(void)
{
    Suite *s;
    TCase *tc_core;

    s = suite_create("Kermit Strings Unit Tests");
    tc_core = tcase_create("Core");

    tcase_add_test(tc_core, test_ckstrncpy);
    tcase_add_test(tc_core, test_ckstrncat);
    tcase_add_test(tc_core, test_cklower_ckupper);
    tcase_add_test(tc_core, test_chartostr);
    tcase_add_test(tc_core, test_ckstrcmp);
    tcase_add_test(tc_core, test_cksplit);
    tcase_add_test(tc_core, test_dquote);
    tcase_add_test(tc_core, test_untabify);
    tcase_add_test(tc_core, test_ckoptsubst);

    suite_add_tcase(s, tc_core);
    return s;
}

int main(void)
{
    int number_failed;
    Suite *s;
    SRunner *sr;

    s = strings_suite();
    sr = srunner_create(s);

    srunner_run_all(sr, CK_NORMAL);
    number_failed = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (number_failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
