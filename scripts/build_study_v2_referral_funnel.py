"""Build Race Control process episodes and conservative adjudication links."""

from f1stewards.referral_funnel import build_referral_funnel


def main() -> None:
    build = build_referral_funnel()
    print(f"run_id={build.run_id}")
    print(f"output_dir={build.output_dir}")
    print(f"parsed_messages={build.parsed_messages}")
    print(f"episodes={build.episodes}")
    print(f"adjudications={build.adjudications}")
    print(f"high_confidence_links={build.high_confidence_links}")


if __name__ == "__main__":
    main()
