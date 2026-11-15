# Real multilanguage acceptance fixtures

These small deterministic programs are test data, not library operators.
The test requires actual Windows Python, Rscript and a compiled C executable.
It never downloads, compiles, installs or substitutes those runtimes.

Prepare the existing Python acceptance store, then separately prepare immutable
R and native generations and set:

- OPERON_ACCEPTANCE_R_ENV_STORE
- OPERON_ACCEPTANCE_R_ENV_GENERATION
- OPERON_ACCEPTANCE_R_ENV_EXECUTABLE (default runtime/bin/Rscript.exe)
- OPERON_ACCEPTANCE_NATIVE_ENV_STORE
- OPERON_ACCEPTANCE_NATIVE_ENV_GENERATION
- OPERON_ACCEPTANCE_NATIVE_ENV_EXECUTABLE (default tools/numeric_transform.exe)

Build the fixture with CMake and Ninja from a configured MSVC or MinGW build
environment. The adjacent CMakeLists.txt selects a static runtime:

    cmake -S tests/fixtures/backend_multilanguage -B verification/.scratch/multilanguage-native -G Ninja -DCMAKE_BUILD_TYPE=Release
    cmake --build verification/.scratch/multilanguage-native

The Windows entry point is wmain; paths use the wide-character extended-path
file interface. The --version probe prints operon-multilang-fixture/1.

The C CLI is:

    numeric_transform --input input.tsv --output output.tsv --offset 5

Both TSV files have exactly one column, named value, and finite numeric rows.
The fixture rejects malformed/nonfinite input and produces value + offset.

The R invocation is:

    Rscript --vanilla scale.R --in-data input.tsv --out-result output.tsv

It multiplies the value column by the sole numeric factor in
OPERON_PARAMETERS_FILE. Its strict fixture-specific JSON parser uses base R,
does not evaluate expressions, and does not require jsonlite.

The exported workflow runs prepare.py -> scale.R -> numeric_transform, then
join.py joins that result with a branch from prepare.py. Initial numbers
[1,2,3], Python factor 2, R factor 3, C offset 5 and join bias 0 produce total 63.
Changing R factor to 4 and C offset to -1 produces total 57. The test checks real
artifacts, exact generation bindings, committed receipts, confirmed Windows
process-tree exit, released leases, resume, and unchanged immutable payload.

This gate covers Windows execution of these explicit TSV/JSON interfaces only.
It does not claim an R scientific package, container, Linux/macOS, or cluster gate.
