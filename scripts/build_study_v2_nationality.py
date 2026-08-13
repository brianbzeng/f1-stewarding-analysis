"""Build the gated Study v2 nationality diagnostic."""

from f1stewards.study_v2_nationality import build_nationality_diagnostic


def main() -> None:
    result = build_nationality_diagnostic()
    print(f"run_id={result.run_id}")
    print(f"output_dir={result.output_dir}")
    print(f"rows={result.rows}")
    print(f"british_rows={result.british_rows}")
    print(f"release_gate_passed={result.release_gate_passed}")


if __name__ == "__main__":
    main()
