from operon.engine.cache_environment import inspect


def test_same_version_dependency_code_change_invalidates_fingerprint(tmp_path, monkeypatch):
    """A same-version reinstall cannot hide behind unchanged METADATA."""
    site = tmp_path / 'site'
    metadata = site / 'operon_cache_fixture-1.0.dist-info'
    metadata.mkdir(parents=True)
    (metadata / 'METADATA').write_text(
        'Metadata-Version: 2.1\nName: operon-cache-fixture\nVersion: 1.0\n', encoding='utf-8')
    (metadata / 'RECORD').write_text(
        'operon_cache_fixture.py,,\noperon_cache_fixture-1.0.dist-info/METADATA,,\n'
        'operon_cache_fixture-1.0.dist-info/RECORD,,\n', encoding='utf-8')
    code = site / 'operon_cache_fixture.py'
    code.write_text('value = 1\n', encoding='utf-8')
    monkeypatch.syspath_prepend(str(site))
    before = inspect(['operon-cache-fixture==1.0'])
    code.write_text('value = 2\n', encoding='utf-8')
    after = inspect(['operon-cache-fixture==1.0'])
    assert before['verified'] and after['verified']
    assert before['digest'] != after['digest']
