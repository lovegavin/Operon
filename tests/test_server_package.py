import importlib.util
from pathlib import Path
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('package_server', Path(__file__).parents[1] / 'scripts/package_server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_server_wrapper_uses_exact_included_wheels(tmp_path):
    (tmp_path/'pyproject.toml').write_text('[project]\nversion="9.1.0"\n')
    for name in ('LICENSE', 'NOTICE', 'scripts/install_server.py', 'scripts/install_server.sh'):
        path=tmp_path/name; path.parent.mkdir(exist_ok=True); path.write_text('fixture')
    app=tmp_path/'operon_studio-9.1.0-py3-none-any.whl'; app.write_bytes(b'app')
    library=tmp_path/'operon_builtin_library-4.0-py3-none-any.whl'; library.write_bytes(b'library')
    output=module.build(tmp_path,app,library,tmp_path/'server.zip')
    with zipfile.ZipFile(output) as z:
        prefix='Operon-9.1.0-Server/'
        assert z.read(prefix+'LICENSE') == b'fixture'
        assert z.read(prefix+'NOTICE') == b'fixture'
        wrapper=z.read(prefix+'install.sh').decode()
        for wheel in (app,library):
            assert '$bundle_dir/wheels/'+wheel.name in wrapper
            assert z.read(prefix+'wheels/'+wheel.name)==wheel.read_bytes()
    with pytest.raises(ValueError, match='match the source'):
        module.build(tmp_path, tmp_path/'operon_studio-9.0.0-py3-none-any.whl',library,tmp_path/'bad.zip')
