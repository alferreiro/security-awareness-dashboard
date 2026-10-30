"""
awareness_analytics.py -- shared analysis layer for the Security Awareness dashboard.

Every number shown in the dashboard and every tidy CSV in data/tidy/ is produced by
a function in this file, so the Quarto pages, the Tableau/Power BI exports and the
unit checks all agree. Statistical details are explained in docs/METHODS.md.

Privacy rule: `suppress_small_groups` blanks any breakdown whose group has fewer
than MIN_GROUP_SIZE distinct people. Nothing in this module ever returns a
person-level table to the dashboard.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from patsy import build_design_matrices

MIN_GROUP_SIZE = 10
Z95 = 1.959964

ROLE_LABELS = {"faculty": "Faculty", "staff": "Staff",
               "researcher": "Researcher", "student_worker": "Student worker"}
METRIC_LABELS = {"click_rate": "Click rate", "report_rate": "Report rate",
                 "open_rate": "Open rate", "data_entry_rate": "Data-entry rate"}

TRAINING_PUSH_MODULE = "TRN-2026-PHISHDEF"
PRE_MONTHS = pd.period_range("2025-09", "2026-02", freq="M")   # 6 months before the push
POST_MONTHS = pd.period_range("2026-04", "2026-09", freq="M")  # 6 months after (March = rollout)
DID_POST_MONTHS = pd.period_range("2026-05", "2026-09", freq="M")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_data(data_dir="data") -> dict:
    d = pathlib.Path(data_dir)
    people = pd.read_csv(d / "people.csv", parse_dates=["start_date"])
    people["role_label"] = people["role"].map(ROLE_LABELS)
    ph = pd.read_csv(d / "phishing_results.csv", parse_dates=["send_date"])
    ph["month"] = ph["send_date"].dt.to_period("M")
    ph = ph.merge(people[["user_id", "department", "department_type", "role", "role_label"]],
                  on="user_id", how="left")
    training = pd.read_csv(d / "training.csv", parse_dates=["assigned_date", "due_date", "completed_date"])
    issues = pd.read_csv(d / "newsletter_issues.csv", parse_dates=["send_date"])
    newsletter = pd.read_csv(d / "newsletter.csv").merge(issues, on="issue_id")
    events = pd.read_csv(d / "events.csv", parse_dates=["event_date"])
    attendance = pd.read_csv(d / "event_attendance.csv").merge(events, on="event_id")
    program_events = pd.read_csv(d / "program_events.csv", parse_dates=["date"])
    campaigns = pd.read_csv(d / "campaigns.csv", parse_dates=["send_date"])
    templates = pd.read_csv(d / "templates.csv")
    return dict(people=people, phishing=ph, training=training, issues=issues, newsletter=newsletter,
                events=events, attendance=attendance, program_events=program_events,
                campaigns=campaigns, templates=templates)


# --------------------------------------------------------------------------- #
# Interval helpers
# --------------------------------------------------------------------------- #
def wilson_ci(k, n, z=Z95):
    """Wilson score interval for a binomial proportion (works at 0 and 1, small n)."""
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        denom = 1.0 + z ** 2 / n
        centre = (p + z ** 2 / (2.0 * n)) / denom
        half = z * np.sqrt(p * (1.0 - p) / n + z ** 2 / (4.0 * n ** 2)) / denom
    return centre - half, centre + half


def median_ci(x, z=Z95):
    """Distribution-free CI for a median from binomial order statistics."""
    x = np.sort(np.asarray(x, dtype=float))
    x = x[~np.isnan(x)]
    n = len(x)
    if n < MIN_GROUP_SIZE:
        return np.nan, np.nan, np.nan
    lo = max(int(np.floor(n / 2.0 - z * np.sqrt(n) / 2.0)), 0)
    hi = min(int(np.ceil(n / 2.0 + z * np.sqrt(n) / 2.0)), n - 1)
    return float(np.median(x)), float(x[lo]), float(x[hi])


def add_rate_cis(df: pd.DataFrame, pairs) -> pd.DataFrame:
    """pairs = [(count_col, n_col, rate_name), ...] -> adds rate, rate_low, rate_high."""
    out = df.copy()
    for k, n, name in pairs:
        out[name] = out[k] / out[n]
        out[f"{name}_low"], out[f"{name}_high"] = wilson_ci(out[k], out[n])
    return out


RATE_PAIRS = [("clicks", "delivered", "click_rate"), ("reports", "delivered", "report_rate"),
              ("opens", "delivered", "open_rate"), ("data_entered", "delivered", "data_entry_rate")]


def _agg_rates(df: pd.DataFrame, by) -> pd.DataFrame:
    d = df[df["delivered"] == 1]
    g = d.groupby(by, observed=True)
    out = g.agg(users=("user_id", "nunique"), delivered=("delivered", "size"), clicks=("clicked", "sum"),
                reports=("reported", "sum"), opens=("opened", "sum"), data_entered=("data_entered", "sum"),
                mean_difficulty=("template_difficulty", "mean")).reset_index()
    out = add_rate_cis(out, RATE_PAIRS)
    med = g["minutes_to_report"].apply(lambda s: pd.Series(median_ci(s), index=["median_minutes_to_report",
                                                                                   "median_low", "median_high"]))
    med = med.unstack().reset_index()
    return out.merge(med, on=by if isinstance(by, list) else [by], how="left")


def suppress_small_groups(df: pd.DataFrame, users_col="users", min_n=MIN_GROUP_SIZE) -> pd.DataFrame:
    """Blank every statistic for groups with fewer than `min_n` people (privacy floor)."""
    out = df.copy()
    small = out[users_col] < min_n
    out["suppressed"] = small.astype(int)
    stat_cols = [c for c in out.columns if c not in (users_col, "suppressed")
                 and pd.api.types.is_numeric_dtype(out[c]) and c not in ("month_num",)]
    key_like = {"delivered", "clicks", "reports", "opens", "data_entered"}
    for c in stat_cols:
        if c in key_like or c.endswith("_rate") or c.endswith("_low") or c.endswith("_high") \
                or c.startswith("median") or c.startswith("adjusted") or c == "mean_difficulty":
            out.loc[small, c] = np.nan
    return out


# --------------------------------------------------------------------------- #
# Monthly trends and KPIs
# --------------------------------------------------------------------------- #
def monthly_rates(ph: pd.DataFrame) -> pd.DataFrame:
    out = _agg_rates(ph, "month")
    out["month_start"] = out["month"].dt.to_timestamp()
    return out.sort_values("month").reset_index(drop=True)


def monthly_rates_by(ph: pd.DataFrame, by: str) -> pd.DataFrame:
    out = _agg_rates(ph, ["month", by])
    out["month_start"] = out["month"].dt.to_timestamp()
    return suppress_small_groups(out).sort_values(["month", by]).reset_index(drop=True)


def rates_long(df: pd.DataFrame, id_cols) -> pd.DataFrame:
    """Wide rate table -> tidy long table: one row per (ids, metric)."""
    rows = []
    for _, name in [(None, "click_rate"), (None, "report_rate"), (None, "open_rate"), (None, "data_entry_rate")]:
        k = {"click_rate": "clicks", "report_rate": "reports", "open_rate": "opens", "data_entry_rate": "data_entered"}[name]
        sub = df[id_cols + ["users", "delivered", k, name, f"{name}_low", f"{name}_high"]].copy()
        sub.columns = id_cols + ["users", "n", "k", "rate", "ci_low", "ci_high"]
        sub.insert(len(id_cols), "metric", name)
        rows.append(sub)
    return pd.concat(rows, ignore_index=True)


@dataclass
class Kpi:
    key: str
    label: str
    current: float
    prior: float
    fmt: str            # "pct" | "min" | "pct_points"
    up_is_good: bool
    current_period: str
    prior_period: str

    @property
    def change(self):
        return self.current - self.prior

    @property
    def improved(self):
        return (self.change > 0) == self.up_is_good if self.change != 0 else None


def _training_completion_asof(training: pd.DataFrame, module_id: str, asof: pd.Timestamp) -> float:
    t = training[(training["module_id"] == module_id) & (training["assigned_date"] <= asof)]
    done = (t["completed"] == 1) & (t["completed_date"] <= asof)
    return done.mean() if len(t) else np.nan


def quarter_kpis(ph: pd.DataFrame, training: pd.DataFrame) -> list[Kpi]:
    d = ph[ph["delivered"] == 1].copy()
    d["quarter"] = d["month"].dt.asfreq("Q")
    quarters = sorted(d["quarter"].unique())
    cur, prev = quarters[-1], quarters[-2]

    def stats_for(q):
        s = d[d["quarter"] == q]
        return dict(click=s["clicked"].mean(), report=s["reported"].mean(),
                    ttr=np.nanmedian(s["minutes_to_report"]),
                    training=_training_completion_asof(training, TRAINING_PUSH_MODULE, q.end_time))
    a, b = stats_for(cur), stats_for(prev)
    label = lambda q: f"Q{q.quarter} {q.year}"
    return [
        Kpi("click_rate", "Click rate", a["click"], b["click"], "pct", False, label(cur), label(prev)),
        Kpi("report_rate", "Report rate", a["report"], b["report"], "pct", True, label(cur), label(prev)),
        Kpi("median_minutes_to_report", "Median time to first report", a["ttr"], b["ttr"], "min", False,
            label(cur), label(prev)),
        Kpi("training_completion", "Training completion (Phishing Defense)", a["training"], b["training"], "pct",
            True, label(cur), label(prev)),
    ]


def kpis_to_frame(kpis: list[Kpi]) -> pd.DataFrame:
    return pd.DataFrame([dict(metric=k.key, label=k.label, current_period=k.current_period, current=k.current,
                              prior_period=k.prior_period, prior=k.prior, change=k.change,
                              up_is_good=k.up_is_good, improved=k.improved) for k in kpis])


# --------------------------------------------------------------------------- #
# Groups: raw and difficulty-adjusted rates
# --------------------------------------------------------------------------- #
def group_rates(ph: pd.DataFrame, by, months=None) -> pd.DataFrame:
    d = ph if months is None else ph[ph["month"].isin(months)]
    out = _agg_rates(d, by)
    return suppress_small_groups(out)


def _prep_model_frame(ph: pd.DataFrame, months=None) -> pd.DataFrame:
    d = ph[ph["delivered"] == 1]
    if months is not None:
        d = d[d["month"].isin(months)]
    d = d.assign(difficulty=d["template_difficulty"].astype(str), month_str=d["month"].astype(str),
                 cluster=pd.factorize(d["user_id"])[0])
    return d.reset_index(drop=True)


def fit_logistic(df: pd.DataFrame, formula: str):
    """Logistic GLM with cluster-robust (by person) standard errors."""
    model = smf.glm(formula, data=df, family=sm.families.Binomial())
    return model.fit(cov_type="cluster", cov_kwds={"groups": df["cluster"].to_numpy()})


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def standardized_rates(res, ref: pd.DataFrame, by: str, model_var: str | None = None,
                       n_draws: int = 400, seed: int = 7) -> pd.DataFrame:
    """
    G-computation / marginal standardization.
    For each level of `by`: give EVERY row in the reference population that level,
    predict with the fitted model, average the predictions. The result is the rate
    the group would have shown had it faced the overall mix of templates, months and
    roles/departments. CI = parametric bootstrap of the coefficient vector (MVN with
    the cluster-robust covariance).
    `model_var` is the column the model actually uses (e.g. 'role' when `by` is the
    display label 'role_label').
    """
    model_var = model_var or by
    rng = np.random.default_rng(seed)
    beta = res.params.to_numpy()
    draws = rng.multivariate_normal(beta, res.cov_params().to_numpy(), size=n_draws)
    design_info = res.model.data.orig_exog.design_info
    label_to_code = dict(zip(ref[by], ref[model_var]))
    rows = []
    for level in sorted(ref[by].unique()):
        tmp = ref.copy()
        tmp[model_var] = label_to_code[level]
        X = np.asarray(build_design_matrices([design_info], tmp)[0])
        point = _sigmoid(X @ beta).mean()
        sims = _sigmoid(X @ draws.T).mean(axis=0)
        rows.append({by: level, "adjusted_rate": point,
                     "adjusted_low": np.percentile(sims, 2.5), "adjusted_high": np.percentile(sims, 97.5)})
    return pd.DataFrame(rows)


ADJUSTMENT_FORMULA = "{outcome} ~ C(difficulty) + C(department) + C(role) + C(month_str)"


def fit_adjustment_model(ph: pd.DataFrame, outcome: str = "clicked"):
    """Logistic model used for all difficulty-adjusted comparisons (fit once, reuse)."""
    df = _prep_model_frame(ph)
    res = fit_logistic(df, ADJUSTMENT_FORMULA.format(outcome=outcome))
    return res, df


def adjusted_group_rates(ph: pd.DataFrame, by: str, outcome: str = "clicked", ref_months=None,
                         fitted=None) -> tuple[pd.DataFrame, object]:
    """
    Raw vs difficulty-adjusted rates for a grouping variable (department or role_label).
    Model: outcome ~ difficulty + department + role + month (all categorical), fitted on
    all delivered rows; standardized over the reference months (default: post-push).
    """
    rate_name = {"clicked": "click_rate", "reported": "report_rate"}[outcome]
    model_var = "role" if by == "role_label" else by
    ref_months = POST_MONTHS if ref_months is None else ref_months
    res, df = fitted if fitted is not None else fit_adjustment_model(ph, outcome)
    ref = df[df["month"].isin(ref_months)]
    adj = standardized_rates(res, ref, by, model_var=model_var)
    raw = group_rates(ph, by, months=ref_months)
    out = raw.merge(adj, on=by, how="left")
    out = suppress_small_groups(out)
    out["raw_rate"], out["raw_low"], out["raw_high"] = out[rate_name], out[f"{rate_name}_low"], out[f"{rate_name}_high"]
    out["rank_change"] = out["raw_rate"].rank(ascending=False) - out["adjusted_rate"].rank(ascending=False)
    return out.sort_values("adjusted_rate", ascending=False).reset_index(drop=True), res


def difficulty_curve(ph: pd.DataFrame) -> pd.DataFrame:
    """Click / report rate by template difficulty (1-5), with Wilson CIs."""
    return _agg_rates(ph, "template_difficulty").rename(columns={"template_difficulty": "difficulty"})


def odds_ratio_table(res, pattern: str) -> pd.DataFrame:
    params = res.params.filter(like=pattern)
    ci = res.conf_int().loc[params.index]
    return pd.DataFrame({"term": params.index, "odds_ratio": np.exp(params.to_numpy()),
                         "or_low": np.exp(ci[0].to_numpy()), "or_high": np.exp(ci[1].to_numpy()),
                         "p_value": res.pvalues.loc[params.index].to_numpy()})


# --------------------------------------------------------------------------- #
# Repeat clickers
# --------------------------------------------------------------------------- #
def repeat_clickers(ph: pd.DataFrame, window: int = 6, threshold: int = 3) -> pd.DataFrame:
    """
    A person is a 'repeat clicker' in month M if they clicked in >= `threshold` of the
    last `window` campaigns (including M). Returns monthly counts only (no identities).
    """
    piv = ph.pivot_table(index="user_id", columns="month", values="clicked", aggfunc="max").fillna(0)
    roll = piv.T.rolling(window, min_periods=window).sum().T
    flagged = roll >= threshold
    rows = []
    prev = None
    for m in piv.columns:
        if roll[m].isna().all():
            continue
        f = flagged[m]
        n = int(f.sum())
        new = int((f & ~prev).sum()) if prev is not None else np.nan
        exited = int((~f & prev).sum()) if prev is not None else np.nan
        rows.append(dict(month=m, month_start=m.to_timestamp(), repeat_clickers=n, population=len(piv),
                         share=n / len(piv), newly_flagged=new, no_longer_flagged=exited))
        prev = f
    return pd.DataFrame(rows)


def repeat_clicker_cohort_rates(ph: pd.DataFrame, flag_month="2026-02", window=6, threshold=3) -> pd.DataFrame:
    """Monthly click/report rate of the cohort flagged as repeat clickers as of `flag_month`
    versus everyone else. Aggregates only; the cohort is never listed."""
    piv = ph.pivot_table(index="user_id", columns="month", values="clicked", aggfunc="max").fillna(0)
    fm = pd.Period(flag_month, freq="M")
    cols = [c for c in piv.columns if c <= fm][-window:]
    cohort = piv.index[piv[cols].sum(axis=1) >= threshold]
    d = ph.assign(cohort=np.where(ph["user_id"].isin(cohort), "Repeat clickers (as of Feb 2026)", "Everyone else"))
    out = _agg_rates(d, ["month", "cohort"])
    out["month_start"] = out["month"].dt.to_timestamp()
    return suppress_small_groups(out)


# --------------------------------------------------------------------------- #
# Effectiveness: before/after and training completion
# --------------------------------------------------------------------------- #
def before_after(ph: pd.DataFrame, pre=PRE_MONTHS, post=POST_MONTHS) -> pd.DataFrame:
    """Difficulty/department/role-adjusted odds ratio for the post-push window vs the pre window."""
    d = ph[ph["month"].isin(list(pre) + list(post))]
    df = _prep_model_frame(d)
    df["post"] = df["month"].isin(post).astype(int)
    rows = []
    for outcome, name in (("clicked", "click_rate"), ("reported", "report_rate")):
        res = fit_logistic(df, f"{outcome} ~ post + C(difficulty) + C(department) + C(role)")
        orr = odds_ratio_table(res, "post").iloc[0]
        pre_k, pre_n = df.loc[df["post"] == 0, outcome].sum(), (df["post"] == 0).sum()
        post_k, post_n = df.loc[df["post"] == 1, outcome].sum(), (df["post"] == 1).sum()
        rows.append(dict(metric=name, pre_rate=pre_k / pre_n, post_rate=post_k / post_n,
                         pre_low=wilson_ci(pre_k, pre_n)[0], pre_high=wilson_ci(pre_k, pre_n)[1],
                         post_low=wilson_ci(post_k, post_n)[0], post_high=wilson_ci(post_k, post_n)[1],
                         adjusted_odds_ratio=orr["odds_ratio"], or_low=orr["or_low"], or_high=orr["or_high"],
                         p_value=orr["p_value"], pre_window=f"{pre[0]} to {pre[-1]}",
                         post_window=f"{post[0]} to {post[-1]}"))
    # time to report: medians
    pre_t = d[d["month"].isin(pre)]["minutes_to_report"]
    post_t = d[d["month"].isin(post)]["minutes_to_report"]
    m0, l0, h0 = median_ci(pre_t)
    m1, l1, h1 = median_ci(post_t)
    rows.append(dict(metric="median_minutes_to_report", pre_rate=m0, post_rate=m1, pre_low=l0, pre_high=h0,
                     post_low=l1, post_high=h1, adjusted_odds_ratio=np.nan, or_low=np.nan, or_high=np.nan,
                     p_value=np.nan, pre_window=f"{pre[0]} to {pre[-1]}", post_window=f"{post[0]} to {post[-1]}"))
    return pd.DataFrame(rows)


def training_status(training: pd.DataFrame, module_id=TRAINING_PUSH_MODULE) -> pd.DataFrame:
    t = training[training["module_id"] == module_id].copy()
    due = t["due_date"].iloc[0]
    t["status"] = np.select(
        [(t["completed"] == 1) & (t["completed_date"] <= due), t["completed"] == 1],
        ["Completed by due date", "Completed late"], default="Not completed")
    return t[["user_id", "status", "completed_date"]]


def training_did(ph: pd.DataFrame, training: pd.DataFrame, pre=PRE_MONTHS, post=DID_POST_MONTHS) -> dict:
    """
    Difference-in-differences: on-time completers vs never-completers, before vs after
    the push. Late completers (finished after the due date) are excluded so that the
    'post' window is clean. The interaction term completer x post is the estimate.
    """
    ts = training_status(training)
    keep = ts[ts["status"] != "Completed late"]
    d = ph[ph["month"].isin(list(pre) + list(post))].merge(keep, on="user_id", how="inner")
    df = _prep_model_frame(d)
    df["post"] = df["month"].isin(post).astype(int)
    df["completer"] = (df["status"] == "Completed by due date").astype(int)
    results, cells = {}, []
    for outcome, name in (("clicked", "click_rate"), ("reported", "report_rate")):
        res = fit_logistic(df, f"{outcome} ~ completer * post + C(difficulty) + C(department) + C(role)")
        row = odds_ratio_table(res, "completer:post").iloc[0]
        results[name] = dict(did_odds_ratio=row["odds_ratio"], or_low=row["or_low"], or_high=row["or_high"],
                             p_value=row["p_value"])
        for c in (0, 1):
            for p in (0, 1):
                s = df[(df["completer"] == c) & (df["post"] == p)]
                k, n = s[outcome].sum(), len(s)
                lo, hi = wilson_ci(k, n)
                cells.append(dict(metric=name, group="Completed by due date" if c else "Not completed",
                                  period="After push" if p else "Before push", users=s["user_id"].nunique(),
                                  n=n, k=k, rate=k / n, ci_low=lo, ci_high=hi))
    cells = suppress_small_groups(pd.DataFrame(cells))
    counts = ts["status"].value_counts().rename_axis("status").reset_index(name="people")
    return dict(effects=pd.DataFrame(results).T.rename_axis("metric").reset_index(), cells=cells,
                status_counts=counts, excluded_late=int((ts["status"] == "Completed late").sum()))


def monthly_by_training_status(ph: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    d = ph.merge(training_status(training), on="user_id", how="left")
    out = _agg_rates(d, ["month", "status"])
    out["month_start"] = out["month"].dt.to_timestamp()
    return suppress_small_groups(out)


def training_completion_summary(training: pd.DataFrame, people: pd.DataFrame) -> pd.DataFrame:
    t = training.merge(people[["user_id", "department", "role_label"]], on="user_id")
    g = t.groupby(["module_id", "module_name", "department"], observed=True)
    out = g.agg(users=("user_id", "nunique"), completed=("completed", "sum")).reset_index()
    out["completion_rate"] = out["completed"] / out["users"]
    out["completion_low"], out["completion_high"] = wilson_ci(out["completed"], out["users"])
    out.loc[out["users"] < MIN_GROUP_SIZE, ["completed", "completion_rate", "completion_low", "completion_high"]] = np.nan
    return out


def training_completion_curve(training: pd.DataFrame, module_id=TRAINING_PUSH_MODULE) -> pd.DataFrame:
    t = training[training["module_id"] == module_id]
    assigned = len(t)
    done = t.dropna(subset=["completed_date"]).groupby("completed_date").size().sort_index().cumsum()
    out = done.rename("cumulative_completed").reset_index().rename(columns={"completed_date": "date"})
    out["completion_rate"] = out["cumulative_completed"] / assigned
    out["assigned"] = assigned
    out["due_date"] = t["due_date"].iloc[0]
    return out


# --------------------------------------------------------------------------- #
# Newsletter and events
# --------------------------------------------------------------------------- #
def newsletter_rates(newsletter: pd.DataFrame) -> pd.DataFrame:
    g = newsletter.groupby(["issue_id", "month", "send_date", "issue_title", "special_issue"], observed=True)
    out = g.agg(sent=("user_id", "size"), opens=("opened", "sum"), clicks=("clicked", "sum")).reset_index()
    out["open_rate"] = out["opens"] / out["sent"]
    out["open_low"], out["open_high"] = wilson_ci(out["opens"], out["sent"])
    out["click_rate"] = out["clicks"] / out["sent"]
    out["click_low"], out["click_high"] = wilson_ci(out["clicks"], out["sent"])
    out["month_start"] = pd.PeriodIndex(out["month"], freq="M").to_timestamp()
    return out.sort_values("send_date").reset_index(drop=True)


def event_summary(attendance: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    g = attendance.groupby(["event_id", "event_name", "event_date", "format"], observed=True)
    out = g.agg(registered=("registered", "sum"), attended=("attended", "sum")).reset_index()
    out["show_rate"] = out["attended"] / out["registered"]
    return out.sort_values("event_date").reset_index(drop=True)


def event_attendee_effect(ph: pd.DataFrame, attendance: pd.DataFrame,
                          months=pd.period_range("2025-11", "2026-02", freq="M")) -> pd.DataFrame:
    """Report rate Nov 2025-Feb 2026 for event attendees vs non-attendees (raw, Wilson CI).
    Observational: attendees self-selected, so this is a descriptive comparison only."""
    att = set(attendance.loc[attendance["attended"] == 1, "user_id"])
    d = ph[ph["month"].isin(months)].copy()
    d["group"] = np.where(d["user_id"].isin(att), "Attended an event", "Did not attend")
    out = _agg_rates(d, "group")
    return suppress_small_groups(out)


# --------------------------------------------------------------------------- #
# Plain-language helpers for chart titles
# --------------------------------------------------------------------------- #
def pct(x, digits=1):
    return "n/a" if pd.isna(x) else f"{100 * x:.{digits}f}%"


def describe_change(new, old, up_is_good: bool, noun: str) -> str:
    """'Report rate doubled since March' style phrase for a ratio."""
    if pd.isna(new) or pd.isna(old) or old == 0:
        return f"{noun} unchanged"
    ratio = new / old
    if ratio >= 1.9:
        word = "doubled" if ratio < 2.6 else f"rose {ratio:.1f}x"
    elif ratio >= 1.15:
        word = f"rose {100 * (ratio - 1):.0f}%"
    elif ratio <= 0.55:
        word = "halved" if ratio > 0.4 else f"fell {100 * (1 - ratio):.0f}%"
    elif ratio <= 0.87:
        word = f"fell {100 * (1 - ratio):.0f}%"
    else:
        word = "held steady"
    return f"{noun} {word}"
