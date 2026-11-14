"""Responsive UI audit using installed Chrome/Edge and Python standard library.

python tests/ui-browser.py [--screenshots] [--normal-motion] [--motion-checks] [--home-checks]
Screenshots/reports use a temporary directory; no browser data or mock files change.
"""
import base64
import functools
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class CDP:
    def __init__(self, url):
        u = urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\n'
                           f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        header = b''
        while not header.endswith(b'\r\n\r\n'):
            header += self.sock.recv(1)
        if not header.startswith(b'HTTP/1.1 101 '):
            raise RuntimeError('WebSocket handshake failed')
        self.seq = 0
        self.errors = []

    def read(self, n):
        data = b''
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise RuntimeError('Browser disconnected')
            data += chunk
        return data

    def send(self, data):
        data = json.dumps(data).encode()
        mask = os.urandom(4)
        n = len(data)
        length = bytes([0x80 | n]) if n < 126 else b'\xfe' + struct.pack('!H', n) if n < 65536 else b'\xff' + struct.pack('!Q', n)
        self.sock.sendall(b'\x81' + length + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(data)))

    def receive(self):
        first, second = self.read(2)
        n = second & 127
        if n == 126:
            n = struct.unpack('!H', self.read(2))[0]
        elif n == 127:
            n = struct.unpack('!Q', self.read(8))[0]
        mask = self.read(4) if second & 128 else None
        data = self.read(n)
        if mask:
            data = bytes(v ^ mask[i % 4] for i, v in enumerate(data))
        if first & 15 == 8:
            raise RuntimeError('Browser closed WebSocket')
        return json.loads(data)

    def call(self, method, **params):
        self.seq += 1
        ident = self.seq
        self.send({'id': ident, 'method': method, 'params': params})
        while True:
            msg = self.receive()
            if msg.get('method') == 'Runtime.exceptionThrown':
                self.errors.append(msg['params']['exceptionDetails'].get('exception', {}).get('description', msg['params']['exceptionDetails']['text']))
            if msg.get('method') == 'Runtime.consoleAPICalled' and msg['params']['type'] == 'error':
                self.errors.append('console.error: ' + ' '.join(str(a.get('description', a.get('value', ''))) for a in msg['params']['args']))
            if msg.get('id') == ident:
                if 'error' in msg:
                    raise RuntimeError(msg['error'])
                return msg.get('result', {})

    def js(self, expression):
        result = self.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def until(self, expression):
        for _ in range(150):
            try:
                if self.js(expression):
                    return
            except RuntimeError:
                pass
            time.sleep(.08)
        raise RuntimeError('Page readiness timeout: ' + expression)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass  # Page navigation can cancel outstanding image requests.


METRICS = """(() => {
  const width=document.documentElement.clientWidth;
  const overflow=[...document.querySelectorAll('body *')].filter(e=>{
    const r=e.getBoundingClientRect(), s=getComputedStyle(e);
    return r.width && r.height && s.visibility!=='hidden' && (r.right>width+1 || r.left< -1) && !e.closest('dialog:not([open])');
  }).slice(0,12).map(e=>({tag:e.tagName,id:e.id,cls:e.className,right:Math.round(e.getBoundingClientRect().right)}));
  return {width:innerWidth,clientWidth:width,scrollWidth:document.documentElement.scrollWidth,overflow,
    inline:document.querySelectorAll('[style]').length,
    headings:[...document.querySelectorAll('h1')].map(e=>e.textContent.trim())};
})()"""

