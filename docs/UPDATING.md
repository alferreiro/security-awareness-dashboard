# Updating the dashboard

The dashboard is a pipeline, not a document: CSV files in `data/` go in, statistics are
computed by `scripts/awareness_analytics.py`, and Quarto renders `dashboard/index.qmd` to a
static site that GitHub Actions publishes. Updating it means replacing or extending the CSVs
and pushing.

## 1. Monthly refresh with real data (the routine)

1. **Export** the latest phishing campaign results, training completions, newsletter stats and
   event attendance from the platforms.
2. **Pseudonymise.** Replace email addresses with a salted hash (`user_id`) *before* the files
   leave the secure environment. Keep the salt with the security team, not in the repository.
3. **Map columns** to the shapes in `DATA.md` §7. A small `scripts/import_<platform>.py`
   (not included; it depends on the export) is the natural place for this.
4. **Append** the new month's rows to `data/phishing_results.csv`, `data/training.csv`,
   `data/newsletter.csv` and `data/event_attendance.csv`. Add new campaigns to
   `data/campaigns.csv` and new templates to `data/templates.csv`.
5. **Record milestones.** Add any new training launch, special newsletter or awareness event to
   `data/program_events.csv`; the Trends page annotates them automatically.
6. **Check the analysis windows.** `PRE_MONTHS`, `POST_MONTHS` and `DID_POST_MONTHS` at the top of
   `scripts/awareness_analytics.py` define the before/after and difference-in-differences
   windows; `TRAINING_PUSH_MODULE` names the module they refer to. Move these when the next
   major intervention happens. The quarter-over-quarter tiles find the last two complete
   quarters on their own.
7. **Run locally** (`bash scripts/build.sh`) and open `dashboard/_site/index.html`, or push to
   `main` and let the workflow render and publish. The build takes about two minutes.

If the real data live somewhere that cannot be committed to git (the usual case), run the
build on an internal machine and publish `_site/` to an internal web server or SharePoint
instead of GitHub Pages; nothing in the Quarto project depends on GitHub.

## 2. Adding a chart

1. Add a function to `awareness_analytics.py` that returns a tidy DataFrame and passes it
   through `suppress_small_groups` if it has a group column.
2. Add a figure builder to `awareness_plots.py` or reuse one (`add_ci_line`, `bar_ci`,
   `dumbbell`, `heatmap`).
3. Add a code cell to the relevant `dashboard/_page.qmd` with a title that states the finding,
   computed from the data (see `describe_change`).
4. Add the DataFrame to `export_tidy.py` so the Tableau/Power BI copy stays complete.
5. Add a line to `tests/smoke_analytics.py`.

## 3. Changing the rules

- **Privacy threshold:** `MIN_GROUP_SIZE` in `awareness_analytics.py`.
- **Repeat-clicker definition:** `repeat_clickers(window=6, threshold=3)`.
- **Adjustment model:** `ADJUSTMENT_FORMULA`. To add an interaction or a new covariate (campus,
  for instance), change the formula and make sure the column exists in `people.csv`.
- **Colours and fonts:** constants at the top of `awareness_plots.py`.
- **Pages and layout:** `dashboard/index.qmd` includes one `_page.qmd` per page; Quarto's
  `## Row` / `### Column` headings control the grid.

## 4. Tidy exports for Tableau Public / Power BI

`python scripts/export_tidy.py` writes these files to `data/tidy/`:

| File | One row per | Key columns |
|---|---|---|
| monthly_rates.csv | month × metric | n, k, rate, ci_low, ci_high |
| monthly_time_to_report.csv | month | median_minutes_to_report, median_low, median_high |
| monthly_rates_by_department.csv, monthly_rates_by_role.csv | month × group × metric | as above + suppressed |
| kpi_quarterly.csv | KPI | current, prior, change, improved |
| adjusted_group_rates.csv | group_type × metric × group | raw_rate, adjusted_rate and intervals, rank_change |
| difficulty_odds_ratios.csv, rates_by_difficulty.csv | difficulty level | odds_ratio / rate with intervals |
| rates_by_department_role_post_push.csv | department × role × metric | rate, intervals, suppressed |
| repeat_clickers_monthly.csv, repeat_clicker_cohort_monthly.csv | month (× cohort) | counts, rates |
| before_after_training_push.csv, training_did_effects.csv, training_did_cells.csv | comparison | rates, odds ratios, intervals |
| monthly_rates_by_training_status.csv, training_completion_by_department.csv, training_completion_curve.csv | month × status / department / date | rates and intervals |
| newsletter_monthly.csv, event_attendance_summary.csv, event_attendee_report_rates.csv | issue / event / group | rates and counts |

Rates are fractions (0.123 = 12.3 %). Suppressed rows keep their key columns with blank
statistics and `suppressed = 1`, so a BI tool shows the gap rather than a zero.

## 5. Automating the refresh

The GitHub Actions workflow runs on every push to `main` and on manual dispatch. For a
monthly cadence add a `schedule:` trigger (`cron: "0 6 2 * *"`, the 2nd of each month) and a
first step that pulls the export from wherever it lands (an S3 bucket, a SharePoint folder via
Graph API, or a platform API such as KnowBe4's reporting API). The render and deploy steps
do not change.
