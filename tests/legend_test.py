import plotly.graph_objects as go, pathlib
from playwright.sync_api import sync_playwright
variants = {
 "h_default": dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0),
 "h_entrywidth": dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0, entrywidth=180, entrywidthmode="pixels"),
 "h_notitle_none": dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0, title=dict(text="")),
 "v_right": dict(orientation="v", x=1.02, y=1),
}
out = pathlib.Path("tests/screenshots/legend"); out.mkdir(exist_ok=True, parents=True)
html = ""
for name, leg in variants.items():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1,2,3], y=[1,2,3], mode="lines+markers", name="Click rate"))
    fig.add_trace(go.Scatter(x=[1,2,3], y=[2,3,4], mode="lines+markers", name="Report rate"))
    fig.add_trace(go.Scatter(x=[1,2,3], y=[3,4,5], mode="lines+markers", name="Entered data (credentials)"))
    fig.update_layout(legend=leg, title=name, height=300, width=600, font=dict(size=14), showlegend=True)
    html += fig.to_html(full_html=False, include_plotlyjs=(name=="h_default") and "cdn", config={"responsive": True})
p = out / "legend.html"; p.write_text("<html><body>"+html+"</body></html>")
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 700, "height": 1300})
    pg.goto(f"file://{p.resolve()}"); pg.wait_for_timeout(3000); pg.screenshot(path=str(out/"legend.png"), full_page=True); b.close()
print("ok")
