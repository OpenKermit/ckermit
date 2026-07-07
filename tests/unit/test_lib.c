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

START_TEST(test_chknum)
{
    ck_assert_int_eq(chknum("123"), 1);
    ck_assert_int_eq(chknum("+456"), 1);
    ck_assert_int_eq(chknum("-789"), 1);
    ck_assert_int_eq(chknum("  123"), 1);
    
    ck_assert_int_eq(chknum("12.3"), 0);
    ck_assert_int_eq(chknum("12a"), 0);
    ck_assert_int_eq(chknum(""), 0);
    ck_assert_int_eq(chknum("   "), 0);
    ck_assert_int_eq(chknum(NULL), 0);
}
END_TEST

START_TEST(test_ulongtohex_hextoulong)
{
    char buf[32];
    char *hex;
    unsigned long val;

    hex = ulongtohex(0x12345678UL, 8);
    strcpy(buf, hex);
    val = hextoulong(buf, 8);
    ck_assert_uint_eq(val, 0x12345678UL);
}
END_TEST

START_TEST(test_base64)
{
    char src[] = "Hello World!";
    char encoded[100];
    char decoded[100];
    int r;

    // Reset base64 decoder state
    b64tob8(NULL, 0, NULL, 0);

    r = b8tob64(src, -1, encoded, sizeof(encoded));
    ck_assert_int_gt(r, 0);
    ck_assert_str_eq(encoded, "SGVsbG8gV29ybGQh");

    r = b64tob8(encoded, -1, decoded, sizeof(decoded));
    ck_assert_int_gt(r, 0);
    ck_assert_str_eq(decoded, "Hello World!");
}
END_TEST

START_TEST(test_ckmatch)
{
    // Test basic matching
    ck_assert_int_gt(ckmatch("foo", "foo", 0, 0), 0);
    ck_assert_int_eq(ckmatch("foo", "bar", 0, 0), 0);

    // Test case-insensitivity (icase parameter)
    // icase = 0 is case-insensitive (matches)
    ck_assert_int_gt(ckmatch("FOO", "foo", 0, 0), 0);
    // icase = 1 is case-sensitive (does not match)
    ck_assert_int_eq(ckmatch("FOO", "foo", 1, 0), 0);

    // Test ? wildcard
    ck_assert_int_gt(ckmatch("f?o", "foo", 0, 0), 0);
    ck_assert_int_eq(ckmatch("f?o", "fbar", 0, 0), 0);

    // Test * wildcard
    ck_assert_int_gt(ckmatch("f*o", "fooooo", 0, 0), 0);
    ck_assert_int_gt(ckmatch("f*o*", "foobar", 0, 0), 0);

    // Test Bit 2 (4): Allow ^ and $ anchors
    ck_assert_int_gt(ckmatch("^foo$", "foo", 0, 4), 0);
    // Without Bit 2 set, ^ and $ are matched literally
    ck_assert_int_eq(ckmatch("^foo$", "foo", 0, 0), 0);

    // Test Bit 0 (1): Match leading dot (requires Bit 1 (2) to be set)
    // Default with glob (2): dot not matched unless pattern starts with '.'
    ck_assert_int_eq(ckmatch("*", ".foo", 0, 2), 0);
    // Bit 0 set with globbing (3): matches leading dot
    ck_assert_int_gt(ckmatch("*", ".foo", 0, 3), 0);
    ck_assert_int_gt(ckmatch(".*", ".foo", 0, 2), 0);

    // Test Bit 1 (2): Globbing (directory separators are fences)
    // Default (0): directory separators are not fences
    ck_assert_int_gt(ckmatch("a*", "a/b", 0, 0), 0);
    // Bit 1 set (2): directory separator '/' is a fence
    ck_assert_int_eq(ckmatch("a*", "a/b", 0, 2), 0);
}
END_TEST

START_TEST(test_hhmmss)
{
    ck_assert_str_eq(hhmmss(0), "00:00:00");
    ck_assert_str_eq(hhmmss(59), "00:00:59");
    ck_assert_str_eq(hhmmss(60), "00:01:00");
    ck_assert_str_eq(hhmmss(3599), "00:59:59");
    ck_assert_str_eq(hhmmss(3600), "01:00:00");
    ck_assert_str_eq(hhmmss(86399), "23:59:59");
    ck_assert_str_eq(hhmmss(86400), "24:00:00");
    ck_assert_str_eq(hhmmss(-1), "");
}
END_TEST

/* Helper to distinguish error vs valid MSB-set value from hextoulong */
static int
distinguish_hex_result(char *s, int n, long result) {
    int len = 0;
    int sig_started = 0;
    int i;
    if (result != -1L) {
        return 0; /* Good positive result, not ambiguous */
    }
    /* result is -1L, which is ambiguous. Check input format. */
    if (!s || n <= 0) {
        return 1; /* returns 0L normally, but if -1L here, error */
    }
    for (i = 0; i < n && s[i]; i++) {
        char c = s[i];
        if (c == ' ' || c == '0') {
            if (sig_started) len++;
            continue;
        }
        if ((c >= '1' && c <= '9') ||
            (c >= 'a' && c <= 'f') ||
            (c >= 'A' && c <= 'F')) {
            sig_started = 1;
            len++;
            continue;
        }
        return -2; /* Illegal code (non-hex character) */
    }
    if (len > (int)(sizeof(long) * 2)) {
        return -3; /* Overflow (too many digits) */
    }
    return 2; /* Valid MSB-set value (e.g., -1L as 0xFFFFFFFFFFFFFFFF) */
}

