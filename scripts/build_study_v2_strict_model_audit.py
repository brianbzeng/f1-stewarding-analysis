"""Build the source-cited Study v2 strict model-audit workspace."""

from f1stewards.study_v2_strict_audit import build_strict_model_audit


def main() -> None:
    build = build_strict_model_audit()
    print(f"run_id={build.run_id}")
    print(f"output_dir={build.output_dir}")
    print(f"included_decisions={build.included_decisions}")
    print(f"exclusion_sources={build.exclusion_sources}")
    print(f"pending_adversarial={build.pending_adversarial}")


if __name__ == "__main__":
    main()
