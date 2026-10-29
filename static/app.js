const APP = 'Team Member'; // English only, never translated
const $ = (s, e = document) => e.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let lang = localStorage.lang || (navigator.language.startsWith('ar') ? 'ar' : 'en');
let me = null, timer = null, curAgent = null, runKind = 'summary';
const t = k => I18N[lang][k] ?? I18N.en[k] ?? k;
const B = `<span class="brand">${APP}</span>`;
const IC = {
 home:'<path d="M3 11l9-8 9 8v10H3z"/>', bot:'<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 14h.01M15 14h.01"/>',
 bolt:'<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>', team:'<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.500 3-6 6-6s6 2.500 6 6M17 5a3 3 0 010 6M21 20c0-2.500-1.500-4.500-4-5.500"/>',
 dashboard:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 send:'<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>', logout:'<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>',
 lang:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>'
};
const ic = k => `<svg class="i" viewBox="0 0 24 24">${IC[k]}</svg>`;

async function api(path, o = {}) {
  const r = await fetch('/api' + path, { method: o.method || 'GET', credentials: 'same-origin',
    headers: o.body ? { 'Content-Type': 'application/json' } : {}, body: o.body ? JSON.stringify(o.body) : undefined });
  let d = null; try { d = await r.json(); } catch {}
  if (!r.ok) { const m = Array.isArray(d?.detail) ? d.detail[0]?.msg : d?.detail; const e = new Error(m || r.statusText); e.status = r.status; throw e; }
  return d;
}
function toast(m) { const d = document.createElement('div'); d.className = 'toast'; d.textContent = m; document.body.append(d); setTimeout(() => d.remove(), 3500); }
const fail = e => toast(e.message || String(e));
const go = h => { location.hash = '#/' + h; };
function applyLang() { document.documentElement.lang = lang; document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'; document.title = APP; }
async function setLang(l) { lang = l; localStorage.lang = l; applyLang(); if (me) api('/me/lang', { method: 'PATCH', body: { lang: l } }).catch(() => {}); route(); }
const agName = a => a.is_default && a.slug ? t('ag_' + a.slug) : a.name;
const agDesc = a => a.is_default && a.slug ? t('ag_' + a.slug + '_d') : a.description;
const fmt = s => (s || '').slice(5, 16).replace('T', ' ');

/* ---------- layout ---------- */
function shell(page, inner) {
  const items = ['home', 'assistant', 'task', 'team'].concat(me.role === 'manager' ? ['dashboard'] : []);
  const icons = { home: 'home', assistant: 'bot', task: 'bolt', team: 'team', dashboard: 'dashboard' };
  $('#app').innerHTML = `<div class="shell"><aside class="side">
   <div class="logo"><span class="lg">${ic('bot')}</span><div><b>${B}</b><small>${t('brand_sub')}</small></div></div>
   <nav>${items.map(k => `<a href="#/${k}" class="${k === page ? 'on' : ''}">${ic(icons[k])}<span>${t('nav_' + k)}</span></a>`).join('')}</nav>
   <div class="sidefoot"><button class="lnk" id="lang">${ic('lang')}<span>${lang === 'ar' ? 'English' : 'العربية'}</span></button>
   <button class="lnk" id="out">${ic('logout')}<span>${t('logout')}</span></button><button class="lnk sm" id="del">${t('delete_data')}</button></div></aside>
   <main class="main">${me.mock_ai ? `<div class="banner">${t('mock')}</div>` : ''}${inner}</main></div>`;
  $('#lang').onclick = () => setLang(lang === 'ar' ? 'en' : 'ar');
  $('#out').onclick = async () => { await api('/logout', { method: 'POST' }); me = null; go(''); };
  $('#del').onclick = async () => { if (confirm(t('del_confirm'))) { try { await api('/me', { method: 'DELETE' }); me = null; go(''); } catch (e) { fail(e); } } };
}
const head = (ti, su) => `<h1>${ti}</h1><p class="mut" style="margin:0 0 6px">${su || ''}</p>`;
const msgHtml = m => `<div class="bub ${m.member_id === me.id && m.source === 'human' ? 'me' : ''}"><small>${esc(m.who)}${m.source === 'agent' ? ' · ' + t('ai_tag') : ''}</small>${esc(m.content)}</div>`;

/* ---------- public pages ---------- */
function pubNav() {
  return `<div class="nav">${B}<div><button class="btn ghost sm" id="lang">${ic('lang')} ${lang === 'ar' ? 'English' : 'العربية'}</button><a class="btn ghost sm" href="#/login">${t('login')}</a></div></div>`;
}
function vLanding() {
  $('#app').innerHTML = `<div class="pub">${pubNav()}<section class="hero"><div class="kick">${t('welcome')} ${B}</div><h1>${t('hero_title')}</h1><p>${t('hero_sub')}</p>
   <a class="btn" href="#/join">${t('join')}</a> <a class="btn ghost" href="#/login">${t('login')}</a></section>
   <h2 class="sec">${t('feat')}</h2><div class="grid3">${[1, 2, 3].map(i => `<div class="card"><h3>${t('f' + i + 't')}</h3><p class="mut">${t('f' + i + 'd')}</p></div>`).join('')}</div>
   <h2 class="sec">${t('how')}</h2><div class="grid3">${[1, 2, 3].map(i => `<div class="card"><div class="num">${i}</div><h3>${t('h' + i)}</h3></div>`).join('')}</div>
   <div class="foot">${B}</div></div>`;
  $('#lang').onclick = () => setLang(lang === 'ar' ? 'en' : 'ar');
}
function authBox(title, fields, btn, foot, onsubmit) {
  $('#app').innerHTML = `<div class="pub">${pubNav()}<form class="card authbox" id="f"><h1>${title}</h1>
   ${fields.map(([n, l, ty]) => `<label>${t(l)}</label><input name="${n}" type="${ty || 'text'}" required ${ty === 'password' ? 'minlength="8"' : ''}>`).join('')}
   <div style="margin-top:18px"><button class="btn full">${btn}</button></div><p class="mut" style="text-align:center">${foot || ''}</p></form></div>`;
  $('#lang').onclick = () => setLang(lang === 'ar' ? 'en' : 'ar');
  $('#f').onsubmit = async e => { e.preventDefault(); try { await onsubmit(Object.fromEntries(new FormData(e.target))); } catch (x) { fail(x); } };
}
const entered = async () => { me = await api('/me'); history.replaceState(null, '', '/#/home'); route(); };
const vLogin = () => authBox(t('login'), [['email', 'email', 'email'], ['password', 'password', 'password']], t('login'),
  `${t('no_acct')} <a href="#/join" style="color:var(--teal)">${t('join')}</a>`, async b => { await api('/login', { method: 'POST', body: b }); await entered(); });
const vJoin = () => authBox(t('join'), [['team_name', 'team_name'], ['name', 'name'], ['email', 'email', 'email'], ['password', 'password', 'password']], t('create_ws'),
  `${t('have_acct')} <a href="#/login" style="color:var(--teal)">${t('login')}</a>`, async b => { await api('/signup', { method: 'POST', body: b }); await entered(); });
async function vAccept(token) {
  let info; try { info = await api('/invite/' + token); } catch (e) { fail(e); return vLanding(); }
  authBox(`${t('invite_for')} ${esc(info.team)}`, [['name', 'name'], ['password', 'password', 'password']], t('accept'), esc(info.email),
    async b => { await api('/accept', { method: 'POST', body: { ...b, token } }); await entered(); });
}

/* ---------- home ---------- */
async function vHome() {
  const d = await api('/home'), s = d.stats;
  shell('home', `${head(t('home_title'), t('home_sub'))}
   <div class="stats">${[['st_members', s.members], ['st_messages', s.messages], ['st_tasks', s.tasks]].map(([k, v]) => `<div class="stat"><span class="mut">${t(k)}</span><b>${v}</b></div>`).join('')}</div>
   <div class="card"><h2>${t('pending')}</h2><div class="list">${d.pending.map(p => p.type === 'todo'
     ? `<div><span>${esc(p.title)}</span><button class="btn ghost sm" data-done="${p.id}">${t('done')}</button></div>`
     : `<div><span>${esc(p.title)} <span class="tag warn">${t('need_appr')}</span></span><a class="btn ghost sm" href="#/task">${t('open')}</a></div>`).join('') || `<p class="mut">${t('no_pending')}</p>`}</div>
    <div class="row" style="margin-top:12px"><input id="todo" placeholder="${t('todo_ph')}"><button class="btn" id="addt">${t('add')}</button></div></div>
   <div class="card"><h2>${t('recent')}</h2><div class="list">${d.recent_messages.map(m => `<div><span><b>${esc(m.who)}</b>: ${esc(m.content.slice(0, 140))}</span><small>${fmt(m.created_at)}</small></div>`).reverse().join('') || `<p class="mut">${t('no_msgs')}</p>`}</div></div>`);
  document.querySelectorAll('[data-done]').forEach(b => b.onclick = async () => { await api('/todos/' + b.dataset.done, { method: 'PATCH' }); vHome(); });
  $('#addt').onclick = async () => { const v = $('#todo').value.trim(); if (v) { await api('/todos', { method: 'POST', body: { title: v } }); vHome(); } };
}

/* ---------- assistant ---------- */
async function vAssistant() {
  const agents = await api('/tasks');
  curAgent = agents.find(a => a.id === curAgent) ? curAgent : agents[0].id;
  const draw = async () => {
    const a = agents.find(x => x.id === curAgent), hist = await api('/chat/' + a.id);
    shell('assistant', `${head(t('asst_title'), esc(agDesc(a)))}
     <div class="chips">${agents.map(x => `<button class="chip ${x.id === curAgent ? 'on' : ''}" data-a="${x.id}">${esc(agName(x))}</button>`).join('')}</div>
     <div class="chat" id="chat">${hist.length ? hist.map(h => `<div class="bub ${h.role === 'user' ? 'me' : ''}">${esc(h.content)}</div>`).join('') : `<div class="empty">${t('asst_empty').replace('{n}', esc(agName(a)))}</div>`}</div>
     <div class="composer"><textarea id="msg" placeholder="${t('asst_ph')}"></textarea><button class="btn send" id="send">${ic('send')}</button></div>`);
    document.querySelectorAll('[data-a]').forEach(b => b.onclick = () => { curAgent = +b.dataset.a; draw(); });
    const chat = $('#chat'); chat.scrollTop = chat.scrollHeight;
    const send = async () => {
      const v = $('#msg').value.trim(); if (!v) return; $('#msg').value = '';
      chat.querySelector('.empty')?.remove();
      chat.insertAdjacentHTML('beforeend', `<div class="bub me">${esc(v)}</div><div class="bub" id="wait">${t('thinking')}</div>`); chat.scrollTop = chat.scrollHeight;
      try { const r = await api('/chat', { method: 'POST', body: { agent_id: a.id, message: v } }); $('#wait').outerHTML = `<div class="bub">${esc(r.reply)}</div>`; }
      catch (e) { $('#wait')?.remove(); fail(e); }
      chat.scrollTop = chat.scrollHeight;
    };
    $('#send').onclick = send;
    $('#msg').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } };
  };
  draw();
}

