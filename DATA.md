# DATA.md — the synthetic data and every assumption behind it

**Everything in `data/` is synthetic.** It was produced by `scripts/generate_data.py` with
seed `20251029` and describes a fictional institution, *Northfield State University*. The
goal was realism in *structure* (the columns a real platform export has) and in *patterns*
(effects an analyst should be able to find), not fidelity to any real university. The
exact numeric values of every parameter are also written to `data/generation_params.json`
when the generator runs.

## 1. Population

| Assumption | Value |
|---|---|
| People | 7,900 |
| Departments | 12 (table below) |
| Roles | faculty, staff, researcher, student worker |
| Role mix | depends on department type: clinical 25/55/10/10 %, research 20/25/40/15 %, academic 35/30/10/25 %, admin 1/73/1/25 % (faculty/staff/researcher/student) |
| Start date | gamma-distributed tenure, cosmetic only |
| Churn | none (no hires or departures over the 18 months; a simplification) |

| Department | Headcount | Type | Click offset | Report offset | Training offset | Story |
|---|---|---|---|---|---|---|
| School of Medicine | 1,400 | clinical | +0.15 | -0.10 | -0.50 | large, busy, HIPAA-adjacent |
| Clinical Operations | 900 | clinical | +0.45 | -0.35 | -0.60 | **lagging unit** |
| School of Nursing | 450 | clinical | +0.05 | +0.10 | +0.10 | |
| Biomedical Research Institute | 700 | research | +0.20 | -0.05 | -0.20 | research-heavy, grant lures |
| College of Engineering | 800 | research | 0.00 | +0.05 | 0.00 | research-heavy |
| College of Arts & Sciences | 1,100 | academic | +0.05 | 0.00 | 0.00 | |
| School of Business | 400 | academic | -0.05 | +0.05 | +0.20 | |
| Information Technology Services | 350 | admin | -0.80 | +0.90 | +0.90 | best performer |
| Finance & Administration | 450 | admin | -0.20 | +0.25 | +0.40 | |
| Student Affairs | 500 | admin | +0.40 | -0.30 | -0.30 | **lagging unit** |
| Facilities & Operations | 550 | admin | +0.55 | -0.45 | -0.80 | **lagging unit** |
| Library & Academic Services | 300 | academic | -0.15 | +0.20 | +0.30 | |

Offsets are on the log-odds (logit) scale; 0 is an average department. The 1 % faculty and
researcher share in admin units exists only to create a few groups smaller than 10 people, so
the privacy-suppression rule is exercised.

Role offsets (click / report / training completion / log time-to-report / newsletter open):
faculty 0 / -0.25 / -0.60 / +0.25 / -0.20; staff -0.05 / +0.10 / +0.30 / 0 / +0.10;
researcher +0.10 / 0 / -0.20 / +0.10 / 0; student worker +0.35 / -0.20 / 0 / +0.10 / -0.40.

## 2. Hidden person-level traits

Each person gets two latent traits that drive every outcome. They are **not** part of a real
export and are written only to `data/synthetic_latents.csv` so the simulation can be audited.

| Trait | Distribution | Effect |
|---|---|---|
| `latent_awareness` | Normal(0, 1) | lowers clicking (slope -0.55), raises reporting (+0.70), raises newsletter opens (+0.45), raises training completion (+0.30 / +0.40), shortens time to report (-0.20 on the log scale) |
| `latent_repeat_clicker` | 3 % of people | +1.60 on the click logit, -0.30 on the report logit; training helps them 20 % less |

Because awareness affects both training completion and clicking, the data contain a genuine
**selection effect**: completers were already safer before training. This is deliberate; it is
why the Effectiveness page uses a difference-in-differences design rather than a simple
completer-versus-non-completer comparison.

## 3. Phishing simulations

- 18 monthly campaigns, April 2025 to September 2026, sent to everyone on a random day
  between the 5th and 20th of the month. 98.5 % of emails are delivered.
- 36 templates with a fixed difficulty 1–5 (`data/templates.csv`): 20 general, 8 research-
  targeted (mean 3.5), 8 clinical-targeted (mean 3.75). Each campaign draws 2 general, 1
  research and 1 clinical template. **In the first 6 months only templates of difficulty ≤ 3 are
  used**, so average difficulty rises as the program matures (from about 2.6 to 3.4).
- Template assignment: clinical units receive the clinical lure with probability 0.70, research
  units the research lure with probability 0.70, academic units the research lure with
  probability 0.20, admin units general lures only. This is what makes the difficulty
  adjustment on the Groups page matter.

Outcome models (logit scale, `d3 = difficulty - 3`, `t` = months since April 2025):

