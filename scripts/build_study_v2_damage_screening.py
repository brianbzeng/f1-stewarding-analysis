"""Build incident-participant harm screening and source-research queues."""

from f1stewards.damage_screening import build_damage_screening


def main() -> None:
    build = build_damage_screening()
    print(f"run_id={build.run_id}")
    print(f"output_dir={build.output_dir}")
    print(f"collision_decision_rows={build.collision_decision_rows}")
    print(f"candidate_incidents={build.candidate_incidents}")
    print(f"participant_rows={build.participant_rows}")
    print(f"timing_eligible_rows={build.timing_eligible_rows}")


if __name__ == "__main__":
    main()
