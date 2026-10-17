const $ = (id) => document.getElementById(id);
const euro = (v) => v == null ? '—' : `€${Number(v).toFixed(2)}`;
const pct = (v, digits=0) => v == null ? '—' : `${(Number(v)*100).toFixed(digits)}%`;
const num = (v) => v == null ? '—' : Number(v).toLocaleString('en-US');

async function getJSON(url){
  const r = await fetch(`${url}?t=${Date.now()}`, {cache:'no-store'});
  if(!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

function coverageFromScore(score){
  if(score == null) return '—';
  if(score < 35) return '50%（仅合规底仓）';
  if(score < 50) return '60%';
  if(score < 65) return '70%';
  if(score < 80) return '85%';
  return '100%（高置信度义务）';
}

function stance(score, maxScore){
  if(score == null) return ['监控','neutral'];
  const normalized = score / maxScore * 100;
  if(normalized >= 72) return ['加速采购窗口','buy'];
  if(normalized >= 50) return ['分批采购 / 中性','neutral'];
  return ['仅维持底仓','wait'];
}

function renderGauge(score, maxScore){
  $('totalScore').textContent = score == null ? '—' : Number(score).toFixed(1);
  $('scoreScale').textContent = score == null ? '公共数据分 / 70' : `公共数据分 / ${maxScore}`;
  const deg = score == null ? 0 : Math.max(0, Math.min(360, score / maxScore * 360));
  $('scoreGauge').style.background = `conic-gradient(var(--accent) ${deg}deg,#203653 ${deg}deg)`;
}

function renderChart(points){
  const el = $('weeklyChart');
  if(!points || points.length < 2){ el.innerHTML = '<div class="muted">暂无足够历史数据</div>'; return; }
  points = points.slice(-52);
  const w=1000,h=280,p={l:55,r:18,t:15,b:35};
  const prices=points.map(x=>Number(x.price));
  let ymin=Math.min(...prices), ymax=Math.max(...prices);
  const pad=Math.max(1,(ymax-ymin)*0.12); ymin-=pad; ymax+=pad;
  const x=i=>p.l+(w-p.l-p.r)*(i/(points.length-1));
  const y=v=>p.t+(h-p.t-p.b)*(1-(v-ymin)/(ymax-ymin));
  const path=points.map((d,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(d.price).toFixed(1)}`).join(' ');
  const area=`${path} L${x(points.length-1)},${h-p.b} L${x(0)},${h-p.b} Z`;
  let grid='';
  for(let i=0;i<5;i++){
    const v=ymin+(ymax-ymin)*i/4, yy=y(v);
    grid += `<line class="grid-line" x1="${p.l}" x2="${w-p.r}" y1="${yy}" y2="${yy}"/><text class="axis-label" x="4" y="${yy+4}">€${v.toFixed(0)}</text>`;
  }
  const labelIdx=[0,Math.floor((points.length-1)/2),points.length-1];
  const labels=labelIdx.map(i=>`<text class="axis-label" text-anchor="${i===0?'start':i===points.length-1?'end':'middle'}" x="${x(i)}" y="${h-8}">${points[i].week_start.slice(5)}</text>`).join('');
  el.innerHTML=`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${grid}<path class="chart-area" d="${area}"/><path class="chart-line" d="${path}"/>${labels}</svg>`;
}

function renderScores(model){
  const wrap=$('scoreComponents'); wrap.innerHTML='';
  (model.components||[]).forEach(c=>{
    const row=document.createElement('div'); row.className='score-row';
    const width=Math.max(0,Math.min(100,Number(c.score)/Number(c.max)*100));
    row.innerHTML=`<div class="score-label"><span>${c.name}</span><strong>${Number(c.score).toFixed(1)} / ${c.max}</strong></div><div class="bar"><span style="width:${width}%"></span></div>`;
    wrap.appendChild(row);
  });
}

function renderOfficial(rows){
  const tbody=$('officialPrices'); tbody.innerHTML='';
  const byQ=new Map((rows||[]).map(x=>[x.quarter,x]));
  for(let q=1;q<=4;q++){
    const x=byQ.get(q)||{};
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>Q${q} 2026</td><td>${x.price==null?'待公布':euro(x.price)}</td><td>${x.price==null?'待官方发布':'已锁定'}</td>`;
    tbody.appendChild(tr);
  }
}

function renderSupply(supply){
  const wrap=$('supplyCards'); wrap.innerHTML='';
  Object.entries(supply||{}).sort().forEach(([year,x])=>{
    const d=document.createElement('div');d.className='mini';
    d.innerHTML=`<span>${year} EEX ETS1 headline auction volume</span><strong>${num(x.total)}</strong><div class="sub">Common ${num(x.cap_common)} · DE ${num(x.germany)} · PL ${num(x.poland)}</div>`;
    wrap.appendChild(d);
  });
  if(!wrap.children.length) wrap.innerHTML='<div class="muted">供给摘要暂不可用</div>';
}

function renderResearch(r){
  if(!r){ $('researchStatus').textContent='未接入'; return; }
  $('researchStatus').textContent=r.meta?.updated_at ? `更新 ${r.meta.updated_at.slice(0,16).replace('T',' ')}` : (r.meta?.status||'—');
  $('researchHeadline').textContent=r.headline||'研究层暂无结论';
  const body=$('researchBody');
  const items=(r.bullets||[]).map(x=>`<li>${x}</li>`).join('');
  body.innerHTML=`${r.summary?`<p>${r.summary}</p>`:''}${items?`<ul>${items}</ul>`:''}${r.overlay_score!=null?`<p><strong>研究层：${r.overlay_score}/30</strong></p>`:''}`;
}

function renderSources(data){
  const wrap=$('sources'); wrap.innerHTML='';
  Object.entries(data.sources||{}).forEach(([k,url])=>{
    const d=document.createElement('div'); d.className='source';
    d.innerHTML=`<strong>${k.replaceAll('_',' ')}</strong><br><a href="${url}" target="_blank" rel="noopener">打开官方来源 ↗</a>`;
    wrap.appendChild(d);
  });
  const ew=$('errors'); ew.innerHTML='';
  (data.meta?.errors||[]).forEach(e=>{const d=document.createElement('div');d.className='warning';d.textContent=e;ew.appendChild(d)});
}

async function load(){
  $('refreshBtn').disabled=true;
  try{
    const data=await getJSON('data/current.json');
    let research=null; try{research=await getJSON('data/research.json')}catch(_e){}
    const a=data.auction_analytics||{}, s=a.stats||{}, w=(a.weekly||[]).at(-1), q=(a.quarterly||[]).at(-1);
    $('dataDate').textContent=data.meta?.data_date||'—';
    $('checkedAt').textContent=(data.meta?.checked_at||'—').replace('T',' ').slice(0,19)+'Z';
    $('dataStatus').textContent=data.meta?.status||'—';
    $('modelVersion').textContent=data.meta?.methodology_version||'—';
    $('latestAuction').textContent=euro(s.latest_price); $('latestAuctionDate').textContent=s.latest_date||'EEX Primary Auction';
    $('weeklyVwap').textContent=euro(w?.price); $('weeklyAuctions').textContent=w?`${w.auctions}场 · ${num(w.volume)} EUA`:'—';
    $('quarterVwap').textContent=euro(q?.price);
    $('rangePosition').textContent=pct(s.position_52w); $('rangeText').textContent=(s.low_52w!=null)?`${euro(s.low_52w)} – ${euro(s.high_52w)}`:'—';

    const model=data.public_score||{}; renderGauge(model.score,model.max_score||70); renderScores(model);
    const [st,cls]=stance(model.score,model.max_score||70); $('stanceBadge').textContent=st; $('stanceBadge').className=`badge ${cls}`;
    $('coverageTarget').textContent=model.score==null?'—':coverageFromScore(model.score/(model.max_score||70)*100);
    $('analysisHeadline').textContent=data.analysis?.headline||'—';
    $('analysisBullets').innerHTML=(data.analysis?.bullets||[]).map(x=>`<li>${x}</li>`).join('');
    renderChart(a.weekly||[]); renderOfficial(data.official_cbam_prices||[]); renderSupply(data.auction_supply||{}); renderResearch(research); renderSources(data);
  }catch(e){
    $('dataStatus').textContent='加载失败'; $('analysisHeadline').textContent='无法读取Dashboard数据';
    $('analysisBullets').innerHTML=`<li>${e.message}</li>`;
  }finally{$('refreshBtn').disabled=false}
}
$('refreshBtn').addEventListener('click',load); load();
