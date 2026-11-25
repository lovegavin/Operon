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
from src.task.step.steps._protein_common import column_index
from src.task.step.steps.structure_convert_format import (
    _ALIASES,
    _column,
    _element,
    _fmt_atom,
    _labels,
    _text,
    decoded_columns,
)
from operon.bytecode import io_path


def selected_indices(chains, wanted, operator='structure_extract_chain'):
    """Return the atom indices whose chain is in ``wanted``.

    Raises a StepError that names the chains the input actually carries, so a
    caller sees why a request for chain "B" found nothing instead of only
    learning that nothing matched.
    """
    selected = [index for index, chain in enumerate(chains) if chain in wanted]
    if not selected:
        available = sorted({chain for chain in chains if chain})
        raise StepError(
            f"{operator}: no atoms belong to chains {', '.join(wanted)}; "
            f"the input carries {', '.join(available) or 'no chain labels'}"
        )
    return selected


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
        chain_values = decoded_columns(form, field_dim, labels, 'chain')
        if chain_values is None:
            raise StepError(
                'structure_extract_chain: the structure input has no chain column '
                '(chain, label_asym_id or auth_asym_id); load the file with the PDB '
                'reader or run structure_convert_format first'
            )
        chains = [str(value) for value in chain_values]
        selected = selected_indices(chains, wanted)
        coords = np.column_stack([
            np.asarray(form.data[:, column_index(form, field_dim, axis)], dtype=np.float64)
            for axis in ('x', 'y', 'z')
        ])
        if not np.isfinite(coords).all():
            raise StepError('structure_extract_chain: coordinates contain NaN/inf')
        def column(key, fallback):
            values = decoded_columns(form, field_dim, labels, key)
            return [str(v) for v in values] if values is not None else fallback

        resnames = column('resname', ['UNK'] * len(chains))
        numbers = np.rint(np.asarray(
            [float(v) for v in column('residue_number', range(1, len(chains) + 1))],
            dtype=np.float64,
        )).astype(np.int64)
        names = column('atom_name', ['C'] * len(chains))
        elements = column('element', [''] * len(chains))
        altlocs = column('altloc', [''] * len(chains))
        codes = column('insertion_code', [''] * len(chains))
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
