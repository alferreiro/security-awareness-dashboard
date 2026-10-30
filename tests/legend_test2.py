import pathlib, subprocess
from playwright.sync_api import sync_playwright
print(subprocess.run("fc-list | wc -l; fc-match sans-serif; fc-match Inter", shell=True, capture_output=True, text=True).stdout)
p = pathlib.Path("tests/screenshots/legend/legend.html").resolve()
for channel in (None, "chromium"):
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
            pg = b.new_page(viewport={"width": 700, "height": 1300})
            pg.goto(f"file://{p}"); pg.wait_for_timeout(3000)
            boxes = pg.evaluate("""() => Array.from(document.querySelectorAll('.plotly-graph-div')).slice(0,1).map(d => Array.from(d.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width)]}))""")
            widths = pg.evaluate("""() => Array.from(document.querySelectorAll('.legend .legendtext')).slice(0,3).map(t => t.getBBox().width)""")
            print(channel, "legend trace boxes (x,y,w):", boxes, "text widths:", widths)
            pg.screenshot(path=f"tests/screenshots/legend/legend_{channel}.png", full_page=True)
            b.close()
    except Exception as e:
        print(channel, "ERR", str(e)[:300])