/* ---------- new task ---------- */
function runView(r) {
  const label = s => s.type === 'llm' ? `${t('s_llm')} · ${s.tokens} tok` : s.type === 'tool' ? `${t('s_tool')}: ${s.name}` :
    ({ approval_requested: t('s_ask'), approval_granted: t('s_ok'), approval_denied: t('s_no') })[s.type] || s.type;
  const p = r.pending_approval;
  $('#runbox').innerHTML = `<div class="card"><div class="row" style="justify-content:space-between"><h2 style="margin:0">${esc(r.title)}</h2>
   <span class="tag ${r.status === 'awaiting_approval' ? 'warn' : ''}" style="flex:none">${t('status_' + r.status)}</span></div>
   <ul class="steps">${r.steps.map(s => `<li>${label(s)}${s.type === 'tool' ? `<small>${esc((s.result || '').slice(0, 160))}</small>` : ''}</li>`).join('')}</ul>
   ${r.result ? `<p style="white-space:pre-wrap">${esc(r.result)}</p>` : ''}
   ${p ? `<label>${t('draft')}</label><textarea id="draft">${esc(p.draft)}</textarea><div class="row" style="margin-top:10px"><button class="btn" id="ok">${t('approve')}</button><button class="btn danger" id="no">${t('deny')}</button></div>` : ''}</div>`;
  if (p) {
    const decide = async ok => { try { runView(await api(`/runs/${r.id}/decision`, { method: 'POST', body: { approve: ok, text: $('#draft').value } })); loadLog(); } catch (e) { fail(e); } };
    $('#ok').onclick = () => decide(true); $('#no').onclick = () => decide(false);
  }
}
async function loadLog() {
  const rs = await api('/runs');
  $('#log').innerHTML = rs.map(r => `<div><span>${esc(r.title)} <span class="tag">${t('k_' + r.kind)}</span></span><span class="row" style="flex:none"><small>${fmt(r.created_at)}</small><span class="tag ${r.status === 'awaiting_approval' ? 'warn' : ''}">${t('status_' + r.status)}</span><button class="btn ghost sm" data-r="${r.id}">${t('open')}</button></span></div>`).join('') || `<p class="mut">${t('no_runs')}</p>`;
  document.querySelectorAll('[data-r]').forEach(b => b.onclick = async () => { runView(await api('/runs/' + b.dataset.r)); scrollTo(0, 0); });
}
async function vTask() {
  shell('task', `${head(t('task_title'), t('task_sub'))}
   <div class="card"><h2>${t('task_type')}</h2><div class="opts">${['summary', 'announcement', 'planning'].map(k => `<button class="opt ${k === runKind ? 'on' : ''}" data-k="${k}"><b>${t('k_' + k)}</b><small>${t('k_' + k + '_d')}</small></button>`).join('')}</div>
    <input id="rt" placeholder="${t('t_title_ph')}"><div style="height:10px"></div><textarea id="rd" placeholder="${t('t_details_ph')}"></textarea>
    <div style="margin-top:12px"><button class="btn full" id="run">${t('run')}</button></div></div>
   <div id="runbox"></div>
   <div class="card"><h2>${t('log')}</h2><div class="list" id="log"></div></div>
   <form class="card" id="na"><h2>${t('create_agent')}</h2><p class="mut" style="margin-top:-6px">${t('agent_sub')}</p>
    <label>${t('agent_name')}</label><input id="an" required maxlength="80"><label>${t('agent_prompt')}</label><textarea id="ap" required></textarea>
    <label style="display:flex;gap:8px;align-items:center;color:var(--ink)"><input type="checkbox" id="aq" checked style="width:auto"> ${t('need_ok')}</label>
    <div style="margin-top:12px"><button class="btn">${t('save_agent')}</button></div></form>`);
  document.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { runKind = b.dataset.k; document.querySelectorAll('[data-k]').forEach(x => x.classList.toggle('on', x === b)); });
  $('#run').onclick = async () => {
    const b = $('#run'); b.disabled = true; b.textContent = t('running');
    try { runView(await api('/runs', { method: 'POST', body: { kind: runKind, title: $('#rt').value, details: $('#rd').value } })); loadLog(); } catch (e) { fail(e); }
    b.disabled = false; b.textContent = t('run');
  };
  $('#na').onsubmit = async e => { e.preventDefault(); try { await api('/tasks', { method: 'POST', body: { name: $('#an').value, description: $('#ap').value, requires_approval: $('#aq').checked } }); toast(t('saved')); e.target.reset(); } catch (x) { fail(x); } };
  loadLog();
}