START_TEST(test_hextoulong_overflow)
{
    unsigned long val;

    /* 64-bit value with MSB set (returns -1L) */
    val = hextoulong("FFFFFFFFFFFFFFFF", 16);
    ck_assert_uint_eq(val, 0xFFFFFFFFFFFFFFFFUL);

    /* Error return is also -1L */
    val = hextoulong("invalidhex", 10);
    ck_assert_uint_eq(val, 0xFFFFFFFFFFFFFFFFUL);

    /* Verify using the helper function how they are distinguished */
    long res1 = hextoulong("FFFFFFFFFFFFFFFF", 16);
    ck_assert_int_eq(
        distinguish_hex_result("FFFFFFFFFFFFFFFF", 16, res1), 2
    );

    long res2 = hextoulong("invalidhex", 10);
    ck_assert_int_eq(
        distinguish_hex_result("invalidhex", 10, res2), -2
    );

    long res3 = hextoulong("1FFFFFFFFFFFFFFFF", 17);
    ck_assert_int_eq(
        distinguish_hex_result("1FFFFFFFFFFFFFFFF", 17, res3), -3
    );
}
END_TEST

START_TEST(test_base64_validation)
{
    char buf[100];
    int r;

    /* Correct response on illegal characters (returns -2) */
    b64tob8(NULL, 0, NULL, 0); /* reset state */
    r = b64tob8("SGVsbG8#", -1, buf, sizeof(buf));
    ck_assert_int_eq(r, -2);

    /* Note on -3: b64tob8 returns -3 if t > 63 or t < 0. But since b64tbl
       only maps characters to -2, -1, or 0..63, -3 is unreachable. */

    /* Buffer overflow constraint handling: returns -1 if destination
       is not big enough. */
    b64tob8(NULL, 0, NULL, 0); /* reset state */
    r = b64tob8("SGVsbG8gV29ybGQh", -1, buf, 2);
    ck_assert_int_eq(r, -1);

    /* Ignored whitespace/newlines inside base64 payload */
    b64tob8(NULL, 0, NULL, 0); /* reset state */
    r = b64tob8("SGVsbG8\r\ngV29y\t bGQh", -1, buf, sizeof(buf));
    ck_assert_int_gt(r, 0);
    ck_assert_str_eq(buf, "Hello World!");

    /* Pessimistic buffer check when whitespace is present:
       If the output buffer is large enough for decoded data (12 bytes)
       but smaller than the unadjusted estimate including whitespace (15
       bytes), it fails with -1. */
    b64tob8(NULL, 0, NULL, 0); /* reset state */
    r = b64tob8("SGVsbG8\r\ngV29y\t bGQh", -1, buf, 12);
    ck_assert_int_eq(r, -1);

    /* State resetting via n = 0 */
    /* 1. Feed partial base64 data to leave leftover bits in state */
    char out_buf[10];
    r = b64tob8("SG", 2, out_buf, sizeof(out_buf));
    ck_assert_int_eq(r, 1);
    ck_assert_int_eq(out_buf[0], 'H');

    /* 2. Reset the decoder state */
    r = b64tob8(NULL, 0, NULL, 0);
    ck_assert_int_eq(r, 0);

    /* 3. Decode fresh data; should succeed if state was properly reset */
    r = b64tob8("SGVsbG8=", -1, out_buf, sizeof(out_buf));
    ck_assert_int_eq(r, 5);
    ck_assert_str_eq(out_buf, "Hello");
}
END_TEST

START_TEST(test_ulongtohex_non_reentrant)
{
    /* Document non-reentrant behavior: ulongtohex uses a shared static
       buffer. Calling it twice in sequence without copying the value
       causes the second call to overwrite the first. */
    char *hex1;
    char *hex2;

    hex1 = ulongtohex(0x12345678UL, 8);
    hex2 = ulongtohex(0xabcdef00UL, 8);

    /* Both pointers point to the exact same static buffer address */
    ck_assert_ptr_eq(hex1, hex2);

    /* Both contain the second value now */
    ck_assert_str_eq(hex1, "ABCDEF00");
}
END_TEST

Suite *lib_suite(void)
{
    Suite *s;
    TCase *tc_core;

    s = suite_create("Kermit Lib Unit Tests");
    tc_core = tcase_create("Core");

    tcase_add_test(tc_core, test_chknum);
    tcase_add_test(tc_core, test_ulongtohex_hextoulong);
    tcase_add_test(tc_core, test_base64);
    tcase_add_test(tc_core, test_ckmatch);
    tcase_add_test(tc_core, test_hhmmss);
    tcase_add_test(tc_core, test_hextoulong_overflow);
    tcase_add_test(tc_core, test_base64_validation);
    tcase_add_test(tc_core, test_ulongtohex_non_reentrant);

    suite_add_tcase(s, tc_core);
    return s;
}

int main(void)
{
    int number_failed;
    Suite *s;
    SRunner *sr;

    s = lib_suite();
    sr = srunner_create(s);

    srunner_run_all(sr, CK_NORMAL);
    number_failed = srunner_ntests_failed(sr);
    srunner_free(sr);
    return (number_failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
