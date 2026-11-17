"""structure_extract_chain: select one or more chains from a structure Form."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import read_source
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from src.task.step.steps._protein_common import column_index, decode_column
from src.task.step.steps.structure_convert_format import (
    _ALIASES,
    _column,
    _element,
    _fmt_atom,
    _labels,
    _text,
)
from operon.bytecode import io_path


class StructureExtractChainStep(Step):
    provider = 'operon-core'
    parameters_file = 'structure_extract_chain.StructureExtractChainStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {
            'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
            'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
        },
        'protocol_version': 3,
        'id': 'structure_extract_chain',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Structure Chain Extraction',
        'description': 'Select chain A/B/... from a structure Form, write a native PDB and return a PDB-style Form.',
        'category': 'Structure',
        'icon': 'Scissors',
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
        atom_dim = str(params.get('atom_dim') or 'atom')
        field_dim = str(params.get('field_dim') or 'field')
        output = str(params.get('output') or 'output')
        filename = str(params.get('filename') or 'chain.pdb')
        if not filename.endswith('.pdb') or '/' in filename or '\\' in filename:
            raise StepError('structure_extract_chain: filename must be a plain .pdb name')
        wanted = [item.strip() for item in str(params.get('chains') or 'A').split(',') if item.strip()]
        if not wanted:
            raise StepError('structure_extract_chain: chains must name at least one chain')
        form = inputs[0] if inputs else None
        if form is None or len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(f'structure_extract_chain: a structure form with dims [{atom_dim}, {field_dim}] is required')
        labels = _labels(form, field_dim)
        for axis in ('x', 'y', 'z'):
            if axis not in labels and f'cartn_{axis}' not in labels:
                raise StepError(f"structure_extract_chain: the input has no '{axis}' or 'Cartn_{axis}' column")
        if 'chain' not in labels and 'label_asym_id' not in labels and 'auth_asym_id' not in labels:
            raise StepError('structure_extract_chain: the input has no chain column')
        chains = [str(value) for value in decode_column(form, field_dim, 'chain')]
        selected = [index for index, chain in enumerate(chains) if chain in wanted]
        if not selected:
            raise StepError(f"structure_extract_chain: no atoms belong to chains {', '.join(wanted)}")
        coords = np.column_stack([
            np.asarray(form.data[:, column_index(form, field_dim, axis)], dtype=np.float64)
            for axis in ('x', 'y', 'z')
        ])
        if not np.isfinite(coords).all():
            raise StepError('structure_extract_chain: coordinates contain NaN/inf')
        resnames = [str(v) for v in decode_column(form, field_dim, 'resname')]
        numbers = np.rint(np.asarray([float(v) for v in decode_column(form, field_dim, 'residue_number')], dtype=np.float64)).astype(np.int64)
        names = [str(v) for v in decode_column(form, field_dim, 'atom_name')]
        elements = [str(v) for v in decode_column(form, field_dim, 'element')]
        altlocs = [str(v) for v in decode_column(form, field_dim, 'altloc')] if 'altloc' in labels or 'label_alt_id' in labels else [''] * len(chains)
        codes = [str(v) for v in decode_column(form, field_dim, 'insertion_code')] if 'insertion_code' in labels or 'pdbx_pdb_ins_code' in labels else [''] * len(chains)
        include_hetatm = bool(params.get('include_hetatm', False))
        lines = []
        previous = None
        serial = 0
        for index in selected:
            chain = _text(chains[index]) or 'A'
            if previous is not None and chain != previous:
                lines.append('TER\n')
            previous = chain
            resname = _text(resnames[index]) or 'UNK'
            hetatm = include_hetatm and resname.upper() in ('HOH', 'WAT', 'SO4', 'GOL', 'EDO', 'LIG')
            serial += 1
            lines.append(_fmt_atom(names[index], resname, chain, numbers[index], *coords[index], 1.0, 0.0,
                                   _element(names[index], elements[index]), altlocs[index], codes[index], serial, hetatm))
        lines.append('END\n')
        directory = output_directory(ctx, 'structure_extract_chain')
        path = Path(directory) / filename
        io_path(path).write_text(''.join(lines), encoding='ascii', errors='replace')
        extracted = read_source(path, ['atom', 'field'], {'atom': 'auto', 'field': 'builtin'})
        extracted.info.update({'chains': wanted, 'path': str(path), 'n_atoms': len(selected)})
        files = [result_file('structure', path, 'pdb', 'Extracted chains ' + ','.join(wanted))]
        remember_native(ctx, output, files)
        self._files = files
        ctx[output] = extracted
        print(f'[structure_extract_chain] {len(selected)} atoms from {",".join(wanted)} -> {path}')

    def export(self, ctx) -> dict:
        return {'result_files': getattr(self, '_files', [])}
