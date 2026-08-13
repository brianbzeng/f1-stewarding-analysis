"""Run and persist the requirement-level Study v2 completion audit."""

from f1stewards.config import PROJECT_ROOT
from f1stewards.study_v2_completion import audit_study_v2_completion


def main() -> None:
    audit = audit_study_v2_completion()
    output = PROJECT_ROOT / "reports" / "generated" / "study_v2" / "completion_audit.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output, index=False)
    print(audit.to_string(index=False))
    print(f"controls={len(audit)};status=pass;output={output}")


if __name__ == "__main__":
    main()
