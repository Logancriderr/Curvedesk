'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=2)=>Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const usd=n=>(n<0?'−':'')+'$'+fmt(Math.abs(n));
const keys=['6M','2Y','5Y','10Y','20Y','30Y'];
let token='', snapshot=null, result=null, selected=0, requestId=0, timer=null, refreshing=false;
let positions=[
 {name:'Example 2031 note',maturity:'2031-01-15',coupon_pct:4,face:100000,frequency:2,convention:'treasury',mode:'spread',value:0},
 {name:'Example 2036 note',maturity:'2036-01-15',coupon_pct:4.25,face:75000,frequency:2,convention:'treasury',mode:'spread',value:0},
 {name:'Example 2046 bond',maturity:'2046-01-15',coupon_pct:4.5,face:50000,frequency:2,convention:'treasury',mode:'spread',value:0}
];
const portfolioCols=['name','maturity','coupon_pct','face','frequency','convention','mode','value','quote_asof'];
async function api(path,body){
 const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json','X-CurveDesk-Token':token},body:JSON.stringify(body)}:{});
 const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;
}
function showError(e){$('error').textContent=e.message||e;$('error').hidden=false;}
function clearError(){$('error').hidden=true;}
function metric(label,value,sub=''){return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${value}</div><div class="sub">${esc(sub)}</div></div>`;}
function table(headers,rows){return '<table><thead><tr>'+headers.map(h=>`<th>${esc(h)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>`<td>${esc(c)}</td>`).join('')+'</tr>').join('')+'</tbody></table>';}
function details(items){return '<div class="detail-grid">'+items.map(([k,v])=>`<div><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join('')+'</div>';}
function download(name,data,mime='text/plain'){const u=URL.createObjectURL(new Blob([data],{type:mime}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function csvCell(v){let s=String(v);if(typeof v==='string' && /^[=+@-]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
function toCSV(headers,rows){return [headers,...rows].map(r=>r.map(csvCell).join(',')).join('\r\n');}
function positionsCSV(){return toCSV(portfolioCols,positions.map(p=>portfolioCols.map(k=>p[k]??'')));}
function parseCSV(text){
 let rows=[],row=[],field='',quoted=false;
 text=text.replace(/^\uFEFF/,'');
 for(let i=0;i<text.length;i++){let c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(field);field='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(s=>s.trim()))rows.push(row);row=[];field='';}else field+=c;}
 if(quoted)throw Error('CSV has an unclosed quote');if(field||row.length){row.push(field);rows.push(row);}return rows;
}
function applyPortfolio(text){
 const rows=parseCSV(text),headers=rows.shift();
 if(!headers||new Set(headers).size!==headers.length||headers.some(x=>!portfolioCols.includes(x))||portfolioCols.filter(x=>x!=='quote_asof').some(x=>!headers.includes(x)))throw Error('Use the exported portfolio CSV headers without adding or removing columns.');
 if(rows.length<1||rows.length>100)throw Error('Import 1 to 100 positions.');
 const imported=rows.map((r,i)=>{if(r.length!==headers.length)throw Error(`CSV row ${i+2} has the wrong number of columns`);let o={};headers.forEach((h,j)=>o[h]=r[j]);for(const k of ['coupon_pct','face','frequency','value']){if(o[k].trim()===''||!Number.isFinite(Number(o[k])))throw Error(`CSV row ${i+2}: ${k} must be numeric`);o[k]=Number(o[k]);}return o;});
 positions=imported;selected=0;populatePositions();queueCalculate(0);
}
function lineChart(id,series,{xLabel='Years to maturity',yLabel='Annual rate %',xTicks=null}={}){
 const all=series.flatMap(s=>s.points).filter(p=>p[1]!=null&&Number.isFinite(p[1]));if(!all.length){$(id).innerHTML='No observations';return;}
 const W=800,H=290,L=57,R=22,T=27,B=42;let xmin=Math.min(...all.map(p=>p[0])),xmax=Math.max(...all.map(p=>p[0]));let ymin=Math.min(...all.map(p=>p[1])),ymax=Math.max(...all.map(p=>p[1]));let pad=Math.max((ymax-ymin)*.18,.08);ymin-=pad;ymax+=pad;
 const X=x=>L+(x-xmin)/(xmax-xmin||1)*(W-L-R),Y=y=>T+(ymax-y)/(ymax-ymin)*(H-T-B);
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)} by ${esc(xLabel)}">`;
 for(let i=0;i<5;i++){let y=ymin+(ymax-ymin)*i/4;s+=`<line x1="${L}" x2="${W-R}" y1="${Y(y)}" y2="${Y(y)}" stroke="#28374a"/><text x="${L-9}" y="${Y(y)+4}" text-anchor="end">${fmt(y,2)}</text>`;}
 const xt=xTicks||[.5,2,5,10,20,30].filter(x=>x>=xmin&&x<=xmax);for(const x of xt)s+=`<text x="${X(x)}" y="${H-23}" text-anchor="middle">${x}</text>`;
 s+=`<text x="${L}" y="13">${esc(yLabel)}</text><text x="${W-R}" y="${H-3}" text-anchor="end">${esc(xLabel)}</text>`;
 for(const a of series){const p=a.points.filter(p=>p[1]!=null&&Number.isFinite(p[1]));s+=`<polyline points="${p.map(p=>`${X(p[0])},${Y(p[1])}`).join(' ')}" fill="none" stroke="${a.color}" stroke-width="2.7"/>`;for(const v of p)s+=`<circle cx="${X(v[0])}" cy="${Y(v[1])}" r="3" fill="${a.color}"><title>${esc(a.name)} · ${v[0]}Y · ${fmt(v[1],4)}%</title></circle>`;}
 s+='</svg><div class="legend">'+series.map(a=>`<span><svg width="16" height="8" aria-hidden="true"><line x1="0" x2="16" y1="4" y2="4" stroke="${a.color}" stroke-width="3"/></svg>${esc(a.name)}</span>`).join('')+'</div>';$(id).innerHTML=s;
}
function bars(id,labels,values,other=null){
 const W=700,H=275,L=65,R=18,T=20,B=58,max=Math.max(...values.map(Math.abs),...(other||[]).map(Math.abs),.001),hasNeg=values.some(x=>x<0)||(other||[]).some(x=>x<0),min=hasNeg?-max:0;
 const Y=v=>T+(max-v)/(max-min)*(H-T-B),group=(W-L-R)/labels.length,bw=group*(other?.25:.52);
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Signed dollar risk chart">`;
 for(let i=0;i<5;i++){const n=min+(max-min)*i/4;s+=`<line x1="${L}" x2="${W-R}" y1="${Y(n)}" y2="${Y(n)}" stroke="#28374a"/><text x="${L-8}" y="${Y(n)+4}" text-anchor="end">${Math.abs(n)>=1000?fmt(n/1000,1)+'k':fmt(n,1)}</text>`;}
 values.forEach((v,i)=>{const center=L+group*(i+.5);const datasets=other?[v,other[i]]:[v];datasets.forEach((n,j)=>{let x=center-bw*(other?1:.5)+j*bw;let y=Math.min(Y(n),Y(0)),h=Math.max(Math.abs(Y(n)-Y(0)),.5);s+=`<rect x="${x}" y="${y}" width="${bw-3}" height="${h}" rx="2" fill="${j?'#87b7ff':n<0?'#ff9a9a':'#68ddc0'}"><title>${esc(labels[i])} ${j?'after':'before'}: ${usd(n)}</title></rect>`;});s+=`<text x="${center}" y="${H-32}" text-anchor="middle">${esc(labels[i])}</text>`;});
 s+='</svg>';if(other)s+='<div class="legend"><span>Before hedge</span><span>Blue · after hedge</span></div>';$(id).innerHTML=s;
}
function populatePositions(){
 $('positionSelect').innerHTML=positions.map((p,i)=>`<option value="${i}">${esc(p.name)}</option>`).join('');$('positionSelect').value=selected;
 const p=positions[selected];for(const [id,key] of Object.entries({bondName:'name',maturity:'maturity',coupon:'coupon_pct',face:'face',frequency:'frequency',convention:'convention',mode:'mode',value:'value',quoteAsOf:'quote_asof'}))$(id).value=p[key]??'';
 $('portfolioText').value=positionsCSV();updateValueLabel();
}
function updateValueLabel(){const m=$('mode').value;const l=$('valueLabel');l.firstChild.textContent=m==='clean'?'Clean price per $100':m==='yield'?'Annual yield percent':'Spread in basis points';}
function readEditor(){const p=positions[selected];p.name=$('bondName').value;p.maturity=$('maturity').value;p.coupon_pct=number('coupon');p.face=number('face');p.frequency=number('frequency');p.convention=$('convention').value;p.mode=$('mode').value;p.value=number('value');p.quote_asof=$('quoteAsOf').value.trim();$('portfolioText').value=positionsCSV();}
function number(id){const s=$(id).value;if(s===''||!Number.isFinite(Number(s)))throw Error(`Enter a valid value for ${id}`);return Number(s);}
function payload(){return {source:$('source').value,curve_date:$('curveDate').value,settlement:$('settlement').value,positions,shocks:keys.map((_,i)=>number('shock'+i)),spread_shock:number('spreadShock'),hedge:{name:'Cash bond hedge',maturity:$('hedgeMaturity').value,coupon_pct:number('hedgeCoupon'),frequency:2,convention:'treasury',mode:'spread',value:number('hedgeSpread')}};}
function invalidate(){requestId++;result=null;$('export').disabled=true;$('cashflowExport').disabled=true;document.body.classList.add('pending');}
function queueCalculate(delay=220){invalidate();clearTimeout(timer);timer=setTimeout(calculate,delay);}
async function calculate(){const id=++requestId;clearError();try{if(!snapshot)throw Error('Load a curve before calculating');const out=await api('/api/calculate',payload());if(id!==requestId)return;result=out;document.body.classList.remove('pending');$('export').disabled=false;$('cashflowExport').disabled=false;render();}catch(e){if(id!==requestId)return;result=null;showError(e);$('status').textContent='Calculation unavailable — correct the inputs. Any dimmed results below are from an earlier calculation.';}}
function render(){
 const r=result,b=r.portfolio,p=b.positions[selected];const byTenor={};Object.entries(r.rates).forEach(([k,v])=>byTenor[Number(k)]=v);
 $('status').innerHTML=`<strong>${esc(r.source==='demo'?'SYNTHETIC DEMO':r.source==='treasury'?'TREASURY DAILY':'IMPORTED CURVE')}</strong>Observation ${esc(r.curve_date)} · Settlement ${esc(r.settlement)} · ${r.retrieved_at?'Retrieved '+esc(r.retrieved_at.slice(0,19).replace('T',' '))+' UTC':'Invented data for exploration'}`;
 $('warnings').innerHTML=r.warnings.map(w=>`<div class="notice">${esc(w)}</div>`).join('');
 $('curveMetrics').innerHTML=metric('2-year par yield',fmt(byTenor[2])+'%','Published tenor')+metric('10-year par yield',fmt(byTenor[10])+'%','Published tenor')+metric('2s10s slope',fmt((byTenor[10]-byTenor[2])*100,1)+' bp','10-year minus 2-year')+metric('5s30s slope',fmt((byTenor[30]-byTenor[5])*100,1)+' bp','30-year minus 5-year');
 renderPar();lineChart('zeroChart',[{name:'Zero',color:'#68ddc0',points:r.curve.map(x=>[x.tenor_years,x.zero_cc_pct])},{name:'Forward',color:'#87b7ff',points:r.curve.map(x=>[x.tenor_years,x.forward_cc_pct])}]);
 $('bookOverview').innerHTML=details([['Net dirty market value',usd(b.net_market_value)],['Curve DV01',usd(b.dv01)+' / bp']]);bars('overviewRisk',keys,b.key_dv01);
 $('bondMetrics').innerHTML=metric('Clean price / 100',fmt(p.clean,4),'Excludes accrued interest')+metric('Yield to maturity',fmt(p.ytm_pct,4)+'%',p.mode==='yield'?'Entered quote':'Solved from valued price')+metric('Yield modified duration',fmt(p.modified_duration,3)+' yr','Single-yield sensitivity')+metric('Position curve DV01',usd(p.curve_dv01),'Signed dollars per basis point');
 $('bondDetails').innerHTML=details([['Dirty price / 100',fmt(p.dirty,5)],['Accrued / 100',fmt(p.accrued,5)],['Curve-only clean price',fmt(p.curve_clean,5)],['Fitted / entered z-spread',fmt(p.z_spread_bps,2)+' bp'],['Curve effective duration',fmt(p.curve_duration,4)+' yr'],['Yield Macaulay duration',fmt(p.macaulay_duration,4)+' yr'],['Yield convexity',fmt(p.yield_convexity,3)+' yr²'],['Curve convexity',fmt(p.curve_convexity,3)+' yr²'],['Quote timestamp',p.quote_asof||'Not supplied'],['Position dirty value',usd(p.market_value)],['Accrued dollars',usd(p.accrued_dollars)]]);
 bars('bondRisk',keys,p.key_dv01);$('cashflows').innerHTML=table(['Payment date','Coupon / 100','Principal / 100','PV / 100','Position payment $'],p.cashflows.map(c=>[c.date,fmt(c.coupon,4),fmt(c.principal),fmt(c.pv_per100,5),fmt(c.position_cashflow)]));
 $('portfolioMetrics').innerHTML=metric('Net dirty market value',usd(b.net_market_value),'Signed positions')+metric('Gross market value',usd(b.gross_market_value),'Sum of absolute position values')+metric('Net curve DV01',usd(b.dv01),'One basis point, central difference')+metric('Rates +100 bp P&L',usd(b.scenarios[0].pnl),'Full cash-flow revaluation');
 $('holdings').innerHTML=table(['Position','Maturity','Face $','Clean / 100','YTM %','Z-spread bp','Market value $','DV01 $/bp'],b.positions.map(x=>[x.name,x.maturity,fmt(x.face,0),fmt(x.clean,4),fmt(x.ytm_pct,3),fmt(x.z_spread_bps,2),fmt(x.market_value),fmt(x.curve_dv01)]));
 if(r.hedge){const h=r.hedge;$('hedgeResult').innerHTML=`<p class="muted">Theoretical ${h.signed_face<0?'short':'long'} face value</p><div class="big-number">${usd(Math.abs(h.signed_face))}</div><p>Residual parallel DV01: ${usd(h.residual_dv01)} / bp</p>`;bars('hedgeChart',keys,b.key_dv01,h.residual_key_dv01);$('hedgeScenarios').innerHTML=table(['Scenario','Before $','After $'],h.scenarios.map(s=>[s.name,fmt(s.before),fmt(s.after)]));}
 $('customPnl').innerHTML=`<span class="muted tiny">CUSTOM SCENARIO P&L</span><div class="big-number ${r.custom_scenario.pnl<0?'negative':'positive'}">${usd(r.custom_scenario.pnl)}</div>`;
 bars('scenarioChart',['+100','−100','Steepen','Flatten','Belly','Spread'],b.scenarios.map(s=>s.pnl));$('scenarioTable').innerHTML=table(['Scenario','Portfolio P&L $'],b.scenarios.map(s=>[s.name,fmt(s.pnl)]));
 const approx=b.positions.reduce((a,x)=>a-x.curve_duration*x.market_value*.01+.5*x.curve_convexity*x.market_value*.01**2,0);$('approximation').innerHTML=`<h2>Duration plus convexity check</h2><p>For a parallel +100 bp move, the second-order estimate is <strong>${usd(approx)}</strong>. Exact model revaluation is <strong>${usd(b.scenarios[0].pnl)}</strong>. Larger moves can widen the approximation error.</p>`;
 $('dataDetails').innerHTML=details([['Source',r.source_label],['Observation date',r.curve_date],['Retrieved UTC',r.retrieved_at||'Not applicable'],['Observations loaded',snapshot.records.length],['Usable complete curves',snapshot.records.filter(x=>x.usable).length],['Rate input units','Annual percent']]);
 $('curveTable').innerHTML=table(['Tenor years','Discount factor','Zero CC %','6M forward CC %'],r.curve.map(x=>[fmt(x.tenor_years,1),fmt(x.discount_factor,7),fmt(x.zero_cc_pct,4),fmt(x.forward_cc_pct,4)]));
}
function renderPar(){if(!result)return;const current=snapshot.records.find(r=>r.date===result.curve_date),compare=snapshot.records.find(r=>r.date===$('compareDate').value);const points=r=>Object.entries(r.rates).filter(([,v])=>v!==null).map(([k,v])=>[+k,v]).sort((a,b)=>a[0]-b[0]);lineChart('parChart',[{name:current.date,color:'#68ddc0',points:points(current)},...(compare?[{name:compare.date,color:'#87b7ff',points:points(compare)}]:[])]);}
function setSnapshot(snap,resetDate=true){snapshot=snap;const dates=snap.records.filter(r=>r.usable).map(r=>r.date).reverse();const prev=$('curveDate').value;$('curveDate').innerHTML=dates.map(d=>`<option>${d}</option>`).join('');if(!resetDate&&dates.includes(prev))$('curveDate').value=prev;$('compareDate').innerHTML='<option value="">None</option>'+dates.map(d=>`<option>${d}</option>`).join('');if(dates.length>1)$('compareDate').value=dates[Math.min(5,dates.length-1)];}
async function loadSource(){invalidate();clearError();snapshot=null;try{const snap=await api('/api/curves?source='+$('source').value);setSnapshot(snap);if($('source').value==='demo')$('settlement').value='2026-01-15';else $('settlement').value=(await api('/api/config')).today;queueCalculate(0);}catch(e){$('status').textContent='No curve loaded for the selected source. Fetch Treasury data or import a curve in Data & methods.';showError(e);}}
async function refresh(){if(refreshing)return;refreshing=true;$('refresh').disabled=true;$('refresh').textContent='Fetching published rates…';clearError();try{const snap=await api('/api/refresh',{});$('source').value='treasury';setSnapshot(snap);$('settlement').value=(await api('/api/config')).today;queueCalculate(0);}catch(e){showError(e);}finally{refreshing=false;$('refresh').disabled=false;$('refresh').textContent='Fetch latest Treasury data';}}
function tab(name){document.querySelectorAll('.tab').forEach(el=>el.classList.toggle('active',el.id===name));document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.tab===name));const titles={overview:['Read the curve. Measure the risk.','From published rates to cash flows and portfolio exposure.'],bond:['Every cash flow. Every basis point.','Reconcile a quote, inspect the schedule, and measure sensitivity.'],portfolio:['Know what your book is exposed to.','Aggregate signed positions and examine a cash-bond hedge.'],scenarios:['Test the shape of the next move.','Reprice the portfolio under parallel, curve and spread shocks.'],methods:['Trace the numbers to their source.','Observation dates, model assumptions and curve diagnostics.']};$('title').textContent=titles[name][0];$('subtitle').textContent=titles[name][1];}
async function init(){
 const config=await api('/api/config');token=config.token;$('settlement').value='2026-01-15';$('hedgeMaturity').value='2036-01-15';
 $('shockInputs').innerHTML=keys.map((k,i)=>`<label>${k} shock bp<input id="shock${i}" type="number" min="-1000" max="1000" step="10" value="0"></label>`).join('');
 document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
 populatePositions();
 $('source').onchange=loadSource;$('refresh').onclick=refresh;$('curveDate').onchange=()=>queueCalculate(0);$('settlement').onchange=()=>queueCalculate(0);$('compareDate').onchange=renderPar;
 $('positionSelect').onchange=()=>{selected=Number($('positionSelect').value);populatePositions();if(result)render();};
 for(const id of ['bondName','maturity','coupon','face','frequency','convention','mode','value','quoteAsOf'])$(id).addEventListener('change',()=>{try{if(id==='mode'){$('value').value=$('mode').value==='clean'?100:$('mode').value==='yield'?4:0;updateValueLabel();}readEditor();queueCalculate();}catch(e){invalidate();showError(e);}});
 for(const id of ['hedgeMaturity','hedgeCoupon','hedgeSpread','spreadShock',...keys.map((_,i)=>'shock'+i)])$(id).addEventListener('change',()=>queueCalculate());
 const setShocks=a=>{a.forEach((v,i)=>$('shock'+i).value=v);queueCalculate(0);};$('plus100').onclick=()=>setShocks([100,100,100,100,100,100]);$('steepen').onclick=()=>setShocks([0,10,25,50,75,100]);$('resetShocks').onclick=()=>{$('spreadShock').value=0;setShocks([0,0,0,0,0,0]);};
 $('export').onclick=()=>{if(result)download('curvedesk-analysis-'+result.curve_date+'.json',JSON.stringify(result,null,2),'application/json');};
 $('cashflowExport').onclick=()=>{if(!result)return;const c=result.portfolio.positions[selected].cashflows;download('cashflows.csv',toCSV(['date','coupon_per100','principal_per100','pv_per100','signed_position_cashflow'],c.map(x=>[x.date,x.coupon,x.principal,x.pv_per100,x.position_cashflow])),'text/csv');};
 $('portfolioExport').onclick=()=>download('positions.csv',positionsCSV(),'text/csv');$('applyPortfolio').onclick=()=>{try{applyPortfolio($('portfolioText').value);}catch(e){showError(e);}};
 $('portfolioFile').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>1000000)throw Error('File exceeds 1 MB');applyPortfolio(await f.text());}catch(err){showError(err);}finally{e.target.value='';}};
 $('curveTemplate').onclick=()=>download('synthetic-curve-template.csv','date,6M,1Y,2Y,3Y,5Y,7Y,10Y,20Y,30Y\n2026-01-15,4.15,4.00,3.85,3.90,4.05,4.20,4.35,4.65,4.70\n','text/csv');
 $('curveFile').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>1000000)throw Error('File exceeds 1 MB');const snap=await api('/api/import-curve',{csv:await f.text()});$('source').value='custom';setSnapshot(snap);$('settlement').value=config.today;queueCalculate(0);}catch(err){showError(err);}finally{e.target.value='';}};
 setInterval(()=>{if($('auto').checked&&$('source').value==='treasury'&&!document.hidden)refresh();},15*60*1000);
 await loadSource();
}
init().catch(showError);
