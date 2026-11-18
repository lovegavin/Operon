"""Install-size estimates for declared isolated environments."""
from operon import environment_estimates


def test_every_builtin_environment_has_a_positive_estimate(tmp_path):
    for name in ('antifold', 'boltz', 'colabfold', 'esm3', 'esmfold', 'openfold', 'openmm81'):
        value = environment_estimates.expected(name, None, tmp_path)
        assert isinstance(value, int) and value > 0


def test_unknown_names_get_a_generic_estimate(tmp_path):
    value = environment_estimates.expected('mystery', None, tmp_path)
    assert environment_estimates.FALLBACK * 0.8 <= value <= environment_estimates.FALLBACK * 1.1


def test_manifest_size_is_used_when_nothing_was_measured(tmp_path):
    assert environment_estimates.expected('custom', {'size_bytes': 4321}, tmp_path) == 4321


def test_recorded_size_wins_over_the_static_estimate(tmp_path):
    environment_estimates.record('openfold', 1234, tmp_path)
    assert environment_estimates.expected('openfold', None, tmp_path) == 1234
    assert (tmp_path / environment_estimates.LEARNED).is_file()
    assert environment_estimates.learned(tmp_path)['openfold'] == 1234


def test_record_ignores_invalid_sizes(tmp_path):
    environment_estimates.record('openfold', 0, tmp_path)
    environment_estimates.record('openfold', -5, tmp_path)
    assert environment_estimates.learned(tmp_path) == {}