/* ---------- team channel ---------- */
async function vTeam() {
  shell('team', `${head(t('team_title'), t('team_sub'))}<small>${t('team_hint')}</small>
   <div class="chat" id="chat" style="margin-top:10px"></div><div class="composer"><textarea id="msg" placeholder="${t('team_ph')}"></textarea><button class="btn send" id="send">${ic('send')}</button></div>`);
  const chat = $('#chat'); let last = '';
  const load = async () => {
    const ms = await api('/messages?limit=100'), sig = ms.length + ':' + (ms.at(-1)?.id || 0); if (sig === last) return; last = sig;
    chat.innerHTML = ms.map(msgHtml).join('') || `<div class="empty">${t('no_msgs')}</div>`; chat.scrollTop = chat.scrollHeight;
  };
  const send = async () => { const v = $('#msg').value.trim(); if (!v) return; $('#msg').value = ''; try { await api('/messages', { method: 'POST', body: { content: v } }); load(); } catch (e) { fail(e); } };
  $('#send').onclick = send; $('#msg').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } };
  await load(); timer = setInterval(() => load().catch(() => {}), 4000);
}

/* ---------- manager dashboard ---------- */
let dashTab = 'ov';
async function vDash() {
  const [ms, st, msgs] = await Promise.all([api('/members'), api('/stats'), api('/messages?limit=5')]);
  const link = tk => location.origin + '/?invite=' + tk;
  const tr = dashTab === 'tr' ? await api('/traces') : [];
  const body = dashTab === 'tr' ? `<div class="card" style="overflow:auto"><table><tr>${['who', 'kind', 'status', 'exit', 'tools', 'tokens', 'cost'].map(h => `<th>${t('th_' + h)}</th>`).join('')}</tr>
    ${tr.map(r => `<tr><td>${esc(r.who)}</td><td>${r.kind}</td><td>${r.status}</td><td>${r.exit_reason || ''}</td><td>${esc(r.tool_calls.join(', '))}</td><td>${r.tokens}</td><td>${r.cost}</td></tr>`).join('') || `<tr><td colspan="7">${t('no_data')}</td></tr>`}</table></div>` :
  `<div class="stats">${[['st_members', st.members], ['st_messages', st.messages], ['st_tasks', st.tasks]].map(([k, v]) => `<div class="stat"><span class="mut">${t(k)}</span><b>${v}</b></div>`).join('')}</div>
   <div class="card"><h2>${t('add_member')}</h2><p class="mut" style="margin-top:-6px">${t('add_member_sub')}</p>
    <div class="row"><div><label>${t('email')}</label><input id="ie" type="email" placeholder="name@company.com"></div>
    <div style="flex:.5"><label>${t('role')}</label><select id="ir"><option value="member">${t('r_member')}</option><option value="manager">${t('r_manager')}</option></select></div>
    <button class="btn" id="inv" style="margin-top:24px">${t('send_invite')}</button></div><div id="ilink"></div></div>
   <div class="card"><h2>${t('members')}</h2><div class="list">${ms.map(m => `<div><span><b>${esc(m.name || m.email)}</b> ${m.id === me.id ? `<span class="tag">${t('you')}</span>` : ''} ${m.status === 'invited' ? `<span class="tag warn">${t('invited')}</span>` : ''}<br><small>${esc(m.email)}</small></span>
     <span class="row" style="flex:none">${m.status === 'invited' ? `<button class="btn ghost sm" data-c="${m.invite_token}">${t('copy')}</button>` : ''}
     ${m.id === me.id ? '' : `<select data-r="${m.id}" style="width:auto"><option value="member" ${m.role === 'member' ? 'selected' : ''}>${t('r_member')}</option><option value="manager" ${m.role === 'manager' ? 'selected' : ''}>${t('r_manager')}</option></select><button class="btn danger sm" data-x="${m.id}">${t('remove')}</button>`}</span></div>`).join('')}</div></div>
   <div class="card"><h2>${t('recent')}</h2><div class="list">${msgs.map(m => `<div><span><b>${esc(m.who)}</b>: ${esc(m.content.slice(0, 140))}</span></div>`).join('') || `<p class="mut">${t('no_msgs')}</p>`}</div></div>`;
  shell('dashboard', `${head(t('dash_title'), t('dash_sub'))}<div class="tabs"><button class="chip ${dashTab === 'ov' ? 'on' : ''}" data-t="ov">${t('tab_ov')}</button><button class="chip ${dashTab === 'tr' ? 'on' : ''}" data-t="tr">${t('tab_tr')}</button></div>${body}`);
  document.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { dashTab = b.dataset.t; vDash(); });
  const copy = async tk => { try { await navigator.clipboard.writeText(link(tk)); } catch {} toast(t('copied') + ': ' + link(tk)); };
  document.querySelectorAll('[data-c]').forEach(b => b.onclick = () => copy(b.dataset.c));
  document.querySelectorAll('[data-r]').forEach(s => s.onchange = async () => { try { await api('/members/' + s.dataset.r, { method: 'PATCH', body: { role: s.value } }); } catch (e) { fail(e); } });
  document.querySelectorAll('[data-x]').forEach(b => b.onclick = async () => { if (confirm(t('rm_confirm'))) { await api('/members/' + b.dataset.x, { method: 'DELETE' }); vDash(); } });
  $('#inv')?.addEventListener('click', async () => {
    try { const r = await api('/invite', { method: 'POST', body: { email: $('#ie').value, role: $('#ir').value } }); $('#ilink').innerHTML = `<div class="row" style="margin-top:12px"><input readonly value="${link(r.token)}"><button class="btn ghost" id="cp">${t('copy')}</button></div>`; $('#cp').onclick = () => copy(r.token); }
    catch (e) { fail(e); }
  });
}

/* ---------- router ---------- */
async function route() {
  clearInterval(timer);
  const inv = new URLSearchParams(location.search).get('invite');
  if (inv) return vAccept(inv);
  const p = location.hash.replace(/^#\/?/, '').split('?')[0];
  if (!me) { try { me = await api('/me'); } catch {} }
  if (!me) return p === 'login' ? vLogin() : p === 'join' ? vJoin() : vLanding();
  if (['', 'login', 'join'].includes(p) || (p === 'dashboard' && me.role !== 'manager')) return go('home');
  ({ home: vHome, assistant: vAssistant, task: vTask, team: vTeam, dashboard: vDash }[p] || vHome)().catch(e => { if (e.status === 401) { me = null; go(''); } else fail(e); });
}
applyLang(); addEventListener('hashchange', route); route();
