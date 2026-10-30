# Statistical methods

This note explains every statistic on the dashboard, why it was chosen, and what it cannot
tell you. The code for all of it is in `scripts/awareness_analytics.py`; the dashboard pages
and the tidy exports call the same functions.

## 1. Rates and their confidence intervals

**Definition.** Click rate = clicks ÷ delivered emails, per month (or per group). Report
rate, open rate and credential-entry rate are defined the same way. Undelivered emails are
excluded from the denominator.

**Wilson score interval.** Each rate carries a 95 % Wilson interval rather than the textbook
normal ("Wald") interval. Wilson behaves correctly when the rate is near 0 or 1 and when the
sample is small, both of which happen in department breakdowns. With ~7,800 delivered emails
a month the interval on a 10 % click rate is about ±0.7 points; for a 300-person department
in a single month it is about ±3.5 points, which is why month-by-department charts are
noisy and the Groups page pools six months.

**Medians.** The median time to first report uses a distribution-free interval from binomial
order statistics: the 95 % interval runs from the ⌊n/2 − 0.98√n⌋-th to the ⌈n/2 + 0.98√n⌉-th
sorted value. It needs no assumption about the shape of the time distribution, which is
heavily right-skewed.

**A caveat on independence.** Wilson intervals assume independent trials. The same 7,900 people
are tested 18 times, so observations within a person are correlated. For the monthly rates this
barely matters (each month is one trial per person). For pooled multi-month rates the
intervals are slightly too narrow; the regression models below address this with clustered
standard errors, and the tidy export documents it.

## 2. Difficulty-adjusted comparisons (Groups page)

**The problem.** Clinical and research units receive role-targeted lures that are harder on
average (mean difficulty ≈ 3.6–3.9 versus ≈ 3.0 for admin units). Comparing raw click rates
would partly measure who was tested harder.

**The model.** A logistic regression, fitted to every delivered email in the 18 months:

```
logit P(clicked) = β0 + β_difficulty[1..5] + β_department[12] + β_role[4] + β_month[18]
```

All terms are categorical. Difficulty is categorical rather than linear because the platform's
1–5 scale is ordinal, not interval; the fitted odds ratios (≈ 1.6, 2.3, 3.5, 5.1 for levels 2–5
versus level 1) show that the effect is not linear. The same model is fitted for
`reported`.

**Standard errors are clustered by person** (Huber-White sandwich with person as the cluster).
Each person contributes 18 rows that share unobserved traits, so naïve standard errors would
be too small by roughly a factor of 1.5–2 for person-level predictors like department.

**Marginal standardisation (g-computation).** A coefficient on "Clinical Operations" is a log
odds ratio relative to a reference department, which is hard to read. Instead the dashboard
reports an *adjusted rate*: take every row in the reference period (the six months after the
training push), set everyone's department to Clinical Operations while keeping their actual
template difficulty, role and month, predict the click probability from the model, and
average. Repeat for every department. The result answers: "what would this department's click
rate have been if it had faced the same mix of templates, roles and months as everyone
else?" It is on the same percentage scale as the raw rate and can be plotted beside it.

**Interval for the adjusted rate.** Parametric bootstrap: draw 400 coefficient vectors from a
multivariate normal with mean = the fitted coefficients and covariance = the clustered
covariance matrix, recompute the standardised rate for each draw, and take the 2.5th and
97.5th percentiles. This propagates uncertainty from all coefficients, not only the
department term.

**Why not a mixed model?** A logistic mixed model with a random intercept per person
(`clicked ~ difficulty + department + role + month + (1 | user)`) is the textbook alternative
and would be my choice in R (`lme4::glmer`) or with `statsmodels.BinomialBayesMixedGLM`. It
estimates the same fixed effects, plus the between-person variance, which is itself
interesting (how much of clicking is "who you are" versus "what you were sent"). Its drawbacks
here are computational (140,000 rows × 7,900 random effects is slow to fit on every render)
and interpretive (mixed-model coefficients are *conditional* on the random effect, so the
standardised rates would need an extra integration step). The fixed-effects GLM with clustered
standard errors gives population-averaged estimates directly, which is what a department
comparison needs. If the dashboard were refreshed monthly rather than on every push, the mixed
model could be fitted offline and its predictions cached.

**What the adjustment does not fix.** It cannot adjust for things that are not in the data:
workload, email volume, whether a unit's mailbox has stricter filtering, or who was on leave.
It also assumes the department effect is the same at every difficulty level (no interaction);
that can be tested by adding `department × difficulty` and was not needed for the synthetic data.

## 3. Before/after the training push (Effectiveness page)

**Design.** Six months before the launch (September 2025 to February 2026) versus six months
after (April to September 2026). March, the rollout month, is excluded because people
completed training throughout it. A logistic regression with a `post` indicator plus the same
difficulty, department and role controls (clustered by person) gives an adjusted odds ratio of
about 0.55 for clicking and 1.9 for reporting.

