"""Build source-explicit incident timing and context candidates."""

from f1stewards.incident_context import build_incident_context_candidates


def main() -> None:
    build = build_incident_context_candidates()
    print(f"run_id={build.run_id}")
    print(f"output_dir={build.output_dir}")
    print(f"cases={build.cases}")
    print(f"current_exact_laps={build.current_exact_laps}")
    print(f"new_explicit_lap_candidates={build.new_explicit_lap_candidates}")
    print(f"new_clock_single_lap_candidates={build.new_clock_single_lap_candidates}")


if __name__ == "__main__":
    main()
