"""Build outcome-blind close-case neighbor sets for Study v2."""

from f1stewards.close_case_matching import build_close_case_matches


def main() -> None:
    build = build_close_case_matches()
    print(f"run_id={build.run_id}")
    print(f"output_dir={build.output_dir}")
    print(f"cases={build.cases}")
    print(f"neighbor_edges={build.neighbor_edges}")
    print(f"minimum_support_cases={build.minimum_support_cases}")


if __name__ == "__main__":
    main()
