const $ = (id) => document.getElementById(id);
const euro = (v) => v == null ? '—' : `€${Number(v).toFixed(2)}`;
const pct = (v, digits=0) => v == null ? '—' : `${(Number(v)*100).toFixed(digits)}%`;
const num = (v) => v == null ? '—' : Number(v).toLocaleString('zh-CN');

async function getJSON(url){
  const r = await fetch(`${url}?t=${Date.now()}`, {cache:'no-store'});
  if(!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

function coverageFromScore(score){
  if(score == null) return '待研究层确认';
  if(score < 35) return '50%（仅合规底仓）';
  if(score < 50) return '60%';
  if(score < 65) return '70%';
  if(score < 80) return '85%';
  return '接近100%（高置信度义务）';
}

function fullStance(score){
  if(score == null) return ['公共层观察','neutral'];
  if(score >= 80) return ['强采购窗口','buy'];
  if(score >= 65) return ['加速采购窗口','buy'];
  if(score >= 50) return ['分批提高覆盖','neutral'];
  if(score >= 35) return ['中性 / 等待更好价格','neutral'];
  return ['仅维持合规底仓','wait'];
}

function publicOnlyStance(score){
  if(score == null) return ['监控','neutral'];
  if(score >= 52) return ['公共层偏积极 · 待研究确认','neutral'];
  if(score >= 38) return ['公共层中性','neutral'];
  return ['公共层偏弱','wait'];
}

function renderGauge(score, maxScore, label){
  $('totalScore').textContent = score == null ? '—' : Number(score).toFixed(1);
  $('scoreScale').textContent = label || `评分 / ${maxScore}`;
  const deg = score == null ? 0 : Math.max(0, Math.min(360, score / maxScore * 360));
  $('scoreGauge').style.background = `conic-gradient(var(--accent) ${deg}deg,var(--track) ${deg}deg)`;
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
    row.innerHTML=`<div class="score-label"><span>${c.name}</span><strong>${Number(c.score).toFixed(1)} / ${c.max}</strong></div><div class="bar"><span style="width:${width}%"></span></div>${c.note?`<div class="score-note">${c.note}</div>`:''}`;
    wrap.appendChild(row);
  });
}

