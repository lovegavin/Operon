"""Shared helpers for protein sequence and structure operators."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from src.core import Form, StepError


_COLUMN_ALIASES = {
    "x": ("x", "cartn_x"),
    "y": ("y", "cartn_y"),
    "z": ("z", "cartn_z"),
    "atom_name": ("atom_name", "label_atom_id", "auth_atom_id"),
    "resname": ("resname", "label_comp_id", "auth_comp_id"),
    "chain": ("chain", "label_asym_id", "auth_asym_id"),
    "residue_number": ("residue_number", "label_seq_id", "auth_seq_id"),
    "element": ("element", "type_symbol"),
    "occupancy": ("occupancy",),
    "bfactor": ("bfactor", "b_iso_or_equiv"),
}


def column_index(form: Form, field_dim: str, name: str) -> int:
    """Return the position of a named field column, or -1 when absent.

    Reads accept the mmCIF spelling too, so a structure read from ``.cif`` keeps
    its ``Cartn_x``/``label_atom_id`` columns usable as ``x``/``atom_name``.
    """
    labels = form.labels.get(field_dim)
    if not labels:
        return -1
    lowered = {str(label).lower(): int(position) for label, position in labels.items()}
    for alias in _COLUMN_ALIASES.get(name, (name,)):
        if alias in lowered:
            return lowered[alias]
    return -1


def has_column(form: Form, field_dim: str, name: str) -> bool:
    return column_index(form, field_dim, name) >= 0


def _format_number(value) -> str:
    if value is None:
        return "_"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "_"
    if number.is_integer():
        return str(int(number))
    return format(number, ".10g")


def structure_file(
    form: Form,
    requested,
    prefix: str,
    atom_dim: str = "atom",
    field_dim: str = "field",
    design_index: int = 0,
) -> Path:
    """Return a PDB file for *form*.

    The operators receive the structure as a form, so asking callers for the
    same file a second time breaks a wired route.  When no usable path is
    passed the coordinates are re-emitted into a temporary PDB file.
    """

    text = str(requested or "").strip()
    if text and text != ".":
        candidate = Path(text).expanduser()
        if candidate.is_file():
            return candidate
    import tempfile

    target = Path(tempfile.mkdtemp(prefix=prefix + "-")) / "structure.pdb"
    return write_structure_pdb(form, atom_dim, field_dim, target, prefix, design_index=design_index)


def design_frame(
    form: Form,
    atom_dim: str = "atom",
    field_dim: str = "field",
    prefix: str = "step",
    design_index: int = 0,
) -> Form:
    """Return a single-design atom x field form for a stacked design table.

    Backbone designers stack several designs into one ``[design, atom, field]`` table.  A PDB
    file holds exactly one structure, so choosing the design is an explicit decision instead of
    silently taking the first entry.
    """

    dims = list(form.dims)
    if len(dims) != 3 or dims[1:] != [atom_dim, field_dim]:
        return form
    total = int(form.data.shape[0])
    try:
        chosen = int(design_index or 0)
    except (TypeError, ValueError):
        chosen = 0
    if chosen == 0:
        raise StepError(
            f"{prefix}: the structure form carries {total} designs (dims {dims}); set "
            "design_index to choose one design before this operator reads the structure"
        )
    if chosen < 1 or chosen > total:
        raise StepError(f"{prefix}: design_index {chosen} is outside the {total} design(s) in the form")
    labels = {}
    for key in (atom_dim, field_dim):
        value = form.labels.get(key)
        if value is not None:
            labels[key] = dict(value)
    return Form(
        data=np.asarray(form.data)[chosen - 1],
        dims=[atom_dim, field_dim],
        labels=labels,
        info=dict(form.info or {}),
        axis_info={},
    )


def write_structure_pdb(
    form: Form,
    atom_dim: str,
    field_dim: str,
    target: Path,
    prefix: str,
    design_index: int = 0,
) -> Path:
    """Write one PDB file from an atom x field form."""

    form = design_frame(form, atom_dim, field_dim, prefix, design_index)
    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2 or list(form.dims) != [atom_dim, field_dim]:
        raise StepError(
            f"{prefix}: expected a form with dims ['{atom_dim}', '{field_dim}'], "
            f"got {list(form.dims)}"
        )
    columns = {}
    for name in ("x", "y", "z", "occupancy", "bfactor", "residue_number"):
        index = column_index(form, field_dim, name)
        if index >= 0:
            columns[name] = data[:, index]
    for required in ("x", "y", "z", "residue_number"):
        if required not in columns:
            raise StepError(
                f"{prefix}: the structure form is missing the '{required}' column; "
                "wire a PDB reader that provides x, y, z and residue_number"
            )
    texts = {
        name: decode_column(form, field_dim, name)
        for name in ("atom_name", "resname", "chain", "element", "altloc", "insertion_code")
    }
    lines = []
    for index in range(data.shape[0]):

        def text(name, default=""):
            column = texts.get(name)
            if column is None:
                return default
            value = str(column[index]).strip()
            return value or default

        def marker(name, default=" "):
            # Readers use "_" (and sometimes "." or "?") for a blank PDB marker;
            # writing those characters shifts the columns external tools parse.
            value = text(name, default)
            return default if str(value).strip() in {"_", ".", "?"} else value

        name = text("atom_name")[:4]
        residue_name = text("resname").strip().upper()
        if not name.strip():
            continue
        if residue_name in {"HOH", "WAT", "DOD", "H2O"}:
            continue
        resname = (residue_name or "UNK")[:3].rjust(3)
        chain = marker("chain")[:1] or " "
        element = text("element")[:2].rjust(2)
        number = int(round(float(columns["residue_number"][index])))
        occupancy = float(columns["occupancy"][index]) if "occupancy" in columns else 1.0
        bfactor = float(columns["bfactor"][index]) if "bfactor" in columns else 0.0
        lines.append(
            "ATOM  {serial:>5} {name:<4}{alt:>1}{res:>3} {chain:>1}{number:>4}{icode:>1}   "
            "{x:>8.3f}{y:>8.3f}{z:>8.3f}{occupancy:>6.2f}{bfactor:>6.2f}          {element:>2}".format(
                serial=(index % 100000) + 1,
                name=name,
                alt=marker("altloc")[:1] or " ",
                res=resname,
                chain=chain,
                number=number,
                icode=marker("insertion_code")[:1] or " ",
                x=float(columns["x"][index]),
                y=float(columns["y"][index]),
                z=float(columns["z"][index]),
                occupancy=occupancy,
                bfactor=bfactor,
                element=element,
            )
        )
    lines.append("END")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")
    return target

def decode_column(form: Form, field_dim: str, name: str) -> np.ndarray | None:
    """Decode one structural column to strings.

    Label-encoded columns are inverted with the encoder recorded in
    ``form.info["encoders"]``; numeric columns are formatted without a
    trailing ``.0`` so residue numbers compare with PDB text.
    """
    index = column_index(form, field_dim, name)
    if index < 0:
        return None
    values = np.asarray(form.data)[:, index]
    encoders = (form.info.get("encoders") or {}).get(field_dim) or {}
    encoder = encoders.get(name)
    if encoder is not None:
        return np.array([str(v) for v in encoder.inverse_transform(values)], dtype=object)
    return np.array([_format_number(v) for v in values], dtype=object)


def _format_column_list(names) -> str:
    items = [repr(str(name)) for name in names]
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _structure_columns_hint() -> str:
    return (
        "load the structure with the PDB reader so the field dimension carries named "
        "columns (chain, resname, residue_number, atom_name, element, x, y and z)"
    )


def require_columns(form: Form, field_dim: str, names, operator: str) -> None:
    """Raise a readable ValueError when a required structural column is absent."""
    missing = [name for name in names if not has_column(form, field_dim, name)]
    if missing:
        present = [name for name in names if name not in missing]
        found = f" (it found {_format_column_list(present)})" if present else ""
        raise ValueError(
            f"{operator}: the structure input has no {_format_column_list(missing)} "
            f"{'column' if len(missing) == 1 else 'columns'} on the "
            f"{field_dim!r} dimension; the operator needs {_format_column_list(names)}{found}, "
            f"so {_structure_columns_hint()}"
        )


def _clean(value: str) -> str:
    text = str(value).strip()
    return "_" if text == "" else text


def residue_labels(form: Form, field_dim: str) -> np.ndarray:
    """Build ``chain:resname:number`` labels for every atom row."""
    chain = decode_column(form, field_dim, "chain")
    resname = decode_column(form, field_dim, "resname")
    number = decode_column(form, field_dim, "residue_number")
    if chain is None or resname is None or number is None:
        raise StepError(
            "structure form must carry chain, resname and residue_number columns"
        )
    insertion = decode_column(form, field_dim, "insertion_code")
    labels = []
    for i in range(len(number)):
        suffix = ""
        if insertion is not None:
            code = str(insertion[i]).strip()
            if code not in ("", "_"):
                suffix = code
        labels.append(
            f"{_clean(chain[i])}:{_clean(resname[i])}:{_clean(number[i])}{suffix}"
        )
    return np.array(labels, dtype=object)


def heavy_atom_mask(form: Form, field_dim: str) -> np.ndarray:
    """Mask non-hydrogen atoms when element or atom name columns exist."""
    element = decode_column(form, field_dim, "element")
    if element is not None:
        return np.array(
            [str(value).strip().upper() not in ("H", "D", "") for value in element],
            dtype=bool,
        )
    atom_name = decode_column(form, field_dim, "atom_name")
    if atom_name is not None:
        return np.array(
            [not str(value).strip().upper().startswith("H") for value in atom_name],
            dtype=bool,
        )
    return np.ones(np.asarray(form.data).shape[0], dtype=bool)


def split_chains(text: str) -> list[str]:
    """Parse a comma/space separated chain list."""
    if text is None:
        return []
    return [part for part in str(text).replace(",", " ").split() if part]


def residue_order(labels: np.ndarray) -> list[str]:
    seen: dict[str, None] = {}
    for label in labels:
        seen.setdefault(str(label), None)
    return list(seen)


def contact_stats(
    query: np.ndarray, reference: np.ndarray, cutoff: float
) -> tuple[np.ndarray, np.ndarray]:
    """Count reference points within ``cutoff`` and report the nearest distance."""
    from scipy.spatial import cKDTree

    tree = cKDTree(reference)
    counts = tree.query_ball_point(query, r=cutoff, return_length=True)
    distances, _ = tree.query(query, k=1)
    return np.asarray(counts, dtype=np.int64), np.asarray(distances, dtype=np.float64)


def proteinmpnn_layout(root: "Path | str") -> "tuple[Path, Path]":
    """Return the checkout and weight directory inside a resource root.

    A linked official checkout lands under ``<root>/ProteinMPNN`` while a
    copied one sits directly at ``<root>``; both carry ``vanilla_model_weights``
    beside ``protein_mpnn_run.py``.  Operators ask this helper so a fresh
    resource install resolves the same files a hand-linked tree does.
    """

    base = Path(root).expanduser()
    for candidate in (base, base / "ProteinMPNN"):
        if (candidate / "protein_mpnn_run.py").is_file():
            return candidate, candidate / "vanilla_model_weights"
    return base, base / "vanilla_model_weights"


def resolve_proteinmpnn_path(value: str, operator: str = "proteinmpnn") -> "Path":
    """Resolve ProteinMPNN from the parameter, the environment, or the resource.

    Operators used to require ``proteinmpnn_path`` (or ``OPERON_PROTEINMPNN_PATH``);
    an install that downloaded the ``proteinmpnn`` resource already has the
    checkout, so fall back to it instead of asking the user to repeat a path the
    installer recorded.
    """

    text = str(value or "").strip() or os.environ.get("OPERON_PROTEINMPNN_PATH", "").strip()
    if text:
        return Path(text).expanduser()
    from src.task.step.steps import _resources_common

    try:
        _, root = _resources_common.require(operator, "proteinmpnn")
    except StepError:
        return Path("")
    return root


def resolve_ligandmpnn_path(value: str, operator: str = "ligandmpnn") -> "Path":
    """Resolve LigandMPNN from the parameter, the environment, or the resource."""

    text = str(value or "").strip() or os.environ.get("OPERON_LIGANDMPNN_PATH", "").strip()
    if text:
        return Path(text).expanduser()
    from src.task.step.steps import _resources_common

    try:
        _, root = _resources_common.require(operator, "ligandmpnn")
    except StepError:
        return Path("")
