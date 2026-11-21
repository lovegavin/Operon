"""DSSP secondary-structure segments."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


import subprocess
import tempfile
from pathlib import Path

_SS_CODES = {"H": "helix", "G": "helix", "I": "helix", "E": "strand", "B": "strand", "T": "turn", "S": "bend", "-": "coil", " ": "coil", "P": "coil"}


def parse_dssp(text: str) -> list[dict]:
    """Parse the fixed-column DSSP residue table (mkdssp 4.x layout).

    Columns are 1-based in the format documentation; Python slices below are
    0-based: residue number ``[5:10]``, chain ``[11]``, one-letter residue
    ``[13]`` and secondary-structure code ``[16]``.  Blank codes are coil.
    """

    records = []
    for line in text.splitlines():
        if len(line) < 17:
            continue
        number_text = line[5:10].strip()
        if not number_text.lstrip("-").isdigit():
            continue
        residue = line[13].strip()
        if not residue.isalpha():
            continue
        code = line[16]
        records.append(
            {
                "chain": line[11].strip(),
                "number": int(number_text),
                "residue": residue,
                "code": code if code.strip() else "-",
                "state": _SS_CODES.get(code, "coil"),
            }
        )
    return records

def segment_rows(records: list[dict]) -> list[dict]:
    if not records:
        raise StepError("structure_dssp_segments: DSSP reported no residue")
    segments = []
    current = None
    for record in records:
        key = (record["chain"], record["state"])
        if current is None or current["key"] != key:
            if current is not None:
                current.pop("key")
                segments.append(current)
            current = {"key": key, "chain": record["chain"], "state": record["state"], "start": record["number"], "end": record["number"], "codes": [record["code"]]}
        else:
            current["end"] = record["number"]
            current["codes"].append(record["code"])
    if current is not None:
        current.pop("key")
        segments.append(current)
    for segment in segments:
        segment["length"] = segment["end"] - segment["start"] + 1
        segment["codes"] = "".join(segment["codes"])
    return segments


def _write_pdb(form, atom_dim: str, field_dim: str, target: Path) -> Path:
    """Write one PDB file from an atom x field form.

    DSSP only reads structure files, while the operator contract receives the
    structure as a form.  Re-emitting the coordinates keeps a wired route
    working without asking callers for a second copy of the same file.
    """
    from . import _protein_common

    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2 or list(form.dims) != [atom_dim, field_dim]:
        raise StepError(
            "structure_dssp_segments: expected a form with dims "
            f"['{atom_dim}', '{field_dim}'], got {list(form.dims)}"
        )
    columns = {}
    for name in ("x", "y", "z", "occupancy", "bfactor", "residue_number"):
        index = _protein_common.column_index(form, field_dim, name)
        if index >= 0:
            columns[name] = data[:, index]
    for required in ("x", "y", "z", "residue_number"):
        if required not in columns:
            raise StepError(
                "structure_dssp_segments: the structure form is missing the "
                f"'{required}' column; {_protein_common._structure_columns_hint()}"
            )
    texts = {
        name: _protein_common.decode_column(form, field_dim, name)
        for name in ("atom_name", "resname", "chain", "element", "altloc", "insertion_code")
    }
    lines = []
    for index in range(data.shape[0]):
        def text(name, default):
            column = texts.get(name)
            if column is None:
                return default
            value = str(column[index]).strip()
            return value or default

        name = text("atom_name", "")[:4]
        resname = text("resname", "UNK")[:3].rjust(3)
        chain = text("chain", " ")[:1] or " "
        element = text("element", "")[:2].rjust(2)
        number = int(round(float(columns["residue_number"][index])))
        occupancy = float(columns["occupancy"][index]) if "occupancy" in columns else 1.0
        bfactor = float(columns["bfactor"][index]) if "bfactor" in columns else 0.0
        lines.append(
            "ATOM  {serial:>5} {name:<4}{alt:>1}{res:>3} {chain:>1}{number:>4}{icode:>1}   "
            "{x:>8.3f}{y:>8.3f}{z:>8.3f}{occupancy:>6.2f}{bfactor:>6.2f}          {element:>2}".format(
                serial=(index % 100000) + 1,
                name=name,
                alt=text("altloc", " ")[:1] or " ",
                res=resname,
                chain=chain,
                number=number,
                icode=text("insertion_code", " ")[:1] or " ",
                x=float(columns["x"][index]),
                y=float(columns["y"][index]),
                z=float(columns["z"][index]),
                occupancy=occupancy,
                bfactor=bfactor,
                element=element or "  ",
            )
        )
    lines.append("END")
    target.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    return target


def resolve_binary(name: str) -> str:
    """Resolve a DSSP binary through PATH, then through the managed environments."""
    import shutil

    found = shutil.which(name)
    if found:
        return found
    try:
        from operon.dependencies import find_tool
    except Exception:  # pragma: no cover - the application package is optional
        return name
    try:
        return find_tool(name) or name
    except Exception:  # pragma: no cover - a broken install must not mask DSSP errors
        return name


def _pdb_to_mmcif(structure: Path, target: Path) -> None:
    """Convert a PDB file to mmCIF for DSSP versions that only read mmCIF."""
    from Bio.PDB import MMCIFIO, PDBParser

    parser = PDBParser(QUIET=True)
    model = parser.get_structure("structure", str(structure))
    writer = MMCIFIO()
    writer.set_structure(model)
    writer.save(str(target))


def _invoke_dssp(binary: str, structure: Path, output: Path, timeout: int):
    command = [binary, "--output-format", "dssp", str(structure), str(output)]
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        raise StepError(f"structure_dssp_segments: DSSP executable '{binary}' was not found on PATH; install mkdssp") from None
    except subprocess.TimeoutExpired:
        raise StepError(f"structure_dssp_segments: DSSP timed out after {timeout} s") from None


def run_dssp(binary: str, structure: Path, workdir: Path, *, timeout: int = 300) -> str:
    output = workdir / "structure.dssp"
    completed = _invoke_dssp(binary, structure, output, timeout)
    if completed.returncode != 0 and structure.suffix.lower() in (".pdb", ".ent"):
        # mkdssp 4.6 rejects some valid PDB files (REMARK/refine records) with
        # an mmCIF parse error.  Convert once and retry before giving up.
        converted = workdir / "structure.cif"
        try:
            _pdb_to_mmcif(structure, converted)
        except Exception:
            converted = None
        if converted is not None and converted.is_file():
            completed = _invoke_dssp(binary, converted, output, timeout)
    if completed.returncode != 0:
        tail = ((completed.stderr or completed.stdout).strip().splitlines() or [""])[-1]
        raise StepError(f"structure_dssp_segments: DSSP failed with exit code {completed.returncode}: {tail}")
    if not output.is_file():
        raise StepError("structure_dssp_segments: DSSP produced no output")
    return output.read_text(errors="replace")


class StructureDsspSegmentsStep(Step):
    provider = "operon-core"
    parameters_file = "structure_dssp_segments.StructureDsspSegmentsStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_dssp_segments",
        "version": "1.0.0",
        "kind": "operator",
        "title": "DSSP secondary-structure segments",
        "category": "Structure",
        "icon": "TreeStructure",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "atom_dim"}, {"param": "field_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory",
                      "external_tools": ["mkdssp"]},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        workdir = Path(tempfile.mkdtemp())
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        structure = None
        if inputs:
            structure = _write_pdb(inputs[0], atom_dim, field_dim, workdir / "structure.pdb")
        else:
            candidate = str(params.get("structure_path") or "").strip()
            if candidate:
                candidate_path = Path(candidate).expanduser()
                if candidate_path.is_file():
                    structure = candidate_path
        if structure is None:
            raise StepError(
                "structure_dssp_segments: connect a structure form or set structure_path to a file"
            )
        binary = resolve_binary(str(params.get("mkdssp_path") or "mkdssp"))
        text = run_dssp(binary, structure, workdir, timeout=int(params.get("timeout_seconds", 300)))
        segments = segment_rows(parse_dssp(text))
        data = np.array([[s["length"]] for s in segments], dtype=np.float32)
        labels = {f"{s['chain']}:{s['state']}[{s['start']}-{s['end']}]": i for i, s in enumerate(segments)}
        total = sum(s["length"] for s in segments)
        fractions = {state: round(sum(s["length"] for s in segments if s["state"] == state) / total, 4) for state in ("helix", "strand", "coil", "turn", "bend")}
        ctx[params.get("output", "segments")] = Form(
            data=data,
            dims=["segment", "statistic"],
            labels={"segment": labels, "statistic": {"length": 0}},
            info={"missing_code": np.nan, "n_segments": len(segments), "n_residues": total, "fractions": fractions, "segments": [{k: s[k] for k in ("chain", "state", "start", "end", "length", "codes")} for s in segments], "mkdssp": binary},
        )
        self._export_data = {"n_segments": len(segments), "n_residues": total}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
