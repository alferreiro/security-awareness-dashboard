# Interview guide: walking through the dashboard

A page-by-page script, the question each page answers, the one chart to point at, and the
follow-up questions an interviewer is likely to ask. Numbers are from the synthetic data.

## The 30-second framing

"This is a reporting layer for a security awareness program. It takes the kind of export you
get from KnowBe4 or Proofpoint, plus training, newsletter and event data, and answers four
questions: where are we, which way are we moving, who needs help, and did our interventions
work. It is built so a non-technical dean can read the titles and get the story, and so an
analyst can trust the numbers: every rate has a confidence interval, department comparisons
are adjusted for how hard the test was, and no breakdown ever shows fewer than ten people.
The data are synthetic, generated with a fixed seed so the whole thing rebuilds identically,
and I documented every assumption so you can see exactly what I planted and whether the
analysis finds it."

## Overview page

**Say:** "Four numbers leadership asks for, each with its change against last quarter and a
colour that says whether the change is good. Click rate is down about a point, report rate is
up four, reports arrive four minutes faster, and training completion rose to 79 %. The trend
chart beneath is the whole story in one picture: clicks and reports were flat for the first
year, October's awareness month gave a short bump, and the March training push produced a
lasting change: report rate roughly doubled and click rate halved."

**Point at:** the "reports per click" bar chart. "I like this ratio because it is the attacker's
odds. In early 2025 roughly one person reported for every one who clicked. Now four report for
every click, which means a real phish gets flagged long before most people would have opened
it."

**Likely questions**
- *Why is click rate not the headline?* Because it depends on how hard the lure was and it will
  never reach zero. Report rate and time-to-report measure whether the organisation can stop an
  attack in progress. (See README.)
- *What is the confidence band?* A 95 % Wilson interval on each monthly rate. With ~7,800
  people a month it is tight, about ±0.7 points, so the month-to-month wiggle in the chart is
  mostly real variation in templates, not noise.

## Trends page

**Say:** "Same series over the full period, with every program milestone drawn on the chart:
the annual training in July, awareness month in October with its newsletter special issue,
the March training push and its due date. The third line is credential entry, the outcome
that actually hurts. Below, the newsletter panel shows opens jumping from 35 % to 43 % for the
two special issues, and the difficulty panel shows average template difficulty rising from 2.6
to 3.4. That last chart is why the Groups and Effectiveness pages adjust for difficulty: the raw
click rate understates how much better people got."

**Point at:** the awareness-month zoom. "The October events produced a real spike in reporting,
31 %, that faded to 24 % within a month. Training produced the lasting change. That is a useful
thing to tell a program manager: events raise attention, training changes behaviour."

**Likely questions**
- *How do you know the bump was the events and not the newsletter?* I do not, from this data;
  they happened together. I say "awareness month" as a package. Separating them would need
  staggered timing or a randomised invitation.

## Groups page

**Say:** "This is the page that avoids unfair comparisons. Clinical and research units get
role-targeted lures, fake EHR password resets and grant-portal notices, which are harder.
So every department rate is shown twice: hollow circle is the raw rate, filled circle is the
rate adjusted by a logistic regression that holds template difficulty, role and month constant.
Engineering looks like a problem on raw numbers and drops four places once you account for
the lures it received. Student Affairs and Facilities move the other way. Three units sit
above the university average even after adjustment, and those are the ones I would plan
targeted work with."

**Point at:** the heat map. "Eight cells say n<10. Those groups exist, but they are too small
to show without identifying people. The suppression is in one function that every table goes
through, so a new chart cannot accidentally leak a small group."

**Likely questions**
- *Explain the adjustment in plain terms.* Imagine every department had been sent exactly the
  same mix of emails. The model predicts what each one's click rate would have been in that
  world. That is the adjusted rate. (Technical name: marginal standardisation or g-computation.)
- *Why logistic regression and not a mixed model?* A mixed model with a random intercept per
  person is the textbook choice and I would use it in R with lme4. For a dashboard that
  re-renders on every push I used a fixed-effects logistic GLM with standard errors clustered by
  person, which gives the population-averaged rates a department comparison needs and fits in
  seconds. The two agree on the ranking. (Details in METHODS.md §2.)
