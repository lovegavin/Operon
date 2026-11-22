"""Plain one-number-per-line reader for single vectors.

Some operators (for example ``diversity_simpson`` or
``numeric_gini_coefficient``) consume a one-dimensional numeric vector,
and until now no reader could produce that shape. This reader reads a
single column of numbers and returns a one-dimensional form, so those
operators can run on a real abundance vector exported from a dataset
rather than on a synthesised matrix.

The file may carry a header line and ``#`` comments; both are optional.
Blank lines are ignored.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class ValuesReader(Reader):
    provider = 'operon-readers'
    """Reader for a single column of numbers; output is a 1-D form."""

    parameters_file = 'values_reader.ValuesReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ValuesReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for a single column of numbers',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 1,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'Reader for a single column of numbers.\n'
                    '\n'
                    '    Returns a one-dimensional numeric form, which is what operators\n'
                    '    that measure a single vector (diversity, Gini coefficient) expect.\n'
                    '    A header line and "#" comments are optional; blank lines are ignored.',
     'extensions': ['.values', '.vals'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['value'],
                    'labels': {'value': 'builtin'}}}

    def _parse(self, path: Path, args) -> np.ndarray:
        column = int(args.get("column", 0))
        if column < 0:
            raise ReaderError("Values reader: column must not be negative")
        comment = str(args.get("comment", "#"))
        header = bool(args.get("header", False))
        values: list[float] = []
        seen_data = False
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ReaderError(f"Values reader: cannot read {path}: {exc}") from exc
        for raw in text.splitlines():
            line = raw.strip()
            if not line or (comment and line.startswith(comment)):
                continue
            fields = [part for part in line.replace("\t", " ").replace(",", " ").split(" ") if part]
            if column >= len(fields):
                raise ReaderError(
                    f"Values reader: line has {len(fields)} column(s); column {column} is missing"
                )
            token = fields[column]
            try:
                value = float(token)
            except ValueError:
                if not seen_data and header:
                    continue
                raise ReaderError(f"Values reader: {token!r} is not a number") from None
            seen_data = True
            values.append(value)
        if not values:
            raise ReaderError("Values reader: the file holds no numbers")
        return np.asarray(values, dtype=np.float64)

    def probe(self, path, **args):
        data = self._parse(Path(path), args)
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (int(data.size),),
            "dtype": "float64",
            "dense_bytes": int(data.size) * 8,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 1:
            raise ReaderError(f"Values reader requires exactly one dim, got {dims}")
        value_dim = dims[0]
        data = compact_numeric(self._parse(Path(path), args))
        form = Form(
            data=data,
            dims=[value_dim],
            labels={
                value_dim: unique_labels(
                    [str(i) for i in range(int(data.shape[0]))], value_dim, "values"
                )
            },
            info={"missing_code": np.nan, "n_values": int(data.shape[0])},
        )
        form.validate()
        return form
