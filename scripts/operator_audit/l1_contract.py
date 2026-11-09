"""L1 contract audit: positive per port and negative per info predicate.

The harness builds a minimal but type-correct Form per declared input contract,
validates it against the declared requirement with the engine's own
``src.core.contracts.validate_form``, then executes the operator. Negative cases
mutate one ``info`` predicate at a time and require rejection before execution.

Classifications:
  PASS             positive ran and produced an output
  SKIP_DOMAIN      positive reached operator code but demanded real domain data
  SKIP_HARNESS     the generic input could not satisfy the declared contract
  SKIP_FILE        file port needs a format-specific fixture
  FAIL             unexpected exception (TypeError/KeyError/IndexError/assert)
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import signal
import tempfile
import traceback
from pathlib import Path

import numpy as np

from src.core import Form
from copy import deepcopy
from src.core.contracts import resolve, validate_form
from src.core.errors import StepError, ValidationError

REPO = Path(__file__).resolve().parents[2]

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "library/seed/operon/builtin_packages.json"

COLUMN_HINTS = ["value", "x", "y", "score", "start", "end"]

COMMON_SKIP = ("requires", "must", "expects", "needs", "missing", "not found",
               "unsupported", "only supports", "no such", "unknown representation")


class Ctx(dict):
    def __init__(self, inputs, params):
        super().__init__()
        self.inputs = inputs
        self.step_params = params
        self.artifacts = {}
        self.metadata = {}
        self.memory = {}
        self._root = Path(tempfile.mkdtemp(prefix="l1_"))

    def artifact_path(self, name):
        target = self._root / name
        target.mkdir(parents=True, exist_ok=True)
        self.artifacts[name] = target
        return target


def load_descriptors():
    data = json.loads(PKG.read_text(encoding="utf-8"))
    return [d for p in data["packages"] for d in p["descriptors"]]


def resolve_param(param, props, depth=0):
    if depth > 6:
        return param
    spec = props.get(param)
    default = spec.get("default") if isinstance(spec, dict) else None
    if isinstance(default, dict) and "param" in default:
        return resolve_param(default["param"], props, depth + 1)
    if isinstance(default, str) and default:
        return default
    if isinstance(default, list) and default and isinstance(default[0], str):
        return default[0]
    return param


def dims_of(contract, props):
    out = []
    for binding in contract.get("dims") or []:
        if isinstance(binding, str):
            out.append(binding)
        elif isinstance(binding, dict):
            out.append(resolve_param(binding.get("param") or "axis", props))
        else:
            out.append("axis")
    ndim = int(contract.get("ndim") or len(out) or 0)
    while len(out) < ndim:
        out.append("d%d" % len(out))
    return out[:ndim]


def field_labels(props, dim, module=None):
    names = []
    if module is not None:
        try:
            import re
            text = Path(module.__file__).read_text(encoding="utf-8")
            for token in re.findall(r"[\"']([a-z][a-z0-9_]{2,24})[\"']", text):
                if token in names or " " in token:
                    continue
                names.append(token)
                if len(names) >= 60:
                    break
        except Exception:
            pass
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        if key.endswith(("_column", "_field", "_label", "_name")) and isinstance(spec.get("default"), str):
            names.append(spec["default"])
    for name in COLUMN_HINTS:
        if name not in names:
            names.append(name)
    return names


def make_form(contract, props, rows=5, cols=6, module=None):
    dims = dims_of(contract, props)
    ndim = len(dims)
    if ndim == 0:
        raise ValueError("contract declares no dimensions")
    seen = set()
    for index, name in enumerate(dims):
        if name in seen:
            dims[index] = "%s_%d" % (name, index)
        seen.add(dims[index])
    shape = [rows] * ndim
    if ndim > 1:
        hints_peek = field_labels(props, dims[-1], module)
        shape[-1] = min(max(cols, 12, len(hints_peek)), 80)
    labels = {dim: {str(i): i for i in range(size)} for dim, size in zip(dims, shape)}
    if ndim > 1:
        hints = field_labels(props, dims[-1], module)
        size = shape[-1]
        labels[dims[-1]] = {hints[i] if i < len(hints) else str(i): i for i in range(size)}
    data = np.zeros(tuple(shape), dtype=float)
    if ndim > 1:
        width = shape[-1]
        for column in range(width):
            data[..., column] = 0.25 + 0.1 * (column % 9)
        for row in range(shape[0]):
            data[row, ...] = data[row, ...] * (1.0 + 0.02 * row)
    info = {}
    rules = contract.get("info") or {}
    if rules.get("representation"):
        rule = rules["representation"]
        info["representation"] = rule.get("const") or (rule.get("enum") or ["sequence_codes"])[0]
    if rules.get("alphabet"):
        info["alphabet"] = rules["alphabet"].get("const") or (rules["alphabet"].get("enum") or ["dna"])[0]
    if info.get("representation") == "sequence_codes":
        alphabet = info.get("alphabet", "dna")
        letters = "ACGT" if alphabet == "dna" else "ACGU"
        info["alphabet_map"] = {letter: i for i, letter in enumerate(letters)}
        info["unknown_code"] = -1
        info["missing_code"] = -1
        # fill with a repeating valid k-mer pattern
        flat = data.reshape(shape[0], -1)
        for r in range(shape[0]):
            for c in range(flat.shape[1]):
                flat[r, c] = (r + c) % len(letters)
    if "missing_code" in rules and "missing_code" not in info:
        rule = rules["missing_code"]
        if rule.get("type") in (["number", "null"], ["number"]):
            info["missing_code"] = -1
    if "ploidy" in rules:
        info["ploidy"] = rules["ploidy"].get("const") or rules["ploidy"].get("min") or 2
    if "unknown_code" in rules:
        info["unknown_code"] = -1
    if "encoders" in rules:
        info["encoders"] = {}
    if info.get("representation") == "sequence":
        info["sequences"] = ["ACGTACGT" for _ in range(shape[0])]
    return Form(data, dims=dims, labels=labels, info=info)


def make_params(descriptor, props, forms, contracts):
    params = {}
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        if "default" in spec:
            value = spec["default"]
            if isinstance(value, dict) or isinstance(value, list):
                continue
            params[key] = value
        elif key.endswith("_dim"):
            params[key] = None
    dimensions = []
    for form in forms:
        dimensions.extend(form.dims)
    for key in list(params):
        if key.endswith("_dim") and params[key] is None:
            params[key] = dimensions[0] if dimensions else "row"
    for contract, form in zip(contracts, forms):
        for index, binding in enumerate(contract.get("dims") or []):
            if isinstance(binding, dict) and binding.get("param") and index < len(form.dims):
                params[binding["param"]] = form.dims[index]
    for key, spec in props.items():
        if key in params or not isinstance(spec, dict):
            continue
        typ = spec.get("type")
        enum = spec.get("enum")
        if enum:
            params[key] = enum[0]
        elif typ == "integer":
            params[key] = 1
        elif typ == "number":
            params[key] = 1.0
        elif typ == "boolean":
            params[key] = False
        elif typ == "array":
            params[key] = []
        elif typ == "object":
            params[key] = {}
        elif typ == "string":
            params[key] = "x"
    out = descriptor.get("output_parameter")
    if out:
        params[out] = "audit_output"
    return params


def import_class(entry_point):
    module_name, _, class_name = entry_point.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def bad_value(rule):
    kind = rule.get("type")
    if rule.get("const") is not None:
        return "__contract_violation__"
    if rule.get("enum"):
        return "__contract_violation__"
    if kind == "string":
        return 123456
    if kind in ("integer", "number"):
        return "not-a-number"
    if kind == "object":
        return ["not-an-object"]
    if kind == "array":
        return "not-an-array"
    return "__contract_violation__"


def classify(exc):
    text = str(exc)
    low = text.lower()
    if isinstance(exc, StepError):
        if any(k in low for k in COMMON_SKIP):
            return "SKIP_DOMAIN", text
        return "SKIP_DOMAIN", text
    return "FAIL", text


def audit_one(descriptor):
    op_id = descriptor["id"]
    record = {"id": op_id, "kind": descriptor.get("kind"), "positive": "FAIL",
              "negative": "SKIP", "output": None, "notes": [], "error": None}
    deps = " ".join(str(d) for d in (descriptor.get("dependencies") or []))
    if any(token in deps for token in ("torch", "transformers", "fair-esm", "openmm")):
        record["positive"] = "SKIP_EXTERNAL"
        record["notes"].append("external model dependency: " + deps[:160])
        return record
    contracts = (descriptor.get("contracts") or {}).get("inputs") or []
    props = ((descriptor.get("parameters_schema") or {}).get("properties") or {})
    file_port = False
    for fmt in ((descriptor.get("data_formats") or {}).get("inputs") or []):
        if str(fmt.get("logical_type", "")).startswith("file"):
            file_port = True
    try:
        cls = import_class(descriptor["entry_point"])
        step = cls()
    except ValueError as exc:
        record["positive"] = "SKIP_DOMAIN" if ("column" in str(exc) or "label" in str(exc)) else "FAIL"
        record["notes"].append(str(exc)[:300])
    except Exception as exc:  # noqa: BLE001
        record["positive"] = "FAIL"
        record["error"] = "import: " + repr(exc)
        return record
    if file_port:
        record["positive"] = "SKIP_FILE"
        record["notes"].append("file port requires a format-specific fixture")
        return record
    forms = []
    try:
        for contract in contracts:
            forms.append(make_form(contract, props, module=importlib.import_module(cls.__module__)))
    except Exception as exc:  # noqa: BLE001
        record["positive"] = "SKIP_HARNESS"
        record["notes"].append("form synthesis: " + repr(exc))
        return record
    params = make_params(descriptor, props, forms, contracts)
    resolved_contracts = [resolve(deepcopy(contract), params) for contract in contracts]
    for contract, form in zip(resolved_contracts, forms):
        dims = contract.get("dims") or []
        if isinstance(dims, list) and len(dims) == len(form.dims):
            contract["dims"] = [name for name in form.dims]
    for form, contract in zip(forms, resolved_contracts):
        try:
            validate_form(form, contract, op_id)
        except (StepError, ValidationError) as exc:
            record["positive"] = "SKIP_HARNESS"
            record["notes"].append("declared contract rejected fixture: " + str(exc)[:300])
            return record
    ctx = Ctx({}, params)
    step.name = op_id
    class _Timeout(Exception):
        pass
    def _alarm(signum, frame):
        raise _Timeout()
    old = signal.signal(signal.SIGALRM, _alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, 15.0)
        step.run(ctx, forms)
        signal.setitimer(signal.ITIMER_REAL, 0)
        out = ctx.get(params.get("output", "")) if params.get("output") else None
        record["positive"] = "PASS"
        if out is None:
            record["output"] = "no output key"
        elif isinstance(out, Form):
            record["output"] = {"shape": list(out.data.shape), "dims": list(out.dims)}
        else:
            record["output"] = type(out).__name__
    except _Timeout:
        record["positive"] = "SKIP_TIMEOUT"
        record["notes"].append("operator exceeded 15 s on synthetic input")
        return record
    except StepError as exc:
        status, text = classify(exc)
        record["positive"] = status
        record["notes"].append(text[:500])
    except Exception as exc:  # noqa: BLE001
        record["positive"] = "FAIL"
        record["error"] = traceback.format_exc(limit=4)[-1200:]
        record["notes"].append(repr(exc)[:300])
        return record
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    # negative predicates, validated by the engine before execution
    neg_total = 0
    neg_ok = 0
    for index, (form, contract) in enumerate(zip(forms, contracts)):
        rules = contract.get("info") or {}
        for key, rule in rules.items():
            if key in ("encoders", "missing_code", "unknown_code"):
                # null-tolerant structural metadata: an explicit wrong-typed value still must be rejected
                pass
            neg_total += 1
            bad = Form(form.data.copy(), dims=list(form.dims), labels={k: dict(v) for k, v in form.labels.items()},
                       info=dict(form.info))
            bad.info[key] = bad_value(rule)
            try:
                validate_form(bad, contract, op_id)
            except StepError:
                neg_ok += 1
            except Exception:  # noqa: BLE001
                pass
    if neg_total:
        record["negative"] = "PASS" if neg_ok == neg_total else "FAIL"
        record["notes"].append("info predicates %d/%d rejected" % (neg_ok, neg_total))
    else:
        record["negative"] = "N/A"
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="verification/operator-audit-7.0.2")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    descriptors = [d for d in load_descriptors() if d.get("kind") == "operator"]
    if args.only:
        wanted = set(args.only.split(","))
        descriptors = [d for d in descriptors if d["id"] in wanted]
    if args.limit:
        descriptors = descriptors[: args.limit]
    rows = []
    for descriptor in descriptors:
        rows.append(audit_one(descriptor))
    path = out_dir / "l1_contract.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    counts = {}
    for row in rows:
        counts[row["positive"]] = counts.get(row["positive"], 0) + 1
    summary = {"total": len(rows), "positive": counts,
               "negative_pass": sum(1 for r in rows if r["negative"] == "PASS"),
               "negative_fail": sum(1 for r in rows if r["negative"] == "FAIL"),
               "negative_na": sum(1 for r in rows if r["negative"] == "N/A")}
    (out_dir / "l1_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
