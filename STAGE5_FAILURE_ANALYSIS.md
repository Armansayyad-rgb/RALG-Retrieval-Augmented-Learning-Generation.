# Stage 5 Preliminary Failure Analysis

This is a diagnostic analysis of automatically generated, unreviewed cases. It is not a final failure rate or customer-facing claim.

## Observed pattern

RALG lost to the lexical baseline on rank for representative cases `s5_case_005`, `s5_case_006`, `s5_case_007`, `s5_case_008`, `s5_case_009`, `s5_case_013`, `s5_case_022`, `s5_case_024`, `s5_case_027`, `s5_case_028`, `s5_case_029`, and `s5_case_030`. Cases `s5_case_024` and `s5_case_028` were retrieved by the lexical baseline but missed by RALG's top five.

The defensible preliminary classifications are:

- **wrong ranking:** relevant RFC returned below the lexical rank;
- **retrieval miss:** relevant RFC absent from RALG top five;
- **evidence mismatch:** a returned result did not contain the expected source prefix;
- **unsupported handling:** no false support was observed on the generated unsupported subset.

The lexical baseline beats RALG on all retrieval quality metrics in this run. RALG's strongest preliminary result is latency, not retrieval quality.

## Limitations

The cases were generated mechanically from source paragraphs and have not been manually or independently reviewed. No causal, conflict, adversarial, or multi-document conclusion should be drawn from them. The next evaluation must use an independently reviewed queue and retain the first untouched run before any tuning.
