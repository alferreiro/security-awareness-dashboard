"""Screenshot every dashboard page with headless Chromium, served over HTTP so Quarto's module scripts load."""
import pathlib, sys, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright
site_dir = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
class Quiet(Handler.func):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site_dir)))
port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
JS_BOX = "() => Array.from(document.querySelectorAll('.plotly-graph-div')).slice(0,3).map(d => Array.from(d.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.width)]}))"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium")
    pg = b.new_page(viewport={"width": 1600, "height": 1000})
    errs = []; pg.on("console", lambda m: errs.append(m.text[:120]) if m.type == "error" else None)
    pg.goto(f"http://127.0.0.1:{port}/index.html"); pg.wait_for_timeout(5000)
    tabs = pg.locator('a[data-bs-toggle="tab"]'); n = tabs.count(); print("pages:", n)
    for i in range(n):
        t = tabs.nth(i); name = t.get_attribute("href").lstrip("#")
        t.click(); pg.wait_for_timeout(3000)
        pg.screenshot(path=str(out / f"{i+1}_{name}.png"), full_page=True); print("saved", name)
    print("legend boxes (first 3 figs):", pg.evaluate(JS_BOX))
    print("plotly:", pg.evaluate("() => Plotly.version"), "| console errors:", errs[:4])
    b.close()
srv.shutdown()
