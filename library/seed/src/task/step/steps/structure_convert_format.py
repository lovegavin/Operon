"""structure_convert_format: Form -> PDB -> Form without external tools."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import read_source
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from operon.bytecode import io_path

_COORDINATES = ('x', 'y', 'z')
_ALIASES = {
    'x': ('x', 'cartn_x'),
    'y': ('y', 'cartn_y'),
    'z': ('z', 'cartn_z'),
    'atom_name': ('atom_name', 'label_atom_id', 'auth_atom_id'),
    'resname': ('resname', 'label_comp_id', 'auth_comp_id'),
    'chain': ('chain', 'label_asym_id', 'auth_asym_id'),
    'residue_number': ('residue_number', 'label_seq_id', 'auth_seq_id'),
    'element': ('element', 'type_symbol'),
    'altloc': ('altloc', 'label_alt_id'),
    'insertion_code': ('insertion_code', 'pdbx_pdb_ins_code'),
}


def _labels(form, field_dim):
    return {str(k).lower(): int(v) for k, v in (form.labels.get(field_dim) or {}).items()}


def _column(form, field_dim, labels, names):
    for name in names:
        if name in labels:
            return form.data.take(labels[name], axis=1)
    return None


def _text(value):
    if value is None:
        return ''
    text = str(value).strip()
    return '' if text.lower() in ('nan', 'none', 'null', '.', '?') else text


def _element(atom_name, element):
    value = _text(element)
    if value:
        return value[:2].upper().rjust(2)[:2]
    name = _text(atom_name).lstrip('0123456789')
    return (name[:1] if name else 'C').upper().rjust(2)[:2]


def _fmt_atom(name, resname, chain, number, x, y, z, occ, b, element, altloc, code, serial, hetatm):
    record = 'HETATM' if hetatm else 'ATOM  '
    atom = _text(name)[:4]
    if len(atom) < 4 and atom[:1] not in ('', ' '):
        atom = ' ' + atom.ljust(3)
    else:
        atom = atom.ljust(4)
    return (
        f"{record}{serial:5d} {atom}{_text(altloc)[:1] or ' '}{_text(resname)[:3].rjust(3)} "
        f"{_text(chain)[:1] or 'A'}{int(number) % 10000:4d}{_text(code)[:1] or ' '}   "
        f"{float(x):8.3f}{float(y):8.3f}{float(z):8.3f}{float(occ):6.2f}{float(b):6.2f}          "
        f"{element:>2}\n"
    )


class StructureConvertFormatStep(Step):
    provider = 'operon-core'
    parameters_file = 'structure_convert_format.StructureConvertFormatStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {
            'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
            'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
        },
        'protocol_version': 3,
        'id': 'structure_convert_format',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Structure Format Conversion',
        'description': 'Convert a structure Form to a complete PDB file and back to a PDB-style Form.',
        'category': 'Structure',
        'icon': 'ArrowsLeftRight',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1, 'ndim': 2, 'numeric': True,
                'dims': [{'param': 'atom_dim', 'default': 'atom'}, {'param': 'field_dim', 'default': 'field'}],
                'labels': [], 'parallel': [],
                'info': {'encoders': {'type': 'object', 'optional': True}},
            }],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24'],
        'dependency_imports': ['numpy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        atom_dim = str(params.get('atom_dim', 'atom'))
        field_dim = str(params.get('field_dim', 'field'))
        output = str(params.get('output', 'output'))
        filename = str(params.get('filename', 'converted.pdb'))
        if not filename.endswith('.pdb') or '/' in filename or '\\' in filename:
            raise StepError('structure_convert_format: filename must be a plain .pdb name')
        form = inputs[0] if inputs else None
        if form is None or len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(f'structure_convert_format: a structure form with dims [{atom_dim}, {field_dim}] is required')
        labels = _labels(form, field_dim)
        arrays = {key: _column(form, field_dim, labels, aliases) for key, aliases in _ALIASES.items()}
        for axis in _COORDINATES:
            if arrays[axis] is None:
                raise StepError(f"structure_convert_format: the input has no '{axis}' or 'Cartn_{axis}' column")
        coords = np.column_stack([np.asarray(arrays[a], dtype=np.float64) for a in _COORDINATES])
        if not np.isfinite(coords).all():
            raise StepError('structure_convert_format: coordinates contain NaN/inf')
        resnames = arrays['resname'] if arrays['resname'] is not None else [params.get('resname', 'UNK')] * len(coords)
        chains = arrays['chain'] if arrays['chain'] is not None else [params.get('chain', 'A')] * len(coords)
        numbers = arrays['residue_number'] if arrays['residue_number'] is not None else np.arange(1, len(coords) + 1)
        names = arrays['atom_name'] if arrays['atom_name'] is not None else ['C'] * len(coords)
        elements = arrays['element'] if arrays['element'] is not None else [None] * len(coords)
        altlocs = arrays['altloc'] if arrays['altloc'] is not None else [''] * len(coords)
        codes = arrays['insertion_code'] if arrays['insertion_code'] is not None else [''] * len(coords)
        include_hetatm = bool(params.get('include_hetatm', False))
        lines = []
        previous_chain = None
        for index in range(len(coords)):
            chain = _text(chains[index]) or 'A'
            if previous_chain is not None and chain != previous_chain:
                lines.append('TER\n')
            previous_chain = chain
            resname = _text(resnames[index]) or 'UNK'
            hetatm = include_hetatm and resname.upper() in ('HOH', 'WAT', 'SO4', 'GOL', 'EDO', 'LIG')
            lines.append(_fmt_atom(names[index], resname, chain, numbers[index], *coords[index], 1.0, 0.0,
                                   _element(names[index], elements[index]), altlocs[index], codes[index], index + 1, hetatm))
        lines.append('END\n')
        directory = output_directory(ctx, 'structure_convert_format')
        path = Path(directory) / filename
        io_path(path).write_text(''.join(lines), encoding='ascii', errors='replace')
        converted = read_source(path, ['atom', 'field'], {'atom': 'auto', 'field': 'builtin'})
        converted.info.update({'source_format': 'form', 'output_format': 'pdb', 'path': str(path), 'n_atoms': len(coords)})
        files = [result_file('structure', path, 'pdb', 'Converted structure')]
        remember_native(ctx, output, files)
        self._files = files
        ctx[output] = converted
        print(f'[structure_convert_format] {len(coords)} atoms -> {path}')

    def export(self, ctx) -> dict:
        return {'result_files': getattr(self, '_files', [])}
