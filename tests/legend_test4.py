import pathlib, sys, plotly.graph_objects as go
sys.path.insert(0, "scripts"); import awareness_plots as ap
from playwright.sync_api import sync_playwright
out = pathlib.Path("tests/screenshots/legend")
def mk():
    fig = go.Figure()
    for n, name in enumerate(["Click rate", "Report rate", "Entered data (credentials)"]):
        fig.add_trace(go.Scatter(x=[1,2,3], y=[1+n,2+n,3+n], mode="lines+markers", name=name))
    return fig
variants = {}
f = mk(); ap.base_layout(f, "Title here", "subtitle", ytitle="y", height=400); variants["base_layout"] = f
f = mk(); ap.base_layout(f, "Title here", "subtitle", ytitle="y", height=400); f.update_layout(legend=dict(yanchor="top", y=-0.15)); variants["base_yanchor_top"] = f
f = mk(); ap.base_layout(f, "Title here", "subtitle", ytitle="y", height=400); f.update_layout(legend=dict(yanchor="top", y=-0.15, title=None)); f.update_layout(legend_title_text=""); variants["base_top_titleblank"] = f
f = mk(); f.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0, font=dict(size=14), title=None), height=400); variants["plain_titleNone"] = f
f = mk(); f.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0, font=dict(size=14)), height=400); variants["plain_noTitleKey"] = f
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chromium")
    for name, fig in variants.items():
        p = out / f"{name}.html"; p.write_text("<html><body>" + fig.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True}) + "</body></html>")
        pg = b.new_page(viewport={"width": 800, "height": 500}); pg.goto(f"file://{p.resolve()}"); pg.wait_for_timeout(2500)
        boxes = pg.evaluate("() => Array.from(document.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)]})")
        print(f"{name:22s}", boxes, "legend json:", fig.layout.legend.to_plotly_json()); pg.screenshot(path=str(out / f"{name}.png")); pg.close()
    b.close()
