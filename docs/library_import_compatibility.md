# Importing operator libraries and routes

## Operator libraries

Use **Add operators → Import package** for an official `.whl` distribution or an
`operon-library.zip` bundle. A plain `.zip` is not an operator library and is
rejected. The bundle must contain the `operon.library` envelope, safe archive
paths, matching checksums, and a source-to-wheel reproducible package.

## Route operators

Use **Add operators → Route operators** with one `.zip` collection. The importer
looks inside `route/` or `routes/` for every `*.operon.zip`, imports all of them,
saves them, and registers them in one step. No manual file selection or
extraction is required. Containers with no matching route bundle are rejected.

Individual `.operon.zip` files and exported `.operon`/`.json` routes can still be
selected directly. A route collection is never accepted by the operator-library
importer, and an operator library is never accepted by the route importer.

## Verification boundary

Archive paths, member counts and sizes are bounded before import. Each nested
route bundle still passes the normal graph validation, parameter freezing,
revision, save and registration checks. The importer does not run the analyses
or establish availability of their external tools, models or datasets.
