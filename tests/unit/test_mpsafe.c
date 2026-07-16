/*
  Unit tests for mpsafe() in ckcpro.c/ckcpro.w, the character-allowlist
  gate that rcv_firstdata() applies to the remote-supplied MAIL
  address / PRINT options text (and the MAIL subject) before it is
  placed on a popen()/sh -c command line.  See doc/mailprint.md.
*/
#include <check.h>
#include <string.h>
#define CK_ANSIC
#include "ckcsym.h"
#include "ckcdeb.h"
#include "ckcfnp.h"

/*
  debug() stub, needed for the same reason as the identical stubs in
  test_lib.c/test_strings.c/test_net.c: mpsafe() itself doesn't call
  debug(), but linking pulls in enough of ckcpro.o's other symbols
  (before --gc-sections prunes them) that the linker still wants it
  resolved.
*/
int deblog = 0;
int fp_digits = 6;
int matchdot = 0;
int dodebug(int a, char *b, char *c, CK_OFF_T d) {
    return 0;
}

/* Plain, ordinary input, both roles */

START_TEST(test_plain_address)
{
    ck_assert_int_eq(mpsafe("user@example.com", 1), 1);
}
END_TEST

START_TEST(test_plain_options)
{
    ck_assert_int_eq(mpsafe("landscape", 0), 1);
}
END_TEST

START_TEST(test_empty_string_is_safe)
{
    /* No characters to object to, either role. */
    ck_assert_int_eq(mpsafe("", 1), 1);
    ck_assert_int_eq(mpsafe("", 0), 1);
}
END_TEST

/* Every individually-allowed punctuation character */

START_TEST(test_allowed_punctuation)
{
    ck_assert_int_eq(mpsafe("a.b_c+d@e/f:g,h%i", 0), 1);
    ck_assert_int_eq(mpsafe("a.b_c+d@e/f:g,h%i", 1), 1);
}
END_TEST

START_TEST(test_digits_and_letters)
{
    ck_assert_int_eq(mpsafe("AbC123xyz", 1), 1);
}
END_TEST

/* Non-leading '-' is fine regardless of first */

START_TEST(test_nonleading_hyphen_allowed)
{
    ck_assert_int_eq(mpsafe("first-last@my-example.com", 1), 1);
    ck_assert_int_eq(mpsafe("a-b", 1), 1);
}
END_TEST

START_TEST(test_internal_hyphen_run_allowed)
{
    /* Only the start of a word matters; a run of '-' that isn't at a
       word start is fine even with first=1. */
    ck_assert_int_eq(mpsafe("a--b", 1), 1);
}
END_TEST

/* Leading '-' rejected when first=1, at the very start of the string */

START_TEST(test_leading_hyphen_rejected)
{
    ck_assert_int_eq(mpsafe("-oQueueDirectory=X", 1), 0);
    ck_assert_int_eq(mpsafe("-", 1), 0);
}
END_TEST

START_TEST(test_leading_hyphen_allowed_when_first_zero)
{
    /* PRINT options: starting with '-' is the whole point. */
    ck_assert_int_eq(mpsafe("-oQueueDirectory=X", 0), 1);
    ck_assert_int_eq(mpsafe("-o landscape -n 2", 0), 1);
}
END_TEST

/*
  Word-boundary cases: a '-' after a space must be rejected under
  first=1 just like a '-' at s[0], since the MAIL address and PRINT
  options are placed unquoted, so the shell splits s on spaces into
  separate argv elements. Checking only s[0] would miss a flag
  smuggled in after the first word.
*/

START_TEST(test_hyphen_after_space_rejected)
{
    ck_assert_int_eq(mpsafe("user@x.com -oProxyCommand=evil", 1), 0);
}
END_TEST

START_TEST(test_hyphen_after_multiple_spaces_rejected)
{
    ck_assert_int_eq(mpsafe("user@x.com  -oProxyCommand=evil", 1), 0);
}
END_TEST

