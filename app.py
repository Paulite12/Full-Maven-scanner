"""Full Maven Scanner: read-only crypto market intelligence dashboard.

This is an experimental monitoring tool, not financial advice and not a proven pump predictor.
It never places trades and never needs exchange API keys for public market data.
"""
from __future__ import annotations
import asyncio, json, logging, math, os, sqlite3, time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

BYBIT_BASE = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
MEXC_BASE = os.getenv('MEXC_BASE_URL', 'https://api.mexc.com')
POLL_SECONDS = max(30, int(os.getenv('POLL_SECONDS', '60')))
MAX_SYMBOLS = max(10, min(500, int(os.getenv('MAX_SYMBOLS_PER_MARKET', '100'))))
RV_THRESHOLD = max(1.0, float(os.getenv('RELATIVE_VOLUME_THRESHOLD', '2.5')))
MOVE_THRESHOLD = max(0.1, float(os.getenv('PRICE_CHANGE_THRESHOLD', '1.0')))
DB_PATH = os.getenv('SCANNER_DB_PATH', '/tmp/full_maven_scanner.db')
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
NEWS_FEEDS = [x.strip() for x in os.getenv('NEWS_FEED_URLS', '').split(',') if x.strip()]
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger('full_maven')

first_seen_map: dict[tuple[str,str], str] = {}
alert_last_sent: dict[str, float] = {}
state: dict[str, Any] = {'status':'Starting', 'updated_at':None, 'last_error':None, 'markets_scanned':{}, 'rows':[], 'news':[], 'scan_seconds':None, 'source_status':{}, 'signal_count':0}

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0b1220"><title>Full Maven Scanner</title>
<style>
:root{color-scheme:dark;--bg:#0b1220;--panel:#121d30;--panel2:#17253b;--line:#283b55;--text:#eef5ff;--muted:#9caec5;--green:#46d6a0;--red:#ff7185;--amber:#ffca70;--blue:#8db7ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#12213a 0,#0b1220 48%);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,Arial}header{position:sticky;top:0;z-index:5;background:#0d1728ed;backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:14px 16px}.brand{display:flex;align-items:center;gap:10px}.logo{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#46d6a0,#5285ff);display:grid;place-items:center;color:#07111e;font-size:22px;font-weight:900}h1{font-size:19px;margin:0}header p{margin:2px 0 0;color:var(--muted);font-size:12px}main{max-width:1450px;margin:auto;padding:14px}.nav{display:flex;gap:7px;overflow:auto;padding:12px 0}.nav button{white-space:nowrap;background:#101b2d;border:1px solid var(--line);border-radius:9px;padding:10px 12px;color:var(--muted)}.nav button.active{color:var(--text);border-color:var(--green);background:#16302f}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.card,.box{background:linear-gradient(160deg,#15233a,#111a2a);border:1px solid var(--line);border-radius:14px;padding:13px;min-width:0}.label{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}.big{font-size:23px;font-weight:800;margin:4px 0}.small{font-size:12px;color:var(--muted);overflow-wrap:anywhere}.controls{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.controls input{flex:1;min-width:150px}input,select,button{font:inherit;background:#0c1728;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:10px}button{cursor:pointer}button:hover{border-color:var(--blue)}.primary{background:#17332f;border-color:#276c5a}.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:900px}.table th,.table td{padding:11px 9px;text-align:right;border-bottom:1px solid #26364d;white-space:nowrap}.table th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);position:sticky;top:0;background:#152239}.table th:first-child,.table td:first-child{text-align:left}.table tbody tr{cursor:pointer}.table tbody tr:hover{background:#1a2b43}.sym{font-weight:800}.sub{font-size:11px;color:var(--muted);white-space:normal;max-width:280px;display:inline-block}.pos{color:var(--green)}.neg{color:var(--red)}.warn{color:var(--amber)}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-size:11px}.section{margin-top:13px}.section h2{font-size:16px;margin:0 0 8px}.section p{color:var(--muted);margin:0 0 10px}.grid2{display:grid;grid-template-columns:1fr;gap:12px}.item{padding:11px 0;border-bottom:1px solid var(--line)}.item:last-child{border-bottom:0}.item a{color:var(--blue)}.notice{border:1px solid #735b2b;background:#302818;color:#ffe2a3;border-radius:11px;padding:11px;margin:12px 0;font-size:12px}.hidden{display:none!important}.tagrow{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.empty{padding:22px;text-align:center;color:var(--muted)}.bar{height:7px;border-radius:99px;background:#26354a;overflow:hidden;margin:7px 0}.bar span{display:block;height:100%;background:linear-gradient(90deg,#46d6a0,#8db7ff)}.detailgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metric{background:#0c1728;border:1px solid var(--line);border-radius:10px;padding:10px}.metric strong{display:block;font-size:17px}.foot{font-size:11px;color:var(--muted);line-height:1.6;margin:18px 2px}.badgeok{color:var(--green)}.badgebad{color:var(--red)}@media(min-width:720px){main{padding:22px}.cards{grid-template-columns:repeat(4,minmax(0,1fr))}.grid2{grid-template-columns:1.2fr .8fr}.detailgrid{grid-template-columns:repeat(4,minmax(0,1fr))}h1{font-size:22px}}
</style></head>
<body><header><div class="brand"><div class="logo">M</div><div><h1>Full Maven Scanner</h1><p>Early activity · momentum · risk intelligence · project news</p></div></div></header>
<main>
<div class="notice"><b>Research tool, not a buy signal.</b> Scores are transparent rules, not proven predictions. Market-cap, unlock, holder, contract and on-chain data may be unavailable. Missing news does not mean a project is safe.</div>
<nav class="nav" aria-label="Main navigation"><button class="active" data-page="home">Overview</button><button data-page="gems">Early Gems</button><button data-page="momentum">Momentum</button><button data-page="risk">Risk Watch</button><button data-page="new">Newly Observed</button><button data-page="news">News Intelligence</button><button data-page="performance">History & Performance</button><button data-page="system">System Status</button></nav>
<section id="page-home"><div class="cards"><div class="card"><div class="label">Scanner status</div><div class="big" id="status">Starting…</div><div class="small" id="updated">Waiting for first scan</div></div><div class="card"><div class="label">Markets tracked</div><div class="big" id="count">—</div><div class="small" id="sources">Bybit + MEXC</div></div><div class="card"><div class="label">Early activity</div><div class="big" id="signals">—</div><div class="small">Rule-qualified candidates</div></div><div class="card"><div class="label">Data health</div><div class="big" id="quality">—</div><div class="small" id="errors">Checking source health</div></div></div>
<div class="controls"><input id="search" placeholder="Search symbol, e.g. ABCUSDT" aria-label="Search markets"><select id="venue"><option value="all">All venues</option><option>Bybit Spot</option><option>Bybit Linear</option><option>MEXC Spot</option></select><select id="sort"><option value="score">Sort: Early activity score</option><option value="volume">Sort: Relative volume</option><option value="change">Sort: 24h change</option><option value="turnover">Sort: 24h turnover</option><option value="new">Sort: First observed</option></select><button class="primary" id="refresh">Refresh now</button></div>
<div class="box tablewrap"><table class="table"><thead><tr><th>Asset / venue</th><th>Price</th><th>24h %</th><th>5m %</th><th>Rel. volume</th><th>Turnover 24h</th><th>Score</th><th>Assessment</th></tr></thead><tbody id="rows"><tr><td colspan="8" class="empty">Waiting for market data…</td></tr></tbody></table></div>
<div class="foot">Tap any market row to inspect its evidence. Relative volume compares the latest closed 5-minute candle turnover with recent closed candles. This system does not place trades.</div></section>
<section id="page-gems" class="hidden"><div class="box section"><h2>Early Gem Finder</h2><p>Looks for unusual activity while avoiding coins already flagged as strongly extended. “Early” means early under these rules, not necessarily before a pump.</p><div id="gems-list" class="empty">Loading candidates…</div></div></section>
<section id="page-momentum" class="hidden"><div class="box section"><h2>Short-term momentum</h2><p>Strong short-term movement can mean opportunity or late entry risk. Inspect liquidity and the risk flags.</p><div id="momentum-list" class="empty">Loading momentum…</div></div></section>
<section id="page-risk" class="hidden"><div class="box section"><h2>Risk watch</h2><p>Flags are heuristics. They do not identify every scam, crash, or manipulation event.</p><div id="risk-list" class="empty">Loading risk flags…</div></div></section>
<section id="page-new" class="hidden"><div class="box section"><h2>Newly observed assets</h2><p>This means first observed by this running process. It is <b>not</b> verified exchange listing date; first-seen memory can reset after a restart.</p><div id="new-list" class="empty">Loading observations…</div></div></section>
<section id="page-news" class="hidden"><div class="grid2"><div class="box section"><h2>Project & market news</h2><p>Public RSS/Atom feeds only. Feed coverage can be incomplete or stale.</p><div id="news-list" class="empty">Loading feeds…</div></div><div class="box section"><h2>News coverage status</h2><div id="news-status" class="empty">Checking feed status…</div><p>Configure <code>NEWS_FEED_URLS</code> on the host to add trusted official project and exchange feeds. This module does not yet perform comprehensive due diligence.</p></div></div></section>
<section id="page-performance" class="hidden"><div class="grid2"><div class="box section"><h2>Recorded market observations</h2><p>History begins when this deployment starts and depends on persistent database configuration.</p><div id="history-summary" class="empty">Loading saved observations…</div></div><div class="box section"><h2>Model status</h2><div class="notice">No trained predictive model is shipped. The included training script requires a labelled dataset with future returns measured after each observation.</div><p id="model-note">This panel reports recorded observations, not a win rate or proof of profitability.</p></div></div><div class="box section"><h2>Latest history</h2><div class="tablewrap"><table class="table"><thead><tr><th>Observed at</th><th>Asset</th><th>Venue</th><th>Price</th><th>5m %</th><th>Rel. volume</th><th>Score</th><th>Assessment</th></tr></thead><tbody id="history-rows"><tr><td colspan="8" class="empty">Loading…</td></tr></tbody></table></div></div></section>
<section id="page-system" class="hidden"><div class="grid2"><div class="box section"><h2>Runtime configuration</h2><div id="config-list" class="empty">Loading config…</div></div><div class="box section"><h2>Source health</h2><div id="source-list" class="empty">Loading source health…</div><h2 style="margin-top:18px">Latest warnings</h2><div id="error-list" class="empty">No warnings loaded.</div></div></div></section>
<section id="detail" class="box section hidden"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center"><div><h2 id="detail-title">Asset details</h2><p id="detail-sub">Select a market row</p></div><button id="close-detail">Close</button></div><div class="detailgrid" id="detail-metrics"></div><div class="grid2" style="margin-top:12px"><div><h2>Why it was flagged</h2><div id="detail-reasons"></div></div><div><h2>Risk flags</h2><div id="detail-risks"></div></div></div><p class="small" style="margin-top:12px">This detail view uses the current snapshot. It does not include verified market cap, contract audit, holder distribution or on-chain flow unless explicitly supplied by a future data integration.</p></section>
<div class="foot">Full Maven Scanner · read-only market monitoring · no exchange trading keys required. Confirm asset identity, trading availability, liquidity, slippage, project announcements and risk independently. Free hosting can sleep or restart; use a persistent database and monitor source status.</div>
</main>
<script>
'use strict';
let data=[],news=[],historyRows=[],statusData={},configData={},activePage='home';
const $=id=>document.getElementById(id);
const fmt=(v,d=2)=>v===null||v===undefined||v===''||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
const pct=v=>v===null||v===undefined?'—':(Number(v)>0?'+':'')+fmt(v)+'%';
const cls=v=>Number(v)>0?'pos':Number(v)<0?'neg':'';
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function setPage(page){activePage=page;document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));document.querySelectorAll('main > section[id^="page-"]').forEach(s=>s.classList.toggle('hidden',s.id!=='page-'+page));if(page==='gems')renderSubset('gems-list',data.filter(x=>x.assessment==='Early activity'||x.assessment==='Watch'));if(page==='momentum')renderSubset('momentum-list',data.filter(x=>(x.change_5m||0)>=2||(x.relative_volume||0)>=2).sort((a,b)=>(b.change_5m||0)-(a.change_5m||0)));if(page==='risk')renderSubset('risk-list',data.filter(x=>(x.risk_flags||[]).length));if(page==='new')renderSubset('new-list',data.filter(x=>x.first_seen).sort((a,b)=>String(b.first_seen).localeCompare(String(a.first_seen))));if(page==='news')renderNews();if(page==='performance')renderHistory();if(page==='system')renderSystem();}
document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.page)));
function filtered(){const q=$('search').value.trim().toUpperCase(),venue=$('venue').value,sort=$('sort').value;let r=data.filter(x=>(!q||String(x.symbol).includes(q))&&(venue==='all'||x.venue===venue));r.sort((a,b)=>sort==='volume'?(b.relative_volume||0)-(a.relative_volume||0):sort==='change'?(b.change_24h||0)-(a.change_24h||0):sort==='turnover'?(b.turnover_24h||0)-(a.turnover_24h||0):sort==='new'?String(b.first_seen||'').localeCompare(String(a.first_seen||'')):(b.score||0)-(a.score||0));return r;}
function renderTable(rows,target='rows'){const el=$(target);if(!rows.length){el.innerHTML='<tr><td colspan="8" class="empty">No matching data yet.</td></tr>';return;}el.innerHTML=rows.slice(0,300).map((x,i)=>`<tr data-idx="${i}" data-symbol="${esc(x.symbol)}" data-venue="${esc(x.venue)}"><td><span class="sym">${esc(x.symbol)}</span><br><span class="sub">${esc(x.venue)} · ${esc(x.source||'')}</span></td><td>${fmt(x.price,8)}</td><td class="${cls(x.change_24h)}">${pct(x.change_24h)}</td><td class="${cls(x.change_5m)}">${pct(x.change_5m)}</td><td>${fmt(x.relative_volume)}×</td><td>${fmt(x.turnover_24h,0)}</td><td><b>${fmt(x.score,0)}</b></td><td><span class="pill">${esc(x.assessment||'Monitoring')}</span>${x.risk_flags?.length?'<br><span class="sub warn">'+esc(x.risk_flags.join(', '))+'</span>':''}<br><span class="sub">${esc((x.reasons||[]).slice(0,2).join('; '))}</span></td></tr>`).join('');el.querySelectorAll('tr[data-symbol]').forEach(tr=>tr.addEventListener('click',()=>{const x=data.find(z=>z.symbol===tr.dataset.symbol&&z.venue===tr.dataset.venue);if(x)showDetail(x);}));}
function renderSubset(target,rows){const el=$(target);if(!rows.length){el.innerHTML='<div class="empty">No matching rows in the latest scan. This may mean there are no qualifying signals or the data source is incomplete.</div>';return;}el.innerHTML=rows.slice(0,80).map(x=>`<div class="item"><div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><b>${esc(x.symbol)} <span class="pill">${esc(x.venue)}</span></b><b>${fmt(x.score,0)}/100</b></div><div class="bar"><span style="width:${Math.max(0,Math.min(100,Number(x.score)||0))}%"></span></div><div>${esc((x.reasons||[]).join(' · ')||'No positive early-activity reason recorded.')}</div><div class="small">Price ${fmt(x.price,8)} · 5m ${pct(x.change_5m)} · rel. volume ${fmt(x.relative_volume)}× · 24h ${pct(x.change_24h)}</div>${x.risk_flags?.length?'<div class="warn">⚠ '+esc(x.risk_flags.join(' · '))+'</div>':''}<button style="margin-top:7px" data-symbol="${esc(x.symbol)}" data-venue="${esc(x.venue)}">Inspect details</button></div>`).join('');el.querySelectorAll('button[data-symbol]').forEach(b=>b.addEventListener('click',()=>{const x=data.find(z=>z.symbol===b.dataset.symbol&&z.venue===b.dataset.venue);if(x)showDetail(x);}));}
function showDetail(x){$('detail').classList.remove('hidden');$('detail-title').textContent=x.symbol;$('detail-sub').textContent=x.venue+' · observed '+(x.observed_at||'time unavailable');const metrics=[['Last price',fmt(x.price,8)],['24h change',pct(x.change_24h)],['5m change',pct(x.change_5m)],['Relative volume',(x.relative_volume==null?'—':fmt(x.relative_volume)+'×')],['24h turnover',fmt(x.turnover_24h,0)],['Activity score',fmt(x.score,0)+'/100'],['Assessment',x.assessment||'Monitoring'],['First observed',x.first_seen||'Unknown']];$('detail-metrics').innerHTML=metrics.map(m=>`<div class="metric"><span class="small">${esc(m[0])}</span><strong>${esc(m[1])}</strong></div>`).join('');$('detail-reasons').innerHTML=(x.reasons||[]).length?(x.reasons||[]).map(t=>`<div class="item">✓ ${esc(t)}</div>`).join(''):'<div class="empty">No positive reasons recorded or candle data unavailable.</div>';$('detail-risks').innerHTML=(x.risk_flags||[]).length?(x.risk_flags||[]).map(t=>`<div class="item warn">⚠ ${esc(t)}</div>`).join(''):'<div class="item">No current heuristic risk flags. This is not a safety certification.</div>';$('detail').scrollIntoView({behavior:'smooth',block:'start'});}
$('close-detail').addEventListener('click',()=>$('detail').classList.add('hidden'));
function renderNews(){ $('news-list').innerHTML=news.length?news.slice(0,80).map(n=>`<div class="item"><b>${esc(n.title)}</b><div class="small">${esc(n.source)} · ${esc(n.published_at||'Publication time unknown')}</div><div>${esc(n.summary||'')}</div>${n.link?'<a href="'+esc(n.link)+'" target="_blank" rel="noopener noreferrer">Open original source ↗</a>':''}</div>`).join(''):'<div class="empty">No feed items returned. Check feed configuration and source health; this is not evidence that there is no negative news.</div>';const status=statusData.source_status?.news||'not checked';$('news-status').innerHTML=`<div class="item"><b>Feed configured:</b> ${configData.news_feeds_configured||0}</div><div class="item"><b>Latest feed status:</b> ${esc(status)}</div><div class="item"><b>Items available:</b> ${news.length}</div><div class="item">Coverage is limited to the configured RSS/Atom feeds. No automated verification of every project's official sources is performed.</div>`;}
function renderHistory(){ $('history-summary').innerHTML=`<div class="detailgrid"><div class="metric"><span class="small">Rows returned</span><strong>${historyRows.length}</strong></div><div class="metric"><span class="small">Model trained</span><strong>No</strong></div></div><p style="margin-top:10px">These are saved observations, not future outcomes. A win rate cannot be calculated from this alone.</p>`;const el=$('history-rows');el.innerHTML=historyRows.length?historyRows.map(x=>`<tr><td>${esc(x.observed_at||'—')}</td><td>${esc(x.symbol)}</td><td>${esc(x.venue)}</td><td>${fmt(x.price,8)}</td><td class="${cls(x.change_5m)}">${pct(x.change_5m)}</td><td>${fmt(x.relative_volume)}×</td><td>${fmt(x.score,0)}</td><td>${esc(x.assessment||'—')}</td></tr>`).join(''):'<tr><td colspan="8" class="empty">No saved history yet. The scanner must run and the database must be writable.</td></tr>';}
function renderSystem(){const counts=statusData.markets_scanned||{},sources=statusData.source_status||{};$('config-list').innerHTML=Object.entries(configData).map(([k,v])=>`<div class="item"><b>${esc(k.replaceAll('_',' '))}:</b> ${esc(typeof v==='object'?JSON.stringify(v):String(v))}</div>`).join('');$('source-list').innerHTML=Object.entries({...counts,...sources}).map(([k,v])=>`<div class="item"><b>${esc(k.replaceAll('_',' '))}:</b> <span class="${String(v).includes('error')?'badgebad':'badgeok'}">${esc(String(v))}</span></div>`).join('')||'<div class="empty">No source checks yet.</div>';$('error-list').innerHTML=statusData.last_error?`<div class="warn">${esc(statusData.last_error)}</div>`:'<div class="badgeok">No error reported by the latest scan. This does not guarantee all source data is complete.</div>';}
async function getJSON(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(url+' returned HTTP '+r.status);return r.json();}
async function refreshAll(){ $('refresh').textContent='Refreshing…';try{const results=await Promise.allSettled([getJSON('/api/status'),getJSON('/api/market?limit=1000'),getJSON('/api/news'),getJSON('/api/config'),getJSON('/api/history?limit=100')]);if(results[0].status==='fulfilled')statusData=results[0].value;if(results[1].status==='fulfilled')data=results[1].value.rows||[];if(results[2].status==='fulfilled')news=results[2].value.items||[];if(results[3].status==='fulfilled')configData=results[3].value;if(results[4].status==='fulfilled')historyRows=results[4].value.rows||[];const s=statusData;$('status').textContent=s.status||'Unknown';$('updated').textContent='Updated '+(s.updated_at||'not yet')+' · scan '+fmt(s.scan_seconds)+'s';const c=s.markets_scanned||{};$('count').textContent=(c.bybit_spot||0)+(c.bybit_linear||0)+(c.mexc_spot||0);$('sources').textContent=`Bybit spot ${c.bybit_spot||0} · perp ${c.bybit_linear||0} · MEXC ${c.mexc_spot||0}`;$('signals').textContent=s.signal_count??0;$('quality').textContent=(s.last_error||Object.values(s.source_status||{}).some(v=>v==='error'||v==='partial'))?'Partial':(s.updated_at?'Online':'Starting');$('errors').textContent=s.last_error||'Review source status for completeness';renderTable(filtered());if(activePage!=='home')setPage(activePage);}catch(e){$('status').textContent='Connection issue';$('errors').textContent=String(e);}finally{$('refresh').textContent='Refresh now';}}
$('search').addEventListener('input',()=>renderTable(filtered()));$('venue').addEventListener('change',()=>renderTable(filtered()));$('sort').addEventListener('change',()=>renderTable(filtered()));$('refresh').addEventListener('click',refreshAll);refreshAll();setInterval(refreshAll,45000);
</script></body></html>'''

def now_iso() -> str: return datetime.now(timezone.utc).isoformat(timespec='seconds')
def num(x: Any, default: float=0.0) -> float:
    try:
        n=float(x)
        return n if math.isfinite(n) else default
    except (ValueError,TypeError): return default

def db_connect():
    # DATABASE_URL support for PostgreSQL is optional; SQLite is the no-setup default.
    if DATABASE_URL.startswith(('postgres://','postgresql://','postgresql+psycopg://')):
        try:
            import psycopg
            url=DATABASE_URL.replace('postgres://','postgresql://',1).replace('postgresql+psycopg://','postgresql://',1)
            return psycopg.connect(url), 'postgres'
        except Exception as e:
            log.warning('PostgreSQL connection unavailable; falling back to SQLite: %s',e)
    Path(DB_PATH).parent.mkdir(parents=True,exist_ok=True)
    return sqlite3.connect(DB_PATH,timeout=15), 'sqlite'

def init_db():
    conn,kind=db_connect()
    try:
        if kind=='postgres':
            with conn.cursor() as c:
                c.execute('''CREATE TABLE IF NOT EXISTS observations (id BIGSERIAL PRIMARY KEY, observed_at TEXT NOT NULL, symbol TEXT NOT NULL, venue TEXT NOT NULL, price DOUBLE PRECISION, change_24h DOUBLE PRECISION, change_5m DOUBLE PRECISION, relative_volume DOUBLE PRECISION, turnover_24h DOUBLE PRECISION, score DOUBLE PRECISION, assessment TEXT, risk_flags TEXT, reasons TEXT, UNIQUE(observed_at,symbol,venue))''')
                c.execute('''CREATE TABLE IF NOT EXISTS news_items (id BIGSERIAL PRIMARY KEY, item_key TEXT UNIQUE NOT NULL, fetched_at TEXT NOT NULL, title TEXT NOT NULL, source TEXT, link TEXT, published_at TEXT, summary TEXT)''')
            conn.commit()
        else:
            conn.executescript('''CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY AUTOINCREMENT, observed_at TEXT NOT NULL, symbol TEXT NOT NULL, venue TEXT NOT NULL, price REAL, change_24h REAL, change_5m REAL, relative_volume REAL, turnover_24h REAL, score REAL, assessment TEXT, risk_flags TEXT, reasons TEXT, UNIQUE(observed_at,symbol,venue)); CREATE INDEX IF NOT EXISTS idx_obs_symbol_time ON observations(symbol,observed_at); CREATE TABLE IF NOT EXISTS news_items (id INTEGER PRIMARY KEY AUTOINCREMENT,item_key TEXT UNIQUE NOT NULL,fetched_at TEXT NOT NULL,title TEXT NOT NULL,source TEXT,link TEXT,published_at TEXT,summary TEXT);''')
            conn.commit()
    finally: conn.close()

def save_observations(rows):
    if not rows:return
    conn,kind=db_connect(); stamp=now_iso()
    try:
        payload=[(stamp,r['symbol'],r['venue'],r.get('price'),r.get('change_24h'),r.get('change_5m'),r.get('relative_volume'),r.get('turnover_24h'),r.get('score'),r.get('assessment'),json.dumps(r.get('risk_flags',[])),json.dumps(r.get('reasons',[]))) for r in rows]
        with conn.cursor() if kind=='postgres' else _nullcontext(conn) as c:
            if kind=='postgres':
                c.executemany('INSERT INTO observations(observed_at,symbol,venue,price,change_24h,change_5m,relative_volume,turnover_24h,score,assessment,risk_flags,reasons) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',payload)
            else:
                c.executemany('INSERT OR IGNORE INTO observations(observed_at,symbol,venue,price,change_24h,change_5m,relative_volume,turnover_24h,score,assessment,risk_flags,reasons) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',payload)
        conn.commit()
    except Exception: log.exception('Could not save market observations')
    finally: conn.close()
class _nullcontext:
    def __init__(self,v):self.v=v
    def __enter__(self):return self.v
    def __exit__(self,*a):return False

def save_news(items):
    if not items:return
    conn,kind=db_connect()
    try:
        payload=[(i['key'],now_iso(),i['title'],i.get('source'),i.get('link'),i.get('published_at'),i.get('summary')) for i in items]
        with conn.cursor() if kind=='postgres' else _nullcontext(conn) as c:
            if kind=='postgres': c.executemany('INSERT INTO news_items(item_key,fetched_at,title,source,link,published_at,summary) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(item_key) DO NOTHING',payload)
            else: c.executemany('INSERT OR IGNORE INTO news_items(item_key,fetched_at,title,source,link,published_at,summary) VALUES(?,?,?,?,?,?,?)',payload)
        conn.commit()
    except Exception: log.exception('Could not save news')
    finally:conn.close()

def get_json_result(payload):
    if not isinstance(payload,dict):raise ValueError('API response was not an object')
    if payload.get('retCode') not in (None,0,'0'):raise RuntimeError(str(payload.get('retMsg','API error')))
    return payload.get('result',payload)

async def fetch_bybit(client: httpx.AsyncClient, category: str, limit: int):
    r=await client.get(f'{BYBIT_BASE}/v5/market/tickers',params={'category':category},timeout=15)
    r.raise_for_status(); body=get_json_result(r.json()); items=body.get('list',[])
    items=[x for x in items if x.get('symbol','').endswith('USDT') and num(x.get('turnover24h'))>0]
    items.sort(key=lambda x:num(x.get('turnover24h')),reverse=True)
    return items[:limit]

async def fetch_candles(client,category,symbol):
    r=await client.get(f'{BYBIT_BASE}/v5/market/kline',params={'category':category,'symbol':symbol,'interval':'5','limit':'30'},timeout=12)
    r.raise_for_status(); payload=get_json_result(r.json()); arr=payload.get('list',[])
    parsed=[]
    for c in arr:
        try: parsed.append({'ts':int(c[0]),'open':num(c[1]),'high':num(c[2]),'low':num(c[3]),'close':num(c[4]),'volume':num(c[5]),'turnover':num(c[6])})
        except (ValueError,TypeError,IndexError): continue
    parsed.sort(key=lambda x:x['ts'])
    # Latest row is normally the still-forming candle; exclude it.
    return parsed[:-1] if len(parsed)>1 else []

def analyze_market(ticker:dict, candles:list[dict], venue:str, category:str='spot') -> dict:
    closes=[c['close'] for c in candles if c['close']>0]; turnovers=[c['turnover'] for c in candles]
    last=candles[-1] if candles else None; prev=candles[-2] if len(candles)>1 else None
    change5=(last['close']/prev['close']-1)*100 if last and prev and prev['close'] else None
    baseline=turnovers[-11:-1] if len(turnovers)>=11 else turnovers[:-1]
    avg=sum(baseline)/len(baseline) if baseline else 0
    rv=last['turnover']/avg if last and avg>0 else None
    change24=num(ticker.get('price24hPcnt'))*100 if ticker.get('price24hPcnt') is not None else None
    price=num(ticker.get('lastPrice')) or (last['close'] if last else 0)
    turnover=num(ticker.get('turnover24h',ticker.get('quoteVolume',0)))
    flags=[]; reasons=[]; score=0.0
    if rv is not None:
        if rv>=RV_THRESHOLD: score+=min(35,12*math.log2(max(1,rv))); reasons.append(f'{rv:.1f}× recent 5m turnover')
        if rv>=8: flags.append('extreme volume: verify liquidity')
    if change5 is not None:
        if abs(change5)>=MOVE_THRESHOLD: score+=min(25,abs(change5)*5); reasons.append(f'{change5:+.2f}% on latest closed 5m candle')
        if change5<=-4: flags.append('sharp short-term decline')
    if change24 is not None:
        if change24>25: flags.append('already strongly extended over 24h')
        if change24<-10: flags.append('large 24h decline')
        if 0<change24<8: score+=5
    # No genuine market-cap or listing data is inferred from turnover.
    if turnover<100000: flags.append('low reported 24h turnover; slippage risk')
    if venue=='Bybit Linear' and ticker.get('fundingRate') is not None and abs(num(ticker.get('fundingRate')))>.001: flags.append('unusually high funding: leverage risk')
    if change5 is not None and change5>10: flags.append('may be late/overextended; do not chase blindly')
    score=round(min(100,score),1)
    if any('sharp' in f or 'large 24h decline' in f for f in flags): assessment='Risk'
    elif score>=35 and not any('extended' in f or 'late/' in f for f in flags): assessment='Early activity'
    elif score>=15: assessment='Watch'
    else: assessment='Monitoring'
    return {'symbol':str(ticker.get('symbol','')),'venue':venue,'source':'Bybit' if venue.startswith('Bybit') else 'MEXC','price':price,'change_24h':round(change24,2) if change24 is not None else None,'change_5m':round(change5,2) if change5 is not None else None,'relative_volume':round(rv,2) if rv is not None else None,'turnover_24h':round(turnover,2),'score':score,'assessment':assessment,'risk_flags':flags,'reasons':reasons,'first_seen':None,'observed_at':now_iso()}

async def fetch_mexc(client:httpx.AsyncClient, limit:int):
    r=await client.get(f'{MEXC_BASE}/api/v3/ticker/24hr',timeout=15);r.raise_for_status();data=r.json()
    if not isinstance(data,list):raise ValueError('Unexpected MEXC ticker response')
    rows=[x for x in data if str(x.get('symbol','')).endswith('USDT') and num(x.get('quoteVolume'))>0]
    rows.sort(key=lambda x:num(x.get('quoteVolume')),reverse=True)
    return rows[:limit]

async def fetch_news(client:httpx.AsyncClient):
    items=[]; errors=[]
    for url in NEWS_FEEDS[:8]:
        try:
            r=await client.get(url,timeout=12,headers={'User-Agent':'FullMavenScanner/1.0'});r.raise_for_status(); raw=r.text[:2_000_000]
            import xml.etree.ElementTree as ET
            root=ET.fromstring(raw)
            for node in root.iter():
                tag=node.tag.split('}')[-1].lower()
                if tag not in ('item','entry'):continue
                fields={c.tag.split('}')[-1].lower():''.join(c.itertext()).strip() for c in list(node)}
                title=fields.get('title','').strip();link=fields.get('link','').strip()
                if not link:
                    for c in list(node):
                        if c.tag.split('}')[-1].lower()=='link':link=c.attrib.get('href','');break
                published=fields.get('pubdate') or fields.get('published') or fields.get('updated') or fields.get('date')
                try: published=parsedate_to_datetime(published).astimezone(timezone.utc).isoformat() if published else None
                except Exception: published=published or None
                desc=fields.get('description') or fields.get('summary') or fields.get('content','')
                summary=' '.join(desc.split())[:500]
                if title:
                    import hashlib
                    key=hashlib.sha256((link or title).encode()).hexdigest()
                    items.append({'key':key,'title':title,'source':url.split('/')[2],'link':link,'published_at':published,'summary':summary})
        except Exception as e: errors.append(f'{url}: {type(e).__name__}')
    # newest and unique
    unique={x['key']:x for x in items}
    items=list(unique.values());items.sort(key=lambda x:x.get('published_at') or '',reverse=True)
    return items[:100],errors

async def send_telegram(text:str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:return
    async with httpx.AsyncClient() as client:
        try:
            r=await client.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',json={'chat_id':TELEGRAM_CHAT_ID,'text':text[:4000]},timeout=10);r.raise_for_status()
        except Exception:log.warning('Telegram alert failed')

async def scan_once():
    started=time.monotonic();errors=[];rows=[];counts={'bybit_spot':0,'bybit_linear':0,'mexc_spot':0};source_status={}
    limits=httpx.Limits(max_connections=20,max_keepalive_connections=10)
    async with httpx.AsyncClient(limits=limits,headers={'User-Agent':'FullMavenScanner/1.0'}) as client:
        for category,venue,key in [('spot','Bybit Spot','bybit_spot'),('linear','Bybit Linear','bybit_linear')]:
            try:
                tickers=await fetch_bybit(client,category,MAX_SYMBOLS);counts[key]=len(tickers);source_status[key]='ok'
                sem=asyncio.Semaphore(12)
                async def one(t):
                    async with sem:
                        try:
                            candles=await fetch_candles(client,category,t['symbol'])
                            return analyze_market(t,candles,venue,category)
                        except Exception as e:
                            errors.append(f'{venue} {t.get("symbol")}: {type(e).__name__}')
                            return analyze_market(t,[],venue,category)
                rows.extend(await asyncio.gather(*(one(t) for t in tickers)))
            except Exception as e:source_status[key]='error';errors.append(f'{venue}: {type(e).__name__}: {e}')
        try:
            mexc=await fetch_mexc(client,MAX_SYMBOLS);counts['mexc_spot']=len(mexc);source_status['mexc_spot']='ok'
            for t in mexc:
                rows.append({'symbol':str(t.get('symbol','')),'venue':'MEXC Spot','source':'MEXC','price':num(t.get('lastPrice')),'change_24h':round(num(t.get('priceChangePercent')),2),'change_5m':None,'relative_volume':None,'turnover_24h':round(num(t.get('quoteVolume')),2),'score':0,'assessment':'Monitoring','risk_flags':['MEXC-only data: match token identity and confirm Bybit listing before trading'],'reasons':['Secondary exchange watchlist; 5m candles not yet analysed'],'first_seen':None,'observed_at':now_iso()})
        except Exception as e:source_status['mexc_spot']='error';errors.append(f'MEXC: {type(e).__name__}: {e}')
        try:
            news,news_errors=await fetch_news(client);state['news']=news;save_news(news)
            source_status['news']='ok' if NEWS_FEEDS and not news_errors else ('partial' if NEWS_FEEDS else 'not_configured')
            errors.extend('News feed error: '+x for x in news_errors)
        except Exception as e:source_status['news']='error';errors.append(f'News: {type(e).__name__}')
    # MEXC is intelligence only. A symbol match is not proof that two markets are the same asset.
    bybit_symbols={r['symbol'] for r in rows if r['venue'].startswith('Bybit')}
    for r in rows:
        if r['venue']=='MEXC Spot' and r['symbol'] in bybit_symbols:r['reasons'].append('Same symbol appears on Bybit; verify contract/token identity')
    stamp=now_iso()
    for r in rows:
        key=(r['venue'],r['symbol'])
        if key not in first_seen_map:first_seen_map[key]=stamp
        r['first_seen']=first_seen_map[key]
    rows.sort(key=lambda r:(r['score'],r.get('relative_volume') or 0),reverse=True)
    save_observations(rows)
    state.update({'status':'Running' if not errors else 'Running with warnings','updated_at':now_iso(),'last_error':'; '.join(errors[:8]) if errors else None,'markets_scanned':counts,'rows':rows,'scan_seconds':round(time.monotonic()-started,2),'source_status':source_status,'signal_count':sum(r['assessment']=='Early activity' for r in rows)})
    # Notify only fresh, high-scoring candidates; this is a rule alert, not a recommendation.
    for r in rows:
        alert_key=r['venue']+':'+r['symbol']
        if r['assessment']=='Early activity' and r['venue'].startswith('Bybit') and r.get('score',0)>=40 and time.time()-alert_last_sent.get(alert_key,0)>=1800:
            await send_telegram(f"Full Maven activity alert: {r['symbol']} ({r['venue']})\nScore: {r['score']}\n5m: {r.get('change_5m')}% | Relative volume: {r.get('relative_volume')}x\nReasons: {', '.join(r['reasons'])}\nCheck liquidity, news and risk manually; not a buy signal.")
            alert_last_sent[alert_key]=time.time()

async def scanner_loop():
    while True:
        try: await scan_once()
        except asyncio.CancelledError: raise
        except Exception as e:log.exception('Scan loop failed');state.update({'status':'Error','last_error':str(e)[:500]})
        await asyncio.sleep(POLL_SECONDS)

@asynccontextmanager
async def lifespan(app:FastAPI):
    try:init_db()
    except Exception:log.exception('Database init failed')
    task=asyncio.create_task(scanner_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):await task

app=FastAPI(title='Full Maven Scanner',version='1.0.0',description='Read-only experimental crypto market intelligence',lifespan=lifespan)
@app.get('/',response_class=HTMLResponse)
async def dashboard():return HTML
@app.get('/health')
async def health():return {'ok':True,'service':'full-maven-scanner','time':now_iso()}
@app.get('/api/status')
async def api_status():return {k:v for k,v in state.items() if k not in ('rows','news')}
@app.get('/api/market')
async def api_market(q:str|None=None,venue:str|None=None,limit:int=Query(300,ge=1,le=1000)):
    rows=state['rows']
    if q:rows=[r for r in rows if q.upper() in r['symbol'].upper()]
    if venue:rows=[r for r in rows if r['venue'].lower()==venue.lower()]
    return {'count':len(rows[:limit]),'rows':rows[:limit]}
@app.get('/api/candidates')
async def api_candidates(min_score:float=Query(10,ge=0,le=100),assessment:str|None=None):
    rows=[r for r in state['rows'] if r['score']>=min_score]
    if assessment:rows=[r for r in rows if r['assessment'].lower()==assessment.lower()]
    return {'count':len(rows),'rows':rows}
@app.get('/api/news')
async def api_news():return {'configured':bool(NEWS_FEEDS),'coverage_status':state.get('source_status',{}).get('news','not_checked'),'items':state['news'][:100]}
@app.get('/api/history')
async def api_history(symbol:str|None=None,limit:int=Query(100,ge=1,le=1000)):
    conn,kind=db_connect()
    try:
        if kind=='postgres':
            with conn.cursor() as c:
                if symbol:c.execute('SELECT observed_at,symbol,venue,price,change_24h,change_5m,relative_volume,turnover_24h,score,assessment,risk_flags,reasons FROM observations WHERE symbol=%s ORDER BY id DESC LIMIT %s',(symbol.upper(),limit))
                else:c.execute('SELECT observed_at,symbol,venue,price,change_24h,change_5m,relative_volume,turnover_24h,score,assessment,risk_flags,reasons FROM observations ORDER BY id DESC LIMIT %s',(limit,))
                rows=c.fetchall()
        else:
            conn.row_factory=sqlite3.Row
            sql='SELECT observed_at,symbol,venue,price,change_24h,change_5m,relative_volume,turnover_24h,score,assessment,risk_flags,reasons FROM observations';params=[]
            if symbol:sql+=' WHERE symbol=?';params.append(symbol.upper())
            sql+=' ORDER BY id DESC LIMIT ?';params.append(limit)
            rows=[dict(r) for r in conn.execute(sql,params).fetchall()]
            return {'count':len(rows),'rows':rows,'note':'History begins when this deployment starts; SQLite on free web hosts may be ephemeral. Configure DATABASE_URL for persistent PostgreSQL.'}
        keys=['observed_at','symbol','venue','price','change_24h','change_5m','relative_volume','turnover_24h','score','assessment','risk_flags','reasons']
        return {'count':len(rows),'rows':[dict(zip(keys,r)) for r in rows],'note':'History begins when this deployment starts.'}
    except Exception as e:return {'count':0,'rows':[],'error':str(e)[:300]}
    finally:conn.close()
@app.get('/api/config')
async def api_config():return {'poll_seconds':POLL_SECONDS,'max_symbols_per_market':MAX_SYMBOLS,'relative_volume_threshold':RV_THRESHOLD,'price_change_threshold':MOVE_THRESHOLD,'database':'postgresql' if DATABASE_URL.startswith(('postgres://','postgresql://','postgresql+psycopg://')) else 'sqlite','news_feeds_configured':len(NEWS_FEEDS),'telegram_configured':bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),'trading_enabled':False}

if __name__=='__main__':
    import uvicorn
    uvicorn.run('app:app',host='0.0.0.0',port=int(os.getenv('PORT','8000')))
