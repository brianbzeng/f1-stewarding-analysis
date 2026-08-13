"""Build the separated Study v2 analysis layers."""

from f1stewards.study_v2_layers import build_study_v2_layers


def main() -> None:
    result = build_study_v2_layers()
    print(f"run_id={result.run_id}")
    print(f"output_dir={result.output_dir}")
    print(f"conduct_rows={result.conduct_rows}")
    print(f"consequence_rows={result.consequence_rows}")
    print(f"sanction_rows={result.sanction_rows}")
    print(f"pace_screen_rows={result.pace_screen_rows}")
    print(f"proportionality_release_rows={result.proportionality_release_rows}")


if __name__ == "__main__":
    main()
