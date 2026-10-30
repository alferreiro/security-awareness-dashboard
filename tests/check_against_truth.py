"""Compare dashboard estimates with the generator's hidden truth (synthetic data only)."""
import sys; sys.path.insert(0, "scripts")
import pandas as pd, numpy as np, awareness_analytics as aa
D = aa.load_data("data"); ph = D["phishing"]
lat = pd.read_csv("data/synthetic_latents.csv").set_index("user_id")
piv = ph.pivot_table(index="user_id", columns="month", values="clicked", aggfunc="max").fillna(0)
for m in ("2025-09", "2026-02", "2026-09"):
    cols = [c for c in piv.columns if c <= pd.Period(m, freq="M")][-6:]
    flagged = piv.index[piv[cols].sum(axis=1) >= 3]
    truth = lat.loc[flagged, "latent_repeat_clicker"]
    n_true_total = int(lat["latent_repeat_clicker"].sum())
    print(f"{m}: flagged={len(flagged)}  of which true repeat clickers={int(truth.sum())} ({truth.mean():.0%}); "
          f"true repeat clickers caught={truth.sum()/n_true_total:.0%} of {n_true_total}")
res, df = aa.fit_adjustment_model(ph, "clicked")
print(aa.odds_ratio_table(res, "difficulty").round(2).to_string())
print("implied logit per step:", np.round(np.log(aa.odds_ratio_table(res, "difficulty")["odds_ratio"].to_numpy()) / np.arange(1, 5), 3), "(simulated: 0.45)")
