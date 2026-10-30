#!/usr/bin/env python3
"""
generate_data.py -- SYNTHETIC security-awareness program data generator.

*** EVERYTHING THIS SCRIPT PRODUCES IS FICTIONAL. ***
"Northfield State University", its departments, people, campaigns and events do
not exist. All numbers come from a seeded pseudo-random generator driven by the
assumptions documented in DATA.md. No real person or institution is represented.

Usage
-----
    python scripts/generate_data.py --out data --seed 20251029

Outputs (CSV, one row per observation; data dictionary in DATA.md)
------------------------------------------------------------------
    people.csv               one row per member of the university community
    campaigns.csv            one row per monthly phishing simulation campaign
    templates.csv            one row per phishing template (with difficulty 1-5)
    phishing_results.csv     one row per user x campaign (KnowBe4-style export)
    training.csv             one row per user x training module assignment
    newsletter_issues.csv    one row per monthly newsletter issue
    newsletter.csv           one row per user x issue (opened / clicked)
    events.csv               one row per Cybersecurity Awareness Month event
    event_attendance.csv     one row per user x event registration
    program_events.csv       dated program milestones used for chart annotations
    synthetic_latents.csv    the generator's hidden truth (NOT available in real
                             exports; kept only so the simulation can be audited)
    generation_params.json   every numeric assumption, for reproducibility
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Fixed assumptions (all documented in DATA.md)
# --------------------------------------------------------------------------- #
UNIVERSITY = "Northfield State University (FICTIONAL)"
DEFAULT_SEED = 20251029
MONTHS = pd.period_range("2025-04", "2026-09", freq="M")  # 18 monthly campaigns

# name, headcount, type, click_offset, report_offset, training_offset
# (offsets are on the log-odds scale; 0 = average department)
DEPARTMENTS = [
    ("School of Medicine",               1400, "clinical",  0.15, -0.10, -0.50),
    ("Clinical Operations",               900, "clinical",  0.45, -0.35, -0.60),  # lags
    ("School of Nursing",                 450, "clinical",  0.05,  0.10,  0.10),
    ("Biomedical Research Institute",     700, "research",  0.20, -0.05, -0.20),
    ("College of Engineering",            800, "research",  0.00,  0.05,  0.00),
    ("College of Arts & Sciences",       1100, "academic",  0.05,  0.00,  0.00),
    ("School of Business",                400, "academic", -0.05,  0.05,  0.20),
    ("Information Technology Services",   350, "admin",    -0.80,  0.90,  0.90),
    ("Finance & Administration",          450, "admin",    -0.20,  0.25,  0.40),
    ("Student Affairs",                   500, "admin",     0.40, -0.30, -0.30),  # lags
    ("Facilities & Operations",           550, "admin",     0.55, -0.45, -0.80),  # lags
    ("Library & Academic Services",       300, "academic", -0.15,  0.20,  0.30),
]

ROLE_MIX = {  # share of each role inside a department type
    "clinical": {"faculty": 0.25, "staff": 0.55, "researcher": 0.10, "student_worker": 0.10},
    "research": {"faculty": 0.20, "staff": 0.25, "researcher": 0.40, "student_worker": 0.15},
    "academic": {"faculty": 0.35, "staff": 0.30, "researcher": 0.10, "student_worker": 0.25},
    "admin":    {"faculty": 0.01, "staff": 0.73, "researcher": 0.01, "student_worker": 0.25},  # tiny pockets -> exercise the n<10 rule
}

# click / report / training-completion / time-to-report / newsletter-open offsets
ROLE_EFFECTS = {
    "faculty":        dict(click=0.00, report=-0.25, train=-0.60, ttr=0.25, news=-0.20, event=0.00),
    "staff":          dict(click=-0.05, report=0.10, train=0.30, ttr=0.00, news=0.10, event=0.30),
    "researcher":     dict(click=0.10, report=0.00, train=-0.20, ttr=0.10, news=0.00, event=0.10),
    "student_worker": dict(click=0.35, report=-0.20, train=0.00, ttr=0.10, news=-0.40, event=-0.30),
}

# (template name, difficulty 1-5, audience)
TEMPLATES = [
    # general-audience lures
    ("Package delivery notice", 1, "general"),
    ("Survey: employee engagement", 1, "general"),
    ("Campus emergency alert update", 1, "general"),
    ("Shared document from a colleague", 2, "general"),
    ("Password expiration warning", 2, "general"),
    ("Parking citation appeal", 2, "general"),
    ("Zoom meeting recording available", 2, "general"),
    ("Conference registration refund", 2, "general"),
    ("Software license renewal", 2, "general"),
    ("HR benefits open enrollment", 3, "general"),
    ("IT help desk ticket update", 3, "general"),
    ("Microsoft 365 storage almost full", 3, "general"),
    ("Gift card request from 'the Dean'", 3, "general"),
    ("Calendar invite: performance review", 3, "general"),
    ("Voicemail transcription attached", 3, "general"),
    ("Payroll direct-deposit change", 4, "general"),
    ("Invoice approval needed", 4, "general"),
    ("DocuSign: signature requested", 4, "general"),
    ("Reply-chain from a real vendor thread", 5, "general"),
    ("MFA fatigue: 'approve this sign-in'", 5, "general"),
    # research-targeted lures (sent mostly to research-heavy units)
    ("Conference abstract accepted", 2, "research"),
    ("Lab equipment recall notice", 3, "research"),
    ("Journal reviewer invitation", 3, "research"),
    ("Core facility invoice", 4, "research"),
    ("Research computing quota exceeded", 3, "research"),
    ("NIH eRA Commons re-verification", 5, "research"),
    ("IRB protocol expiration notice", 4, "research"),
    ("Collaborator shared dataset (OneDrive)", 4, "research"),
    # clinical-targeted lures (sent mostly to clinical / HIPAA-adjacent units)
    ("Pharmacy formulary update", 2, "clinical"),
    ("Patient portal message pending", 4, "clinical"),
    ("On-call schedule change", 3, "clinical"),
    ("Telehealth platform update", 3, "clinical"),
    ("CME credits expiring", 4, "clinical"),
    ("EHR (Epic) password reset", 5, "clinical"),
    ("Credentialing document request", 4, "clinical"),
    ("HIPAA compliance attestation due", 5, "clinical"),
]

# Program milestones (also written to program_events.csv for chart annotations)
TRAINING_MODULES = [
    dict(module_id="TRN-2025-ESSENTIALS", module_name="Security Awareness Essentials (annual)",
         assigned_date="2025-07-01", due_date="2025-08-31",
         base_logit=0.55, awareness_weight=0.30, late_tail_days=75,
         click_effect=-0.15, report_effect=0.20, ttr_effect=-0.10),
    dict(module_id="TRN-2026-PHISHDEF", module_name="Phishing Defense: Recognize & Report",
         assigned_date="2026-03-02", due_date="2026-04-30",
         base_logit=1.60, awareness_weight=0.40, late_tail_days=150,
         click_effect=-0.75, report_effect=1.00, ttr_effect=-0.60),
]
TRAINING_PUSH_DATE = "2026-03-02"            # "the training push" referenced everywhere
SPILLOVER_AFTER_PUSH = dict(click=-0.10, report=0.15)   # non-completers, via comms
REPEAT_CLICKER_TRAINING_DISCOUNT = 0.20       # training helps repeat clickers a bit less

CSAM_MONTH = pd.Period("2025-10", freq="M")   # Cybersecurity Awareness Month
CSAM_EFFECT = {  # month offset from October -> (click, report, log time-to-report)
    0: (-0.35, 0.60, -0.20),
    1: (-0.20, 0.35, -0.10),
    2: (-0.10, 0.15, 0.00),
}
EVENTS = [
    ("EVT-01", "Cybersecurity Awareness Month kickoff & Phish Bowl", "2025-10-01", "in-person", "all"),
    ("EVT-02", "Lunch & Learn: Spot the Phish (live demo)",         "2025-10-07", "virtual",   "all"),
    ("EVT-03", "Password manager & MFA clinic",                       "2025-10-14", "in-person", "all"),
    ("EVT-04", "Protecting research data: faculty panel",             "2025-10-16", "virtual",   "research"),
    ("EVT-05", "Clinical phishing tabletop exercise",                 "2025-10-22", "in-person", "clinical"),
    ("EVT-06", "Report-a-Phish challenge awards",                     "2025-10-29", "virtual",   "all"),
]
EVENT_EFFECT = dict(click=-0.15, report=0.35, ttr=-0.15)

PARAMS = dict(
    university=UNIVERSITY,
    months=[str(m) for m in MONTHS],
    delivery_rate=0.985,
    repeat_clicker_share=0.03,
    repeat_clicker_click_bonus=1.60,
    repeat_clicker_report_penalty=-0.30,
    click_intercept=-2.00,
    click_difficulty_slope=0.45,
    click_awareness_slope=-0.55,
    click_secular_trend_per_month=-0.03,
    report_intercept=-1.75,
    report_difficulty_slope=-0.15,
    report_awareness_slope=0.70,
    report_secular_trend_per_month=0.02,
    report_after_click_penalty=-0.60,
    open_intercept=-0.15,
    open_difficulty_slope=0.30,
    data_entry_intercept=-0.60,
    data_entry_difficulty_slope=0.30,
    data_entry_awareness_slope=-0.30,
    ttr_median_minutes=90.0,
    ttr_log_sd=0.85,
    ttr_awareness_slope=-0.20,
    ttr_difficulty_slope=0.10,
    ttr_bounds_minutes=[1, 2880],
    targeted_template_probability={"clinical": 0.70, "research": 0.70, "academic": 0.20, "admin": 0.0},
    early_phase_months=6,
    early_phase_max_difficulty=3,
    newsletter_open_intercept=-0.65,
    newsletter_open_awareness_slope=0.45,
    newsletter_special_issue_bonus=0.35,
    newsletter_click_given_open_intercept=-1.30,
    newsletter_click_awareness_slope=0.30,
    event_registration_intercept=-3.10,
    event_registration_awareness_slope=0.50,
    event_virtual_bonus=0.30,
    event_targeted_audience_bonus=0.60,
    event_it_department_bonus=1.00,
    event_attendance_given_registration=0.72,
    csam_month=str(CSAM_MONTH),
    csam_effect=CSAM_EFFECT,
    event_effect=EVENT_EFFECT,
    training_modules=TRAINING_MODULES,
    training_push_date=TRAINING_PUSH_DATE,
    spillover_after_push=SPILLOVER_AFTER_PUSH,
    repeat_clicker_training_discount=REPEAT_CLICKER_TRAINING_DISCOUNT,
    departments=[dict(name=n, headcount=h, type=t, click_offset=c, report_offset=r, training_offset=tr)
                 for n, h, t, c, r, tr in DEPARTMENTS],
    role_mix=ROLE_MIX,
    role_effects=ROLE_EFFECTS,
)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
def make_people(rng: np.random.Generator) -> pd.DataFrame:
    frames = []
    for name, n, dtype, c, r, t in DEPARTMENTS:
        mix = ROLE_MIX[dtype]
        roles = rng.choice(list(mix), size=n, p=list(mix.values()))
        frames.append(pd.DataFrame({"department": name, "department_type": dtype, "role": roles,
                                    "_dept_click": c, "_dept_report": r, "_dept_train": t}))
    people = pd.concat(frames, ignore_index=True)
    people = people.sample(frac=1.0, random_state=int(rng.integers(1 << 30))).reset_index(drop=True)
    people.insert(0, "user_id", [f"U{100001 + i:06d}" for i in range(len(people))])
    # hidden latent traits (exported separately to synthetic_latents.csv only)
    people["_awareness"] = rng.normal(0.0, 1.0, len(people))
    people["_repeat_clicker"] = rng.random(len(people)) < PARAMS["repeat_clicker_share"]
    for k in ("click", "report", "train", "ttr", "news", "event"):
        people[f"_role_{k}"] = people["role"].map(lambda r: ROLE_EFFECTS[r][k])
    # a plausible-looking start date so the table resembles an HR feed
    tenure_days = rng.gamma(shape=1.6, scale=1500, size=len(people)).clip(30, 12000)
    people["start_date"] = (pd.Timestamp("2025-04-01") - pd.to_timedelta(tenure_days, unit="D")).date
    people["email_domain"] = "northfield-state.example"
    return people


# --------------------------------------------------------------------------- #
# Training assignments & completions
# --------------------------------------------------------------------------- #
def make_training(rng, people):
    rows = []
    for mod in TRAINING_MODULES:
        assigned = pd.Timestamp(mod["assigned_date"])
        due = pd.Timestamp(mod["due_date"])
        window = (due - assigned).days
        logit = (mod["base_logit"] + people["_dept_train"] + people["_role_train"]
                 + mod["awareness_weight"] * people["_awareness"])
        completed = rng.random(len(people)) < sigmoid(logit.to_numpy())
        # completion timing: most people finish close to the due date (Beta skewed
        # right); ~20 % of completers finish late, within late_tail_days.
        on_time = rng.random(len(people)) < 0.80
        offset_on_time = rng.beta(2.2, 1.3, len(people)) * window
        offset_late = window + rng.exponential(mod["late_tail_days"] / 3.0, len(people))
        offset = np.where(on_time, offset_on_time, offset_late).clip(0, window + mod["late_tail_days"])
        completed_date = assigned + pd.to_timedelta(np.round(offset), unit="D")
        score = np.round(rng.normal(86, 8, len(people)).clip(50, 100)).astype(int)
        rows.append(pd.DataFrame({
            "user_id": people["user_id"],
            "module_id": mod["module_id"],
            "module_name": mod["module_name"],
            "assigned_date": assigned.date(),
            "due_date": due.date(),
            "completed": completed.astype(int),
            "completed_date": np.where(completed, completed_date.date, None),
            "quiz_score": np.where(completed, score, np.nan),
        }))
    out = pd.concat(rows, ignore_index=True)
    out["completed_date"] = pd.to_datetime(out["completed_date"]).dt.date
    return out


# --------------------------------------------------------------------------- #
# Cybersecurity Awareness Month events
# --------------------------------------------------------------------------- #
def make_events(rng, people):
    events = pd.DataFrame(EVENTS, columns=["event_id", "event_name", "event_date", "format", "audience"])
    rows = []
    for _, ev in events.iterrows():
        logit = (PARAMS["event_registration_intercept"]
                 + PARAMS["event_registration_awareness_slope"] * people["_awareness"]
                 + people["_role_event"]
                 + (PARAMS["event_virtual_bonus"] if ev["format"] == "virtual" else 0.0)
                 + np.where(people["department"] == "Information Technology Services",
                            PARAMS["event_it_department_bonus"], 0.0)
                 + np.where((ev["audience"] != "all") & (people["department_type"] == ev["audience"]),
                            PARAMS["event_targeted_audience_bonus"], 0.0))
        registered = rng.random(len(people)) < sigmoid(logit.to_numpy())
        attended = registered & (rng.random(len(people)) < PARAMS["event_attendance_given_registration"])
        sub = people.loc[registered, ["user_id"]].copy()
        sub["event_id"] = ev["event_id"]
        sub["registered"] = 1
        sub["attended"] = attended[registered].astype(int)
        rows.append(sub)
    attendance = pd.concat(rows, ignore_index=True)
    return events, attendance


# --------------------------------------------------------------------------- #
# Campaigns and templates
# --------------------------------------------------------------------------- #
def make_campaigns(rng):
    templates = pd.DataFrame(TEMPLATES, columns=["template_name", "template_difficulty", "audience"])
    templates.insert(0, "template_id", [f"T{i + 1:03d}" for i in range(len(templates))])
    campaign_rows, ct_rows = [], []
    for t, month in enumerate(MONTHS):
        send_date = month.start_time + pd.Timedelta(days=int(rng.integers(4, 20)))
        cid = f"PC-{month}"
        campaign_rows.append(dict(campaign_id=cid, campaign_name=f"{month.strftime('%b %Y')} phishing simulation",
                                  month=str(month), send_date=send_date.date()))
        # early program months use easier general templates; later months use the
        # full catalogue, so average difficulty rises as the program matures.
        early = t < PARAMS["early_phase_months"]
        for aud, k in (("general", 2), ("research", 1), ("clinical", 1)):
            pool = templates[templates["audience"] == aud]
            if early:
                pool = pool[pool["template_difficulty"] <= PARAMS["early_phase_max_difficulty"]]
            pick = pool.sample(n=k, random_state=int(rng.integers(1 << 30)))
            for _, tp in pick.iterrows():
                ct_rows.append(dict(campaign_id=cid, template_id=tp["template_id"]))
    campaigns = pd.DataFrame(campaign_rows)
    campaign_templates = pd.DataFrame(ct_rows).merge(templates, on="template_id")
    return campaigns, templates, campaign_templates


# --------------------------------------------------------------------------- #
# Phishing simulation results (one row per user x campaign)
# --------------------------------------------------------------------------- #
def make_phishing(rng, people, campaigns, campaign_templates, training, attendance, events):
    n = len(people)
    P = PARAMS
    # per-user completion dates by module
    comp = {}
    for mod in TRAINING_MODULES:
        sub = training[training["module_id"] == mod["module_id"]].set_index("user_id")
        comp[mod["module_id"]] = pd.to_datetime(sub.loc[people["user_id"], "completed_date"]).to_numpy()
    # first attended event date per user
    att = attendance[attendance["attended"] == 1].merge(events[["event_id", "event_date"]], on="event_id")
    first_event = att.groupby("user_id")["event_date"].min()
    first_event = pd.to_datetime(people["user_id"].map(first_event)).to_numpy()

    aware = people["_awareness"].to_numpy()
    repeat = people["_repeat_clicker"].to_numpy()
    dept_c, dept_r = people["_dept_click"].to_numpy(), people["_dept_report"].to_numpy()
    role_c, role_r, role_ttr = (people["_role_click"].to_numpy(), people["_role_report"].to_numpy(),
                                people["_role_ttr"].to_numpy())
    dtype = people["department_type"].to_numpy()
    push = np.datetime64(TRAINING_PUSH_DATE)

    out = []
    for t, (_, camp) in enumerate(campaigns.iterrows()):
        send = np.datetime64(pd.Timestamp(camp["send_date"]))
        month = pd.Period(camp["month"], freq="M")
        ct = campaign_templates[campaign_templates["campaign_id"] == camp["campaign_id"]]
        general = ct[ct["audience"] == "general"]
        targeted = {a: ct[ct["audience"] == a] for a in ("research", "clinical")}

        # --- template assignment: targeted lure with department-type probability
        p_target = np.array([P["targeted_template_probability"][d] for d in dtype])
        use_target = rng.random(n) < p_target
        aud_pref = np.where(np.isin(dtype, ["clinical"]), "clinical",
                            np.where(np.isin(dtype, ["research", "academic"]), "research", "general"))
        tid = general["template_id"].to_numpy()[rng.integers(0, len(general), n)].astype(object)
        for a in ("research", "clinical"):
            mask = use_target & (aud_pref == a)
            pool = targeted[a]["template_id"].to_numpy()
            tid[mask] = pool[rng.integers(0, len(pool), mask.sum())]
        diff = pd.Series(tid).map(ct.set_index("template_id")["template_difficulty"]).to_numpy().astype(float)
        d3 = diff - 3.0

        # --- time-varying program effects
        csam_k = (month - CSAM_MONTH).n
        csam_c, csam_r, csam_ttr = CSAM_EFFECT.get(csam_k, (0.0, 0.0, 0.0))
        doneA = comp["TRN-2025-ESSENTIALS"] < send
        doneB = comp["TRN-2026-PHISHDEF"] < send
        post_push = send >= push
        modA, modB = TRAINING_MODULES
        disc = 1.0 - REPEAT_CLICKER_TRAINING_DISCOUNT
        train_c = (modA["click_effect"] * doneA
                   + np.where(doneB, modB["click_effect"] * np.where(repeat, disc, 1.0),
                              np.where(post_push, SPILLOVER_AFTER_PUSH["click"], 0.0)))
        train_r = (modA["report_effect"] * doneA
                   + np.where(doneB, modB["report_effect"] * np.where(repeat, disc, 1.0),
                              np.where(post_push, SPILLOVER_AFTER_PUSH["report"], 0.0)))
        train_ttr = modA["ttr_effect"] * doneA + np.where(doneB, modB["ttr_effect"], 0.0)
        ev_done = first_event < send

        # --- outcomes
        delivered = rng.random(n) < P["delivery_rate"]
        logit_click = (P["click_intercept"] + dept_c + role_c + P["click_difficulty_slope"] * d3
                       + P["click_awareness_slope"] * aware + P["repeat_clicker_click_bonus"] * repeat
                       + P["click_secular_trend_per_month"] * t + csam_c + train_c
                       + EVENT_EFFECT["click"] * ev_done)
        clicked = delivered & (rng.random(n) < sigmoid(logit_click))
        opened = clicked | (delivered & (rng.random(n) < sigmoid(P["open_intercept"] + P["open_difficulty_slope"] * d3)))
        data_entered = clicked & (rng.random(n) < sigmoid(P["data_entry_intercept"] + P["data_entry_difficulty_slope"] * d3
                                                           + P["data_entry_awareness_slope"] * aware))
        logit_report = (P["report_intercept"] + dept_r + role_r + P["report_difficulty_slope"] * d3
                        + P["report_awareness_slope"] * aware + P["repeat_clicker_report_penalty"] * repeat
                        + P["report_secular_trend_per_month"] * t + csam_r + train_r
                        + EVENT_EFFECT["report"] * ev_done + P["report_after_click_penalty"] * clicked)
        reported = delivered & (rng.random(n) < sigmoid(logit_report))
        log_med = (np.log(P["ttr_median_minutes"]) + P["ttr_awareness_slope"] * aware + role_ttr
                   + csam_ttr + train_ttr + EVENT_EFFECT["ttr"] * ev_done + P["ttr_difficulty_slope"] * d3)
        minutes = np.exp(log_med + P["ttr_log_sd"] * rng.normal(0, 1, n))
        minutes = np.clip(minutes, *P["ttr_bounds_minutes"]).round(1)
        minutes = np.where(reported, minutes, np.nan)

        out.append(pd.DataFrame({
            "user_id": people["user_id"],
            "campaign_id": camp["campaign_id"],
            "campaign_name": camp["campaign_name"],
            "send_date": camp["send_date"],
            "template_id": tid,
            "template_difficulty": diff.astype(int),
            "delivered": delivered.astype(int),
            "opened": opened.astype(int),
            "clicked": clicked.astype(int),
            "data_entered": data_entered.astype(int),
            "reported": reported.astype(int),
            "minutes_to_report": minutes,
        }))
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- #
# Monthly newsletter
# --------------------------------------------------------------------------- #
NEWSLETTER_TITLES = [
    "Welcome to Secure Northfield",                      # 2025-04
    "Why we run phishing simulations",                   # 2025-05
    "Travel safely this summer",                         # 2025-06
    "Spot the fake login page",                          # 2025-07
    "Back-to-campus device checklist",                   # 2025-08
    "Last call: Security Essentials training",           # 2025-09
    "Cybersecurity Awareness Month special issue",       # 2025-10 (special)
    "Holiday shopping scams",                            # 2025-11
    "Year in review: what you reported",                 # 2025-12
    "New year, new passwords",                           # 2026-01
    "Tax-season scams targeting employees",              # 2026-02
    "Phishing Defense training launches this month",     # 2026-03 (special)
    "How to report a phish in one click",                # 2026-04
    "Protecting patient information",                    # 2026-05
    "Research data: sharing without oversharing",        # 2026-06
    "Summer travel & public Wi-Fi",                      # 2026-07
    "AI-generated phishing: what changed",               # 2026-08
    "Quarterly results: we are reporting faster",        # 2026-09
]
SPECIAL_ISSUES = {"2025-10", "2026-03"}


def make_newsletter(rng, people):
    P = PARAMS
    issues = pd.DataFrame({
        "issue_id": [f"NL-{m}" for m in MONTHS],
        "month": [str(m) for m in MONTHS],
        "send_date": [(m.start_time + pd.Timedelta(days=int(rng.integers(1, 7)))).date() for m in MONTHS],
        "issue_title": NEWSLETTER_TITLES,
        "special_issue": [int(str(m) in SPECIAL_ISSUES) for m in MONTHS],
    })
    aware = people["_awareness"].to_numpy()
    role_news = people["_role_news"].to_numpy()
    rows = []
    for _, iss in issues.iterrows():
        bonus = P["newsletter_special_issue_bonus"] * iss["special_issue"]
        post = 0.10 if iss["month"] >= "2026-03" else 0.0
        p_open = sigmoid(P["newsletter_open_intercept"] + P["newsletter_open_awareness_slope"] * aware + role_news + bonus + post)
        opened = rng.random(len(people)) < p_open
        p_click = sigmoid(P["newsletter_click_given_open_intercept"] + P["newsletter_click_awareness_slope"] * aware + bonus)
        clicked = opened & (rng.random(len(people)) < p_click)
        rows.append(pd.DataFrame({"user_id": people["user_id"], "issue_id": iss["issue_id"],
                                  "opened": opened.astype(int), "clicked": clicked.astype(int)}))
    return issues, pd.concat(rows, ignore_index=True)


def make_program_events():
    rows = [
        dict(date="2025-07-01", event_type="training_launch", label="Annual Essentials training assigned"),
        dict(date="2025-10-01", event_type="awareness_month", label="Cybersecurity Awareness Month (6 events)"),
        dict(date="2025-10-06", event_type="newsletter_special", label="Newsletter special issue: Awareness Month"),
        dict(date=TRAINING_PUSH_DATE, event_type="training_launch", label="Training push: Phishing Defense assigned"),
        dict(date="2026-03-04", event_type="newsletter_special", label="Newsletter special issue: training launch"),
        dict(date="2026-04-30", event_type="training_due", label="Phishing Defense due date"),
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data", help="output directory")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    people = make_people(rng)
    training = make_training(rng, people)
    events, attendance = make_events(rng, people)
    campaigns, templates, campaign_templates = make_campaigns(rng)
    phishing = make_phishing(rng, people, campaigns, campaign_templates, training, attendance, events)
    issues, newsletter = make_newsletter(rng, people)
    program_events = make_program_events()

    public_cols = ["user_id", "department", "department_type", "role", "start_date", "email_domain"]
    people[public_cols].to_csv(out / "people.csv", index=False)
    people[["user_id", "_awareness", "_repeat_clicker"]].rename(
        columns={"_awareness": "latent_awareness", "_repeat_clicker": "latent_repeat_clicker"}
    ).to_csv(out / "synthetic_latents.csv", index=False, float_format="%.4f")
    campaigns.merge(
        campaign_templates.groupby("campaign_id")
        .agg(templates=("template_id", lambda s: "|".join(s)), mean_difficulty=("template_difficulty", "mean"))
        .reset_index(), on="campaign_id",
    ).to_csv(out / "campaigns.csv", index=False, float_format="%.2f")
    templates.to_csv(out / "templates.csv", index=False)
    phishing.to_csv(out / "phishing_results.csv", index=False, float_format="%.1f")
    training.to_csv(out / "training.csv", index=False, float_format="%.0f")
    issues.to_csv(out / "newsletter_issues.csv", index=False)
    newsletter.to_csv(out / "newsletter.csv", index=False)
    events.to_csv(out / "events.csv", index=False)
    attendance.to_csv(out / "event_attendance.csv", index=False)
    program_events.to_csv(out / "program_events.csv", index=False)
    with open(out / "generation_params.json", "w") as fh:
        json.dump(dict(seed=args.seed, **PARAMS), fh, indent=2, default=str)

    # quick sanity summary
    d = phishing[phishing["delivered"] == 1]
    print(f"people: {len(people):,}  campaigns: {len(campaigns)}  phishing rows: {len(phishing):,}")
    print("overall click rate: %.3f  report rate: %.3f  median minutes to report: %.0f"
          % (d["clicked"].mean(), d["reported"].mean(), d["minutes_to_report"].median()))
    print(training.groupby("module_id")["completed"].mean().round(3).to_string())
    print("newsletter open rate: %.3f  event attendees: %d"
          % (newsletter["opened"].mean(), attendance.loc[attendance["attended"] == 1, "user_id"].nunique()))
    print(d.groupby(d["send_date"].astype(str).str[:7])[["clicked", "reported"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
