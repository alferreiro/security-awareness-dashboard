#!/usr/bin/env python3
"""
export_tidy.py -- write tidy (long-format) CSV tables to data/tidy/ so the same
dashboard can be rebuilt in Tableau Public, Power BI, Looker Studio or Excel.

Each table has one row per observation, one column per variable, no merged
headers, ISO dates, and rates expressed as fractions (0.123 = 12.3 %). Every
breakdown respects the 10-person privacy floor (suppressed rows keep their key
columns but have blank statistics and suppressed = 1).

Usage:
    python scripts/export_tidy.py --data data --out data/tidy
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import awareness_analytics as aa  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="data/tidy")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    D = aa.load_data(args.data)
    ph, tr, people = D["phishing"], D["training"], D["people"]

    def save(df: pd.DataFrame, name: str):
        df = df.copy()
        for c in df.columns:
            if isinstance(df[c].dtype, pd.PeriodDtype):
                df[c] = df[c].astype(str)
        df.to_csv(out / name, index=False, float_format="%.5f")
        print(f"  {name:45s} {len(df):>7,} rows")

    print("writing tidy tables to", out)
    monthly = aa.monthly_rates(ph)
    save(aa.rates_long(monthly, ["month"]), "monthly_rates.csv")
    save(monthly[["month", "users", "delivered", "median_minutes_to_report", "median_low", "median_high"]],
         "monthly_time_to_report.csv")
    for by in ("department", "role_label"):
        save(aa.rates_long(aa.monthly_rates_by(ph, by), ["month", by]), f"monthly_rates_by_{by.replace('_label', '')}.csv")

    save(aa.kpis_to_frame(aa.quarter_kpis(ph, tr)), "kpi_quarterly.csv")

    fit_click = aa.fit_adjustment_model(ph, "clicked")
    fit_report = aa.fit_adjustment_model(ph, "reported")
    frames = []
    for by in ("department", "role_label"):
        for outcome, fitted in (("clicked", fit_click), ("reported", fit_report)):
            adj, _ = aa.adjusted_group_rates(ph, by, outcome, fitted=fitted)
            adj = adj.rename(columns={by: "group"})
            adj.insert(0, "group_type", by.replace("_label", ""))
            adj.insert(1, "metric", {"clicked": "click_rate", "reported": "report_rate"}[outcome])
            frames.append(adj[["group_type", "metric", "group", "users", "delivered", "mean_difficulty", "raw_rate",
                               "raw_low", "raw_high", "adjusted_rate", "adjusted_low", "adjusted_high", "rank_change",
                               "suppressed"]])
    save(pd.concat(frames, ignore_index=True), "adjusted_group_rates.csv")
    save(aa.odds_ratio_table(fit_click[0], "difficulty").assign(outcome="clicked"), "difficulty_odds_ratios.csv")
    save(aa.rates_long(aa.difficulty_curve(ph), ["difficulty"]), "rates_by_difficulty.csv")
    cell = aa.group_rates(ph, ["department", "role_label"], months=aa.POST_MONTHS)
    save(aa.rates_long(cell, ["department", "role_label"]).assign(period="2026-04 to 2026-09"),
         "rates_by_department_role_post_push.csv")

    save(aa.repeat_clickers(ph), "repeat_clickers_monthly.csv")
    save(aa.rates_long(aa.repeat_clicker_cohort_rates(ph), ["month", "cohort"]), "repeat_clicker_cohort_monthly.csv")

    save(aa.before_after(ph), "before_after_training_push.csv")
    did = aa.training_did(ph, tr)
    save(did["effects"], "training_did_effects.csv")
    save(did["cells"], "training_did_cells.csv")
    save(aa.rates_long(aa.monthly_by_training_status(ph, tr), ["month", "status"]), "monthly_rates_by_training_status.csv")
    save(aa.training_completion_summary(tr, people), "training_completion_by_department.csv")
    save(aa.training_completion_curve(tr), "training_completion_curve.csv")

    save(aa.newsletter_rates(D["newsletter"]), "newsletter_monthly.csv")
    save(aa.event_summary(D["attendance"], D["events"]), "event_attendance_summary.csv")
    save(aa.event_attendee_effect(ph, D["attendance"]), "event_attendee_report_rates.csv")
    print("done")


if __name__ == "__main__":
    main()
