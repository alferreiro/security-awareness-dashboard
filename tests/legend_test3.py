import pathlib, plotly.graph_objects as go
from playwright.sync_api import sync_playwright
out = pathlib.Path("tests/screenshots/legend")
def page(js_src, leg):
    fig = go.Figure()
    for n, name in enumerate(["Click rate", "Report rate", "Entered data (credentials)"]):
        fig.add_trace(go.Scatter(x=[1,2,3], y=[1+n,2+n,3+n], mode="lines+markers", name=name))
    fig.update_layout(legend=leg, height=320, width=620, font=dict(size=14), showlegend=True, margin=dict(b=80))
    return "<html><body><script src='%s'></script>%s</body></html>" % (js_src, fig.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True}))
variants = {
  "js2_h": ("https://cdn.plot.ly/plotly-2.35.2.min.js", dict(orientation="h", yanchor="top", y=-0.2, xanchor="left", x=0)),
  "js3_h": ("https://cdn.plot.ly/plotly-3.7.0.min.js", dict(orientation="h", yanchor="top", y=-0.2, xanchor="left", x=0)),
  "js3_vbelow": ("https://cdn.plot.ly/plotly-3.7.0.min.js", dict(orientation="v", yanchor="top", y=-0.2, xanchor="left", x=0)),
}
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chromium")
    for name, (src, leg) in variants.items():
        p = out / f"{name}.html"; p.write_text(page(src, leg))
        pg = b.new_page(viewport={"width": 700, "height": 400}); pg.goto(f"file://{p.resolve()}"); pg.wait_for_timeout(3000)
        boxes = pg.evaluate("() => Array.from(document.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)]})")
        print(name, boxes); pg.screenshot(path=str(out / f"{name}.png")); pg.close()
    b.close()