INTERACTIONS = """(() => {
  const checks=[];
  const check=(ok,name)=>{if(!ok)throw Error('UI interaction: '+name);checks.push(name);};
  const click=s=>document.querySelector(s)?.click();
  const submit=s=>document.querySelector(s)?.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  const toggle=document.querySelector('.nav-toggle');
  if(toggle && getComputedStyle(toggle).display!=='none'){
    toggle.click();check(toggle.getAttribute('aria-expanded')==='true','mobile menu opens');
    toggle.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    check(toggle.getAttribute('aria-expanded')==='false','mobile menu closes with Escape');
  }
  if(location.pathname.endsWith('/profile.html')){
    const input=document.querySelector('#profile-form [name=display_name]');const old=input.value;
    input.value='';submit('#profile-form');check(input.getAttribute('aria-invalid')==='true','profile validation remains visible');input.value=old;
  }
  if(location.pathname.endsWith('/detail.html')){
    click('.photo-grid__cell');check(document.querySelector('#lightbox').open,'gallery opens');
    const r=document.querySelector('#lightbox').getBoundingClientRect();
    check(r.left>=-1 && r.right<=innerWidth+1 && r.top>=-1 && r.bottom<=innerHeight+1,'gallery fits viewport');
    click('#lb-next');click('#lb-close');check(!document.querySelector('#lightbox').open,'gallery closes');
    click('#write-review-btn');check(!document.querySelector('#review-form-wrapper').hidden,'review form opens');click('#cancel-review-btn');
    click('.room-pick');check(document.querySelector('#summary-rooms').textContent.includes('1'),'room selection UI updates');
  }
  if(location.pathname.endsWith('/booking-list.html'))click('[data-action="cancel"]');
  if(location.pathname.endsWith('/host-homestays.html'))click('[data-del]');
  if(location.pathname.endsWith('/admin.html'))click('[data-action="approve"]');
  const dialog=document.querySelector('#confirm-dialog');
  if(dialog?.open){const r=dialog.getBoundingClientRect();check(r.left>=-1&&r.right<=innerWidth+1&&r.top>=-1&&r.bottom<=innerHeight+1,'confirmation dialog fits viewport');click('[data-cancel]');}
  if(location.pathname.endsWith('/host-bookings.html')){
    if(document.querySelector('[data-reject]')){click('[data-reject]');check(document.querySelector('#reject-dialog').open,'rejection dialog opens');click('#rejectCancel');}
    else check(!!document.querySelector('.host-bookings-empty'),'empty booking state renders');
  }
  if(location.pathname.endsWith('/host-rooms.html')){
    if(!document.querySelector('#addBtn').disabled){click('#addBtn');check(document.querySelector('#roomForm').classList.contains('is-open'),'room editor opens');submit('#roomForm');check(document.querySelector('#rName').getAttribute('aria-invalid')==='true','room editor validation');}
    else check(document.getElementById('homestayName').textContent.includes('Bạn chưa có homestay nào.'),'new host has no room editor without a homestay');
  }
  if(location.pathname.includes('dashboard')||location.pathname.endsWith('/admin.html')){
    click('.period-tabs__btn[data-key="7d"]');check(document.querySelector('.period-tabs__btn[data-key="7d"]').getAttribute('aria-pressed')==='true','dashboard filter updates');
  }
  return checks;
})()"""


