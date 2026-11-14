"""Run real Chrome/Edge headless against a temporary localhost server/profile.

No packages required: python tests/mock-accounts-browser.py [path/to/chrome.exe]
The test never uses the user's browser profile or repository database.
"""
import functools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
RESULT = []
DONE = threading.Event()
SCRIPT = r"""
const results = [];
const assert = (ok, message) => { if (!ok) throw Error(message); results.push(message); };
const delay = ms => new Promise(r => setTimeout(r, ms));
const frame = document.querySelector('iframe');
const doc = () => frame.contentDocument;
const win = () => frame.contentWindow;
async function waitFor(fn, label) {
  for (let n = 0; n < 250; n++) { if (fn()) return; await delay(40); }
  throw Error('Timeout: ' + label);
}
async function page(path, ready) {
  await Promise.race([
    new Promise(resolve => { frame.onload = resolve; frame.src = path; }),
    delay(10000).then(() => { throw Error('Navigation timeout: ' + path); })
  ]);
  if (ready) await waitFor(() => ready(doc()), path);
}
const field = (form, key, value) => { form.elements.namedItem(key).value = value; };
const submit = form => form.dispatchEvent(new (win().Event)('submit', { bubbles: true, cancelable: true }));
const api = () => win().eval("import('./js/api.js')");
async function rejects(action, status, label) {
  let error; try { await action(); } catch (e) { error = e; }
  assert(error?.status === status, label);
}
const oldPassword = 'Mock-' + crypto.randomUUID();
const newPassword = 'Changed-' + crypto.randomUUID();
try {
  localStorage.clear(); sessionStorage.clear();
  await page('register.html', d => !!d.querySelector('site-header header'));
  let form = doc().getElementById('register-form');
  field(form, 'display_name', 'Browser Test'); field(form, 'email', 'FLOW@example.test');
  field(form, 'phone', '0912345678'); field(form, 'password', oldPassword); field(form, 'confirm', oldPassword);
  submit(form);
  await waitFor(() => win().location.pathname.endsWith('/index.html'), 'register navigation');
  await waitFor(() => doc().querySelector('[data-action="logout"]'), 'logout button');
  const id = JSON.parse(localStorage.app_user).id;
  assert(id > 99, 'New account ID does not collide with demo IDs');
  doc().querySelector('[data-action="logout"]').click();
  await waitFor(() => !localStorage.app_token, 'logout');
  await page('login.html', d => !!d.getElementById('login-form'));
  await page('login.html?reload=1', d => !!d.getElementById('login-form'));
  form = doc().getElementById('login-form');
  field(form, 'email', 'flow@example.test'); field(form, 'password', oldPassword); submit(form);
  await waitFor(() => win().location.pathname.endsWith('/index.html') && !!localStorage.app_token, 'login after reload');
  assert(JSON.parse(localStorage.app_user).id === id, 'Register -> logout -> reload -> login preserves account');
  await page('profile.html', d => !d.querySelector('#profile-form [type=submit]').disabled);
  assert(doc().querySelector('[name=display_name]').value === 'Browser Test', 'Profile fills current account');
  form = doc().getElementById('profile-form');
  field(form, 'display_name', '<b>Changed Name</b>'); field(form, 'email', 'changed@example.test');
  field(form, 'phone', '+84912345678'); submit(form);
  await waitFor(() => JSON.parse(localStorage.app_user).email === 'changed@example.test', 'profile save');
  assert(doc().querySelector('[data-user-name]').textContent === '<b>Changed Name</b>' && !doc().querySelector('[data-user-name] b'), 'Header updates name as text');
  await page('profile.html?reload=1', d => !d.querySelector('#profile-form [type=submit]').disabled);
  assert(doc().querySelector('[name=phone]').value === '+84912345678', 'Profile persists after page reload');
  let service = await api();
  await rejects(() => service.register({display_name:'Duplicate',email:' CHANGED@EXAMPLE.TEST ',password:oldPassword}),409,'Duplicate email rejected with normalization');
  await rejects(() => service.updateProfile({display_name:'Valid Name',email:'huy@test.com',phone:''}),409,'Profile rejects another account email');
  const imageInput = doc().getElementById('avatar');
  async function choose(file) {
    const transfer = new (win().DataTransfer)(); transfer.items.add(file); imageInput.files = transfer.files;
    imageInput.dispatchEvent(new (win().Event)('change', { bubbles:true }));
    await delay(200);
    await waitFor(() => !doc().querySelector('#profile-form [type=submit]').disabled, 'avatar processing');
  }
  await choose(new (win().File)(['fake'], 'bad.svg', {type:'image/svg+xml'}));
  assert(!!doc().getElementById('avatar-error').textContent, 'SVG avatar rejected');
  await choose(new (win().File)(['fake'], 'fake.png', {type:'image/png'}));
  assert(!!doc().getElementById('avatar-error').textContent, 'Spoofed image MIME rejected');
  await choose(new (win().File)([new Uint8Array(5*1024*1024+1)], 'large.png', {type:'image/png'}));
  assert(!!doc().getElementById('avatar-error').textContent, 'Avatar over 5MB rejected');
  const canvas = doc().createElement('canvas'); canvas.width=4; canvas.height=4;
  canvas.getContext('2d').fillRect(0,0,4,4);
  const blob = await new Promise(resolve => canvas.toBlob(resolve));
  await choose(new (win().File)([blob], 'avatar.png', {type:'image/png'}));
  assert(doc().getElementById('avatar-preview').src.startsWith('data:image/png'), 'Valid avatar previews');
  submit(doc().getElementById('profile-form'));
  await waitFor(() => JSON.parse(localStorage.app_user).avatar.startsWith('data:image/png'), 'avatar save');
  await page('profile.html?reload=2', d => !d.querySelector('#profile-form [type=submit]').disabled);
  assert(doc().getElementById('avatar-preview').src.startsWith('data:image/png'), 'Avatar persists after reload');
  service = await api();
  await rejects(() => service.changePassword('Wrong-current',newPassword),400,'Wrong current password rejected');
  await rejects(() => service.changePassword(oldPassword,'short'),400,'Short new password rejected');
  form = doc().getElementById('password-form');
  field(form,'current_password',oldPassword); field(form,'new_password',newPassword); field(form,'confirm_password','Mismatch'); submit(form);
  assert(!!form.querySelector('[name=confirm_password]').getAttribute('aria-invalid'), 'Password mismatch shows field error');
  field(form,'confirm_password',newPassword); submit(form);
  await waitFor(() => form.elements.namedItem('current_password').value === '', 'password change');
  assert(!win().location.search.includes('password') && !win().location.href.includes(oldPassword), 'Password never enters URL');
  await rejects(() => service.login('changed@example.test',oldPassword),401,'Old password rejected after change');
  await service.login('changed@example.test',newPassword);
  assert(true,'New password accepted');
  await page('index.html', d => !!d.querySelector('[data-action="logout"]'));
  doc().querySelector('[data-action="logout"]').click();
  await waitFor(() => !localStorage.app_token, 'second logout');
  await page('login.html', d => !!d.getElementById('login-form'));
  form=doc().getElementById('login-form'); field(form,'email','changed@example.test'); field(form,'password',newPassword); submit(form);
  await waitFor(() => !!localStorage.app_token, 'login with changed password');
  assert(JSON.parse(localStorage.app_user).id===id,'Changed email/password works after logout and navigation');
  const storage = JSON.stringify(Object.fromEntries(Object.keys(localStorage).map(k => [k,localStorage[k]])));
  assert(!storage.includes(oldPassword) && !storage.includes(newPassword), 'No raw passwords persisted');
  assert(!('credential' in JSON.parse(localStorage.app_user)), 'Session excludes password verifier');
  const hostAuth=await win().eval("import('./js/auth.js')");
  const seededHost=JSON.parse(localStorage.luxstay_mock_users_v1).find(user=>user.id==='host001');
  localStorage.setItem('luxstay_mock_host_applications_v1',JSON.stringify([{
    id:'approved-host-app',userId:'host001',status:'approved',
    application_data:{homestay_name:'Previous Homestay',address:'123 Test Street',province:'Lam Dong',
      room_count:1,description:'A previous approved host application.',experience:'',phone:'0912345678',accept_terms:true},
    createdAt:new Date().toISOString(),history:[],
  }]));
  hostAuth.saveSession({access_token:'mock-token',user:seededHost});
  await page('profile.html?host-cancel-test=1',d=>!d.getElementById('cancel-host-section').hidden);
  service=await api();
  const ownedStays=await service.getHostHomestays(), ownedRooms=await service.getHostRooms();
  assert(ownedStays.length===22 && ownedRooms.length===48,'Host cancellation starts with seeded owned homestays and rooms');
  localStorage.setItem('bookings',JSON.stringify([{id:'active-cancel-guard',roomId:ownedRooms[0].id,status:'confirmed'}]));
  doc().getElementById('cancel-host-open').click();
  assert(doc().getElementById('cancel-host-dialog').open,'Host cancellation dialog opens');
  doc().getElementById('cancel-host-reason').value='Tôi không còn kinh doanh homestay.';
  doc().querySelector('#cancel-host-dialog [data-confirm]').click();
  await waitFor(()=>!!doc().getElementById('cancel-host-error').textContent
    &&!doc().querySelector('#cancel-host-dialog [data-confirm]').disabled,'active booking cancellation rejection');
  assert(JSON.parse(localStorage.luxstay_mock_users_v1).find(user=>user.id==='host001').role==='host',
    'Active booking rejection preserves Host role');
  localStorage.setItem('bookings','[]');
  doc().getElementById('cancel-host-reason').value='Tôi không còn kinh doanh homestay.';
  doc().querySelector('#cancel-host-dialog [data-confirm]').click();
  await waitFor(()=>win().location.pathname.endsWith('/login.html')&&!localStorage.app_token,'successful host cancellation sign-out');
  assert(JSON.parse(localStorage.luxstay_mock_users_v1).find(user=>user.id==='host001').role==='user',
    'Successful cancellation changes Host role to Customer');
  assert(JSON.parse(localStorage.homestays).filter(stay=>stay.hostId==='host001').every(stay=>stay.status==='inactive'),
    'Successful cancellation pauses only the former Host homestays');
  service=await api();
  const adminAuth=await win().eval("import('./js/auth.js')");
  adminAuth.saveSession({access_token:'mock-token',user:{id:99,display_name:'Admin LuxStay',role:'admin'}});
  const notices=await service.getAdminHostCancellations();
  assert(notices.some(notice=>notice.host.id==='host001'
    &&notice.reason==='Tôi không còn kinh doanh homestay.'),'Admin can read self-cancellation reason');
  assert(!(await service.getAdminHosts()).some(host=>host.id==='host001'),'Former Host leaves the Admin host list');
  const formerHost=JSON.parse(localStorage.luxstay_mock_users_v1).find(user=>user.id==='host001');
  adminAuth.saveSession({access_token:'mock-token',user:formerHost});
  await page('profile.html?after-host-cancel=1',d=>!d.getElementById('host-apply-open').hidden);
  service=await api();
  assert(doc().getElementById('host-apply-open').textContent==='Trở thành host',
    'Former Host sees the become-host action again');
  doc().getElementById('host-apply-open').click();
  assert(!doc().getElementById('host-application-form').hidden,'Former Host can open a fresh application form');
  const newApplication=await service.applyHost({
    homestay_name:'New Homestay',address:'123 Test Street',province:'Lam Dong',room_count:2,
    description:'A comfortable place for future guest stays.',experience:'',phone:'0912345678',accept_terms:true,
  });
  assert(newApplication.status==='pending','Former Host can submit a new application for review');
  const formerAuth=await win().eval("import('./js/auth.js')");
  formerAuth.saveSession({access_token:'mock-token',user:{id:99,display_name:'Admin LuxStay',role:'admin'}});
  await page('admin.html?host-notification-test=1',d=>!!d.querySelector('#host-cancellation-list .host-cancellation-card'));
  const cancellationCard=doc().querySelector('#host-cancellation-list .host-cancellation-card');
  assert(cancellationCard.textContent.includes('Tôi không còn kinh doanh homestay.')
    &&cancellationCard.querySelector('.host-cancellation-card__email')
    &&cancellationCard.querySelector('time'),
  'Admin dashboard renders self-cancellation details in the dedicated card layout');
  const currentAuth=await win().eval("import('./js/auth.js')");
  const changedUser=JSON.parse(localStorage.luxstay_mock_users_v1).find(user=>user.email==='changed@example.test');
  currentAuth.saveSession({access_token:'mock-token',user:changedUser});
  await page('host-register.html', d => !!d.getElementById('host-password'));
  const button=doc().querySelector('[data-target="host-password"]'), password=doc().getElementById('host-password');
  button.click(); assert(password.type==='text','Host password toggle changes once');
  button.click(); assert(password.type==='password','Host password toggle restores on second click');
  service=await api();
  const seeded=await service.login('host@test.com',String.fromCharCode(49,50,51,52,53,54,55,56));
  assert(seeded.user.id==='host001','Existing demo host login remains compatible');
  const spoof=await service.register({display_name:'Role Test',email:'role@example.test',password:newPassword,role:'admin'});
  assert(spoof.user.role==='user','Registration cannot request admin role');
  // Force quota failure without filling the real device storage.
  const original=win().Storage.prototype.setItem;
  win().Storage.prototype.setItem=function(k,v) { if(k==='luxstay_mock_users_v1') throw new Error('quota'); return original.call(this,k,v); };
  try { await rejects(() => service.updateProfile({display_name:'Quota Test',email:'quota@example.test',phone:''}),0,'Storage failure is reported'); }
  finally { win().Storage.prototype.setItem=original; }
  assert(JSON.parse(localStorage.app_user).email==='changed@example.test','Failed save does not update active session');
  const cached=localStorage.luxstay_mock_users_v1; localStorage.luxstay_mock_users_v1='{invalid';
  await rejects(() => service.login('changed@example.test',newPassword),0,'Corrupt account storage fails explicitly');
  localStorage.luxstay_mock_users_v1=cached;
  const oldCrypto=Object.getOwnPropertyDescriptor(win(),'crypto');
  Object.defineProperty(win(),'crypto',{value:{}, configurable:true});
  try { await rejects(() => service.register({display_name:'No Crypto',email:'nocrypto@example.test',password:newPassword}),0,'Missing Web Crypto refuses registration without plaintext fallback'); }
  finally { Object.defineProperty(win(),'crypto',oldCrypto); }
  assert(localStorage.luxstay_mock_users_v1===cached,'Missing Web Crypto leaves account data unchanged');
  await page('profile.html?reload=3', d => !d.querySelector('#profile-form [type=submit]').disabled);
  const auth=await win().eval("import('./js/auth.js')");
  localStorage.app_user='{broken';
  assert(auth.getUser()===null && !auth.isLoggedIn(),'Corrupt session is treated as logged out');
  localStorage.removeItem('app_token'); localStorage.removeItem('app_user');
  await page('profile.html', d => !!d.getElementById('login-form'));
  assert(win().location.pathname.endsWith('/login.html'),'Guest profile redirects to login');
  await page('detail.html?id=3', d => !!d.getElementById('huy-phong'));
  assert(!doc().querySelector('a[href*="terms.html"]'),'Missing terms link removed; cancellation text remains');
  const config=await win().eval("import('./js/config.js')"); assert(config.USE_MOCK===true,'USE_MOCK remains true');
  await fetch('/__result', {method:'POST', body:JSON.stringify({ok:true,results})});
} catch(error) {
  await fetch('/__result', {method:'POST', body:JSON.stringify({ok:false,results,error:error.message})});
}
"""


