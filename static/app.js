const $=s=>document.querySelector(s);let S={},page='overview',tab='callcenter',ed=null,demo={log:[],lang:'mr-IN'},fillerTab='all',fillerSearch='',fillersData=null,cmpData=null,cmpTab='all';
const api=(u,b,m='POST')=>fetch(u,b?{method:m,headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{}).then(r=>r.json());
const NAV=[['overview','Overview','◎'],['campaign','Campaigns','📢'],['callcenter','Call Center','☎'],['scheme','Scheme Calling','✦'],['scripts','Scripts','✎'],['kb','Knowledge Base','▤'],['fillers','Filler Dictionary','📖'],['demo','Live Demo','●'],['set','Integrations','⚙']];
const toast=t=>{const d=document.createElement('div');d.className='toast';d.textContent=t;document.body.appendChild(d);setTimeout(()=>d.remove(),3500)};
const fmt=t=>new Date(t).toLocaleString('en-IN',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const dur=s=>s?Math.floor(s/60)+'m '+(s%60)+'s':'-';
const oc=o=>`<span class="chip ${o=='Resolved'?'ok':o=='Sent to expert'?'warn':o=='In progress'?'cy':'bad'}">${o}</span>`;
const sn=id=>(S.schemes.find(s=>s.id==id)||{}).name||'';
const bn=c=>c.bot=='scheme'?`<span class="chip vi">Scheme: ${sn(c.scheme)}</span>`:'<span class="chip cy">Call Center</span>';
async function load(){S=await api('/api/state');await draw()}
async function draw(){
  $('#nav').innerHTML=NAV.map(n=>`<button class="${n[0]==page?'on':''}" onclick="go('${n[0]}')"><span>${n[2]}</span>${n[1]}</button>`).join('');
  const f={overview,campaign:campaignPage,callcenter:()=>botPage('callcenter'),scheme:schemePage,scripts,kb,fillers:fillersPage,demo:demoPage,set}[page];
  const html=await f();
  $('#m').innerHTML=html;
  after&&after();
  after=null;
}
let after=null;const go=async p=>{page=p;await draw()};
function count(){document.querySelectorAll('[data-n]').forEach(e=>{const t=+e.dataset.n,s=e.dataset.s||'';let st=null;const f=ts=>{st=st||ts;const p=Math.min((ts-st)/900,1);e.textContent=Math.round(t*p)+s;if(p<1)requestAnimationFrame(f)};requestAnimationFrame(f)})}
const kpi=(l,v,d,s)=>`<div class="glass kpi"><div class="l">${l}</div><div class="v" data-n="${v}" data-s="${s||''}">0</div><div class="d">${d||''}</div></div>`;
function stats(cs){const done=cs.filter(c=>c.outcome!='No answer'&&c.status!='live'),res=done.filter(c=>c.outcome=='Resolved').length,ex=cs.filter(c=>c.outcome=='Sent to expert').length;
 return{n:cs.length,pct:done.length?Math.round(res/done.length*100):0,ex,avg:Math.round(done.reduce((a,c)=>a+c.dur,0)/(done.length||1))}}
function chart(cs){const days=[...Array(7)].map((_,i)=>{const d=new Date(Date.now()-(6-i)*864e5);return d.toDateString()});
 const ser=b=>days.map(d=>cs.filter(c=>c.bot==b&&new Date(c.start).toDateString()==d).length),a=ser('callcenter'),s=ser('scheme'),mx=Math.max(...a,...s,1);
 const pts=v=>v.map((x,i)=>[40+i*(520/6),170-x/mx*140]),path=v=>pts(v).map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join(' ');
 return `<svg viewBox="0 0 600 200" style="width:100%"><defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22d3ee" stop-opacity=".45"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></linearGradient></defs>
 <path d="${path(a)} L560 170 L40 170Z" fill="url(#g1)"/><path d="${path(a)}" fill="none" stroke="#22d3ee" stroke-width="3"/><path d="${path(s)}" fill="none" stroke="#a78bfa" stroke-width="3" stroke-dasharray="6 5"/>
 ${days.map((d,i)=>`<text x="${40+i*(520/6)}" y="192" fill="#8b97b8" font-size="11" text-anchor="middle">${d.slice(0,3)}</text>`).join('')}</svg><div class="row" style="font-size:12px;color:var(--mut)"><span><b style="color:var(--c1)">●</b> Call Center</span><span><b style="color:var(--c2)">●</b> Scheme Calling</span></div>`}
function table(cs){return `<div class="wrap"><table><tr><th>Time</th><th>Name</th><th>Bot</th><th>Channel</th><th>Duration</th><th>Outcome</th></tr>${cs.slice(0,14).map(c=>`<tr class="r" onclick="openCall('${c.id}')"><td>${fmt(c.start)}</td><td>${c.name}</td><td>${bn(c)}</td><td>${c.channel}</td><td>${dur(c.dur)}</td><td>${oc(c.outcome)}</td></tr>`).join('')}</table></div>`}
function overview(){const st=stats(S.calls),cc=S.calls.filter(c=>c.bot=='callcenter').length,sc=S.calls.length-cc;after=count;
 return `<h1>Command Centre</h1><div class="sub">Live view of every call across both bots · Natural politician & civic outreach in Marathi (मराठी)</div><div class="grid k4">${kpi('Total calls',st.n,'+12% this week')}${kpi('Resolved by bot',st.pct,'no human needed','%')}${kpi('Expert hand-offs',st.ex,'warm transfers')}${kpi('Learned Fillers',(S.fillers_summary&&S.fillers_summary.total_words)||37,'dictionary size')}</div>
 <div class="grid two" style="margin-top:16px"><div class="glass"><h2>Calls this week</h2>${chart(S.calls)}</div><div class="glass"><h2>Bot split</h2><div style="width:150px;height:150px;border-radius:50%;margin:10px auto;background:conic-gradient(var(--c1) 0 ${cc/(cc+sc||1)*100}%,var(--c2) 0);display:grid;place-items:center"><div style="width:100px;height:100px;border-radius:50%;background:#0b1022;display:grid;place-items:center;font-weight:800;font-size:22px">${cc+sc}</div></div>
 <div class="row" style="font-size:13px"><span><b style="color:var(--c1)">●</b> Call Center ${cc}</span><span><b style="color:var(--c2)">●</b> Scheme ${sc}</span></div></div></div>
 <div class="glass" style="margin-top:16px"><h2>Recent calls</h2>${table(S.calls)}</div>`}

// --- Outbound Campaign Manager Page
async function campaignPage(){
  cmpData = await api('/api/campaign/state', null, 'GET');
  after = () => { count(); fillCmpScripts(); };
  const q = cmpData.queue || [], total = cmpData.total || q.length;
  const completed = cmpData.completed || q.filter(c=>c.status=='completed'||c.status=='connected').length;
  const pending = q.filter(c=>c.status=='pending').length;
  const pct = total ? Math.min(100, Math.round((completed / total) * 100)) : 0;
  const isRunning = cmpData.status === 'running';
  const isPaused = cmpData.status === 'paused';

  let filtered = q;
  if(cmpTab === 'pending') filtered = q.filter(c=>c.status === 'pending');
  else if(cmpTab === 'calling') filtered = q.filter(c=>c.status === 'calling');
  else if(cmpTab === 'completed') filtered = q.filter(c=>c.status === 'completed' || c.status === 'connected');

  const curr = cmpData.current_call;

  return `<h1>Outbound Campaign Manager</h1>
  <div class="sub">Upload voter & citizen lists to automatically dial contacts one-by-one with natural politician opening</div>
  <div class="grid k4">
    ${kpi('Total In Queue', total, 'contacts to dial')}
    ${kpi('Calls Dialed', completed, 'one-by-one completed')}
    ${kpi('Remaining', pending, 'pending calls')}
    <div class="glass kpi">
      <div class="l">Campaign Status</div>
      <div class="v" style="font-size:24px;margin-top:4px">
        <span class="chip ${isRunning?'ok':isPaused?'warn':'cy'}">
          ${isRunning?'<span class="dot"></span> Dialing Live':isPaused?'⏸ Paused':'⏹ Idle'}
        </span>
      </div>
      <div class="d">${pct}% progress</div>
    </div>
  </div>

  <div class="grid two" style="margin-top:16px">
    <div class="glass">
      <h2>Campaign Controller</h2>
      <div class="sub">Configure automated dialer and start calling your list one-by-one</div>
      <div class="row">
        <div>
          <label>Campaign Bot</label>
          <select id="cmp_bot" onchange="fillCmpScripts()">
            <option value="callcenter" ${cmpData.bot=='callcenter'?'selected':''}>Call Center (मतदार संपर्क / Politician Outreach)</option>
            <option value="scheme" ${cmpData.bot=='scheme'?'selected':''}>Scheme Calling (शासकीय योजना जनजागृती)</option>
          </select>
        </div>
        <div>
          <label>Speech Script (Live)</label>
          <select id="cmp_script"></select>
        </div>
      </div>
      <div class="row" style="margin-top:10px">
        <div>
          <label>Dialing Mode</label>
          <select id="cmp_mode">
            <option value="auto" ${cmpData.mode=='auto'?'selected':''}>Interactive / Simulated Dialing (Zero charges, Sarvam voice)</option>
            <option value="phone" ${cmpData.mode=='phone'?'selected':''}>Real Phone Outbound (Twilio Call)</option>
          </select>
        </div>
      </div>

      <div style="margin:16px 0">
        <div class="row" style="justify-content:space-between;margin-bottom:6px">
          <span style="font-size:12px;color:var(--mut)"><b>Dialing Progress:</b> ${completed} of ${total} (${pct}%)</span>
          <span style="font-size:12px;font-weight:700;color:var(--c1)">${pct}%</span>
        </div>
        <div class="bar" style="height:12px;border-radius:6px"><i style="width:${pct}%"></i></div>
      </div>

      <div class="row" style="margin-top:16px">
        ${!isRunning ? `
          <button class="btn" onclick="startCmp()">${isPaused?'▶ Resume Campaign':'▶ Start Calling List'}</button>
        ` : `
          <button class="btn g" onclick="pauseCmp()">⏸ Pause</button>
        `}
        <button class="btn g" onclick="stopCmp()" ${!isRunning&&!isPaused?'disabled':''}>⏹ Stop</button>
        <button class="btn g" onclick="restartCmp()">↺ Restart List</button>
      </div>

      ${curr ? `
      <div class="glass" style="margin-top:18px;background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.3)">
        <div class="row" style="justify-content:space-between">
          <span><span class="dot"></span> <b>Active Call:</b> ${curr.contact.name} (${curr.contact.phone||'-'})</span>
          <span class="chip ok">${curr.status}</span>
        </div>
        <div class="sub" style="margin:6px 0 0"><b>Booth:</b> ${curr.contact.booth||'-'} · <b>Lang:</b> ${curr.lang}</div>
        <div style="font-size:13px;color:var(--ink);margin-top:8px;line-height:1.5">
          <i style="color:var(--mut)">Politician Spoken Opening:</i><br>
          "${curr.opening}"
        </div>
      </div>` : ''}
    </div>

    <div class="glass">
      <h2>+ Upload Campaign Contact List</h2>
      <div class="sub">Upload CSV file or paste voter contacts (Name, Phone, Polling Booth, Language)</div>
      <label>Paste CSV contacts (one per line)</label>
      <textarea id="cmp_csv" rows="7" placeholder="Ramesh Pawar, 9820011223, Zilla Parishad School Ward 14, mr-IN&#10;Sunita Jadhav, 9820011224, Community Hall Ward 9, mr-IN&#10;Mahesh Kale, 9820011225, Gram Panchayat Office, mr-IN"></textarea>
      
      <div class="row" style="margin:10px 0">
        <div>
          <label style="margin:0 0 4px">Or select CSV / TXT file</label>
          <input type="file" accept=".csv,.txt" onchange="loadCmpFile(this)">
        </div>
      </div>

      <div class="row" style="margin-top:14px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
          <input type="checkbox" id="cmp_replace" style="width:auto;margin:0"> Replace existing queue
        </label>
        <button class="btn" onclick="uploadCmpList()">Upload & Queue List</button>
      </div>
      <div class="sub" style="margin-top:12px;font-size:12px">
        ✓ Contacts are automatically assigned to the outbound dialer queue.<br>
        ✓ Each call opens respectfully as a direct outreach from the politician/seva office.
      </div>
    </div>
  </div>

  <div class="glass" style="margin-top:16px">
    <div class="row" style="justify-content:space-between;margin-bottom:12px">
      <h2>Voter / Citizen Queue (${total})</h2>
      <div class="tabs" style="margin-bottom:0">
        <button class="btn ${cmpTab=='all'?'':'g'}" onclick="cmpTab='all';draw()">All (${total})</button>
        <button class="btn ${cmpTab=='pending'?'':'g'}" onclick="cmpTab='pending';draw()">Pending (${pending})</button>
        <button class="btn ${cmpTab=='calling'?'':'g'}" onclick="cmpTab='calling';draw()">Dialing (${q.filter(c=>c.status=='calling').length})</button>
        <button class="btn ${cmpTab=='completed'?'':'g'}" onclick="cmpTab='completed';draw()">Completed (${completed})</button>
      </div>
    </div>
    <div class="wrap" style="max-height:420px;overflow-y:auto">
      <table>
        <tr><th>#</th><th>Name</th><th>Phone</th><th>Polling Booth / Area</th><th>Language</th><th>Status</th><th>Outcome</th><th>Action</th></tr>
        ${filtered.map((c,i)=>`<tr>
          <td>${i+1}</td>
          <td><b>${c.name}</b></td>
          <td>${c.phone ? c.phone.slice(0,3)+'xxxxxx'+c.phone.slice(-2) : '-'}</td>
          <td>${c.booth||'-'}</td>
          <td><span class="chip cy">${c.lang||'mr-IN'}</span></td>
          <td><span class="chip ${c.status=='completed'||c.status=='connected'?'ok':c.status=='calling'?'warn':c.status=='failed'?'bad':''}">${c.status||'pending'}</span></td>
          <td>${c.outcome ? `<span class="chip ok">${c.outcome}</span>` : '-'}</td>
          <td><button class="btn g" style="padding:4px 8px;font-size:11px" onclick="testCallContact('${c.id}')">☎ Call now</button></td>
        </tr>`).join('') || '<tr><td colspan="8" class="sub" style="text-align:center">No contacts in this list</td></tr>'}
      </table>
    </div>
  </div>`;
}

function fillCmpScripts(){
  const bot = $('#cmp_bot') ? $('#cmp_bot').value : 'callcenter';
  const scs = S.scripts.filter(s=>s.status=='live'&&s.bot==bot);
  const el = $('#cmp_script');
  if(el){
    el.innerHTML = scs.map(s=>`<option value="${s.id}">${s.title} (${s.lang})</option>`).join('') || '<option value="">Default Live Script</option>';
  }
}

async function startCmp(){
  const bot = $('#cmp_bot').value;
  const scriptId = $('#cmp_script').value;
  const mode = $('#cmp_mode').value;
  await api('/api/campaign/start', {bot, scriptId, mode});
  toast('Outbound campaign started! Dialing contacts one-by-one...');
  cmpData = await api('/api/campaign/state', null, 'GET');
  await draw();
}

async function pauseCmp(){
  await api('/api/campaign/pause');
  toast('Campaign paused');
  cmpData = await api('/api/campaign/state', null, 'GET');
  await draw();
}

async function stopCmp(){
  await api('/api/campaign/stop');
  toast('Campaign stopped');
  cmpData = await api('/api/campaign/state', null, 'GET');
  await draw();
}

async function restartCmp(){
  const bot = $('#cmp_bot').value;
  const scriptId = $('#cmp_script').value;
  const mode = $('#cmp_mode').value;
  await api('/api/campaign/start', {bot, scriptId, mode, restart: true});
  toast('Restarted campaign list from beginning');
  cmpData = await api('/api/campaign/state', null, 'GET');
  await draw();
}

async function uploadCmpList(){
  const csv = $('#cmp_csv').value.trim();
  const replace = $('#cmp_replace').checked;
  if(!csv) return toast('Please enter or upload contacts first');
  const r = await api('/api/campaign/upload', {csv, replace});
  toast(`Added ${r.added} contacts to campaign!`);
  $('#cmp_csv').value = '';
  cmpData = await api('/api/campaign/state', null, 'GET');
  await draw();
}

function loadCmpFile(input){
  if(input.files && input.files[0]){
    const reader = new FileReader();
    reader.onload = e => {
      $('#cmp_csv').value = e.target.result;
      toast('File loaded into CSV box. Click Upload & Queue List.');
    };
    reader.readAsText(input.files[0]);
  }
}

async function testCallContact(cid){
  const c = (cmpData && cmpData.queue && cmpData.queue.find(x=>x.id==cid)) || S.contacts.find(x=>x.id==cid);
  toast(`Initiating direct call to ${c ? c.name : 'contact'}...`);
  const r = await api('/api/sim/start', {bot: 'callcenter', contactId: cid});
  go('demo');
  demo.id = r.callId;
  demo.lang = r.lang;
  logIt('b', r.opening);
  play(r, r.opening);
}

function botPage(bot){const cs=S.calls.filter(c=>c.bot==bot),st=stats(cs),live=cs.filter(c=>c.status=='live'),sc=S.scripts.filter(s=>s.bot==bot&&s.status=='live');after=count;
 return `<h1>Call Center</h1><div class="sub">General voter-help bot, driven by its own live Marathi script with external civic reference</div><div class="grid k4">${kpi('Calls',st.n)}${kpi('Resolved',st.pct,'','%')}${kpi('Hand-offs',st.ex)}${kpi('Avg seconds',st.avg)}</div>
 <div class="grid eq" style="margin-top:16px"><div class="glass"><h2>Live monitor</h2>${live.length?live.map(c=>`<div class="row" style="padding:8px 0"><span><span class="dot"></span> ${c.name} · ${c.channel}</span><button class="btn g" onclick="toast('Listen-in joins via Twilio conference in production')">Listen in</button><button class="btn g" onclick="toast('Take-over transfers the caller to you')">Take over</button></div>`).join(''):'<div class="sub">No live calls right now. Start one from Live Demo.</div>'}</div>
 <div class="glass"><h2>Active script</h2>${sc.map(s=>`<div><b>${s.title}</b> <span class="chip ok">live</span><div class="sub" style="margin:6px 0">Valid ${s.from} to ${s.to} · ${s.lang}</div><div style="color:var(--mut)">${s.body}</div></div>`).join('')||'No live script'}<br><button class="btn" onclick="tab='callcenter';go('scripts')">Edit scripts</button></div></div>
 <div class="glass" style="margin-top:16px"><h2>All calls, recordings and transcripts</h2>${table(cs)}</div>`}
function schemePage(){const cs=S.calls.filter(c=>c.bot=='scheme');after=count;
 return `<h1>Scheme Calling</h1><div class="sub">Scheme-wise bot with a human expert behind every scheme</div><div class="grid k4">${S.schemes.map(s=>{const x=cs.filter(c=>c.scheme==s.id),h=x.filter(c=>c.outcome=='Sent to expert').length,sc=S.scripts.find(q=>q.bot=='scheme'&&q.scheme==s.id&&q.status=='live');
 return `<div class="glass"><h2>${s.name}</h2><div class="sub" style="margin:0 0 8px">${x.length} calls · ${h} hand-offs</div><div class="bar"><i style="width:${x.length?100-h/x.length*100:0}%"></i></div><label>Expert name</label><input id="en_${s.id}" value="${s.expert.name}"><label>Expert phone (hand-off)</label><input id="ep_${s.id}" value="${s.expert.phone}" placeholder="+91..."><div style="margin:10px 0"><span class="chip ${sc?'ok':'bad'}">${sc?'script live':'no live script'}</span></div><button class="btn g" onclick="saveScheme('${s.id}')">Save expert</button></div>`}).join('')}</div>
 <div class="grid eq" style="margin-top:16px"><div class="glass"><h2>Beneficiary list</h2><div class="wrap"><table><tr><th>Name</th><th>Scheme</th><th>Phone</th><th>Language</th></tr>${S.contacts.slice(-8).map(c=>`<tr><td>${c.name}</td><td>${sn(c.scheme)}</td><td>${c.phone?c.phone.slice(0,3)+'xxxxxx'+c.phone.slice(-2):'-'}</td><td>${c.lang}</td></tr>`).join('')}</table></div>
 <label>Add contacts (CSV: name, phone, scheme id, booth, language)</label><textarea id="csv" rows="3" placeholder="Anita More,+919800000000,health,Ward 5 school,mr-IN"></textarea><div class="row" style="margin-top:10px"><button class="btn g" onclick="addCsv()">Upload list</button><button class="btn" onclick="go('campaign')">Go to Campaigns</button></div></div>
 <div class="glass"><h2>Scheme calls</h2>${table(cs)}</div></div>`}
async function saveScheme(id){await api('/api/scheme',{id,expert:{name:$('#en_'+id).value,phone:$('#ep_'+id).value},info:S.schemes.find(s=>s.id==id).info});toast('Expert saved');load()}
async function addCsv(){await api('/api/contacts',{csv:$('#csv').value});toast('Contacts added');load()}
function openCall(id){const c=S.calls.find(x=>x.id==id);$('#ov').innerHTML=`<div class="modal" onclick="if(event.target==this)this.remove()"><div class="glass"><h2>${c.name} ${bn(c)} ${oc(c.outcome)}</h2><div class="sub">${fmt(c.start)} · ${dur(c.dur)} · ${c.channel} · <span class="chip cy">${c.lang||'mr-IN'}</span></div>${c.rec?`<audio controls style="width:100%" src="/api/rec?id=${c.id}"></audio>`:'<div class="sub">Recording appears here for real phone calls (Twilio).</div>'}<h2 style="margin-top:14px">Transcript</h2><div class="chat" style="height:auto;max-height:300px">${c.transcript.map(t=>`<div class="m ${t.r=='bot'?'b':'u'}">${t.t}${t.fillers&&t.fillers.length?`<div style="font-size:11px;color:var(--c3);margin-top:4px">🏷️ Fillers: ${t.fillers.join(', ')}</div>`:''}</div>`).join('')||'<div class="sub">No conversation</div>'}</div><br><button class="btn g" onclick="this.closest('.modal').remove()">Close</button></div></div>`}
function scripts(){const list=S.scripts.filter(s=>s.bot==tab);if(!ed||ed.bot!=tab)ed=list[0]?{...list[0]}:{bot:tab,scheme:'',title:'',lang:'mr-IN',from:'',to:'',body:'',status:'draft'};
 return `<h1>Script Manager</h1><div class="sub">The script decides what each bot says. Update it every 15 to 20 days. Natural politician outreach in Marathi.</div><div class="tabs"><button class="btn ${tab=='callcenter'?'':'g'}" onclick="tab='callcenter';ed=null;draw()">Call Center scripts</button><button class="btn ${tab=='scheme'?'':'g'}" onclick="tab='scheme';ed=null;draw()">Scheme scripts</button></div>
 <div class="grid two"><div class="glass"><h2>${ed.id?'Edit script':'New script'}</h2><div class="row"><div><label>Title</label><input id="t" value="${ed.title}"></div><div><label>Language</label><select id="l">${['mr-IN','hi-IN','en-IN'].map(x=>`<option ${x==ed.lang?'selected':''}>${x}</option>`).join('')}</select></div>${tab=='scheme'?`<div><label>Scheme</label><select id="sc">${S.schemes.map(s=>`<option value="${s.id}" ${s.id==ed.scheme?'selected':''}>${s.name}</option>`).join('')}</select></div>`:''}</div>
 <div class="row"><div><label>Valid from</label><input type="date" id="f" value="${ed.from}"></div><div><label>Valid to</label><input type="date" id="to" value="${ed.to}"></div></div><label>What the bot will say (use variables)</label><textarea id="b" rows="6">${ed.body}</textarea>
 <div class="row" style="margin:8px 0"><button class="btn g" onclick="ins('{name}')">{name}</button><button class="btn g" onclick="ins('{booth}')">{booth}</button><button class="btn g" onclick="ins('{scheme}')">{scheme}</button></div>
 <div class="row"><button class="btn g" onclick="prev()">▶ Preview voice</button><button class="btn g" onclick="saveS('draft')">Save draft</button><button class="btn" onclick="saveS('live')">Publish live</button></div></div>
 <div class="glass"><h2>Versions</h2>${list.map(s=>`<div class="row" style="padding:8px 0;border-bottom:1px solid var(--gb)" onclick="ed={...S.scripts.find(x=>x.id=='${s.id}')};draw()"><span>${s.title}<div class="sub" style="margin:0">${s.from} to ${s.to} · ${s.lang}</div></span><span class="chip ${s.status=='live'?'ok':s.status=='draft'?'warn':''}" style="flex:0">${s.status}</span></div>`).join('')}<button class="btn g" style="margin-top:12px" onclick="ed={bot:tab,scheme:'',title:'',lang:'mr-IN',from:'',to:'',body:'',status:'draft'};draw()">+ New script</button></div></div>`}
const ins=v=>{const e=$('#b');e.setRangeText(v,e.selectionStart,e.selectionEnd,'end');e.focus()};
async function saveS(status){const o={id:ed.id,bot:tab,scheme:tab=='scheme'?$('#sc').value:'',title:$('#t').value,lang:$('#l').value,from:$('#f').value,to:$('#to').value,body:$('#b').value,status};const r=await api('/api/script',o);ed=r;toast(status=='live'?'Published. Both bots use it from the next call.':'Draft saved');load()}
async function prev(){speak($('#b').value.replace(/\{name\}/g,'Ramesh').replace(/\{booth\}/g,'Ward 14 school').replace(/\{scheme\}/g,'Health Support'),$('#l').value)}
async function speak(text,lang,ob,tx){
  if(window.__activeAudio){try{window.__activeAudio.pause();window.__activeAudio.currentTime=0;}catch(e){}window.__activeAudio=null;}
  if(window.speechSynthesis)window.speechSynthesis.cancel();
  const r=await api('/api/preview',{text,lang});
  const orb=$('.orb');
  if(r&&r.audio){
    const a=new Audio('data:audio/wav;base64,'+r.audio);
    window.__activeAudio=a;
    if(orb)orb.classList.add('talk');
    a.onended=()=>{if(orb)orb.classList.remove('talk');if(window.__activeAudio===a)window.__activeAudio=null;};
    a.onerror=()=>{if(orb)orb.classList.remove('talk');if(window.__activeAudio===a)window.__activeAudio=null;};
    a.play().catch(e=>{console.warn('Audio play error:',e);if(orb)orb.classList.remove('talk');});
  }else{
    const u=new SpeechSynthesisUtterance(text);
    u.lang=lang;
    speechSynthesis.speak(u);
  }
}
function kb(){return `<h1>Knowledge Base</h1><div class="sub">External civic guidelines, voter ID alternatives & government schemes referenced by the bot</div><div class="grid two"><div class="glass"><h2>Documents & FAQ</h2>${S.knowledge.map(k=>`<div style="padding:10px 0;border-bottom:1px solid var(--gb)"><b>${k.title}</b> <span class="chip ok">indexed</span><div class="sub" style="margin:4px 0">${k.text.slice(0,180)}...</div></div>`).join('')}</div>
 <div class="glass"><h2>Add brochure text</h2><label>Title</label><input id="kt"><label>Text (paste, or load a .txt file)</label><textarea id="kx" rows="7"></textarea><input type="file" accept=".txt" onchange="const r=new FileReader();r.onload=()=>$('#kx').value=r.result;r.readAsText(this.files[0])" style="margin:8px 0"><button class="btn" onclick="addK()">Add to knowledge base</button></div></div>`}
async function addK(){await api('/api/knowledge',{title:$('#kt').value||'Untitled',text:$('#kx').value});toast('Indexed');load()}

// --- Filler words dictionary page
async function fillersPage(){
  if(!fillersData) fillersData = await api('/api/fillers');
  after = count;
  const f = (fillersData && fillersData.fillers) || {}, st = (fillersData && fillersData.stats) || {total_words:0,total_occurrences:0,by_lang:{}};
  const mrCount = (st.by_lang && st.by_lang['mr-IN']) || Object.keys(f['mr-IN']||{}).length;
  const hiCount = (st.by_lang && st.by_lang['hi-IN']) || Object.keys(f['hi-IN']||{}).length;
  const enCount = (st.by_lang && st.by_lang['en-IN']) || Object.keys(f['en-IN']||{}).length;

  let words = [];
  for(const [lang, dict] of Object.entries(f)){
    for(const [w, meta] of Object.entries(dict)){
      words.push({lang, word: w, count: meta.count || 0, meaning: meta.meaning || '', category: meta.category || '', last_seen: meta.last_seen || 0});
    }
  }
  words.sort((a,b)=>b.count - a.count);

  if(fillerTab !== 'all') words = words.filter(w=>w.lang === fillerTab);
  if(fillerSearch) words = words.filter(w=>w.word.toLowerCase().includes(fillerSearch.toLowerCase()) || w.meaning.toLowerCase().includes(fillerSearch.toLowerCase()));

  const langBadge = l => l === 'mr-IN' ? '<span class="chip vi">मराठी (mr-IN)</span>' : l === 'hi-IN' ? '<span class="chip cy">हिंदी (hi-IN)</span>' : '<span class="chip ok">English</span>';

  return `<h1>Filler Words Dictionary & Self-Learner</h1>
  <div class="sub">Dynamic dictionary of conversational hesitation markers and colloquial fillers automatically learned from caller speech across Marathi, Hindi, and English</div>
  <div class="grid k4">
    ${kpi('Learned Fillers', st.total_words || words.length, 'across all languages')}
    ${kpi('Total Detections', st.total_occurrences || 0, 'hesitation moments recognized')}
    ${kpi('Marathi Fillers', mrCount, 'मराठी शब्द (म्हणजे, बघा, हो ना)')}
    ${kpi('Hindi / English', hiCount + enCount, 'मतलब, um, like')}
  </div>
  <div class="grid two" style="margin-top:16px">
    <div class="glass">
      <div class="row" style="justify-content:space-between;margin-bottom:12px">
        <div class="tabs" style="margin-bottom:0">
          <button class="btn ${fillerTab=='all'?'':'g'}" onclick="fillerTab='all';draw()">All (${(st.total_words)||words.length})</button>
          <button class="btn ${fillerTab=='mr-IN'?'':'g'}" onclick="fillerTab='mr-IN';draw()">मराठी (${mrCount})</button>
          <button class="btn ${fillerTab=='hi-IN'?'':'g'}" onclick="fillerTab='hi-IN';draw()">हिंदी (${hiCount})</button>
          <button class="btn ${fillerTab=='en-IN'?'':'g'}" onclick="fillerTab='en-IN';draw()">English (${enCount})</button>
        </div>
        <div style="max-width:200px">
          <input placeholder="Search words..." value="${fillerSearch}" oninput="fillerSearch=this.value;draw()">
        </div>
      </div>
      <div class="wrap" style="max-height:460px;overflow-y:auto">
        <table>
          <tr><th>Word</th><th>Language</th><th>Meaning</th><th>Category</th><th>Detections</th><th>Last Detected</th><th></th></tr>
          ${words.map(w=>`<tr>
            <td><b style="font-size:15px;color:var(--c1)">${w.word}</b></td>
            <td>${langBadge(w.lang)}</td>
            <td style="color:var(--mut)">${w.meaning}</td>
            <td><span class="chip warn">${w.category}</span></td>
            <td><b>${w.count}</b> <div class="bar" style="width:50px;display:inline-block;margin-left:6px;vertical-align:middle"><i style="width:${Math.min(100, w.count * 4)}%"></i></div></td>
            <td style="font-size:11px;color:var(--mut)">${w.last_seen ? fmt(w.last_seen) : 'pre-seeded'}</td>
            <td><button class="btn g" style="padding:3px 7px;font-size:11px" onclick="deleteFiller('${w.lang}','${w.word}')" title="Delete">✕</button></td>
          </tr>`).join('') || '<tr><td colspan="7" class="sub" style="text-align:center">No filler words match</td></tr>'}
        </table>
      </div>
    </div>
    <div class="glass">
      <h2>+ Add / Update Filler Word</h2>
      <div class="sub">Register new local colloquial filler phrases for the bot to recognize</div>
      <label>Language</label>
      <select id="flang">
        <option value="mr-IN">Marathi (मराठी)</option>
        <option value="hi-IN">Hindi (हिंदी)</option>
        <option value="en-IN">English (en-IN)</option>
      </select>
      <label>Filler Word or Phrase (e.g. म्हणजे, बघा, काय ते, खरं तर)</label>
      <input id="fword" placeholder="e.g. खरं तर">
      <label>Meaning / Role in Conversation</label>
      <input id="fmeaning" placeholder="e.g. actually / clarification filler">
      <label>Category</label>
      <select id="fcat">
        <option value="hesitation">Hesitation (अं, उं, um)</option>
        <option value="clarification">Clarification (म्हणजे, मतलब, I mean)</option>
        <option value="attention">Attention (बघा, ऐका ना, सुनिए)</option>
        <option value="transition">Transition (बरं, तो, so)</option>
        <option value="agreement">Agreement (हो ना, हाँ जी)</option>
        <option value="pause">Pause marker (एक मिनिट, एक सेकंड)</option>
      </select>
      <button class="btn" style="margin-top:16px;width:100%" onclick="addFiller()">Save to Dictionary</button>
      <div class="sub" style="margin-top:14px;font-size:12px;line-height:1.5">💡 <b>Self-Learning Active:</b> When callers speak filler words not yet in the dictionary, the AI brain detects and automatically registers them into this dictionary in real time!</div>
    </div>
  </div>`;
}

async function addFiller(){
  const lang=$('#flang').value, word=$('#fword').value.trim(), meaning=$('#fmeaning').value.trim(), category=$('#fcat').value;
  if(!word) return toast('Please enter a filler word');
  await api('/api/fillers',{lang, word, meaning, category});
  toast('Filler word saved');
  fillersData = await api('/api/fillers');
  await draw();
}

async function deleteFiller(lang, word){
  await api('/api/fillers',{lang, word},'DELETE');
  toast('Filler removed');
  fillersData = await api('/api/fillers');
  await draw();
}

// --- Live Demo with dynamic language adaptation & filler detection
function demoPage(){
  after=fillSc;
  const langTitle = demo.lang == 'mr-IN' ? 'Marathi (मराठी)' : demo.lang == 'hi-IN' ? 'Hindi (हिंदी)' : 'English (en-IN)';
  return `<h1>Live Demo</h1><div class="sub">Talk to the bot in Marathi, Hindi, or English — the bot opens with natural politician outreach, automatically adapts to your language, and learns filler words</div>
  <div class="grid eq"><div class="glass"><h2>Setup</h2><label>Bot</label>
  <select id="db" onchange="fillSc()">
    <option value="callcenter">Call Center bot (मतदार मदत व मार्गदर्शन)</option>
    <option value="scheme">Scheme bot (आरोग्य व शासकीय योजना)</option>
  </select>
  <label>Script (live)</label><select id="ds"></select>
  <label>Voice (Female Marathi)</label>
  <select id="dv">
    <option value="rupali" selected>Rupali (रुपाली - Authentic Maharashtrian Marathi Female)</option>
    <option value="priya">Priya (प्रिया - Expressive Female)</option>
    <option value="ritu">Ritu (रितू - Support Agent Female)</option>
    <option value="shruti">Shruti (श्रुती - Soft Female)</option>
    <option value="kavya">Kavya (काव्या - Clear Female)</option>
  </select>
  <label>Contact</label><select id="dc">${S.contacts.map(c=>`<option value="${c.id}">${c.name} · ${sn(c.scheme)} (${c.lang})</option>`).join('')}</select>
  <div class="row" style="margin-top:14px"><button class="btn" onclick="startDemo()">▶ Start browser call</button></div>
  <label>Or call a phone (Twilio, e.g. +9198xxxxxxx0)</label><div class="row"><input id="ph" placeholder="+91..."><button class="btn g" onclick="callPhone()">☎ Call this number</button></div></div>
  <div class="glass"><div class="orbw"><div class="orb"></div></div>
  <div id="langIndicator" class="sub" style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:8px">
    <span class="dot"></span> Active Language: <b id="langTxt" style="color:var(--c1)">${langTitle}</b>
    <span class="chip ok" style="font-size:11px">Auto-adapting</span>
  </div>
  <div class="chat" id="chat">${demo.log.map(l=>`<div class="m ${l.r}">${l.t}${l.fillers&&l.fillers.length?`<div style="font-size:11px;color:var(--c3);margin-top:4px;font-weight:600">🏷️ Fillers: ${l.fillers.join(', ')}</div>`:''}</div>`).join('')}</div>
  <div class="row" style="margin-top:10px"><input id="say" placeholder="Type in Marathi/Hindi/English or press mic..." onkeydown="if(event.key=='Enter')sayIt($('#say').value)"><button class="btn g" style="flex:0" onclick="mic()" title="Speak with mic">🎤</button><button class="btn" style="flex:0" onclick="sayIt($('#say').value)">Send</button></div></div></div>`;
}

function fillSc(){$('#ds').innerHTML=S.scripts.filter(s=>s.status=='live'&&s.bot==$('#db').value).map(s=>`<option value="${s.id}">${s.title}</option>`).join('')}
const logIt=(r,t,fillers)=>{
  demo.log.push({r,t,fillers});
  const c=$('#chat');
  if(c){
    c.innerHTML=demo.log.map(l=>`<div class="m ${l.r}">${l.t}${l.fillers&&l.fillers.length?`<div style="font-size:11px;color:var(--c3);margin-top:4px;font-weight:600">🏷️ Fillers: ${l.fillers.join(', ')}</div>`:''}</div>`).join('');
    c.scrollTop=1e9;
  }
};

function play(r,t){
  if(window.__activeAudio){try{window.__activeAudio.pause();window.__activeAudio.currentTime=0;}catch(e){}window.__activeAudio=null;}
  if(window.speechSynthesis)window.speechSynthesis.cancel();
  const orb=$('.orb');
  if(r&&r.audio){
    const a=new Audio('data:audio/wav;base64,'+r.audio);
    window.__activeAudio=a;
    if(orb)orb.classList.add('talk');
    a.onended=()=>{if(orb)orb.classList.remove('talk');if(window.__activeAudio===a)window.__activeAudio=null;};
    a.onerror=()=>{if(orb)orb.classList.remove('talk');if(window.__activeAudio===a)window.__activeAudio=null;};
    a.play().catch(e=>{console.warn('Audio play error:',e);if(orb)orb.classList.remove('talk');});
  }else{
    const u=new SpeechSynthesisUtterance(t);
    u.lang=demo.lang||'mr-IN';
    u.pitch=1.15;
    if(window.speechSynthesis){
      const vs=window.speechSynthesis.getVoices();
      const fv=vs.find(v=>(v.lang===u.lang||v.lang.startsWith(u.lang.slice(0,2)))&&(v.name.toLowerCase().includes('female')||v.name.toLowerCase().includes('rupali')||v.name.toLowerCase().includes('priya')||v.name.toLowerCase().includes('kalpana')||v.name.toLowerCase().includes('google')||!v.name.toLowerCase().includes('male')))
        ||vs.find(v=>v.lang===u.lang);
      if(fv)u.voice=fv;
    }
    u.onstart=()=>orb&&orb.classList.add('talk');
    u.onend=()=>orb&&orb.classList.remove('talk');
    speechSynthesis.speak(u);
  }
}

async function startDemo(){
  demo.log=[];
  const bot=$('#db').value;
  const speaker=$('#dv')?$('#dv').value:'rupali';
  demo.speaker=speaker;
  const r=await api('/api/sim/start',{bot,scriptId:$('#ds').value,contactId:$('#dc').value,speaker});
  demo.id=r.callId;
  demo.lang=r.lang||'mr-IN';
  logIt('b',r.opening);
  play(r,r.opening);
  const lt = demo.lang == 'mr-IN' ? 'Marathi (मराठी)' : demo.lang == 'hi-IN' ? 'Hindi (हिंदी)' : 'English (en-IN)';
  const el=$('#langTxt'); if(el) el.textContent = lt;
}

async function sayIt(t){
  if(!demo.id||!t)return toast('Start a call first');
  $('#say').value='';
  logIt('u',t);
  const speaker=demo.speaker||($('#dv')?$('#dv').value:'rupali');
  const r=await api('/api/sim/say',{callId:demo.id,text:t,speaker});
  if(r.lang && r.lang !== demo.lang){
    demo.lang = r.lang;
    const lt = r.lang == 'mr-IN' ? 'Marathi (मराठी)' : r.lang == 'hi-IN' ? 'Hindi (हिंदी)' : 'English (en-IN)';
    const el=$('#langTxt'); if(el) el.textContent = lt;
    toast('🌐 Switched language to ' + lt);
  }
  logIt('b',r.reply,r.detected_fillers);
  play(r,r.reply);
  if(r.handoff)toast('Hand-off: connecting the scheme expert');
  fillersData = null; // Refresh fillers on next view
  await load();
}

function mic(){
  const R=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!R)return toast('Use Chrome for the mic, or type');
  const r=new R();
  r.lang=demo.lang||'mr-IN';
  r.onresult=e=>sayIt(e.results[0][0].transcript);
  r.start();
  toast('Listening in ' + (demo.lang||'mr-IN') + '...');
}

async function callPhone(){const r=await api('/api/call',{to:$('#ph').value,bot:$('#db').value,scriptId:$('#ds').value,contactId:$('#dc').value});toast(r.error||'Calling now. Pick up the phone.')}
function set(){const s=S.status,row=(n,ok,d)=>`<div class="row" style="padding:12px 0;border-bottom:1px solid var(--gb)"><span><b>${n}</b><div class="sub" style="margin:0">${d}</div></span><span class="chip ${ok?'ok':'bad'}" style="flex:0">${ok?'connected':'add key in .env'}</span></div>`;
 return `<h1>Integrations</h1><div class="sub">Keys live in the .env file, never in the browser</div><div class="glass">${row('Twilio (phone calls and recording)',s.twilio,'Free trial. Verified numbers only.')}${row('Sarvam AI (Indian voice: speech-to-text and text-to-speech)',s.sarvam,'Authentic Marathi Female Voice (Priya - Bulbul v3) + Saarika v2.5 STT')}${row('Groq (AI brain)',s.groq,'Llama / GPT-OSS multilingual model')}${row('Google Gemini (AI brain, free tier)',s.google,'Alternative to Groq for the demo')}
 <div class="sub" style="margin-top:12px">Public URL: ${s.base}. Twilio inbound webhook: ${s.base}/twilio/voice</div></div>`}

load();
setInterval(async () => {
  if(page === 'campaign' && cmpData && cmpData.status === 'running'){
    cmpData = await api('/api/campaign/state', null, 'GET');
    await draw();
  } else if(page !== 'scripts' && page !== 'demo' && page !== 'fillers' && page !== 'campaign' && !$('#ov').innerHTML){
    await load();
  }
}, 3000);
