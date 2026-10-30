"""
awareness_plots.py -- Plotly figure builders with one shared, colorblind-safe style.

Palette: the first slots of a validated categorical palette (blue, orange, aqua,
yellow) that clear deuteranopia / protanopia / tritanopia separation checks; one-hue
blue ramp for magnitudes. Fonts follow presentation sizes (ticks >= 14 pt, axis
titles >= 16 pt, chart titles >= 18 pt, legend >= 14 pt).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

CLICK = "#2a78d6"      # blue  - clicked / slot 1
REPORT = "#eb6834"     # orange - reported / slot 2
THIRD = "#1baf7a"      # aqua  - slot 3
FOURTH = "#eda100"     # yellow - slot 4
GRAY = "#8a8984"
MUTED = "#c3c2b7"
GRID = "#ebeae6"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
SEQ_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
            "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
GOOD = "#0ca30c"
BAD = "#d03b3b"

FONT = dict(family="Inter, 'Segoe UI', Helvetica, Arial, sans-serif", size=14, color=TEXT)


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def base_layout(fig: go.Figure, title: str, subtitle: str | None = None, ytitle: str = "", xtitle: str = "",
                y_pct: bool = True, legend: bool = True, height: int | None = None, wrap: int = 62) -> go.Figure:
    """Shared layout. Long titles are wrapped at `wrap` characters so a finding is never clipped."""
    import textwrap
    t_lines = textwrap.wrap(title, wrap) or [title]
    s_lines = textwrap.wrap(subtitle, int(wrap * 1.45)) if subtitle else []
    t = "<b>" + "<br>".join(t_lines) + "</b>"
    if s_lines:
        t += f"<br><span style='font-size:14px;color:{TEXT2}'>" + "<br>".join(s_lines) + "</span>"
    top = 40 + 24 * len(t_lines) + 19 * len(s_lines)
    n_leg = sum(1 for tr in fig.data if tr.showlegend is not False) if legend else 0
    many = n_leg >= 3                      # legend wraps to two rows: leave room under the x axis
    leg_y, bottom = (-0.42, 96) if many else (-0.28, 56)
    fig.update_layout(
        template="plotly_white", font=FONT, paper_bgcolor="white", plot_bgcolor="white",
        title=dict(text=t, font=dict(size=18, color=TEXT), x=0, xanchor="left", y=1, yanchor="top", pad=dict(t=12)),
        margin=dict(l=60, r=24, t=top, b=bottom), autosize=True, height=height,
        hovermode="x unified", hoverlabel=dict(font=dict(size=14), bgcolor="white"),
        legend=dict(orientation="h", yanchor="top", y=leg_y, xanchor="left", x=0, font=dict(size=14),
                    title=None) if legend else dict(),
        showlegend=legend,
    )
    fig.update_xaxes(title=dict(text=xtitle, font=dict(size=16)), tickfont=dict(size=14), showgrid=False,
                     linecolor=GRID, zeroline=False, showline=True)
    fig.update_yaxes(title=dict(text=ytitle, font=dict(size=16)), tickfont=dict(size=14), gridcolor=GRID,
                     gridwidth=1, zeroline=False, showline=False,
                     tickformat=".0%" if y_pct else None, rangemode="tozero")
    return fig


def add_ci_line(fig: go.Figure, x, y, lo, hi, name: str, color: str, hover_fmt: str = ".1%", dash=None,
                show_ci=True, legendgroup=None):
    if show_ci:
        fig.add_trace(go.Scatter(x=list(x) + list(x)[::-1], y=list(hi) + list(lo)[::-1], fill="toself",
                                 fillcolor=_rgba(color, 0.16), line=dict(color="rgba(0,0,0,0)"),
                                 hoverinfo="skip", showlegend=False, name=f"{name} 95% CI",
                                 legendgroup=legendgroup or name))
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=name, legendgroup=legendgroup or name,
                             line=dict(color=color, width=2.5, dash=dash), marker=dict(size=8, color=color,
                             line=dict(color="white", width=2)),
                             hovertemplate=f"%{{y:{hover_fmt}}}<extra>{name}</extra>"))
    return fig


def add_event_markers(fig: go.Figure, events: pd.DataFrame, y_top: float = 1.0):
    """Vertical reference lines for program milestones, labelled at the top.
    Events outside the x-range of the plotted data are skipped."""
    styles = {"training_launch": (THIRD, "solid"), "awareness_month": (FOURTH, "solid"),
              "newsletter_special": (GRAY, "dot"), "training_due": (THIRD, "dot")}
    xs = [pd.Timestamp(x) for tr in fig.data if tr.x is not None for x in tr.x]
    if xs:
        lo, hi = min(xs) - pd.Timedelta(days=20), max(xs) + pd.Timedelta(days=20)
        events = events[(pd.to_datetime(events["date"]) >= lo) & (pd.to_datetime(events["date"]) <= hi)]
    for i, (_, ev) in enumerate(events.sort_values("date").iterrows()):
        color, dash = styles.get(ev["event_type"], (GRAY, "dot"))
        x = ev["date"]
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, xref="x", yref="paper",
                      line=dict(color=color, width=1.5, dash=dash), layer="below")
        fig.add_annotation(x=x, y=1.0 - 0.07 * (i % 3), xref="x", yref="paper", text=ev["label"],
                           showarrow=False, xanchor="left", xshift=4, font=dict(size=12, color=TEXT2),
                           bgcolor="rgba(255,255,255,0.85)")
    return fig


def add_shaded_period(fig: go.Figure, start, end, label: str, color: str = FOURTH):
    fig.add_vrect(x0=start, x1=end, fillcolor=_rgba(color, 0.10), line_width=0, layer="below",
                  annotation_text=label, annotation_position="top left",
                  annotation=dict(font=dict(size=12, color=TEXT2)))
    return fig


def dumbbell(df: pd.DataFrame, label_col: str, raw="raw_rate", adj="adjusted_rate",
             adj_lo="adjusted_low", adj_hi="adjusted_high", title="", subtitle=None,
             raw_name="Raw rate", adj_name="Adjusted rate (same template mix for every group)",
             reference: float | None = None, reference_label: str = "") -> go.Figure:
    d = df.sort_values(adj, ascending=True)
    labels = d[label_col].tolist()
    fig = go.Figure()
    for lab, r, a in zip(labels, d[raw], d[adj]):
        fig.add_trace(go.Scatter(x=[r, a], y=[lab, lab], mode="lines", line=dict(color=MUTED, width=3),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d[raw], y=labels, mode="markers", name=raw_name,
                             marker=dict(size=11, color="white", line=dict(color=GRAY, width=2.5)),
                             hovertemplate="%{y}<br>raw %{x:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d[adj], y=labels, mode="markers", name=adj_name,
                             marker=dict(size=12, color=CLICK, line=dict(color="white", width=2)),
                             error_x=dict(type="data", symmetric=False, array=d[adj_hi] - d[adj],
                                          arrayminus=d[adj] - d[adj_lo], color=_rgba(CLICK, 0.6), thickness=2),
                             hovertemplate="%{y}<br>adjusted %{x:.1%}<extra></extra>"))
    if reference is not None:
        fig.add_vline(x=reference, line=dict(color=GRAY, width=1.5, dash="dot"),
                      annotation_text=reference_label, annotation_position="top",
                      annotation=dict(font=dict(size=12, color=TEXT2)))
    base_layout(fig, title, subtitle, xtitle="Click rate", y_pct=False)
    fig.update_xaxes(tickformat=".0%", gridcolor=GRID, showgrid=True)
    fig.update_yaxes(tickfont=dict(size=14), automargin=True, rangemode="normal")
    fig.update_layout(hovermode="closest", margin=dict(l=10, r=24, b=90))
    return fig


def bar_ci(df: pd.DataFrame, x: str, y: str, lo: str, hi: str, title: str, subtitle=None, color=CLICK,
           xtitle="", ytitle="", y_pct=True, orientation="v", text_fmt=".1%") -> go.Figure:
    fig = go.Figure()
    err = dict(type="data", symmetric=False, array=df[hi] - df[y], arrayminus=df[y] - df[lo],
               color=_rgba(TEXT, 0.45), thickness=1.5, width=4)
    if orientation == "v":
        fig.add_trace(go.Bar(x=df[x], y=df[y], marker_color=color, error_y=err, width=0.55,
                             text=[f"{v:{text_fmt}}" for v in df[y]], textposition="outside",
                             textfont=dict(size=14, color=TEXT2), hovertemplate="%{x}<br>%{y:.1%}<extra></extra>"))
    else:
        fig.add_trace(go.Bar(y=df[x], x=df[y], marker_color=color, error_x=err, orientation="h", width=0.55,
                             text=[f"{v:{text_fmt}}" for v in df[y]], textposition="outside",
                             textfont=dict(size=14, color=TEXT2), hovertemplate="%{y}<br>%{x:.1%}<extra></extra>"))
    base_layout(fig, title, subtitle, xtitle=xtitle, ytitle=ytitle, y_pct=(y_pct and orientation == "v"), legend=False)
    if orientation == "h":
        fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=GRID)
        fig.update_yaxes(automargin=True, rangemode="normal")
    fig.update_layout(hovermode="closest", bargap=0.35)
    return fig


def heatmap(piv: pd.DataFrame, title: str, subtitle=None, fmt=".0%", colorbar_title="Rate",
            suppressed: pd.DataFrame | None = None) -> go.Figure:
    """`suppressed`: same shape as piv, True where a cell exists but is hidden (n<10).
    Missing cells with no such group show a dash; suppressed cells say 'n<10'."""
    z = piv.to_numpy(dtype=float)
    text = np.vectorize(lambda v: "" if np.isnan(v) else f"{v:{fmt}}")(z).astype(object)
    if suppressed is not None:
        sup = suppressed.reindex(index=piv.index, columns=piv.columns).fillna(False).to_numpy(dtype=bool)
        text = np.where(np.isnan(z) & sup, "n<10", np.where(np.isnan(z), "\u2014", text))
    else:
        text = np.where(np.isnan(z), "\u2014", text)
    fig = go.Figure(go.Heatmap(z=z, x=list(piv.columns), y=list(piv.index), colorscale=SEQ_BLUE,
                               text=text, texttemplate="%{text}", textfont=dict(size=14),
                               hoverongaps=False, xgap=2, ygap=2,
                               colorbar=dict(title=dict(text=colorbar_title, side="right"), tickformat=".0%",
                                             tickfont=dict(size=14), thickness=14),
                               hovertemplate="%{y} / %{x}<br>%{text}<extra></extra>"))
    base_layout(fig, title, subtitle, y_pct=False, legend=False)
    fig.update_xaxes(side="top", showgrid=False)
    fig.update_yaxes(showgrid=False, automargin=True, rangemode="normal", autorange="reversed")
    fig.update_layout(hovermode="closest", margin=dict(l=230, r=24, b=24))
    return fig


def kpi_tiles_html(kpis, synthetic_note=True) -> str:
    """Stat tiles: label, big value, signed delta vs named period (green/red by direction x up-is-good)."""
    cards = []
    for k in kpis:
        if k.fmt == "pct":
            val = f"{100 * k.current:.1f}%"
            delta = f"{100 * k.change:+.1f} pts"
        else:
            val = f"{k.current:.0f} min"
            delta = f"{k.change:+.0f} min"
        if k.improved is None:
            cls, arrow, word = "flat", "&#8596;", "no change"
        elif k.improved:
            cls, arrow, word = "good", ("&#9650;" if k.change > 0 else "&#9660;"), "better"
        else:
            cls, arrow, word = "bad", ("&#9650;" if k.change > 0 else "&#9660;"), "worse"
        cards.append(
            f'<div class="kpi"><div class="kpi-label">{k.label}</div>'
            f'<div class="kpi-value">{val}</div>'
            f'<div class="kpi-delta {cls}"><span class="kpi-arrow" aria-hidden="true">{arrow}</span> '
            f'{delta} vs {k.prior_period} <span class="kpi-word">({word})</span></div>'
            f'<div class="kpi-period">{k.current_period}</div></div>')
    return '<div class="kpi-row">' + "".join(cards) + "</div>"
