import pathlib, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright
site_dir = pathlib.Path("dashboard/_site").resolve()
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site_dir)))
port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
BOX = "() => {const d=document.querySelectorAll('.plotly-graph-div')[0]; return Array.from(d.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.width)]})}"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium"); pg = b.new_page(viewport={"width": 1600, "height": 1000})
    pg.goto(f"http://127.0.0.1:{port}/index.html"); pg.wait_for_timeout(5000)
    print("initial:", pg.evaluate(BOX))
    print("fullLayout.legend subset:", pg.evaluate("() => {const l=document.querySelectorAll('.plotly-graph-div')[0]._fullLayout.legend; return JSON.stringify({o:l.orientation, x:l.x, y:l.y, w:l._width, h:l._height, ew:l.entrywidth, ewm:l.entrywidthmode, iw:l.itemwidth, mw:l._maxWidth})}"))
    print("div size/style:", pg.evaluate("() => {const d=document.querySelectorAll('.plotly-graph-div')[0]; return [d.clientWidth, d.clientHeight, d.getAttribute('style'), d.parentElement.className]}"))
    print("legendtext bbox widths:", pg.evaluate("() => Array.from(document.querySelectorAll('.plotly-graph-div')[0].querySelectorAll('.legend .legendtext')).map(t=>[t.getBBox().width, t.getBoundingClientRect().width, getComputedStyle(t).fontFamily])"))
    pg.evaluate("() => {const d=document.querySelectorAll('.plotly-graph-div')[0]; return Plotly.react(d, d.data, d.layout, {responsive:true});}"); pg.wait_for_timeout(1500)
    print("after react:", pg.evaluate(BOX))
    pg.evaluate("() => {const d=document.querySelectorAll('.plotly-graph-div')[0]; return Plotly.relayout(d, {'legend.entrywidth': 150, 'legend.entrywidthmode':'pixels'});}"); pg.wait_for_timeout(1500)
    print("after entrywidth:", pg.evaluate(BOX))
    # test: is a plain page with bootstrap css affected?
    b.close()
srv.shutdown()
