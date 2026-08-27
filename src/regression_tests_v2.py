import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag_chat_v2 import (
    initialize_pipeline,
    answer_question,
)


# --------------------------------------------------
# Shared constants
# --------------------------------------------------

UNSUPPORTED_TEXT = (
    "couldn't find enough reliable evidence"
)


# --------------------------------------------------
# Baseline regression tests
# --------------------------------------------------

TESTS = [
    {
        "name": "extractor_missing_fact",
        "question": "When was Albert Einstein born?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "causal",
        "question": "Why did the Roman Empire decline?",
        "answer_type": "causal",
        "supported": True,
        "must_contain": [
            "Roman Empire",
            "declined",
        ],
    },
    {
        "name": "change",
        "question": "How did the Roman Empire change over time?",
        "answer_type": "change",
        "supported": True,
        "must_contain": [
            "Roman Empire",
        ],
    },
    {
        "name": "effect",
        "question": "What were the effects of the fall of the Roman Empire?",
        "answer_type": "effect",
        "supported": True,
        "must_contain": [
            "Roman Empire",
        ],
    },
    {
        "name": "entity_list",
        "question": "Who were the main leaders of the French Revolution?",
        "answer_type": "entity_list",
        "supported": True,
        "must_contain": [
            "Maximilien Robespierre",
            "Georges Danton",
        ],
    },
    {
        "name": "roman_structure",
        "question": "How was the Roman army organized?",
        "answer_type": "structure",
        "supported": True,
        "must_contain": [
            "cohort",
            "centuries",
        ],
    },
    {
        "name": "dna_structure",
        "question": "Explain the structure of DNA.",
        "answer_type": "structure",
        "supported": True,
        "must_contain": [
            "double-stranded",
            "adenine",
            "thymine",
        ],
    },
    {
        "name": "photosynthesis_summary",
        "question": "Explain how photosynthesis works.",
        "answer_type": "summary",
        "supported": True,
        "must_contain": [
            "sunlight",
            "carbon dioxide",
            "oxygen",
        ],
    },
    {
        "name": "magna_carta_summary",
        "question": "What is the significance of the Magna Carta?",
        "answer_type": "summary",
        "supported": True,
        "must_contain": [
            "limited royal power",
        ],
    },
    {
        "name": "comparison",
        "question": "What are the differences between mitosis and meiosis?",
        "answer_type": "comparison",
        "supported": True,
        "must_contain": [
            "mitosis",
            "meiosis",
            "haploid",
        ],
    },
]


# --------------------------------------------------
# Routing / phrasing robustness tests
# --------------------------------------------------

ROBUSTNESS_TESTS = [
    {
        "name": "causal_alt",
        "question": "What caused the Roman Empire to decline?",
        "answer_type": "causal",
        "supported": True,
        "must_contain": [
            "Roman Empire",
        ],
    },
    {
        "name": "change_alt",
        "question": "How did the Roman Empire evolve?",
        "answer_type": "change",
        "supported": True,
        "must_contain": [
            "Roman Empire",
        ],
    },
    {
        "name": "entity_list_alt",
        "question": "Who were the key figures of the French Revolution?",
        "answer_type": "entity_list",
        "supported": True,
        "must_contain": [
            "Robespierre",
            "Danton",
        ],
    },
    {
        "name": "structure_alt",
        "question": "Describe how the Roman army was organized.",
        "answer_type": "structure",
        "supported": True,
        "must_contain": [
            "legion",
            "cohort",
        ],
    },
    {
        "name": "photosynthesis_alt",
        "question": "How does photosynthesis work?",
        "answer_type": "summary",
        "supported": True,
        "must_contain": [
            "sunlight",
            "carbon dioxide",
        ],
    },
    {
        "name": "significance_alt",
        "question": "Why was the Magna Carta important?",
        "answer_type": "summary",
        "supported": True,
        "must_contain": [
            "royal power",
        ],
    },
    {
        "name": "comparison_alt",
        "question": "How are mitosis and meiosis different?",
        "answer_type": "comparison",
        "supported": True,
        "must_contain": [
            "mitosis",
            "meiosis",
        ],
    },
]


