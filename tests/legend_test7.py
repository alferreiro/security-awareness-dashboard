import pathlib, threading, functools, http.server, socketserver
from playwright.sync_api import sync_playwright
site_dir = pathlib.Path("dashboard/_site").resolve()
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site_dir)))
port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
BOX = "(i) => {const d=document.querySelectorAll('.plotly-graph-div')[i]; return Array.from(d.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.width)]})}"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium"); pg = b.new_page(viewport={"width": 1600, "height": 1000})
    # hypothesis A: tester measurement broken at parse time. Check what the tester measures now.
    pg.goto(f"http://127.0.0.1:{port}/index.html"); pg.wait_for_timeout(5000)
    print("initial:", pg.evaluate(BOX, 0))
    print("tester present:", pg.evaluate("() => { const t=document.querySelector('.js-plotly-tester'); return t ? [t.getAttribute('style'), getComputedStyle(t).display, t.getBoundingClientRect().width] : null }"))
    # B: purge + newPlot with nudged legend font (new bbox cache key)
    print("nudged font:", pg.evaluate("""() => { const d=document.querySelectorAll('.plotly-graph-div')[0]; const data=d.data, layout=JSON.parse(JSON.stringify(d.layout)); layout.legend.font = Object.assign({}, layout.legend.font||{}, {size: 14.5}); Plotly.purge(d); return Plotly.newPlot(d, data, layout, {responsive:true}).then(()=>Array.from(d.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.width)]})); }"""))
    # C: fresh page, but block the inline plotly scripts until load? Instead: check timing by measuring a fresh figure drawn now
    print("fresh newPlot into new div:", pg.evaluate("""() => { const div=document.createElement('div'); div.style.width='900px'; div.style.height='400px'; document.body.appendChild(div); return Plotly.newPlot(div, [{x:[1,2],y:[1,2],name:'Click rate'},{x:[1,2],y:[2,3],name:'Report rate'}], {legend:{orientation:'h', font:{size:14, family:"Inter, 'Segoe UI', Helvetica, Arial, sans-serif"}}}).then(()=>Array.from(div.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.width)]})); }"""))
    print("fresh newPlot size 13:", pg.evaluate("""() => { const div=document.createElement('div'); div.style.width='900px'; div.style.height='400px'; document.body.appendChild(div); return Plotly.newPlot(div, [{x:[1,2],y:[1,2],name:'Click rate'},{x:[1,2],y:[2,3],name:'Report rate'}], {legend:{orientation:'h', font:{size:13, family:"Inter, 'Segoe UI', Helvetica, Arial, sans-serif"}}}).then(()=>Array.from(div.querySelectorAll('.legend .traces')).map(t => {const r=t.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.width)]})); }"""))
    b.close()
srv.shutdown()
