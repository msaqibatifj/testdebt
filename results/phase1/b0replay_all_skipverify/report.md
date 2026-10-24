# Run b0replay_all_skipverify

| scope | tests | accepted_rate | compile_rate | pass_rate | smell_reduction_tsdetect | accepted_losing_mutants_rate | accepted_safe_rate | tokens_per_test | wall_time_s |
|---|---|---|---|---|---|---|---|---|---|
| overall | 483 | - | - | - | 59.9 | - | - | 0 | 227.8 |
| commons-cli | 77 | - | - | - | 86.4 | - | - | 0 | 32.8 |
| gson | 238 | - | - | - | 58.4 | - | - | 0 | 120.2 |
| jsoup | 168 | - | - | - | 53.5 | - | - | 0 | 74.8 |

commons-cli: reduction 86.4% vs paper 86.0% (delta 0.4, within 5 points: True)

gson: reduction 58.4% vs paper 89.0% (delta -30.6, within 5 points: False)

jsoup: reduction 53.5% vs paper 91.0% (delta -37.5, within 5 points: False)

| smell | targeted | removed | removed % |
|---|---|---|---|
| EagerTest | 343 | 109 | 31.8 |
| AssertionRoulette | 311 | 196 | 63.0 |
| ExceptionHandling | 222 | 202 | 91.0 |
| SensitiveEquality | 79 | 64 | 81.0 |
| MagicNumberTest | 55 | 29 | 52.7 |
| DuplicateAssert | 45 | 35 | 77.8 |
| ConditionalTestLogic | 10 | 8 | 80.0 |
| RedundantAssertion | 5 | 5 | 100.0 |
| MysteryGuest | 4 | 0 | 0.0 |
| ResourceOptimism | 4 | 2 | 50.0 |