def check_pointer_motion(c):
    """Force actual CSS pseudo states through DevTools; preserve the media preference."""
    c.js("document.querySelector('[data-reject]').focus();document.querySelector('[data-reject]').click()")
    c.call('Input.dispatchKeyEvent', type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27)
    c.call('Input.dispatchKeyEvent', type='keyUp', key='Escape', code='Escape', windowsVirtualKeyCode=27)
    c.until("!document.getElementById('reject-dialog').open")
    if not c.js("document.activeElement.matches('[data-reject]')"):
        raise RuntimeError('Native dialog did not restore focus after Escape')
    c.call('DOM.enable'); c.call('CSS.enable')
    root = c.call('DOM.getDocument')['root']['nodeId']
    def force(selector, states):
        node = c.call('DOM.querySelector', nodeId=root, selector=selector)['nodeId']
        if not node:
            raise RuntimeError('Missing motion test target: ' + selector)
        c.call('CSS.forcePseudoState', nodeId=node, forcedPseudoClasses=states)
    reduced = c.js("matchMedia('(prefers-reduced-motion: reduce)').matches")
    button = '[data-act]'
    force(button, ['active'])
    time.sleep(.25)
    scale = c.js("getComputedStyle(document.querySelector('[data-act]')).transform")
    if (scale != 'none') == reduced:
        raise RuntimeError('Incorrect active transform: ' + scale)
    force(button, ['focus-visible'])
    if not c.js("parseFloat(getComputedStyle(document.querySelector('[data-act]')).outlineWidth)>=2"):
        raise RuntimeError('Missing keyboard focus ring')
    force(button, [])
    interactive = '.host-booking-card:has([data-act])'
    force(interactive, ['hover'])
    time.sleep(.3)
    if c.js("matchMedia('(hover: hover) and (pointer: fine)').matches"):
        transformed = c.js("getComputedStyle(document.querySelector('.host-booking-card:has([data-act])')).transform!=='none'")
        if transformed == reduced:
            raise RuntimeError('Incorrect interactive card hover')
    force(interactive, [])
    terminal = '.host-booking-card:not(:has(button))'
    force(terminal, ['hover'])
    if not c.js("getComputedStyle(document.querySelector('.host-booking-card:not(:has(button))')).transform==='none'"):
        raise RuntimeError('Noninteractive booking suggests interaction')
    force(terminal, [])
    if not reduced:
        c.js("import('./js/motion.js').then(m=>m.animateList(document.getElementById('list')))")
        c.call('Emulation.setEmulatedMedia', features=[{'name':'prefers-reduced-motion','value':'reduce'}])
        c.until("document.getAnimations().length===0")
        c.call('Emulation.setEmulatedMedia', features=[{'name':'prefers-reduced-motion','value':'no-preference'}])
    return ['modal Escape restores focus', 'button active and keyboard focus', 'interactive and terminal card hover', 'live reduced motion preference']


