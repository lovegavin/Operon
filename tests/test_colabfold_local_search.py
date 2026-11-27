from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps import colabfold_predict as mod


def _stub_search(tmp_path: Path) -> Path:
    binary = tmp_path / "colabfold_search"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "out = pathlib.Path(sys.argv[-1])\n"
        "(out / '0' / 'a3m').mkdir(parents=True, exist_ok=True)\n"
        "(out / '0' / 'a3m' / 'query.a3m').write_text('>q\\nAAA\\n')\n"
        "pathlib.Path('argv.txt').write_text(' '.join(sys.argv[1:]))\n"
    )
    binary.chmod(0o755)
    return binary


def test_local_database_runs_colabfold_search_and_returns_a3m_directory(tmp_path):
    batch = tmp_path / "colabfold_batch"
    batch.write_text("#!/usr/bin/env python3\n")
    batch.chmod(0o755)
    _stub_search(tmp_path)
    db = tmp_path / "uniref30_2302_db"
    db.write_text("")
    Path(str(db) + ".dbtype").write_text("0")
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">q\nAAA\n")

    out = mod.search_database(
        fasta,
        binary=str(batch),
        workdir=tmp_path,
        db1=str(db),
        threads=4,
    )

    assert (out / "0" / "a3m" / "query.a3m").is_file()
    argv = (tmp_path / "argv.txt").read_text()
    assert "--db1" in argv and str(db) in argv
    assert "--threads 4" in argv
    assert "--mmseqs" in argv


def test_local_database_requires_the_search_entry_point(tmp_path):
    batch = tmp_path / "colabfold_batch"
    batch.write_text("#!/usr/bin/env python3\n")
    batch.chmod(0o755)
    db = tmp_path / "uniref30_2302_db"
    db.write_text("")
    Path(str(db) + ".dbtype").write_text("0")
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">q\nAAA\n")

    with pytest.raises(StepError, match="colabfold_search"):
        mod.search_database(fasta, binary=str(batch), workdir=tmp_path, db1=str(db))


def test_local_database_requires_an_index(tmp_path):
    batch = tmp_path / "colabfold_batch"
    batch.write_text("#!/usr/bin/env python3\n")
    batch.chmod(0o755)
    _stub_search(tmp_path)
    db = tmp_path / "uniref30_2302_db"
    db.write_text("")
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">q\nAAA\n")

    with pytest.raises(StepError, match="dbtype"):
        mod.search_database(fasta, binary=str(batch), workdir=tmp_path, db1=str(db))
