import pathlib
from playwright.sync_api import sync_playwright
site = pathlib.Path("dashboard/_site/index.html").resolve()
JS_BOX = "() => {const d=document.querySelectorAll('.plotly-graph-div')[0]; return Array.from(d.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width)]})}"
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chromium"); pg = b.new_page(viewport={"width": 1600, "height": 1000})
    msgs = []; pg.on("console", lambda m: msgs.append(m.text[:150]))
    pg.goto(f"file://{site}"); pg.wait_for_timeout(4000)
    print("initial:", pg.evaluate(JS_BOX))
    print("widths:", pg.evaluate("() => Array.from(document.querySelectorAll('.plotly-graph-div')[0].querySelectorAll('.legend .legendtext')).map(t=>t.getBBox().width)"))
    pg.evaluate("() => { const d=document.querySelectorAll('.plotly-graph-div')[0]; return Plotly.relayout(d, {}); }"); pg.wait_for_timeout(1000)
    print("after relayout:", pg.evaluate(JS_BOX))
    pg.evaluate("() => { const d=document.querySelectorAll('.plotly-graph-div')[0]; return Plotly.relayout(d, {'legend.orientation':'h'}); }"); pg.wait_for_timeout(1000)
    print("after relayout orientation:", pg.evaluate(JS_BOX))
    print("plotly version:", pg.evaluate("() => Plotly.version"))
    print("legend layout:", pg.evaluate("() => JSON.stringify(document.querySelectorAll('.plotly-graph-div')[0]._fullLayout.legend)")[:400])
    print("console:", msgs[:5])
    b.close()
