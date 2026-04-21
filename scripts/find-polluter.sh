#!/bin/bash
# find-polluter.sh — Binary search to find which test pollutes shared state
#
# When a test passes in isolation but fails when run with the full suite,
# another test is polluting shared state. This script uses binary search
# to find the polluting test.
#
# Usage:
#   bash find-polluter.sh <test-command> <failing-test> <test-list-file>
#
# Arguments:
#   test-command   : The command to run tests (e.g., "pytest", "npm test --")
#   failing-test   : The test that fails when run with others (e.g., "tests/test_auth.py::test_login")
#   test-list-file : File containing one test path per line (all other tests)
#
# Example:
#   # First, generate a list of all tests except the failing one:
#   pytest --collect-only -q | grep "::" | grep -v "test_login" > all_tests.txt
#   # Then run the bisection:
#   bash find-polluter.sh "pytest" "tests/test_auth.py::test_login" all_tests.txt
#
# The script will narrow down which test, when run before the failing test,
# causes it to fail.

set -euo pipefail

TEST_CMD="${1:?Usage: find-polluter.sh <test-command> <failing-test> <test-list-file>}"
FAILING_TEST="${2:?Missing failing-test argument}"
TEST_LIST_FILE="${3:?Missing test-list-file argument}"

if [ ! -f "$TEST_LIST_FILE" ]; then
    echo "ERROR: Test list file not found: $TEST_LIST_FILE"
    exit 1
fi

# Read all tests into an array
mapfile -t ALL_TESTS < "$TEST_LIST_FILE"
TOTAL=${#ALL_TESTS[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "ERROR: Test list is empty"
    exit 1
fi

echo "=== Test Pollution Bisection ==="
echo "Failing test: $FAILING_TEST"
echo "Candidate polluters: $TOTAL tests"
echo ""

# Check if the failing test actually fails with all tests
echo "Step 0: Verify test fails with full suite..."
if $TEST_CMD "${ALL_TESTS[@]}" "$FAILING_TEST" > /dev/null 2>&1; then
    echo "WARNING: Test passes with full suite. Cannot bisect."
    echo "The failure may be non-deterministic."
    exit 1
fi
echo "  Confirmed: test fails with full suite."
echo ""

# Check if the failing test passes in isolation
echo "Step 0b: Verify test passes in isolation..."
if ! $TEST_CMD "$FAILING_TEST" > /dev/null 2>&1; then
    echo "WARNING: Test also fails in isolation. Not a pollution issue."
    exit 1
fi
echo "  Confirmed: test passes in isolation."
echo ""

# Binary search
LOW=0
HIGH=$((TOTAL - 1))
ROUND=1

while [ "$LOW" -lt "$HIGH" ]; do
    MID=$(( (LOW + HIGH) / 2 ))
    echo "--- Round $ROUND: testing indices $LOW..$MID (${#ALL_TESTS[@]:$LOW:$((MID - LOW + 1))} tests) ---"

    # Run tests[LOW..MID] + failing test
    SUBSET=("${ALL_TESTS[@]:$LOW:$((MID - LOW + 1))}")
    if $TEST_CMD "${SUBSET[@]}" "$FAILING_TEST" > /dev/null 2>&1; then
        # Test passes → polluter is in the upper half
        echo "  Test PASSED → polluter is in indices $((MID + 1))..$HIGH"
        LOW=$((MID + 1))
    else
        # Test fails → polluter is in this half
        echo "  Test FAILED → polluter is in indices $LOW..$MID"
        HIGH=$MID
    fi
    ROUND=$((ROUND + 1))
done

echo ""
echo "=== POLLUTER FOUND ==="
echo "Test that pollutes shared state: ${ALL_TESTS[$LOW]}"
echo ""
echo "Next steps:"
echo "  1. Run: $TEST_CMD '${ALL_TESTS[$LOW]}' '$FAILING_TEST'"
echo "  2. Confirm it fails"
echo "  3. Inspect '${ALL_TESTS[$LOW]}' for shared state mutations"
echo "  4. Fix the polluter (add cleanup/teardown)"