START_TEST(test_space_then_hyphen_at_very_start_rejected)
{
    ck_assert_int_eq(mpsafe(" -x", 1), 0);
}
END_TEST

START_TEST(test_multiple_addresses_no_hyphen_allowed)
{
    /* Legitimate multi-recipient MAIL address, no flags smuggled. */
    ck_assert_int_eq(mpsafe("user1@x.com user2@y.com", 1), 1);
}
END_TEST

START_TEST(test_trailing_space_allowed)
{
    ck_assert_int_eq(mpsafe("user@x.com ", 1), 1);
}
END_TEST

/* Shell metacharacters: rejected in every role, leading or not */

START_TEST(test_shell_metacharacters_rejected)
{
    static const char * bad[] = {
        ";", "|", "&", "$", "`", "'", "\"", "(", ")", "<", ">",
        "\\", "*", "?", "[", "]", "{", "}", "~", "^", "#", "!",
        "\n", "\t",
        NULL
    };
    int i;
    for (i = 0; bad[i]; i++) {
        char buf[32];
        strcpy(buf, "safe");
        strcat(buf, bad[i]);
        strcat(buf, "text");
        ck_assert_int_eq(mpsafe(buf, 0), 0);
        ck_assert_int_eq(mpsafe(buf, 1), 0);
    }
}
END_TEST

START_TEST(test_command_substitution_rejected)
{
    ck_assert_int_eq(mpsafe("x@y$(touch /tmp/pwned)", 0), 0);
    ck_assert_int_eq(mpsafe("x@y`touch /tmp/pwned`", 0), 0);
}
END_TEST

START_TEST(test_control_byte_rejected)
{
    char buf[8];
    buf[0] = 'a';
    buf[1] = (char)0x01;
    buf[2] = 'b';
    buf[3] = '\0';
    ck_assert_int_eq(mpsafe(buf, 0), 0);
}
END_TEST

START_TEST(test_high_bit_byte_rejected)
{
    char buf[8];
    buf[0] = 'a';
    buf[1] = (char)0x80;
    buf[2] = 'b';
    buf[3] = '\0';
    ck_assert_int_eq(mpsafe(buf, 0), 0);
}
END_TEST

int
main(int argc, char ** argv)
{
    int failed;
    Suite * s = suite_create("Kermit mpsafe() Unit Tests");
    TCase * tc = tcase_create("core");

    tcase_add_test(tc, test_plain_address);
    tcase_add_test(tc, test_plain_options);
    tcase_add_test(tc, test_empty_string_is_safe);
    tcase_add_test(tc, test_allowed_punctuation);
    tcase_add_test(tc, test_digits_and_letters);
    tcase_add_test(tc, test_nonleading_hyphen_allowed);
    tcase_add_test(tc, test_internal_hyphen_run_allowed);
    tcase_add_test(tc, test_leading_hyphen_rejected);
    tcase_add_test(tc, test_leading_hyphen_allowed_when_first_zero);
    tcase_add_test(tc, test_hyphen_after_space_rejected);
    tcase_add_test(tc, test_hyphen_after_multiple_spaces_rejected);
    tcase_add_test(tc, test_space_then_hyphen_at_very_start_rejected);
    tcase_add_test(tc, test_multiple_addresses_no_hyphen_allowed);
    tcase_add_test(tc, test_trailing_space_allowed);
    tcase_add_test(tc, test_shell_metacharacters_rejected);
    tcase_add_test(tc, test_command_substitution_rejected);
    tcase_add_test(tc, test_control_byte_rejected);
    tcase_add_test(tc, test_high_bit_byte_rejected);
    suite_add_tcase(s, tc);

    SRunner * sr = srunner_create(s);
    srunner_run_all(sr, CK_NORMAL);
    failed = srunner_ntests_failed(sr);
    srunner_free(sr);

    return failed ? 1 : 0;
}