```
click    = -2.00 + dept + role + 0.45·d3 − 0.55·awareness + 1.60·repeat − 0.03·t
           + CSAM_click + training_click − 0.15·attended_event
opened   = clicked OR Bernoulli(sigmoid(−0.15 + 0.30·d3))
entered  = clicked AND Bernoulli(sigmoid(−0.60 + 0.30·d3 − 0.30·awareness))
report   = -1.75 + dept + role − 0.15·d3 + 0.70·awareness − 0.30·repeat + 0.02·t
           + CSAM_report + training_report + 0.35·attended_event − 0.60·clicked
minutes  = exp( ln 90 − 0.20·awareness + role_ttr + 0.10·d3 + CSAM_ttr + training_ttr
           − 0.15·attended_event + 0.85·N(0,1) ), clipped to 1–2,880 min, only if reported
```

## 4. Program effects built into the data

| Effect | Implementation |
|---|---|
| **Training push (March 2026)** | Module *Phishing Defense: Recognize & Report* assigned 2 March 2026, due 30 April. Completion probability sigmoid(1.60 + dept + role + 0.40·awareness) ≈ 79 %. After a person's completion date: click logit −0.75, report logit +1.00, time-to-report −0.60 (log scale). Non-completers get a small spillover after launch (click −0.10, report +0.15) because the newsletter and comms reach everyone. |
| **Annual Essentials training (July 2025)** | Assigned 1 July, due 31 August, completion ≈ 59 %. Smaller effects: click −0.15, report +0.20, time-to-report −0.10. |
| **Cybersecurity Awareness Month (October 2025)** | October: click −0.35, report +0.60, time-to-report −0.20; November half of that; December a quarter. Six events; registration probability sigmoid(−3.1 + 0.5·awareness + role + 0.3 if virtual + 0.6 if the event targets the person's unit type + 1.0 if IT); 72 % of registrants attend. Attending any event: click −0.15, report +0.35 thereafter. |
| **Harder templates get more clicks** | +0.45 logit per difficulty step (odds ratio ≈ 1.6 per step, ≈ 5 for difficulty 5 vs 1). |
| **Lagging departments** | Clinical Operations, Facilities & Operations, Student Affairs (offsets above). |
| **Repeat clickers** | 3 % latent group; the dashboard *detects* them from behaviour (≥ 3 clicks in the last 6 campaigns) rather than reading the latent flag. |
| **Secular trend** | −0.03 click logit and +0.02 report logit per month, representing general maturation. |

Training completion timing: 80 % of completers finish inside the assignment window with a
Beta(2.2, 1.3) shape (most finish close to the due date); 20 % finish late with an exponential
tail (up to 75 days for Essentials, 150 days for Phishing Defense, which is why completion
still creeps up through September 2026).

## 5. Newsletter and events

- 18 monthly issues. Open probability sigmoid(−0.65 + 0.45·awareness + role + 0.35 if special
  issue + 0.10 after March 2026); click-through given open sigmoid(−1.30 + 0.30·awareness + 0.30
  if special). Special issues: October 2025 and March 2026.
- Six Awareness Month events in October 2025 (`data/events.csv`), about 2,000 unique attendees.

## 6. Simplifications you would not see in real data

- No staff turnover, leave, or new-hire onboarding assignments.
- Everyone receives every campaign (real programs often sample or stagger).
- One template per person per campaign; no re-sends.
- Reporting and clicking are independent draws given the person's traits; in reality a report
  often *follows* a click ("I clicked, then realised").
- Time to report is lognormal with a fixed spread; real distributions are heavier-tailed.
- Department and role effects are constant over time.

## 7. Data dictionary

**people.csv** — `user_id`, `department`, `department_type` (clinical/research/academic/admin), `role`, `start_date`, `email_domain`.

**campaigns.csv** — `campaign_id`, `campaign_name`, `month`, `send_date`, `templates` (pipe-separated template ids), `mean_difficulty`.

**templates.csv** — `template_id`, `template_name`, `template_difficulty` (1–5), `audience` (general/research/clinical).

**phishing_results.csv** (one row per person × campaign, 142,200 rows) — `user_id`, `campaign_id`, `campaign_name`, `send_date`, `template_id`, `template_difficulty`, `delivered`, `opened`, `clicked`, `data_entered`, `reported` (0/1), `minutes_to_report` (blank unless reported).

**training.csv** (one row per person × module) — `user_id`, `module_id`, `module_name`, `assigned_date`, `due_date`, `completed`, `completed_date`, `quiz_score`.

**newsletter_issues.csv** — `issue_id`, `month`, `send_date`, `issue_title`, `special_issue`. **newsletter.csv** — `user_id`, `issue_id`, `opened`, `clicked`.

**events.csv** — `event_id`, `event_name`, `event_date`, `format`, `audience`. **event_attendance.csv** — `user_id`, `event_id`, `registered`, `attended`.

**program_events.csv** — `date`, `event_type` (training_launch / awareness_month / newsletter_special / training_due), `label`; used for chart annotations.

**synthetic_latents.csv** — `user_id`, `latent_awareness`, `latent_repeat_clicker` (generator truth; never used by the dashboard).

**generation_params.json** — every parameter above, as run.

**tidy/** — see `docs/UPDATING.md` §4 for the list of tidy tables and their columns.
