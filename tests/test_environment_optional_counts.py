"""Optional bindings must not read as missing required dependencies.

`core` declares `vina==1.2.5` as a best-effort binding.  PyPI has no cp311 wheel
for it, so it can never be installed from the declared source; the card said
"1 依赖缺失" forever even though all 67 required dependencies were present.
"""
from operon import environment_install


ENTRY = {
    'requirements': ['numpy==1.26.4', 'pandas>=2.0'],
    'imports': ['numpy'],
    'best_effort': ['vina==1.2.5'],
}


def test_optional_rows_are_marked():
    rows = environment_install.dependency_rows(ENTRY)
    optional = [row for row in rows if row.get('optional')]
    required = [row for row in rows if not row.get('optional')]
    assert [row['name'] for row in optional] == ['vina==1.2.5']
    assert 'numpy==1.26.4' in [row['name'] for row in required]


def test_counts_leave_out_the_optional_binding():
    rows = environment_install.dependency_rows(ENTRY)
    for row in rows:
        row['installed'] = row['name'] != 'vina==1.2.5'
    counts = environment_install._split_dependency_counts(rows)
    assert (counts['dependency_installed'], counts['dependency_total']) == (3, 3)
    assert (counts['optional_installed'], counts['optional_total']) == (0, 1)
    assert counts['optional_missing'] == ['vina==1.2.5']


def test_a_missing_required_dependency_still_counts():
    rows = environment_install.dependency_rows(ENTRY)
    for row in rows:
        row['installed'] = row['name'] not in {'pandas>=2.0', 'vina==1.2.5'}
    counts = environment_install._split_dependency_counts(rows)
    assert counts['dependency_installed'] == 2
    assert counts['dependency_total'] == 3