- *What does the adjustment not fix?* Anything not in the data: workload, mail filtering
  differences, who was on leave.

## Effectiveness page

**Say:** "Three questions, in increasing rigour. First, before versus after the training push:
clicks fell 35 % and reports rose 53 %; adjusted for difficulty, the odds of a click fell 45 %.
Second, repeat clickers, the people most likely to cause an incident: 447 people had clicked
three of the last six simulations in February; by September it was 201, and the cohort's own
click rate fell from 60 % to 20 %. Third, and this is the one I would defend hardest: does
completing training predict lower clicking? People who complete training are safer to begin
with, so I used a difference-in-differences design, comparing each group to its own pre-March
baseline. Completers went from 12.9 % to 6.7 %; non-completers from 15.8 % to 14.0 %. The
interaction odds ratio is 0.54, so training roughly halves the odds of clicking over and above
the general improvement everyone got from the newsletters."

**Point at:** the "tracked together until March, then split" chart. "This is the parallel-trends
check. The two lines move together for eleven months and then separate exactly at the
intervention. If they had been diverging before March, the design would not be valid."

**Likely questions**
- *Is this causal?* It is the strongest observational claim the data support. Completion was
  voluntary, so it is the effect on people who chose to complete; it may not transfer to those
  who did not. A randomised rollout, assigning training to departments in random order, would
  settle it and is cheap to run.
- *Why exclude late completers?* They were partly treated during the post window. Including
  them as untreated would dilute the estimate; including them as treated would mis-date their
  exposure. A staggered-adoption version that dates each person from their own completion is
  the natural extension.
- *Why fix the repeat-clicker cohort in February?* Selecting people on recent bad luck and then
  watching them improve is regression to the mean. Fixing the cohort before the intervention
  and following them both directions avoids that.
- *How good is the "3 of 6" rule?* Honest answer: not very precise at these base rates. Because
  the data are synthetic I could check against the truth: only about a quarter of flagged
  people are the planted habitual clickers, and the rule catches under half of them. The
  count is still a useful program-level trend, but I would not use the flag to target
  individuals. With real data I would move to an empirical-Bayes estimate of each person's click
  propensity, which borrows strength across people and gives a probability rather than a
  yes/no. Being able to say that is one reason I generated the data myself.

## Methods & data page

**Say:** "The methods page is the audit trail: what the data are, how every number is
computed, the privacy rules, and the campaign catalogue. The repository has a DATA.md listing
every parameter I used to generate the data, so you can check that the analysis finds what
was planted: the fitted difficulty odds ratios recover the simulated effect, and the detected
repeat-clicker count matches the planted 3 % plus expected noise."

## How I would update it

"Monthly. Export from the platform, hash the email addresses before the file leaves the secure
environment, map the columns, append the new rows, add any new milestone to the events file,
push. The workflow regenerates the tidy tables, re-renders and publishes in about two minutes.
The analysis windows for before/after are three constants at the top of the analytics module
and move when the next intervention happens. If the data cannot live in GitHub, the same build
runs on an internal machine and the static HTML goes on an internal web server; nothing depends
on GitHub." (Full detail in UPDATING.md.)

## Questions about the build itself

- *Why Quarto?* Reproducible: the dashboard is code plus data, it renders to static HTML with
  no server, it works with Python or R, and it is reviewable in git like any other code.
- *Why Plotly?* Hover values, zoom and a table-view twin give readers a way to inspect numbers
  without reading a spreadsheet; the palette was chosen to be distinguishable under the common
  forms of colour-vision deficiency and every series is also labelled.
- *Why tidy CSV exports?* So the same dashboard can be rebuilt in Tableau Public or Power BI
  by someone who does not run Python, with the privacy suppression already applied.
- *What would you add next?* A staggered-adoption model for training; a randomised invitation
  test for events; mixed-model estimates cached offline; a "coaching queue" view that is only
  visible to the security team (counts per manager, never names); and a data-quality panel
  (delivery failures, unmapped departments) so a bad export is caught before it is published.
