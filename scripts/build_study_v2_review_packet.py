"""Build the deterministic blind source packets for Study v2 human review."""

from __future__ import annotations

from f1stewards.study_v2_review import build_review_packet


def main() -> None:
    build = build_review_packet()
    print(f"packet_id={build.packet_id}")
    print(f"output_dir={build.output_dir}")
    print(f"reviewer_a_rows={build.reviewer_a_rows}")
    print(f"reviewer_b_rows={build.reviewer_b_rows}")
    print(f"elevated_risk_documents={build.elevated_risk_documents}")
    print(f"high_risk_inclusions={build.high_risk_inclusions}")


if __name__ == "__main__":
    main()