function renderOfficial(rows){
  const tbody=$('officialPrices'); tbody.innerHTML='';
  const byQ=new Map((rows||[]).map(x=>[x.quarter,x]));
  for(let q=1;q<=4;q++){
    const x=byQ.get(q)||{};
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>2026年第${q}季度</td><td>${x.price==null?'待公布':euro(x.price)}</td><td>${x.price==null?'等待官方发布':'已锁定'}</td>`;
    tbody.appendChild(tr);
  }
}

function renderSupply(supply){
  const wrap=$('supplyCards'); wrap.innerHTML='';
  Object.entries(supply||{}).sort().forEach(([year,x])=>{
    const d=document.createElement('div');d.className='mini';
    d.innerHTML=`<span>${year}年 EEX EU ETS1 拍卖计划总量</span><strong>${num(x.total)}</strong><div class="sub">共同平台 ${num(x.cap_common)} · 德国 ${num(x.germany)} · 波兰 ${num(x.poland)}</div>`;
    wrap.appendChild(d);
  });
  if(!wrap.children.length) wrap.innerHTML='<div class="muted">拍卖供给摘要暂不可用</div>';
}

function validOverlay(r){
  return r && typeof r.overlay_score === 'number' && Number.isFinite(Number(r.overlay_score));
}

function renderResearch(r){
  if(!r){ $('researchStatus').textContent='暂未接入'; return; }
  $('researchStatus').textContent=r.meta?.updated_at ? `更新于 ${r.meta.updated_at.slice(0,16).replace('T',' ')}` : (r.meta?.status||'—');
  $('researchHeadline').textContent=r.headline||'研究层暂无结论';
  const body=$('researchBody');
  const items=(r.bullets||[]).map(x=>`<li>${x}</li>`).join('');
  const scoreText=validOverlay(r)?`<p class="research-score"><strong>研究层评分：${Number(r.overlay_score).toFixed(1)} / 30</strong></p>`:'<p class="muted">研究层尚未形成有效量化分，本次不输出完整100分采购建议。</p>';
  body.innerHTML=`${r.summary?`<p>${r.summary}</p>`:''}${items?`<ul>${items}</ul>`:''}${scoreText}`;
}

const SOURCE_NAMES={
  eex_auction_report:'EEX EUA一级拍卖年度报告',
  eex_auction_page:'EEX EU ETS1拍卖信息',
  eex_cbam_reference:'EEX CBAM参考指数',
  ec_cbam_price:'欧盟委员会CBAM证书官方价格'
};
function renderSources(data){
  const wrap=$('sources'); wrap.innerHTML='';
  Object.entries(data.sources||{}).forEach(([k,url])=>{
    const d=document.createElement('div'); d.className='source';
    d.innerHTML=`<strong>${SOURCE_NAMES[k]||k.replaceAll('_',' ')}</strong><br><a href="${url}" target="_blank" rel="noopener">打开来源 ↗</a>`;
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
    $('checkedAt').textContent=(data.meta?.checked_at||'—').replace('T',' ').slice(0,19)+' UTC';
    $('dataStatus').textContent=data.meta?.status==='ok'?'正常':(data.meta?.status||'—');
    $('modelVersion').textContent=data.meta?.methodology_version||'—';
    $('latestAuction').textContent=euro(s.latest_price); $('latestAuctionDate').textContent=s.latest_date?`${s.latest_date} · EEX一级拍卖`:'EEX一级拍卖';
    $('weeklyVwap').textContent=euro(w?.price); $('weeklyAuctions').textContent=w?`${w.auctions}场 · ${num(w.volume)} EUA`:'—';
    $('quarterVwap').textContent=euro(q?.price);
    $('rangePosition').textContent=pct(s.position_52w); $('rangeText').textContent=(s.low_52w!=null)?`${euro(s.low_52w)} – ${euro(s.high_52w)}`:'—';

    const model=data.public_score||{};
    const publicScore=typeof model.score==='number'?Number(model.score):null;
    const overlayOK=validOverlay(research);
    const overlay=overlayOK?Number(research.overlay_score):null;
    const combined=(publicScore!=null && overlayOK)?Math.max(0,Math.min(100,publicScore+overlay)):null;

    if(combined!=null){
      renderGauge(combined,100,`完整模型 / 100 · 公共${publicScore.toFixed(1)} + 研究${overlay.toFixed(1)}`);
      const [st,cls]=fullStance(combined); $('stanceBadge').textContent=st; $('stanceBadge').className=`badge ${cls}`;
      $('coverageTarget').textContent=coverageFromScore(combined);
    }else{
      renderGauge(publicScore,model.max_score||70,'公共自动层 / 70 · 等待研究层');
      const [st,cls]=publicOnlyStance(publicScore); $('stanceBadge').textContent=st; $('stanceBadge').className=`badge ${cls}`;
      $('coverageTarget').textContent='待研究层确认';
    }

    renderScores(model);
    $('analysisHeadline').textContent=data.analysis?.headline||'—';
    $('analysisBullets').innerHTML=(data.analysis?.bullets||[]).map(x=>`<li>${x}</li>`).join('');
    renderChart(a.weekly||[]); renderOfficial(data.official_cbam_prices||[]); renderSupply(data.auction_supply||{}); renderResearch(research); renderSources(data);
  }catch(e){
    $('dataStatus').textContent='加载失败'; $('analysisHeadline').textContent='无法读取Dashboard数据';
    $('analysisBullets').innerHTML=`<li>${e.message}</li>`;
  }finally{$('refreshBtn').disabled=false}
}
$('refreshBtn').addEventListener('click',load); load();
