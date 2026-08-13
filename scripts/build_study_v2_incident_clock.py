"""Map FIA incident clocks into participant lap intervals."""

from f1stewards.incident_clock import build_incident_clock_windows


def main() -> None:
    build = build_incident_clock_windows()
    print(f"run_id={build.run_id}")
    print(f"output_dir={build.output_dir}")
    print(f"cases={build.cases}")
    print(f"mapped_cases={build.mapped_cases}")
    print(f"single_lap_cases={build.single_lap_cases}")
    print(f"known_validation={build.known_contained_cases}/{build.known_validation_cases}")


if __name__ == "__main__":
    main()