def main():
    browser = next((p for p in [shutil.which('google-chrome'), shutil.which('chromium'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google/Chrome/Application/chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft/Edge/Application/msedge.exe')]
        if p and Path(p).is_file()), None)
    if not browser:
        raise SystemExit('Chrome/Edge required')
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT / 'frontend')))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    output = Path(tempfile.mkdtemp(prefix='luxstay-ui-audit-'))
    users = json.loads((ROOT / 'frontend/mock/users.json').read_text(encoding='utf-8'))['users']
    booking = {
        'id': 1, 'userId': 1, 'code': 'BK000001', 'homestayId': 3,
        'homestayName': 'Homestay kiểm tra giao diện', 'homestayImage': 'img/placeholder.svg',
        'homestayAddress': 'Đà Lạt', 'roomName': 'Phòng kiểm tra', 'checkIn': '2026-10-12',
        'checkOut': '2026-10-14', 'nights': 2, 'guests': 2, 'pricePerNight': 420000,
        'roomSubtotal': 840000, 'serviceFee': 42000, 'totalPrice': 882000,
        'status': 'pending', 'guestName': 'Người dùng kiểm tra', 'hostPhone': '0900000000',
    }
    pages = [
        ('index.html', "document.querySelector('#results .card')", 0),
        ('search.html', "document.querySelector('#results .card')", 0),
        ('detail.html?id=3', "document.querySelector('#room-list .room-card')", 0),
        ('booking-list.html', "document.querySelector('#booking-list .row') || document.querySelector('#booking-empty:not([hidden])')", 0),
        ('booking-detail.html?id=1', "document.querySelector('#bd-title')?.textContent!=='Đang tải...'", 0),
        ('booking-page.html?id=3&rooms=superior:1', "document.querySelector('#sumTitle')?.textContent!=='—'", 0),
        ('booking-confirmed.html', "document.querySelector('#bCode')?.textContent!=='—'", 0),
        ('profile.html', "document.querySelector('#profile-form [type=submit]')?.disabled===false", 0),
        ('login.html', "document.querySelector('#login-form [type=submit]')?.disabled===false", None),
        ('register.html', "document.querySelector('#register-form [type=submit]')?.disabled===false", None),
        ('host-register.html', "document.querySelector('#host-register-form [type=submit]')?.disabled===false", None),
        ('host-dashboard.html', "document.querySelectorAll('.period-tabs__btn').length===3", 1),
        ('host-homestays.html', "document.querySelector('.host-homestay-card, .host-homestays-empty')", 1),
        ('host-rooms.html', "document.querySelector('.host-room-card, .host-rooms-empty') || document.getElementById('homestayName')?.textContent.includes('Bạn chưa có homestay nào.')", 1),
        ('host-homestay-form.html', "document.querySelector('#form') && document.querySelector('site-header header')", 1),
        ('host-bookings.html', "document.querySelector('.host-booking-card, .host-bookings-empty')", 1),
        ('admin.html', "document.querySelectorAll('.period-tabs__btn').length===3", 2),
        ('404.html', "document.querySelector('site-header header')", None),
    ]
    report = []
    try:
        with tempfile.TemporaryDirectory(prefix='luxstay-ui-chrome-') as profile:
            process = subprocess.Popen([browser, '--headless=new', '--disable-gpu', '--no-first-run',
                '--remote-debugging-port=0', '--user-data-dir=' + profile, '--disable-background-networking',
                '--host-resolver-rules=MAP fonts.googleapis.com ~NOTFOUND, MAP fonts.gstatic.com ~NOTFOUND',
                'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                portfile = Path(profile) / 'DevToolsActivePort'
                for _ in range(100):
                    try:
                        port = portfile.read_text().splitlines()[0]
                        break
                    except (OSError, IndexError):
                        time.sleep(.1)
                else:
                    raise RuntimeError('Chrome debugging port unavailable')
                targets = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
                c = CDP(next(t['webSocketDebuggerUrl'] for t in targets if t['type'] == 'page'))
                c.call('Page.enable'); c.call('Runtime.enable'); c.call('Network.enable')
                c.call('Emulation.setEmulatedMedia', features=[{'name':'prefers-reduced-motion','value':'no-preference' if '--normal-motion' in sys.argv else 'reduce'}])
                c.call('Page.navigate', url=origin + '/login.html')
                c.until("location.pathname==='/login.html' && document.readyState==='complete'")
                for width in (375, 768, 1024, 1440):
                    print('Checking viewport', width, flush=True)
                    c.call('Emulation.setDeviceMetricsOverride', width=width, height=1000, deviceScaleFactor=1, mobile=False)
                    for path, ready, user_index in pages:
                        user = {k:v for k,v in users[user_index].items() if k!='credential'} if user_index is not None else None
                        c.js("localStorage.removeItem('app_token');localStorage.removeItem('app_user');")
                        if user:
                            c.js("localStorage.setItem('app_token','mock-token');localStorage.setItem('app_user'," + json.dumps(json.dumps(user)) + ");")
                        if path.startswith('booking-confirmed'):
                            c.js("sessionStorage.setItem('lastBooking'," + json.dumps(json.dumps(booking)) + ");")
                        c.call('Page.navigate', url=origin + '/' + path)
                        c.until("location.pathname==='/" + path.split('?')[0] + "' && document.readyState==='complete' && !!(" + ready + ")")
                        time.sleep(.15)
                        data = c.js(METRICS)
                        data.update(page=path, errors=c.errors[:]); c.errors.clear()
                        # Inspect the currently hidden room editor as well.
                        if path=='host-rooms.html' and c.js("!document.getElementById('addBtn').disabled"):
                            c.js("document.getElementById('addBtn').click()")
                            data['editor'] = c.js(METRICS)
                        if '--screenshots' in sys.argv:
                            c.js('scrollTo(0,0)')
                            shot = c.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
                            (output / f'{width}-{path.split(".")[0]}.png').write_bytes(base64.b64decode(shot['data']))
                        data['interactions'] = c.js(INTERACTIONS)
                        if '--home-checks' in sys.argv:
                            c.sock.settimeout(90)
                            data['interactions'].extend(c.js((ROOT / 'tests/home-checks.js').read_text(encoding='utf-8')))
                            if '--screenshots' in sys.argv:
                                shot = c.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
                                (output / f'{width}-verified-{path.split(".")[0]}.png').write_bytes(base64.b64decode(shot['data']))
                            if path == 'index.html' and width == 375:
                                c.call('Emulation.setTouchEmulationEnabled', enabled=True)
                                point = c.js("(()=>{const r=document.getElementById('hero-carousel').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+70,index:Number(document.getElementById('hero-carousel').dataset.index)};})()")
                                c.call('Input.dispatchTouchEvent', type='touchStart', touchPoints=[{'x':point['x']+60,'y':point['y']}])
                                c.call('Input.dispatchTouchEvent', type='touchMove', touchPoints=[{'x':point['x']-60,'y':point['y']}])
                                c.call('Input.dispatchTouchEvent', type='touchEnd', touchPoints=[])
                                c.until("Number(document.getElementById('hero-carousel').dataset.index)==="+str((point['index']+1)%6))
                                data['interactions'].append('Chrome touch swipe advances hero without navigating')
                                c.call('Emulation.setTouchEmulationEnabled', enabled=False)
                        if '--motion-checks' in sys.argv:
                            if path == 'host-bookings.html' and c.js("!!document.querySelector('[data-reject]')"):
                                data['interactions'].extend(check_pointer_motion(c))
                            data['interactions'].extend(c.js((ROOT / 'tests/motion-checks.js').read_text(encoding='utf-8')))
                        if path=='host-rooms.html' and c.js("!!document.getElementById('hsSwitch')"):
                            c.js("const s=document.getElementById('hsSwitch');s.value='hs010';s.dispatchEvent(new Event('change',{bubbles:true}));")
                            c.until("!!document.querySelector('.host-rooms-empty')")
                            data['interactions'].append('homestay dropdown updates room empty state')
                        if path=='search.html':
                            c.js("document.getElementById('q').value='ui-audit-no-matching-homestay';document.getElementById('filter-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
                            c.until("!!document.querySelector('#results .empty')")
                            data['interactions'].append('search empty state renders')
                        toast_ok=c.js("""(async()=>{const {toast}=await import('./js/ui.js');toast('Kiểm tra thông báo giao diện trên màn hình hiện tại.');await new Promise(r=>requestAnimationFrame(r));const e=document.getElementById('toast'),r=e.getBoundingClientRect();return e.classList.contains('is-visible')&&r.left>=-1&&r.right<=innerWidth+1;})()""")
                        if not toast_ok:
                            raise RuntimeError('Toast outside viewport: '+path)
                        data['interactions'].append('toast fits viewport')
                        # Dialog opening uses an async confirmation helper; capture the final layout too.
                        data['afterInteractions'] = c.js(METRICS)
                        data['errors'].extend(c.errors); c.errors.clear()
                        report.append(data)
                        if any(x['scrollWidth']>x['clientWidth']+1 for x in (data,data.get('editor',data),data['afterInteractions'])) or data['errors']:
                            print(json.dumps(data, ensure_ascii=True), flush=True)
                (output / 'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                overflow=sum(any(x['scrollWidth']>x['clientWidth']+1 for x in (p,p.get('editor',p),p['afterInteractions'])) for p in report)
                print('AUDIT:',len(report),'page/viewport combinations; overflow:',overflow,
                      'runtime errors:',sum(len(x['errors']) for x in report),
                      'interaction assertions:',sum(len(x['interactions']) for x in report), 'OUTPUT:',str(output), flush=True)
                c.sock.close()
                if overflow or any(x['errors'] for x in report):
                    raise SystemExit('FAIL: responsive audit found overflow or console errors')
            finally:
                process.terminate(); process.wait(timeout=10)
    finally:
        server.shutdown(); server.server_close()


if __name__=='__main__':
    main()
