# Run dev_B2_b2_s1

| scope | tests | accepted_rate | compile_rate | pass_rate | smell_reduction_tsdetect | smell_reduction_strict | smell_reduction_accepted | accepted_losing_mutants_rate | accepted_safe_rate | tokens_per_test | wall_time_s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| overall | 5 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 100.0 | 2621 | 560.0 |
| commons-cli | 5 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 100.0 | 2621 | 560.0 |

commons-cli: reduction 100.0% vs paper 86.0% (delta 14.0, within 5 points: False)

| smell | targeted | removed | removed % |
|---|---|---|---|
| AssertionRoulette | 2 | 2 | 100.0 |
| SensitiveEquality | 2 | 2 | 100.0 |
| ExceptionHandling | 1 | 1 | 100.0 |