class Handler(SimpleHTTPRequestHandler):
    timeout = 5
    def log_message(self, *args):
        pass  # Never print request URLs or form contents.

    def do_GET(self):
        if self.path == '/__test':
            errors = "window.addEventListener('error', e => fetch('/__result', {method:'POST',body:JSON.stringify({ok:false,results:[],error:e.message})}));"
            body = ('<!doctype html><iframe></iframe><script>' + errors + '</script><script type="module">' + SCRIPT + '</script>').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != '/__result':
            self.send_error(405)
            return
        RESULT.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(204)
        self.end_headers()
        DONE.set()


def main():
    candidates = [sys.argv[1]] if len(sys.argv) > 1 else [
        shutil.which('google-chrome'), shutil.which('chromium'), shutil.which('chrome'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google/Chrome/Application/chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft/Edge/Application/msedge.exe'),
    ]
    browser = next((p for p in candidates if p and Path(p).is_file()), None)
    if not browser:
        raise SystemExit('Chrome/Edge not found; pass the executable path.')
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT / 'frontend')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='luxstay-browser-test-') as profile:
            process = subprocess.Popen([browser, '--headless=new', '--disable-gpu', '--no-first-run',
                '--host-resolver-rules=MAP fonts.googleapis.com ~NOTFOUND, MAP fonts.gstatic.com ~NOTFOUND, MAP images.unsplash.com ~NOTFOUND, MAP cf.bstatic.com ~NOTFOUND',
                '--disable-background-networking', '--no-default-browser-check',
                '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows', '--user-data-dir=' + profile,
                f'http://127.0.0.1:{server.server_port}/__test'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                if not DONE.wait(55):
                    raise SystemExit('FAIL: browser test timed out (no result).')
                result = RESULT[0]
                for label in result['results']:
                    print('PASS:', label)
                if not result['ok']:
                    raise SystemExit('FAIL: ' + result['error'])
                print(f"PASS: {len(result['results'])} browser assertions")
            finally:
                process.terminate()
                process.wait(timeout=10)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
