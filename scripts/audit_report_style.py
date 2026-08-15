"""Audit the final public report against its portfolio writing rules."""

from f1stewards.config import PROJECT_ROOT
from f1stewards.report_style import audit_report_style

REPORT = PROJECT_ROOT / "reports" / "the_cost_of_discretion_study_v2.html"


def main() -> None:
    violations = audit_report_style(REPORT)
    if violations:
        for violation in violations:
            print(f"FAIL: {violation}")
        raise SystemExit(f"report style audit failed with {len(violations)} violation(s)")
    print("report style audit passed")


if __name__ == "__main__":
    main()
