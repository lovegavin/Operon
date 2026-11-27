"""Generate the minimal valid inputs for T12-annotation (基因组注释与区间运算).

Only synthetic, deterministic fixtures (<= a few MB).  Real reference data lives
in evidence/ and is not regenerated here.
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
INPUT = HERE / "input"


def main() -> None:
    INPUT.mkdir(exist_ok=True)
    # TODO: family-specific fixtures.  Keep names stable; the graphs reference them.
    print("inputs ready:", INPUT)


if __name__ == "__main__":
    main()