**Why adjust a before/after comparison at all?** Because templates got harder over time. The
raw click rate fell 35 %; after holding difficulty constant, the odds of a click fell 45 %. Without
the adjustment the program would under-report its own progress.

**Limitations.** This is an interrupted-time-series design with one interruption and no control
group. It shows that things improved after March; it cannot separate the training from anything
else that changed at the same time (a new email filter, a news story, seasonal differences).
The "before" window contains the October Awareness Month bump, which makes the estimate
conservative. A fuller version would fit a segmented regression with a level change and a
slope change at March and report both; with 18 months the slope terms are poorly identified,
so the dashboard keeps the simpler two-window comparison and says so.

## 4. Does training completion predict lower clicking? (difference-in-differences)

**The selection problem.** People who complete training by the due date are more
security-minded to begin with (in the synthetic data, by construction; in real data, almost
certainly). A plain comparison of completers and non-completers after the push would credit the
training with a difference that existed before it.

**The design.** Compare each group with its own pre-push baseline:

```
logit P(clicked) = β0 + β1·completer + β2·post + β3·(completer × post) + difficulty + department + role
```

`β3` is the difference-in-differences: the change in completers' log odds minus the change in
non-completers' log odds. Its exponential (≈ 0.54 for clicking, ≈ 2.3 for reporting) is the
estimate of the training's effect on the people who took it. "Completer" means completed by
the 30 April due date; "post" is May to September. The 1,192 late completers are excluded
because they are neither clearly treated nor clearly untreated during the post window; a
sensitivity analysis could instead date each person's exposure from their own completion
date (a staggered-adoption design).

**The key assumption, and how to check it.** Parallel trends: absent training, the two groups'
click rates would have moved in parallel. The chart "Completers and non-completers tracked
together until March, then split" is the visual check; the two lines move together for eleven
months before diverging. The non-completers' own small improvement after March (15.8 % to
14.0 %) is the spillover from newsletters and general attention, and the design correctly
removes it from the training estimate.

**What it still cannot do.** Completion was voluntary, so β3 is the effect *on completers*, not
the effect training would have on the people who did not take it. Those may be exactly the
people a program most needs to reach. The honest claim is "training completion is associated
with roughly halving the odds of clicking, over and above the general improvement."

## 5. Repeat clickers

A person is a repeat clicker in month M if they clicked in at least 3 of the 6 campaigns
ending in M. The definition is applied every month, so the chart shows a rolling count. Only
counts are shown; the list of people stays with the security team.

**Precision of the rule, checked against the generator's truth.** Three-of-six is the rule many
programs use, and it is deliberately simple. It is not very precise when base rates are above
10 %: with a 13 % click rate an ordinary person has roughly a 3–4 % chance of three clicks in
six campaigns by bad luck alone, and with 7,600 ordinary people that is about 270 false
flags. In the synthetic data only about 23 % of the ~450 people flagged in early 2026 are the
planted habitual clickers, and the rule catches about 44 % of them. The trend is still
informative (the count falls 55 % after training, and the flagged cohort's own click rate falls
from 60 % to 20 %), but anyone using the flag to *target* individuals should know that most
flagged people are not habitual. Better options, in order of effort: raise the threshold to
4 of 6 (fewer false flags, fewer true ones caught); use a longer window; or estimate each
person's click propensity with an empirical-Bayes (beta-binomial) shrinkage model and flag
people whose posterior probability exceeds a cut-off. The last is the approach I would take
with real data and is a natural extension of this repository.

The cohort chart fixes the group as of February 2026 and follows those same people forward
and backward. Fixing the cohort *before* the intervention avoids the regression-to-the-mean
trap of selecting people on their recent bad luck and then observing that they improve.

## 6. Awareness Month events

Attendance was voluntary, so attendees versus non-attendees is reported descriptively only.
A causal estimate would need a randomised invitation (invite a random half, compare the
halves) or at least an adjustment for prior behaviour; both are reasonable next steps.

## 7. Privacy floor

Every group-level table passes through `suppress_small_groups`, which blanks statistics for
groups with fewer than 10 distinct people. The rule applies before anything is plotted or
exported. Ten is a common threshold in institutional reporting; it is a parameter
(`MIN_GROUP_SIZE`) and can be raised.

## 8. Reproducibility and validation

- The generator is seeded; the Actions workflow regenerates the data on every build and
  compares the files byte for byte.
- `tests/smoke_analytics.py` runs every analysis function and prints its outputs.
- Because `synthetic_latents.csv` holds the true person-level traits, the estimates can be
  checked against the truth: the fitted difficulty odds ratios recover the +0.45 logit per
  step that was simulated (fitted ≈ 0.41–0.47 per step), and the repeat-clicker check in §5
  comes from the same comparison (`tests/check_against_truth.py`).