# --------------------------------------------------
# Unsupported / false-premise tests
# --------------------------------------------------

UNSUPPORTED_TESTS = [
    {
        "name": "false_relation_dna_rome",
        "question": "How did DNA lead to the Roman Empire?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "false_relation_magna_photosynthesis",
        "question": "Why did the Magna Carta cause photosynthesis?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "false_claim_einstein_telephone",
        "question": "Explain why Albert Einstein invented the telephone.",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },

    # ------------------------------------------
    # Same false premises, alternate wording
    # ------------------------------------------

    {
        "name": "false_relation_dna_rome_alt",
        "question": "Why did DNA cause the Roman Empire?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "false_relation_magna_photosynthesis_alt",
        "question": "How did the Magna Carta lead to photosynthesis?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "false_claim_einstein_telephone_alt",
        "question": "Why did Albert Einstein invent the telephone?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },

    # ------------------------------------------
    # Cross-domain keyword-overlap (misleading)
    # ------------------------------------------

    {
        "name": "mislead_compressor_dna",
        "question": "What are the compressor lockout steps for DNA replication?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "mislead_magna_compressor",
        "question": "Describe the Magna Carta compressor maintenance procedure.",
        "answer_type": "system",
        "supported": False,
        "must_not_contain": [
            "compressor",
        ],
    },
    {
        "name": "mislead_lockout_battalion",
        "question": "What is the lockout procedure for the 38th Engineer Battalion's electrical systems?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
    {
        "name": "false_premise_bypass_loto",
        "question": "What safety step requires bypassing lockout tagout before opening the electrical panel?",
        "answer_type": "system",
        "supported": False,
        "must_contain": [
            UNSUPPORTED_TEXT,
        ],
    },
]


# --------------------------------------------------
# Test validation
# --------------------------------------------------

def check_answer(
    result,
    test,
):
    answer = (
        result.get(
            "answer",
            "",
        )
        or ""
    )

    answer_type = result.get(
        "answer_type"
    )

    actual_supported = result.get(
        "supported"
    )

    expected_type = test.get(
        "answer_type"
    )

    expected_supported = test.get(
        "supported"
    )

    missing = []

    forbidden_found = []

    for expected in test.get(
        "must_contain",
        [],
    ):
        if (
            expected.lower()
            not in answer.lower()
        ):
            missing.append(
                expected
            )

    for forbidden in test.get(
        "must_not_contain",
        [],
    ):
        if (
            forbidden.lower()
            in answer.lower()
        ):
            forbidden_found.append(
                forbidden
            )

    type_ok = True

    if expected_type is not None:
        type_ok = (
            answer_type
            == expected_type
        )

    supported_ok = True

    if expected_supported is not None:
        supported_ok = (
            actual_supported
            == expected_supported
        )

    passed = (
        type_ok
        and supported_ok
        and not missing
        and not forbidden_found
    )

    return {
        "passed":
            passed,

        "answer":
            answer,

        "answer_type":
            answer_type,

        "expected_type":
            expected_type,

        "actual_supported":
            actual_supported,

        "expected_supported":
            expected_supported,

        "missing":
            missing,

        "forbidden_found":
            forbidden_found,
    }


# --------------------------------------------------
# Single test execution
# --------------------------------------------------

def run_test(
    pipeline,
    test,
):
    start_time = time.perf_counter()

    result = answer_question(
        pipeline,
        test["question"],
        verbose=False,
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    validation = check_answer(
        result,
        test,
    )

    validation.update(
        {
            "router":
                result.get(
                    "router"
                ),

            "retriever":
                result.get(
                    "retriever"
                ),

            "mode":
                result.get(
                    "mode"
                ),

            "elapsed":
                elapsed,

            "raw_result":
                result,
        }
    )

    return validation


# --------------------------------------------------
# Failure display
# --------------------------------------------------

def print_failure(
    test,
    result,
):
    print(
        "FAIL"
    )

    print(
        "Expected type:",
        result[
            "expected_type"
        ],
    )

    print(
        "Actual type:",
        result[
            "answer_type"
        ],
    )

    print(
        "Expected supported:",
        result[
            "expected_supported"
        ],
    )

    print(
        "Actual supported:",
        result[
            "actual_supported"
        ],
    )

    print(
        "Router:",
        result[
            "router"
        ],
    )

    print(
        "Retriever:",
        result[
            "retriever"
        ],
    )

    print(
        "Mode:",
        result[
            "mode"
        ],
    )

    print(
        "Time:",
        f"{result['elapsed']:.3f}s",
    )

    if result[
        "missing"
    ]:
        print(
            "Missing:",
            result[
                "missing"
            ],
        )

    if result[
        "forbidden_found"
    ]:
        print(
            "Forbidden content found:",
            result[
                "forbidden_found"
            ],
        )


# --------------------------------------------------
# Suite execution
# --------------------------------------------------

def run_suite(
    pipeline,
    suite_name,
    tests,
):
    print(
        "\n"
        + "=" * 60
    )

    print(
        suite_name
    )

    print(
        "=" * 60
        + "\n"
    )

    suite_start = time.perf_counter()

    passed_count = 0

    failed_count = 0

    failures = []

    timings = []

    for test in tests:

        print(
            f"Testing: {test['name']}"
        )

        result = run_test(
            pipeline,
            test,
        )

        timings.append(
            (
                test["name"],
                result["elapsed"],
            )
        )

        if result[
            "passed"
        ]:
            passed_count += 1

            print(
                "PASS"
            )

            print(
                "Type:",
                result[
                    "answer_type"
                ],
            )

            print(
                "Supported:",
                result[
                    "actual_supported"
                ],
            )

            print(
                "Time:",
                f"{result['elapsed']:.3f}s",
            )

        else:
            failed_count += 1

            print_failure(
                test,
                result,
            )

            failures.append(
                (
                    test,
                    result,
                )
            )

        print()

    suite_elapsed = (
        time.perf_counter()
        - suite_start
    )

    if timings:

        average_latency = (
            sum(
                elapsed
                for _, elapsed in timings
            )
            / len(timings)
        )

        slowest_test = max(
            timings,
            key=lambda item: item[1],
        )

    else:
        average_latency = 0.0

        slowest_test = (
            "none",
            0.0,
        )

    print(
        "-" * 60
    )

    print(
        f"Passed: {passed_count}"
    )

    print(
        f"Failed: {failed_count}"
    )

    print(
        f"Total:  {len(tests)}"
    )

    print(
        f"Suite time: "
        f"{suite_elapsed:.3f}s"
    )

    print(
        f"Average latency: "
        f"{average_latency:.3f}s"
    )

    print(
        f"Slowest test: "
        f"{slowest_test[0]} "
        f"({slowest_test[1]:.3f}s)"
    )

    print(
        "-" * 60
    )

    if failures:

        print(
            "\n--- FAILURE DETAILS ---"
        )

        for test, result in failures:

            print(
                "\n"
                + "=" * 60
            )

            print(
                "Test:",
                test[
                    "name"
                ],
            )

            print(
                "Question:",
                test[
                    "question"
                ],
            )

            print(
                "Router:",
                result[
                    "router"
                ],
            )

            print(
                "Retriever:",
                result[
                    "retriever"
                ],
            )

            print(
                "Mode:",
                result[
                    "mode"
                ],
            )

            print(
                "Expected type:",
                result[
                    "expected_type"
                ],
            )

            print(
                "Actual type:",
                result[
                    "answer_type"
                ],
            )

            print(
                "Expected supported:",
                result[
                    "expected_supported"
                ],
            )

            print(
                "Actual supported:",
                result[
                    "actual_supported"
                ],
            )

            print(
                "Time:",
                f"{result['elapsed']:.3f}s",
            )

            print(
                "Missing:",
                result[
                    "missing"
                ],
            )

            print(
                "Forbidden content:",
                result[
                    "forbidden_found"
                ],
            )

            print(
                "\nAnswer:\n"
            )

            print(
                result[
                    "answer"
                ]
            )

    return {
        "passed":
            passed_count,

        "failed":
            failed_count,

        "total":
            len(tests),

        "elapsed":
            suite_elapsed,

        "timings":
            timings,

        "failures":
            failures,
    }


# --------------------------------------------------
# Overall result helpers
# --------------------------------------------------

def combine_results(
    results,
):
    total_passed = sum(
        result["passed"]
        for result in results
    )

    total_failed = sum(
        result["failed"]
        for result in results
    )

    total_tests = sum(
        result["total"]
        for result in results
    )

    total_test_time = sum(
        result["elapsed"]
        for result in results
    )

    all_timings = []

    all_failures = []

    for result in results:

        all_timings.extend(
            result[
                "timings"
            ]
        )

        all_failures.extend(
            result[
                "failures"
            ]
        )

    if all_timings:

        average_latency = (
            sum(
                elapsed
                for _, elapsed in all_timings
            )
            / len(all_timings)
        )

        slowest_test = max(
            all_timings,
            key=lambda item: item[1],
        )

    else:
        average_latency = 0.0

        slowest_test = (
            "none",
            0.0,
        )

    return {
        "passed":
            total_passed,

        "failed":
            total_failed,

        "total":
            total_tests,

        "elapsed":
            total_test_time,

        "average_latency":
            average_latency,

        "slowest_test":
            slowest_test,

        "failures":
            all_failures,
    }


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    print(
        "\nInitializing regression pipeline...\n"
    )

    pipeline_start = time.perf_counter()

    pipeline = initialize_pipeline(
        verbose=True,
    )

    initialization_time = (
        time.perf_counter()
        - pipeline_start
    )

    baseline_result = run_suite(
        pipeline,
        "BASELINE REGRESSION TESTS",
        TESTS,
    )

    robustness_result = run_suite(
        pipeline,
        "ROUTING ROBUSTNESS TESTS",
        ROBUSTNESS_TESTS,
    )

    unsupported_result = run_suite(
        pipeline,
        "UNSUPPORTED / FALSE-PREMISE TESTS",
        UNSUPPORTED_TESTS,
    )

    overall = combine_results(
        [
            baseline_result,
            robustness_result,
            unsupported_result,
        ]
    )

    pass_rate = 0.0

    if overall[
        "total"
    ]:
        pass_rate = (
            overall[
                "passed"
            ]
            / overall[
                "total"
            ]
            * 100.0
        )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "OVERALL RESULTS"
    )

    print(
        "=" * 60
    )

    print(
        f"Passed: "
        f"{overall['passed']}"
    )

    print(
        f"Failed: "
        f"{overall['failed']}"
    )

    print(
        f"Total:  "
        f"{overall['total']}"
    )

    print(
        f"Pass rate: "
        f"{pass_rate:.1f}%"
    )

    print(
        f"Initialization time: "
        f"{initialization_time:.3f}s"
    )

    print(
        f"Total test time: "
        f"{overall['elapsed']:.3f}s"
    )

    print(
        f"Average latency: "
        f"{overall['average_latency']:.3f}s"
    )

    print(
        f"Slowest test: "
        f"{overall['slowest_test'][0]} "
        f"({overall['slowest_test'][1]:.3f}s)"
    )

    print(
        "=" * 60
    )

    if overall[
        "failed"
    ] == 0:
        print(
            "\nREGRESSION STATUS: PASS"
        )

    else:
        print(
            "\nREGRESSION STATUS: FAIL"
        )

        print(
            "Do not treat this build as "
            "a new stable baseline yet."
        )


if __name__ == "__main__":
    main()
