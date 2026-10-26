# Labelling guide: manual smell check (G2, rule iii)

Two labellers (Hasan, Gulsher) label every row of `results/E4/manual/sheet_<run>.csv` independently, without
looking at the detector columns or at each other's labels. Calibrate on 20 dev-split tests first and settle
disagreements by editing this guide; after that the guide is frozen and the 100 test-split tests are labelled.

For each row, open `case_file` (original and refactored method) and decide for the row's smell:

- `present_before_<you>`: 1 if the ORIGINAL method has the smell, else 0
- `present_after_<you>`: 1 if ANY of the refactored methods still has it, else 0

Definitions (as in tsDetect / UTRefactor, method level):

| Smell | Present when |
|---|---|
| AssertionRoulette | 2+ assertions in one test and at least one has no failure message (assertThat / assertThrows exempt) |
| EagerTest | the test calls 2+ distinct methods of the class under test (getters used only inside assertions count) |
| DuplicateAssert | the same assertion (same arguments) appears twice in one test |
| MagicNumberTest | an assertion compares against a numeric literal other than 0/1 that has no named constant |
| SensitiveEquality | an assertion compares a toString() result |
| ExceptionHandling | the test catches an exception or throws one explicitly (try/catch or throw in the body) |
| ConditionalTestLogic | if / loops / switch inside the test body |
| Others | the tsDetect definition (docs: testsmells.org) |

When both labellers agree, that is the label. Otherwise both discuss and write the agreed value into
`adjudicated_before` / `adjudicated_after`. Then run `python3 -m testdebt.team.hasan.manual score <sheet>`.
