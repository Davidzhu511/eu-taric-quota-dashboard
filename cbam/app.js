const $ = (id) => document.getElementById(id);
const euro = (v) => v == null ? '—' : `€${Number(v).toFixed(2)}`;
const pct = (v, digits=0) => v == null ? '—' : `${(Number(v)*100).toFixed(digits)}%`;
const num = (v) => v == null ? '—' : Number(v).toLocaleString('zh-CN');

async function getJSON(url){
  const r = await fetch(`${url}?t=${Date.now()}`, {cache:'no-store'});
  if(!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
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

function renderOfficial(rows){
  const tbody=$('officialPrices'); tbody.innerHTML='';
  // Import-year pricing is independent of the calendar year in which certificates are purchased.
  const byQ=new Map((rows||[]).filter(x=>x.year===2026).map(x=>[x.quarter,x]));
  for(let q=1;q<=4;q++){
    const x=byQ.get(q)||{};
    const price=(typeof x.price==='number' && Number.isFinite(x.price) && x.price>0)?x.price:null;
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>2026年第${q}季度</td><td>${price==null?'待公布':euro(price)}</td><td>${price==null?'等待官方公布':'官方已公布 · 固定价'}</td>`;
    tbody.appendChild(tr);
  }
  const q1=byQ.get(1);
  const price=(typeof q1?.price==='number' && Number.isFinite(q1.price) && q1.price>0)?q1.price:null;
  $('example2026Price').textContent=price==null?'2026年第一季度价格尚未取得':`1,000张 × ${euro(price)} / 张`;
  $('example2026Cost').textContent=price==null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:2}).format(price*1000);
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

function renderResearch(r){
  $('researchStatus').textContent = r?.meta?.updated_at?.slice(0, 10) || '—';
  $('researchHeadline').textContent = r?.headline || '暂无研究更新';
  const body = $('researchBody');
  body.replaceChildren();
  for (const line of [r?.summary, ...(r?.bullets || [])].filter(Boolean)){
    const item = document.createElement('p');
    item.textContent = line;
    body.appendChild(item);
  }
}

const SOURCE_NAMES={
  eex_auction_report:'EEX EUA一级拍卖年度报告',
  eex_auction_page:'EEX EU ETS1拍卖信息',
  eex_cbam_reference:'EEX CBAM参考指数',
  ec_cbam_price:'欧盟委员会CBAM证书官方价格',
  price_regulation:'证书定价实施条例（EU）2025/2548'
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

const kinds = {
  official: '欧委会官方价', complete_estimate: '完整周拍卖估值',
  partial_estimate: '周内拍卖估值', no_auctions_estimate: '无计划拍卖 · 沿用前次拍卖周估值',
};

function describeQuote(row){
  if (!row) return '等待可核实的价格及适用期';
  const details = [kinds[row.kind], '形成周 ' + row.formation_week];
  if (row.published) details.push('公布 ' + row.published);
  if (row.valid_from) details.push(row.valid_from + ' 至 ' + row.valid_to);
  if (row.auctions) details.push(row.auctions + ' 场，成交 ' + num(row.volume) + ' / 计划 ' + num(row.planned_volume) + ' EUA');
  if (row.reference_week) details.push('参考周 ' + row.reference_week);
  return details.join(' · ');
}

function readQty(id){
  const el = $(id);
  return el.value !== '' && el.validity.valid && Number.isSafeInteger(el.valueAsNumber) ? el.valueAsNumber : null;
}

let displayedWindow = null;
function updateLedger(){
  const required = readQty('requiredQty'), held = readQty('heldQty'), flex = readQty('flexQty');
  $('shortfall').textContent = required === null || held === null ? '待核对' : num(Math.max(0, required-held)) + ' 张';
  const spread = displayedWindow?.spread;
  const amount = spread == null || flex == null ? null : spread * flex;
  $('flexImpact').textContent = amount == null ? '待核对' : euro(amount) + (displayedWindow.mode === 'simulation' ? '（模拟）' : '（按当前对比）');
}

function renderWindow(w, data){
  const today = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Europe/Brussels'}).format(new Date());
  const morning = w?.as_of !== today && data.morning_window?.as_of === today;
  if (morning) w = data.morning_window;
  const historical = w?.as_of !== today;
  const simulation = w?.mode === 'simulation';
  if (historical && !simulation && w) {
    const active = (data.official_weekly_prices || []).filter(row =>
      row.published <= today && row.valid_from <= today && today <= row.valid_to);
    const current = active.length === 1 ? active[0] : null;
    if (!current || w.current?.formation_week !== current.formation_week) {
      // A price published in the last snapshot may take effect before tonight's refresh.
      // Replace the old window as a unit so its spread and score cannot follow the new P.
      w = {as_of: w.as_of, mode: 'live', current, history_weeks: 0};
    }
  }
  const prefix = historical ? '历史快照' : simulation ? '开售前模拟' : '当期价格';
  displayedWindow = historical || morning ? null : w;
  $('currentLabel').textContent = simulation ? '模拟本期参考价' : '当前有效官方价';
  $('currentPrice').textContent = euro(w?.current?.price);
  $('currentPeriod').textContent = describeQuote(w?.current);
  $('nextPrice').textContent = euro(w?.next?.price);
  $('nextPeriod').textContent = describeQuote(w?.next);
  $('spread').textContent = euro(w?.spread);
  $('unitImpact').textContent = w?.impact_per_1000 == null ? '等待两个相邻窗口' : '每 1,000 张成本差 ' + euro(w.impact_per_1000);
  $('switchDate').textContent = w?.next_effective_from || '待确认';
  $('lastDay').textContent = w?.current?.valid_to ? '本期最后适用日 ' + w.current.valid_to : '开售及换价以官方适用期为准';
  renderGauge(w?.score, 100, '60/40 窗口评分 / 100');
  const badge = morning ? (simulation ? '晨间模拟' : '晨间参考 · 待当日核验') : prefix;
  $('stanceBadge').textContent = badge + (w?.as_of ? ' · ' + w.as_of : '');
  let headline = '等待相邻价格及拍卖证据';
  if (w?.spread != null){
    const signals = {current_cheaper:'本期参考价较低', next_cheaper:'下一期参考价较低', within_threshold:'相邻价差尚未达到提醒门槛'};
    headline = signals[w.direction];
  }
  $('analysisHeadline').textContent = w ? headline : '等待新版数据';
  const lines = [];
  if (morning) lines.push('采用 ' + w.evidence_as_of + ' 已取得的数据，按今天的价格有效期推算。办理前请核对欧委会当日信息。');
  if (historical) lines.push('数据来自前次快照，官方价按有效期展示。请复核来源和平台办理时间。');
  if (simulation) lines.push('2027年2月1日开始销售证书，此处仅用于演练当年进口义务的周度比较。');
  if (w && !simulation && !w.actionable) lines.push('尚缺可执行窗口的核验材料。');
  if (w){
    lines.push('换价分 ' + (w.spread_points ?? '—') + '/60，历史价位分 ' + (w.history_points ?? '—') + '/40。可核实历史 ' + w.history_weeks + '/26 周。');
    if (w.percentile != null) lines.push('本期价格的半年百分位 ' + pct(w.percentile, 1) + '，提醒价差 ' + euro(w.threshold) + '/张。');
  }
  const latest = data.auction_analytics?.latest;
  if (latest) lines.push('最近单场 EUA 拍卖 ' + euro(latest.price) + '（' + latest.date + '）。');
  $('analysisBullets').replaceChildren(...lines.map(line => {const li=document.createElement('li'); li.textContent=line; return li;}));
  updateLedger();
}

async function load(){
  $('refreshBtn').disabled = true;
  try{
    const data = await getJSON('data/current.json');
    const research = await getJSON('data/research.json').catch(() => null);
    $('dataDate').textContent = data.meta?.data_date || '—';
    $('checkedAt').textContent = (data.meta?.checked_at || '—').replace('T',' ').slice(0,19)+' UTC';
    $('dataStatus').textContent = data.meta?.status === 'ok' ? '正常' : '部分数据待核验';
    $('modelVersion').textContent = data.meta?.methodology_version || '—';
    renderWindow(data.procurement_window, data);
    renderChart(data.auction_analytics?.weekly);
    renderOfficial(data.official_cbam_prices);
    renderSupply(data.auction_supply);
    renderResearch(research);
    renderSources(data);
  }catch(error){
    renderWindow(null, {});
    $('dataStatus').textContent = '加载失败';
    $('analysisHeadline').textContent = error.message;
  }finally{
    $('refreshBtn').disabled = false;
  }
}
for (const id of ['requiredQty', 'heldQty', 'flexQty']) $(id).addEventListener('input', updateLedger);
$('refreshBtn').addEventListener('click',load);
load();
