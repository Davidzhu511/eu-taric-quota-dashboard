(() => {
  const en = document.documentElement.lang === 'en';
  const uk = /^uk(?:-en)?\.html$/.test(location.pathname.split('/').pop());
  const t = (zh, english) => en ? english : zh;
  const section = document.querySelector('#quarterly-summary');
  if (!section) return;
  const esc = x => String(x ?? '—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const pct = x => x == null ? '—' : Number(x).toFixed(4).replace(/0+$/,'').replace(/\.$/,'')+'%';
  fetch('./data/quarterly-summary.json?v='+Date.now(), {cache:'no-store'}).then(r => {
    if (!r.ok) throw Error('HTTP '+r.status); return r.json();
  }).then(data => {
    const rows = data[uk ? 'uk' : 'eu'] || [];
    section.innerHTML = `<h2>${t('本季度中国适用配额 · 开季申报加权关税','Current-quarter quotas applicable to China · Opening-day weighted quota duty')}</h2>
      <p>${t('按表中申报接受日期的历史获配比例计算：(100% − 获配比例) × 50%。适用于参与对应分配批次、单位完税价格相同的货物；并非整个季度统一税率，不含其他税费。最终以该票海关实际分配及税款通知为准。','Calculated from historical allocation for the declaration acceptance date shown: (100% − allocation ratio) × 50%. Applies to eligible requests in that allocation batch with equal customs value per unit. This is not a uniform rate for the whole quarter and excludes other duties and taxes. Confirm each consignment against its customs allocation and assessment.')}</p>
      <div class="quota-table-scroll"><table><thead><tr>${[t('类别','Category'),t('配额号','Order number'),t('原产地 / 共用池','Origin / pool'),t('季度','Quarter'),t('申报接受日期','Declaration accepted'),t('获配比例','Allocated'),t('加权配额关税','Weighted quota duty'),t('证据 / 状态','Evidence / status')].map(x=>`<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.category)}</td><td>${esc(x.code)}</td><td>${esc(x.origin)}</td><td>${esc(x.validity_period)}</td><td>${esc(x.declaration_date)}</td><td>${pct(x.allocation_pct)}</td><td><strong>${pct(x.weighted_duty_pct)}</strong></td><td>${x.status==='historical_allocation' ? `${t('历史分配','Historical allocation')} ${esc(x.allocation_date)}<br><a href="./data/history/${encodeURIComponent(x.evidence[0].file)}" target="_blank" rel="noopener">${t('官方日期','Official data date')} ${esc(x.official_update_date)} ↗</a>` : x.status==='allocation_not_published' ? t('UK公开CSV未提供同日获配比例；不能用Fill rate或余额推算。','The public UK CSV does not provide a same-day allocation ratio. It cannot be inferred from fill rate or balance.') : x.status==='conflicting_evidence' ? t('历史证据冲突，待核验','Conflicting historical evidence; review required') : t('尚无可核验的开季分配结果','No verified opening-day allocation result yet')}</td></tr>`).join('')}</tbody></table></div>`;
  }).catch(e => { section.textContent=t('季度加权关税表加载失败：','Quarterly weighted duty table could not be loaded: ')+e.message; });
})();
