"""L2 independent-oracle checks for a representative operator sample."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "operator_audit"))
import l1_contract as L  # noqa: E402

DESCRIPTORS = {d["id"]: d for d in L.load_descriptors()}
OUT = {}


def label_index(form, dim, name):
    for key, index in form.labels[dim].items():
        if key == name:
            return index
    raise KeyError(f"{dim} label {name!r} not in {list(form.labels[dim])}")


def params_for(descriptor, dims, **overrides):
    props = descriptor["parameters_schema"].get("properties", {})
    params = {}
    for key, spec in props.items():
        if not isinstance(spec, dict):
            continue
        if "default" in spec and not isinstance(spec["default"], (dict, list)):
            params[key] = spec["default"]
    for d in dims:
        params[f"{d}_dim"] = d
    params["output"] = "o"
    params.update(overrides)
    return params


def run(descriptor, forms, params):
    cls = L.import_class(descriptor["entry_point"])
    step = cls()
    step.name = descriptor["id"]
    ctx = L.Ctx(forms, params)
    step.run(ctx, forms)
    return ctx[params["output"]]


def matrix(rows, cols, labels, values=None):
    data = np.zeros((rows, cols), dtype=float) if values is None else np.asarray(values, dtype=float)
    return L.Form(data, dims=["row", "field"],
                  labels={"row": {str(i): i for i in range(rows)},
                          "field": {name: i for i, name in enumerate(labels)}}, info={})


def check_kalman():
    rng = np.random.default_rng(7)
    n = 40
    obs = 0.7 + np.sin(np.arange(n) / 5.0) + rng.normal(0, 0.05, n)
    form = matrix(n, 3, ["time", "unused", "observed"], np.stack([np.arange(n), np.zeros(n), obs], axis=1))
    form.info["missing_code"] = -999.0
    p = params_for(DESCRIPTORS["kalman_local_level"], ["row", "field"],
                   process_variance=0.1, observation_variance=0.5)
    out = run(DESCRIPTORS["kalman_local_level"], [form], p)
    got = out.data[:, label_index(out, "statistic", "filtered_mean")]
    # independent scalar Kalman recursion, written separately from the operator
    m, v = obs[0], 1.0
    reference = []
    for z in obs:
        predicted = v + 0.1
        k = predicted / (predicted + 0.5)
        m = m + k * (z - m)
        v = (1.0 - k) * predicted
        reference.append(m)
    reference = np.asarray(reference)
    delta = float(np.max(np.abs(got - reference)))
    return {"pass": delta < 1e-9, "delta": delta, "n": n, "oracle": "scalar Kalman recursion"}


def check_blur():
    rng = np.random.default_rng(3)
    data = rng.normal(size=(24, 24))
    form = matrix(24, 24, [f"c{i}" for i in range(24)], data)
    p = params_for(DESCRIPTORS["image_gaussian_blur"], ["row", "field"], sigma=1.2, truncate=4.0)
    out = run(DESCRIPTORS["image_gaussian_blur"], [form], p)
    ref = ndimage.gaussian_filter(data, sigma=1.2, truncate=4.0, mode="reflect")
    delta = float(np.max(np.abs(out.data - ref)))
    return {"pass": delta < 1e-8, "delta": delta, "oracle": "scipy.ndimage.gaussian_filter"}


def check_pca():
    rng = np.random.default_rng(11)
    data = rng.normal(size=(60, 6)) @ rng.normal(size=(6, 6))
    form = matrix(60, 6, [f"g{i}" for i in range(6)], data)
    form.info["missing_code"] = -999.0
    p = params_for(DESCRIPTORS["pca"], ["row", "field"], n_components=3)
    p.pop("row_dim", None); p.pop("field_dim", None); p["dim"] = "row"
    out = run(DESCRIPTORS["pca"], [form], p)
    # operator compresses rows, so observations are the columns of the input
    X = data.T
    centered = X - X.mean(axis=0)
    std = centered.std(axis=0, ddof=0); std[std < 1e-12] = 1.0
    scaled = centered / std
    U, s, _ = np.linalg.svd(scaled, full_matrices=False)
    scores = U[:, :3] * s[:3]
    got = np.asarray(out.data)[:, :3]
    corrs = []
    for j in range(3):
        a, b = got[:, j], scores[:, j]
        corrs.append(abs(float(np.corrcoef(a, b)[0, 1])))
    return {"pass": bool(min(corrs) > 0.9999), "corrs": corrs, "scores_shape": list(got.shape),
            "oracle": "numpy SVD on transposed, standardized matrix"}


def check_conformal():
    rng = np.random.default_rng(5)
    n = 60
    y = rng.normal(size=n)
    pred = y + rng.normal(0, 0.3, n)
    phase = np.array([0] * 40 + [1] * 20)
    form = matrix(n, 3, ["y", "pred", "phase"], np.stack([y, pred, phase], axis=1))
    p = params_for(DESCRIPTORS["conformal_split_regression"], ["row", "field"], alpha=0.1)
    out = run(DESCRIPTORS["conformal_split_regression"], [form], p)
    cal = np.abs(y - pred)[phase == 0]
    q = np.quantile(cal, min(1.0, np.ceil((len(cal) + 1) * 0.9) / len(cal)), method="higher")
    width_col = next((idx for name, idx in out.labels["statistic"].items()
                      if "width" in name.lower()), None)
    got = float(out.data[0, width_col]) if width_col is not None else None
    return {"pass": bool(got is not None and abs(got - 2 * q) < 1e-9),
            "got": got, "expected": 2 * q, "oracle": "empirical split-conformal quantile"}


def check_bayes():
    rng = np.random.default_rng(13)
    n = 120
    x = rng.normal(size=(n, 2))
    y = 0.8 + 1.5 * x[:, 0] - 0.7 * x[:, 1] + rng.normal(0, 0.2, n)
    form = matrix(n, 3, ["y", "x1", "x2"], np.column_stack([y, x]))
    p = params_for(DESCRIPTORS["bayesian_linear_regression"], ["row", "field"],
                   y_column="y", covariate_columns="x1,x2",
                   n_samples=3000, burn_in=800, seed=0)
    out = run(DESCRIPTORS["bayesian_linear_regression"], [form], p)
    design = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    term = out.labels.get("param") or out.labels.get("term") or out.labels.get("parameter")
    got = {}
    for name, idx in (term or {}).items():
        got[name] = float(out.data[idx, 0])
    keys = list(got)
    post = np.array([got[k] for k in keys])
    delta = float(np.max(np.abs(post - beta)))
    return {"pass": bool(delta < 0.08), "delta": delta,
            "posterior": got, "ols": [float(v) for v in beta],
            "oracle": "statsmodels/numpy OLS"}



def check_kappa():
    table = np.array([[20, 5, 0], [3, 15, 2], [0, 4, 11]], dtype=float)
    form = matrix(3, 3, ["a", "b", "c"], table)
    p = params_for(DESCRIPTORS["cohens_kappa"], [], row_dim="row", col_dim="field", weights="none")
    out = run(DESCRIPTORS["cohens_kappa"], [form], p)
    n = table.sum()
    po = float(np.trace(table) / n)
    pe = float((table.sum(axis=1) * table.sum(axis=0)).sum() / (n * n))
    expected = (po - pe) / (1.0 - pe)
    row = next(idx for name, idx in out.labels["statistic"].items() if name == "kappa")
    got = float(out.data[row, 0])
    delta = abs(got - expected)
    return {"pass": bool(delta < 1e-7), "delta": delta, "got": got, "expected": expected,
            "tolerance": 1e-7, "note": "operator rounds kappa to 8 decimals",
            "oracle": "hand-computed Cohen kappa from the contingency table"}


def check_sobel():
    rng = np.random.default_rng(17)
    data = rng.normal(size=(20, 18))
    form = matrix(20, 18, [f"c{i}" for i in range(18)], data)
    p = params_for(DESCRIPTORS["image_sobel_gradient"], [])
    out = run(DESCRIPTORS["image_sobel_gradient"], [form], p)
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=float)
    ky = kx.T
    ref = np.zeros_like(data)
    for y in range(1, data.shape[0] - 1):
        for x in range(1, data.shape[1] - 1):
            patch = data[y - 1:y + 2, x - 1:x + 2]
            gx = float((patch * kx).sum())
            gy = float((patch * ky).sum())
            ref[y, x] = np.sqrt(gx * gx + gy * gy)
    delta = float(np.max(np.abs(out.data - ref)))
    return {"pass": bool(delta < 1e-12), "delta": delta, "oracle": "hand-written 3x3 Sobel kernels"}


def check_call_rate():
    rng = np.random.default_rng(19)
    data = rng.normal(size=(30, 6))
    mask = rng.random(size=data.shape) < 0.15
    data[mask] = np.nan
    form = matrix(30, 6, [f"s{i}" for i in range(6)], data)
    form.dims = ["variant", "sample"]
    form.labels = {"variant": {str(i): i for i in range(30)},
                   "sample": {f"s{i}": i for i in range(6)}}
    p = params_for(DESCRIPTORS["genotype_call_rate_qc"], [], min_call_rate=0.8)
    out = run(DESCRIPTORS["genotype_call_rate_qc"], [form], p)
    called = np.isfinite(data).sum(axis=0)
    rate = np.round(called / 30.0, 8)
    flag = (rate >= 0.8).astype(float)
    stats = {name: idx for name, idx in out.labels["statistic"].items()}
    sample = {name: idx for name, idx in out.labels["sample"].items()}
    got_rate = np.array([out.data[sample[f"s{i}"], stats["call_rate"]] for i in range(6)])
    got_flag = np.array([out.data[sample[f"s{i}"], stats["pass_flag"]] for i in range(6)])
    delta = float(max(np.max(np.abs(got_rate - rate)), np.max(np.abs(got_flag - flag))))
    return {"pass": bool(delta < 1e-12), "delta": delta, "oracle": "manual call-rate arithmetic with NaN as missing"}



def _dims(form, first, second):
    form.dims = [first, second]
    form.labels = {first: dict(form.labels["row"]), second: dict(form.labels["field"])}


def check_zscore():
    rng = np.random.default_rng(23)
    data = rng.normal(3.0, 2.0, size=(24, 3))
    data[3, 1] = np.nan
    form = matrix(24, 3, ["a", "b", "c"], data)
    _dims(form, "sample", "feature")
    p = params_for(DESCRIPTORS["zscore"], ["sample", "feature"], dim="feature")
    out = run(DESCRIPTORS["zscore"], [form], p)
    mean = np.nanmean(data, axis=1, keepdims=True)
    std = np.nanstd(data, axis=1, ddof=1, keepdims=True)
    std = np.where(np.isfinite(std) & (std > 0), std, 1.0)
    expected = np.where(np.isfinite(data), (data - mean) / std, 0.0)
    delta = float(np.max(np.abs(out.data - expected)))
    return {"pass": bool(delta < 1e-5), "delta": delta, "oracle": "NumPy nanmean/nanstd(ddof=1) along the feature axis"}


def check_minmax():
    rng = np.random.default_rng(29)
    data = rng.normal(-1.0, 4.0, size=(24, 3))
    data[5, 0] = np.nan
    form = matrix(24, 3, ["a", "b", "c"], data)
    _dims(form, "sample", "feature")
    p = params_for(DESCRIPTORS["min_max_scale"], ["sample", "feature"], dim="feature")
    out = run(DESCRIPTORS["min_max_scale"], [form], p)
    lo = np.nanmin(data, axis=1, keepdims=True)
    hi = np.nanmax(data, axis=1, keepdims=True)
    span = hi - lo
    scaled = np.where(span > 0, (data - lo) / span, 0.0)
    expected = np.where(np.isfinite(scaled), scaled, 0.0)
    delta = float(np.max(np.abs(out.data - expected)))
    return {"pass": bool(delta < 1e-6), "delta": delta, "oracle": "manual min-max scaling along the feature axis"}


def check_ttest():
    from scipy import stats

    rng = np.random.default_rng(31)
    data = rng.normal(0.4, 1.5, size=(24, 2))
    form = matrix(24, 2, ["a", "b"], data)
    _dims(form, "sample", "feature")
    p = params_for(DESCRIPTORS["ttest_one_sample"], ["sample", "feature"], popmean=0.25)
    out = run(DESCRIPTORS["ttest_one_sample"], [form], p)
    stats_idx = out.labels["statistic"]
    feat_idx = out.labels["feature"]
    delta = 0.0
    for i, name in enumerate(["a", "b"]):
        t, pv = stats.ttest_1samp(data[:, i], 0.25)
        got_t = float(out.data[feat_idx[name], stats_idx["T"]])
        got_p = float(out.data[feat_idx[name], stats_idx["P"]])
        delta = max(delta, abs(got_t - t), abs(got_p - pv))
    return {"pass": bool(delta < 1e-5), "delta": float(delta), "oracle": "scipy.stats.ttest_1samp"}



def check_chi_square():
    from scipy import stats
    table = np.array([[12, 7, 9], [8, 15, 6]], dtype=float)
    form = matrix(2, 3, ["c0", "c1", "c2"], table)
    form.dims = ["row", "col"]
    form.labels = {"row": {"r0": 0, "r1": 1}, "col": {"c0": 0, "c1": 1, "c2": 2}}
    p = params_for(DESCRIPTORS["chi_square"], [], correction=True)
    out = run(DESCRIPTORS["chi_square"], [form], p)
    chi2, pv, dof, _ = stats.chi2_contingency(table, correction=True)
    st = out.labels["statistic"]
    got = [float(out.data[0, st[k]]) for k in ("chi2", "P", "dof")]
    delta = float(max(abs(got[0] - chi2), abs(got[1] - pv), abs(got[2] - dof)))
    return {"pass": bool(delta < 1e-5), "delta": delta,
            "oracle": "scipy.stats.chi2_contingency(correction=True)"}


def check_fisher_exact():
    from scipy import stats
    table = np.array([[3, 1], [1, 3]], dtype=float)
    form = matrix(2, 2, ["c0", "c1"], table)
    form.dims = ["row", "col"]
    form.labels = {"row": {"r0": 0, "r1": 1}, "col": {"c0": 0, "c1": 1}}
    p = params_for(DESCRIPTORS["fisher_exact"], [], alternative="two-sided")
    out = run(DESCRIPTORS["fisher_exact"], [form], p)
    odds, pv = stats.fisher_exact(table, alternative="two-sided")
    st = out.labels["statistic"]
    delta = float(max(abs(float(out.data[0, st["odds_ratio"]]) - odds),
                      abs(float(out.data[0, st["P"]]) - pv)))
    return {"pass": bool(delta < 1e-6), "delta": delta,
            "oracle": "scipy.stats.fisher_exact(two-sided)"}


CHECKS = [("kalman_local_level", check_kalman),
          ("image_gaussian_blur", check_blur),
          ("pca", check_pca),
          ("conformal_split_regression", check_conformal),
          ("bayesian_linear_regression", check_bayes),
          ("cohens_kappa", check_kappa),
          ("image_sobel_gradient", check_sobel),
          ("genotype_call_rate_qc", check_call_rate),
          ("zscore", check_zscore),
          ("min_max_scale", check_minmax),
          ("ttest_one_sample", check_ttest),
          ("chi_square", check_chi_square),
          ("fisher_exact", check_fisher_exact)]

def main():
    results = {}
    for operator_id, fn in CHECKS:
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            result = {"pass": False, "error": f"{type(exc).__name__}: {exc}"}
        results[operator_id] = result
        print(operator_id, result)
    version = os.environ.get("OPERON_AUDIT_VERSION", "7.0.7")
    out_dir = ROOT / "verification" / f"operator-audit-{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"library_version": version, "mode": "independent-oracle",
               "results": results, "passed": sum(1 for r in results.values() if r.get("pass")),
               "total": len(results)}
    (out_dir / "l2_oracle.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if payload["passed"] == payload["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
