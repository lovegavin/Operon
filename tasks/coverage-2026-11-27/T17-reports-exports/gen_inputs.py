"""Generate the minimal valid inputs for T17-reports-exports (报告、导出与工作流特性).

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
