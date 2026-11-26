from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fundamental_event_trader.features import event_study, registry
from fundamental_event_trader.qualification import qualify, validate_dataset
from fundamental_event_trader.sec import (
    USER_AGENT,
    DataGateError,
    capture,
    import_swing_sidecar,
    sha,
)


def normalize_capture(folder: Path, output: Path):
    from fundamental_event_trader.archive import normalize

    return normalize(folder, output)


def _main():
    parser = argparse.ArgumentParser(
        description="Public-data fundamental/event research; fail-closed"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("capture")
    p.add_argument("--cik", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT", USER_AGENT))
    p = sub.add_parser("normalize")
    p.add_argument("--capture", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("import-swing-sidecar")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("qualify")
    p.add_argument("--dataset", type=Path)
    p.add_argument("--output", type=Path)
    p = sub.add_parser("registry")
    p.add_argument("--output", type=Path)
    p = sub.add_parser("news-refresh", help="Read public financial news; no historical-strategy admission")
    p.add_argument("--output", type=Path)
    p.add_argument("--max-articles", type=int, default=12)
    p.add_argument("--budget-seconds", type=float, default=75.)
    p = sub.add_parser("news-screen-freeze", help="Freeze an ETF news-proxy performance-screen protocol")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("news-screen-build", help="Acquire historical news proxies and export frozen targets; no strategy admission")
    p.add_argument("--registry", type=Path, required=True)
    p = sub.add_parser("news-vintage-freeze", help="Freeze a historical-released-vintage news timing screen")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("news-vintage-build", help="Acquire the complete historical monthly news-index release census")
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--resume", action="store_true", help="Reuse hash-checked releases after transport failure; never retry denied access")
    p = sub.add_parser("news-vintage-audit", help="Reconstruct primary news-vintage features and targets from raw release bytes")
    p.add_argument("--screen", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--latest-screen", type=Path)
    p = sub.add_parser("news-maturity-freeze", help="Freeze a fixed historical-news observation-maturity follow-up")
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("news-maturity-build", help="Build fixed maturity-adjusted targets from sealed released histories")
    p.add_argument("--registry", type=Path, required=True)
    p = sub.add_parser("research")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("portfolio-research")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("audit-research")
    p.add_argument("--report", type=Path, required=True)
    for name in ("status", "daily", "configure"):
        p = sub.add_parser(name)
        p.add_argument("--dataset", type=Path)
        p.add_argument("--report", type=Path)
        if name == "daily":
            p.add_argument("--output", type=Path, required=True)
            p.add_argument("--refresh-news", action="store_true")
    p = sub.add_parser("import-sec-bulk")
    p.add_argument("--submissions", type=Path, required=True)
    p.add_argument("--companyfacts", type=Path, required=True)
    p.add_argument("--cik", required=True)
    p.add_argument("--captured-at", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "news-maturity-freeze":
        from fundamental_event_trader.news_maturity_research import freeze

        print(freeze(args.parent, args.output))
    elif args.command == "news-maturity-build":
        from fundamental_event_trader.news_maturity_research import build

        print(build(args.registry))
    elif args.command == "news-vintage-freeze":
        from fundamental_event_trader.news_vintage_research import freeze

        print(freeze(args.bundle, args.output))
    elif args.command == "news-vintage-build":
        from fundamental_event_trader.news_vintage_research import build

        print(build(args.registry, resume=args.resume))
    elif args.command == "news-vintage-audit":
        from fundamental_event_trader.news_vintage_audit import audit

        print(json.dumps(audit(args.screen, args.output, latest_screen=args.latest_screen), indent=2))
    elif args.command == "news-screen-freeze":
        from fundamental_event_trader.news_research import freeze

        print(freeze(args.bundle, args.output))
    elif args.command == "news-screen-build":
        from fundamental_event_trader.news_research import acquire, build

        print(json.dumps(acquire(args.registry), indent=2))
        print(build(args.registry))
    elif args.command == "news-refresh":
        from datetime import UTC, datetime

        from fundamental_event_trader.news import refresh, status

        output = args.output or Path("data/news/captures") / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        refresh(Path.cwd(), output, max_articles=args.max_articles, budget=args.budget_seconds)
        current = status(Path.cwd())
        print(json.dumps({key: value for key, value in current.items() if key not in {"items", "limits"}}, indent=2))
    elif args.command == "portfolio-research":
        from fundamental_event_trader.research import run

        print(run(args.dataset, args.output))
    elif args.command == "audit-research":
        from fundamental_event_trader.operating import audit_report

        print(json.dumps(audit_report(args.report), indent=2))
    elif args.command == "status":
        from fundamental_event_trader.operating import status

        result = status(Path.cwd(), dataset=args.dataset, report=args.report)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        if result["status"] == "blocked":
            raise SystemExit(2)
    elif args.command == "daily":
        from fundamental_event_trader.operating import daily

        print(daily(Path.cwd(), args.output, dataset=args.dataset, report=args.report, refresh_news=args.refresh_news))
        if json.loads((args.output / "status.json").read_text())["status"] == "blocked":
            raise SystemExit(2)
    elif args.command == "configure":
        from fundamental_event_trader.operating import configure

        if args.dataset is None or args.report is None:
            parser.error("configure requires --dataset and --report")
        print(configure(Path.cwd(), args.dataset, args.report))
    elif args.command == "import-sec-bulk":
        from fundamental_event_trader.archive import extract_issuer

        print(
            extract_issuer(
                args.submissions,
                args.companyfacts,
                args.cik,
                args.output,
                captured_at=args.captured_at,
            )
        )
    elif args.command == "capture":
        path = capture(args.cik, args.output, user_agent=args.user_agent)
        print(path)
        if json.loads(path.read_text())["status"] == "blocked":
            raise SystemExit(2)
    elif args.command == "normalize":
        normalize_capture(args.capture, args.output)
    elif args.command == "import-swing-sidecar":
        print(import_swing_sidecar(args.manifest, args.output))
    elif args.command == "registry":
        encoded = (
            json.dumps(
                {
                    "hypotheses": registry(),
                    "tested_on_real_data": False,
                    "action_authorized": False,
                },
                indent=2,
            )
            + "\n"
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as handle:
                handle.write(encoded)
        else:
            print(encoded)
    elif args.command == "qualify":
        result = qualify(args.dataset)
        encoded = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as handle:
                handle.write(encoded)
        print(encoded)
        if not result["historical_event_study_allowed"]:
            raise SystemExit(2)
    else:
        status = qualify(args.dataset)
        if not status["historical_event_study_allowed"]:
            print(json.dumps(status, indent=2))
            raise SystemExit(2)
        events, prices = validate_dataset(args.dataset)
        args.output.mkdir(parents=True, exist_ok=False)
        # Event studies are not portfolio backtests; overlapping observations
        # must not be annualized as tradable CAGR or treated as independent.
        for horizon in (5, 21, 63):
            for cost in (20, 50, 100):
                event_study(events, prices, horizon=horizon, roundtrip_bps=cost).to_parquet(
                    args.output / f"events_h{horizon}_c{cost}.parquet", index=False
                )
        (args.output / "manifest.json").write_text(
            json.dumps(
                {
                    "dataset_manifest_sha256": sha(args.dataset / "manifest.json"),
                    "authority": "event_study_only",
                    "strategy_promoted": False,
                    "portfolio_cagr_claim_allowed": False,
                    "clustered_uncertainty_required_before_inference": True,
                    "artifacts": {p.name: sha(p) for p in args.output.iterdir()},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def main():
    try:
        _main()
    except (DataGateError, OSError, KeyError, TypeError, AssertionError) as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "action_authorized": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:400],
                }
            )
        )
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
