"""result_report: turn a final Form (or a produced file) into a report file.

The report step closes a workflow: it accepts either a Form produced by an
operator or a file artifact produced upstream, and writes a human readable
report (``csv``, ``json`` or ``markdown``) that is registered as a native
result so the run keeps the artifact.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from operon.bytecode import io_path

_EXTENSIONS = {'csv': 'csv', 'json': 'json', 'markdown': 'md', 'md': 'md'}


class ResultReportStep(Step):
    """Write a report from a Form or from an upstream file artifact."""

    provider = 'operon-core'
    parameters_file = 'result_report.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {
            'inputs': [{'logical_type': 'form',
                        'representations': ['form', 'file_artifact'],
                        'metadata': {}}],
            'outputs': [],
        },
        'protocol_version': 3,
        'id': 'result_report',
        'version': '1.0.0',
        'kind': 'operator',
        'title': '结果报告',
        'description': '把最终 Form 或上游文件写成报告文件（csv/json/markdown），并登记为运行产物。',
        'category': '数据整理',
        'icon': 'FileText',
        'contracts': {'version': 1,
                      'inputs': [{'version': 1, 'numeric': True, 'info': {},
                                  'dims': [], 'labels': [], 'parallel': []}],
                      'output': {'mode': 'report'}},
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': None,
    }

    def _summary(self, form: Form) -> list[list[str]]:
        rows = [['item', 'value']]
        rows.append(['shape', 'x'.join(str(int(size)) for size in np.asarray(form.data).shape)])
        rows.append(['dims', ', '.join(str(dim) for dim in form.dims)])
        rows.append(['dtype', str(np.asarray(form.data).dtype)])
        labels = form.labels or {}
        for dim, mapping in list(labels.items())[:6]:
            rows.append([f'labels[{dim}]', f'{len(mapping)} entries'])
        info = form.info or {}
        for key in list(info)[:8]:
            rows.append([f'info[{key}]', str(info[key])[:120]])
        preview = np.asarray(form.data)
        if preview.ndim:
            flat = preview.reshape(preview.shape[0], -1)[:5]
            rows.append(['preview', json.dumps(flat.tolist())[:600]])
        return rows

    def run(self, ctx: Context, inputs) -> None:
        data = inputs[0]
        params = ctx.step_params or {}
        fmt = str(params.get('format') or 'csv').strip().lower()
        extension = _EXTENSIONS.get(fmt)
        if extension is None:
            raise StepError(f"result_report: unsupported format '{fmt}' (use csv, json or markdown)")
        title = str(params.get('title') or 'result report')

        directory = output_directory(ctx, 'report')
        destination = Path(io_path(directory / f'report.{extension}'))

        if isinstance(data, FileArtifact):
            names = list((data.files or {}).values()) if hasattr(data, 'files') else []
            summary = [['item', 'value'], ['source', 'file_artifact'],
                       ['format', str(getattr(data, 'format', ''))],
                       ['files', ', '.join(str(name) for name in names[:8])]]
            if extension == 'csv':
                text = '\n'.join(','.join(row) for row in summary) + '\n'
            elif extension == 'json':
                text = json.dumps({'title': title, 'artifact': {'format': str(getattr(data, 'format', '')),
                                                                'files': [str(n) for n in names]}}, indent=2)
            else:
                text = f'# {title}\n\n- format: `{getattr(data, "format", "")}`\n- files: {len(names)}\n'
            destination.write_text(text, encoding='utf-8')
            report = {'source': 'file', 'format': extension, 'rows': len(summary)}
        elif isinstance(data, Form):
            rows = self._summary(data)
            if extension == 'csv':
                text = '\n'.join(','.join(str(cell) for cell in row) for row in rows) + '\n'
            elif extension == 'json':
                text = json.dumps({'title': title,
                                   'shape': [int(size) for size in np.asarray(data.data).shape],
                                   'dims': [str(dim) for dim in data.dims],
                                   'dtype': str(np.asarray(data.data).dtype)}, indent=2)
            else:
                body = '\n'.join(f'| {row[0]} | {row[1]} |' for row in rows[1:])
                text = f'# {title}\n\n| item | value |\n| --- | --- |\n{body}\n'
            destination.write_text(text, encoding='utf-8')
            report = {'source': 'form', 'format': extension, 'rows': len(rows)}
        else:
            raise StepError('result_report: input must be a Form or a file artifact')

        files = [result_file('report', destination, extension, title)]
        remember_native(ctx, 'report', files)
        self._result_files = files
        self._report = report
