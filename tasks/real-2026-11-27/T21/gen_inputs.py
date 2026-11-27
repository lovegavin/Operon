"""Prepare inputs for T21 from downloaded real data (no synthetic fallback)."""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def main() -> None:
    print("inputs:", sorted(p.name for p in (HERE / "input").iterdir()))


if __name__ == "__main__":
    main()
