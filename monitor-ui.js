(() => {
  'use strict';
  const KEY = 'internhunt.monitor.v1';
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const webURL = value => { try {const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'#';} catch{return '#';} };
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { /* recover with defaults */ }
  let model = window.INTERN_MONITOR || {jobs:{},sources:{},events:[],companies:[]};
  let query='', filter='open', watchlist=true, location='all', hideCitizenOnly=preferences.hideCitizenOnly!==false, limit=8;
  const savePreferences = () => {try {localStorage.setItem(KEY,JSON.stringify(preferences));} catch {window.alert('Browser storage is unavailable. Tracking cannot be saved here.');}};
  const date = value => value ? new Date(value).toLocaleString() : 'Never';
  const citizenshipKey = r => (r.company+'\0'+r.title).toLowerCase();
  const citizenOnlyJobs = () => new Set(Object.values(model.jobs).filter(r=>r.sponsorship==='U.S. Citizenship is Required').map(citizenshipKey));
  const citizenshipRequired = (r, keys) => r.sponsorship === 'U.S. Citizenship is Required' || keys.has(citizenshipKey(r));
  const toFeed = r => ({c:r.company,t:r.title,u:r.url,l:r.locations.join(' · '),m:r.season||'Season not confirmed',g:'',s:({'Does Not Offer Sponsorship':'no','U.S. Citizenship is Required':'us','Offers Sponsorship':'yes'})[r.sponsorship]||'',d:r.first_seen.slice(0,10),dmv:r.locations.some(l=>/\b(VA|Virginia|DC|MD|Maryland|Arlington|Reston|McLean|Herndon|Bethesda)\b/i.test(l))?1:0,rem:r.remote||r.locations.some(l=>/remote/i.test(l))?1:0});
  function syncFeed(){const citizenOnly=citizenOnlyJobs();window.setMonitorFeed(Object.values(model.jobs).filter(j=>j.status==='open'&&(!hideCitizenOnly||!citizenshipRequired(j,citizenOnly))).map(toFeed));}
  function render(){
    const all=Object.values(model.jobs), citizenOnly=citizenOnlyJobs(), sources=Object.values(model.sources).filter(s=>s.enabled!==false);
    const latest=new Map();
    for(const event of model.events) if(event.job_id) latest.set(event.job_id,event);
    const unread=model.events.filter(e=>['new','reopened'].includes(e.kind)&&e.at>(preferences.readThrough||'')&&(!watchlist||e.company_id));
    const ignored=preferences.ignored||{};
    const selected=all.filter(r=>{
      if(watchlist&&!r.company_id)return false;
      if(hideCitizenOnly&&citizenshipRequired(r,citizenOnly))return false;
      if(filter==='ignored')return !!ignored[r.id];
      if(ignored[r.id])return false;
      if(filter==='open'&&r.status!=='open')return false;
      if(filter==='closed'&&r.status!=='closed')return false;
      if(filter==='new'&&!unread.some(e=>e.job_id===r.id))return false;
      if(location==='dmv'&&!toFeed(r).dmv)return false;
      if(location==='remote'&&!toFeed(r).rem)return false;
      return (r.company+' '+r.title+' '+r.locations.join(' ')).toLowerCase().includes(query.toLowerCase());
    }).sort((a,b)=>a.priority.localeCompare(b.priority)||(latest.get(b.id)?.at||b.first_seen).localeCompare(latest.get(a.id)?.at||a.first_seen));
    const ok=sources.filter(s=>s.status==='ok').length, partial=sources.filter(s=>s.status==='partial').length, failed=sources.filter(s=>s.status==='error');
    const pageWatches=sources.filter(s=>s.status==='page_watch');
    const pageChanges=model.events.filter(e=>e.kind==='page_changed'&&e.at>(preferences.readThrough||''));
    const missing=model.companies.filter(c=>c.enabled!==false&&!c.careers_urls?.length);
    const stale=model.generated_at && Date.now()-Date.parse(model.generated_at)>36*3600000;
    document.getElementById('monitor').innerHTML=`
      <h2>Daily job monitor</h2>
      <p>${model.generated_at?'Last check: '+safe(date(model.generated_at)):'Run the checker to start monitoring.'} · Your application statuses stay under your control.</p>
      ${stale?'<p class="monitor-warning">These results are more than 36 hours old. Run the daily workflow and reload the latest board data.</p>':''}
      <div class="monitor-summary"><span>${unread.length} unread role updates</span><span>${all.filter(j=>j.status==='open').length} open or discovered roles</span><span>${ok} complete sources</span><span>${partial} partial sources</span><span>${pageWatches.length} page watches</span><span>${failed.length+missing.length} need attention</span></div>
      ${pageChanges.length?`<p class="monitor-warning">${pageChanges.length} careers pages changed. Review: ${pageChanges.slice(0,12).map(e=>`<a href="${safe(webURL(e.url))}" target="_blank" rel="noopener">${safe(e.company)}</a>`).join(', ')}. These changes are not confirmed new roles.</p>`:''}
      <div class="monitor-controls">
        <input id="mq" aria-label="Search monitored jobs" placeholder="Search roles, companies, locations" value="${safe(query)}">
        <select id="mf" aria-label="Job status"><option value="open">Open roles</option><option value="new">Unread updates</option><option value="closed">Closed roles</option><option value="ignored">Ignored roles</option></select>
        <select id="ml" aria-label="Job location"><option value="all">All locations</option><option value="dmv">DC / MD / VA</option><option value="remote">Remote</option></select>
        <label><input type="checkbox" id="mw" ${watchlist?'checked':''}>My companies only</label>
        <label><input type="checkbox" id="mc" ${hideCitizenOnly?'checked':''}>Hide U.S.-citizen-only</label>
        <button class="mini" id="markRead">Mark updates read</button><button class="mini" id="reloadMonitor">Reload results</button>
      </div>
      <p>${selected.length} matching roles. Alerts start after a source’s first successful check. “Open” means last reported open by a source.</p>
      <div class="monitor-jobs">${selected.slice(0,limit).map(r=>{
        const event=latest.get(r.id), fresh=event&&event.at>(preferences.readThrough||'');
        const staleJob=!r.last_verified||Date.now()-Date.parse(r.last_verified)>36*3600000;
        const saved=preferences.jobs?.[r.id]||'not_started';
        return `<article class="monitor-job"><span class="event">${safe(fresh?event.kind:r.priority+' · '+r.status)}</span>
          <h3>${safe(r.company)}</h3><div>${safe(r.title)}</div><p>${safe(r.locations.slice(0,3).join(' · ')||'Location not supplied')}${r.locations.length>3?' · +'+(r.locations.length-3)+' more':''}</p>
          ${r.locations.length>3?`<details><summary>All locations</summary><p>${safe(r.locations.join(' · '))}</p></details>`:''}
          <p>${safe(r.season||'Season not confirmed')} · ${safe(!r.sponsorship||r.sponsorship==='Other'?'Sponsorship not supplied':r.sponsorship)}</p>
          <p>${r.verified?'Last reported open: '+safe(date(r.last_verified)):'Unverified posting link — check employer page'}${staleJob&&r.status==='open'?' · Needs a fresh check':''}</p>
          <label>My application <select data-app="${r.id}" aria-label="Application status for ${safe(r.company+' '+r.title)}">${[['not_started','Not started'],['saved','Saved'],['applied','Applied'],['interview','Interview'],['offer','Offer'],['rejected','Rejected']].map(([v,l])=>`<option value="${v}" ${saved===v?'selected':''}>${l}</option>`).join('')}</select></label>
          <div class="actions"><a href="${safe(webURL(r.url))}" target="_blank" rel="noopener noreferrer">Open posting ↗</a><button class="mini" data-track="${r.id}">Add to company</button><button class="mini" data-ignore="${r.id}">${ignored[r.id]?'Unignore':'Ignore'}</button></div></article>`;
      }).join('')||'<p>No roles match these filters.</p>'}</div>
      ${selected.length>limit?'<button class="mini" id="moreMonitor" style="margin-top:12px">Show more roles</button>':''}
      <details><summary>Source coverage and problems (${sources.length+missing.length})</summary><p>Partial sources discover jobs but never infer closures from missing listings. Page watches alert when visible page content changes; they cannot verify individual jobs and may flag unrelated text changes. Companies without a careers URL can still match the community feed.</p><div class="monitor-sources">${[...failed,...sources.filter(s=>s.status!=='error')].map(s=>`<div class="monitor-source"><strong>${safe(s.company)}</strong> — ${safe(s.status.replace('_',' '))}${s.count!==undefined&&s.status!=='page_watch'?' · '+s.count+' roles':''}<small>${safe(s.error||s.method||'')} · Last success: ${safe(date(s.last_success))}</small><a href="${safe(webURL(s.url))}" target="_blank" rel="noopener">Source page</a></div>`).join('')}${missing.map(c=>`<div class="monitor-source"><strong>${safe(c.name)}</strong> — careers URL needed</div>`).join('')}</div></details>`;
    document.getElementById('mf').value=filter;document.getElementById('ml').value=location;
    document.getElementById('mq').oninput=e=>{const cursor=e.target.selectionStart;query=e.target.value;limit=24;render();const box=document.getElementById('mq');box.focus();box.setSelectionRange(cursor,cursor);};
    document.getElementById('mf').onchange=e=>{filter=e.target.value;limit=24;render();};
    document.getElementById('ml').onchange=e=>{location=e.target.value;limit=24;render();};
    document.getElementById('mw').onchange=e=>{watchlist=e.target.checked;render();};
    document.getElementById('mc').onchange=e=>{hideCitizenOnly=e.target.checked;preferences.hideCitizenOnly=hideCitizenOnly;savePreferences();syncFeed();render();};
    document.getElementById('markRead').onclick=()=>{preferences.readThrough=model.generated_at||new Date().toISOString();savePreferences();render();};
    document.getElementById('reloadMonitor').onclick=async()=>{try{await window.refreshMonitor();}catch{window.alert('Could not reload results. Keep the data folder beside this file, or open the hosted board.');}};
    document.getElementById('moreMonitor')?.addEventListener('click',()=>{limit+=24;render();});
    document.querySelectorAll('[data-app]').forEach(b=>b.onchange=()=>{preferences.jobs=preferences.jobs||{};preferences.jobs[b.dataset.app]=b.value;savePreferences();});
    document.querySelectorAll('[data-ignore]').forEach(b=>b.onclick=()=>{preferences.ignored=preferences.ignored||{};preferences.ignored[b.dataset.ignore]=!preferences.ignored[b.dataset.ignore];savePreferences();render();});
    document.querySelectorAll('[data-track]').forEach(b=>b.onclick=()=>window.trackMonitorRole(toFeed(model.jobs[b.dataset.track])));
  }
  window.refreshMonitor=()=>new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src='data/monitor-data.js?t='+Date.now();
    script.onload=()=>{model=window.INTERN_MONITOR;syncFeed();render();script.remove();resolve();};
    script.onerror=()=>{script.remove();reject(new Error('Results unavailable'));};document.head.appendChild(script);
  });
  function download(name,data){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
  document.getElementById('backupBtn').onclick=async()=>{const board=await window.storage.get('internhunt.v1');download('intern-hunt-backup.json',{version:1,board:board?JSON.parse(board.value):null,monitor:preferences});};
  document.getElementById('restoreBtn').onclick=()=>document.getElementById('restoreFile').click();
  document.getElementById('restoreFile').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    try{
      const backup=JSON.parse(await file.text());
      if(backup.version!==1||!Array.isArray(backup.board?.companies)||!backup.monitor||typeof backup.monitor!=='object')throw new Error('Not an Intern Hunt backup');
      for(const c of backup.board.companies){if(typeof c.name!=='string'||typeof c.id!=='string'||!Array.isArray(c.links)||c.links.some(l=>webURL(l)==='#'))throw new Error('Invalid company or URL in backup');}
      if(!confirm('Replace this browser’s tracking with the selected backup?'))return;
      await window.storage.set('internhunt.v1',JSON.stringify(backup.board));localStorage.setItem(KEY,JSON.stringify(backup.monitor));window.location.reload();
    }catch(error){window.alert('Could not restore: '+error.message);}
  };
  syncFeed();render();
})();
