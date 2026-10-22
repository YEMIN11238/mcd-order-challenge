import { fresh, restore, answer, advance, score, badge, shareText, money } from './model.mjs';

const ROOT = document.getElementById('app');
const KEY = 'mcd-order-challenge-progress-v1';
const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
let deck, state, selected = null;
let storageWorks = true;
const has = (obj, key) => Object.hasOwn(obj, key);
const icons = ['↘', '♡', '＋', '↔', '！'];

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); }
  catch { storageWorks = false; }
}

function focusTitle() {
  const heading = ROOT.querySelector('h1');
  heading?.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: 'auto' });
}

function renderHome() {
  const count = Object.keys(state.answers).length;
  ROOT.innerHTML = `<section class="home"><div class="hero-copy"><div class="eyebrow"><span class="live-dot"></span>真实报价出题，答完就知道。</div><h1 tabindex="-1">这单，<br>你会<span class="underline">怎么点？</span></h1><p class="lead">便宜一点，就值得换？<br>套餐写 28，这次真付 28？</p><p class="hero-description">5 道真实点餐题，把预算、搭配和价格<br class="desktop-break">放在一起，看看你能选对几道。</p><div class="start-row"><button class="button primary" data-action="start" id="start">${count ? (state.complete ? '查看上次成绩' : `继续第 ${state.current + 1} 题`) : '开始挑战'} <span aria-hidden="true">↗</span></button><span class="start-meta">5 道题 · 约 2 分钟<br>免登录 · 手机直接玩</span></div>${count ? '<button class="text-button" data-action="restart">重新挑战这 5 道题</button>' : ''}<p class="truth-note"><span aria-hidden="true">↶</span> 使用官方接口历史记录，每题可查证据。<br>非实时查价，不连接你的麦当劳账号，也不下单。</p></div><div class="hero-art" aria-label="两份历史报价的选择示意"><span class="art-label">ONE ORDER. TWO CHOICES.</span><div class="receipt receipt-back"><div class="receipt-top"><span>CHOICE B</span><span>↗</span></div><div class="food-drawing" aria-hidden="true"><span class="burger-top"></span><span class="burger-fill"></span><span class="burger-bottom"></span></div><p>换一项，会怎样？</p><span class="dashed-line"></span><div class="receipt-price">¥34.50<small>历史整单核价</small></div><span class="receipt-foot">预算之内 / 选项不同</span></div><div class="receipt receipt-front"><div class="receipt-top"><span>CHOICE A</span><span>?</span></div><div class="food-drawing" aria-hidden="true"><span class="burger-top"></span><span class="burger-fill"></span><span class="burger-bottom"></span></div><p>原来的搭配</p><span class="dashed-line"></span><div class="receipt-price">¥37.00<small>历史整单核价</small></div><span class="receipt-foot">保留要求 / 看清总价</span></div><div class="art-stamp">算你<br><strong>会点</strong></div><span class="art-caption">来源：2026-10-23 悦荟广场两份板烧套餐记录</span></div></section><section class="how"><div><span>01—05</span><strong>五关，各有一个小问题。</strong></div><div class="topic-chips">${deck.questions.map((q,i)=>`<span><b>${icons[i]}</b>${escape(q.tag)}</span>`).join('')}</div><p>只比较题中有限候选；错选项是待判断的说法。答题进度只保存在本浏览器。</p></section>`;
}

function progress() {
  return `<div class="progress-header"><span>第 <b>${state.current + 1}</b> / ${deck.questions.length} 题</span><span>已答对 ${score(deck, state)} 题</span></div><div class="progress-track" aria-label="题目进度">${deck.questions.map((q,i)=>`<span class="${i === state.current ? 'current' : ''} ${has(state.answers,q.id) ? (state.answers[q.id] === q.correctId ? 'passed' : 'missed') : ''}"></span>`).join('')}</div>`;
}

function evidence(q) {
  return `<details class="evidence"><summary>查看这题的真实数据 <span>日期 · 金额 · traceId</span></summary><div class="evidence-body"><p class="source-context">${escape(q.context)}。以下是已完成的官方查询记录。</p>${q.sources.map(s=>`<article><div><strong>${escape(s.tool)}</strong>${has(s,'priceFen') ? `<b>${money(s.priceFen)}</b>` : '<span>选项证据</span>'}</div><p>${escape(s.at)}（北京时间）${s.reservation ? `<br>测试预约：${escape(s.reservation)}` : ''}</p><code>${escape(s.traceId)}</code><a href="${deck.repo}/blob/main/${s.file}" target="_blank" rel="noopener noreferrer">原始记录 ${escape(s.id)} ↗</a></article>`).join('')}<a class="evidence-report" href="${q.evidenceUrl}" target="_blank" rel="noopener noreferrer">核对完整题目、请求与答案 ↗</a><p class="evidence-boundary">历史价格不代表当前供应或报价。核价响应确认套餐与总金额，未逐项回显全部特制，未验证出餐。</p></div></details>`;
}

function renderQuestion() {
  const q = deck.questions[state.current];
  const revealed = has(state.answers, q.id);
  const chosen = revealed ? state.answers[q.id] : selected;
  const correct = revealed && chosen === q.correctId;
  ROOT.innerHTML = `<section class="game"><aside class="game-aside"><span class="eyebrow">THE ORDER CHALLENGE</span><h2>每一关，<br>看清一点。</h2><p>真实菜单与核价记录，<br>给这次选择一个可核对的答案。</p><div class="mini-receipt"><span>${icons[state.current]}</span><strong>${escape(q.tag)}</strong><small>${escape(q.context)}</small></div><button class="text-button" data-action="home">← 回首页，保留进度</button></aside><div class="question-area">${progress()}<div class="question-heading"><span class="question-number">${String(state.current + 1).padStart(2,'0')}</span><span class="tag">${escape(q.tag)}</span><span class="recorded-tag">历史实测题</span></div><h1 tabindex="-1">${escape(q.title)}</h1><p class="question-story">${escape(q.story)}</p><div class="condition-chips">${q.conditions.map(c=>`<span>${escape(c)}</span>`).join('')}</div><div class="question-context">${escape(q.context)}</div><div class="options" role="group" aria-label="选择你的答案">${q.options.map((o,i)=>`<button class="option ${chosen === o.id ? 'selected' : ''} ${revealed && o.id === q.correctId ? 'correct' : ''} ${revealed && chosen === o.id && !correct ? 'incorrect' : ''}" type="button" data-choice="${escape(o.id)}" aria-pressed="${chosen === o.id}" ${revealed ? 'disabled' : ''}><span class="choice-key">${String.fromCharCode(65+i)}</span><span class="choice-copy"><strong>${escape(o.title)}</strong><small>${escape(o.subtitle)}</small></span>${has(o,'priceFen') ? `<b class="option-price">${money(o.priceFen)}<small>历史核价</small></b>` : ''}${revealed && o.id === q.correctId ? '<span class="choice-mark" aria-label="正确答案">✓</span>' : revealed && chosen === o.id ? '<span class="choice-mark" aria-label="本次选错">×</span>' : ''}</button>`).join('')}</div>${revealed ? `<section class="answer-box ${correct ? 'answer-correct' : 'answer-learn'}" role="status"><span class="answer-label">${correct ? '✓ 这题选对了' : '↗ 这题，一起看明白'}</span><h2>${escape(q.verdict)}</h2><p>${escape(q.explanation)}</p><p class="takeaway">${escape(q.takeaway)}</p></section>${evidence(q)}<button class="button primary next" data-action="next">${state.current === deck.questions.length-1 ? '查看我的成绩' : '下一题'} <span aria-hidden="true">→</span></button>` : `<div class="confirm-row"><span id="selection-hint" role="status">${selected ? '选好了？确认后揭晓真实记录。' : '先选一项，再揭晓答案。'}</span><button class="button primary" id="confirm" data-action="confirm" ${selected ? '' : 'disabled'}>确认选择 <span aria-hidden="true">↗</span></button></div>`}<p class="local-note">${storageWorks ? '进度仅保存在本浏览器，随时可以回来继续。' : '浏览器未允许保存进度；当前页面仍可完成挑战。'}</p></div></section>`;
}

function renderResult() {
  const total = score(deck, state);
  ROOT.innerHTML = `<section class="result"><div class="result-main"><span class="eyebrow">CHALLENGE COMPLETE</span><h1 tabindex="-1">这顿，<br>你更会点了。</h1><div class="score-display"><strong>${total}</strong><span>/ ${deck.questions.length}<small>题答对</small></span><span class="score-spark" aria-hidden="true">✳</span></div><span class="result-badge">${badge(total)}</span><p class="result-copy">预算、口味、加价、门店与附加条件，<br>下一次点餐，多看清一步。</p><p class="score-meaning">这是本次本地答题成绩，不是消费能力评级或全网排名。</p><div class="result-actions"><button class="button primary" data-action="share" id="share">发给饭搭子挑战 ↗</button><button class="button secondary" data-action="copy" id="copy">复制成绩与链接</button><button class="button secondary" data-action="download" id="download">保存成绩卡 PNG ↓</button></div><p id="share-status" role="status" aria-live="polite"></p><button class="text-button" data-action="restart">↶ 再挑战一次</button></div><div class="result-review"><div class="review-heading"><h2>五题复盘</h2><span>答案都有出处</span></div>${deck.questions.map((q,i)=>{const right=state.answers[q.id]===q.correctId;const a=q.options.find(o=>o.id===q.correctId);return `<details class="review-item"><summary><span class="review-mark ${right ? 'is-right' : ''}">${right?'✓':'↗'}</span><span><small>${String(i+1).padStart(2,'0')} / ${escape(q.tag)}</small><strong>${escape(q.title)}</strong></span><b aria-hidden="true">＋</b></summary><div><p class="correct-caption">正确选择：${escape(a.title)}${has(a,'priceFen')?' '+money(a.priceFen):''}</p><p>${escape(q.explanation)}</p><a href="${q.evidenceUrl}" target="_blank" rel="noopener noreferrer">查看原始证据 ↗</a></div></details>`;}).join('')}<a class="star-callout" href="${deck.repo}" target="_blank" rel="noopener noreferrer"><span>觉得这 5 题有用？<strong>欢迎 Star，或给下一道题提建议。</strong></span><span aria-hidden="true">☆ ↗</span></a><p class="review-note">分享链接只包含题库版本，不包含你的逐题答案。成绩卡包含本次得分。</p></div></section>`;
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); }
  catch {
    const input=document.createElement('textarea');input.value=text;input.style.cssText='position:fixed;left:-9999px;top:0';document.body.append(input);input.select();const done=document.execCommand('copy');input.remove();if(!done) throw new Error('Clipboard unavailable');
  }
}

function wrapText(ctx,text,x,y,maxWidth,lineHeight) {
  let line='';
  for(const char of text){if(ctx.measureText(line+char).width>maxWidth&&line){ctx.fillText(line,x,y);line=char;y+=lineHeight;}else line+=char;}
  if(line)ctx.fillText(line,x,y);
  return y+lineHeight;
}

async function downloadCard() {
  const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1440;
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas unavailable');
  ctx.fillStyle='#f6f3e9';ctx.fillRect(0,0,1080,1440);
  ctx.fillStyle='#292f25';ctx.fillRect(55,55,970,1330);
  ctx.fillStyle='#dbef6d';ctx.font='700 28px sans-serif';ctx.fillText('THE ORDER CHALLENGE',110,135);
  ctx.fillStyle='#fffdf5';ctx.font='800 76px sans-serif';ctx.fillText('麦麦点餐挑战',110,255);
  ctx.font='800 290px sans-serif';ctx.fillText(String(score(deck,state)),100,600);
  ctx.fillStyle='#dbef6d';ctx.font='600 100px sans-serif';ctx.fillText('/ 5',335,600);
  ctx.font='700 46px sans-serif';ctx.fillText(badge(score(deck,state)),110,705);
  ctx.fillStyle='#fffdf5';ctx.font='400 38px sans-serif';wrapText(ctx,'预算、口味、加价、门店与附加条件，你能选对几道？',110,810,850,62);
  ctx.strokeStyle='#686f60';ctx.lineWidth=2;ctx.setLineDash([8,10]);ctx.beginPath();ctx.moveTo(110,990);ctx.lineTo(970,990);ctx.stroke();ctx.setLineDash([]);
  ctx.fillStyle='#dbef6d';ctx.font='700 34px sans-serif';ctx.fillText('手机打开，同一套五道题。',110,1070);
  ctx.fillStyle='#fffdf5';ctx.font='400 25px sans-serif';ctx.fillText('yemin11238.github.io/mcd-order-challenge/',110,1135);
  ctx.fillStyle='#bfc6b5';ctx.font='400 24px sans-serif';ctx.fillText('历史实测 2026-10-20 / 10-23 · 非实时查价 · 不下单',110,1240);ctx.fillText('本地答题成绩 · 独立参赛作品 · 非官方产品',110,1290);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw new Error('PNG export failed');
  const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`麦麦点餐挑战-${score(deck,state)}分.png`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
}

ROOT.addEventListener('click',async event=>{
  const choice=event.target.closest('button[data-choice]');
  if(choice&&!has(state.answers,deck.questions[state.current].id)){
    selected=choice.dataset.choice;
    ROOT.querySelectorAll('[data-choice]').forEach(button=>{const chosen=button.dataset.choice===selected;button.classList.toggle('selected',chosen);button.setAttribute('aria-pressed',String(chosen));});
    document.getElementById('confirm').disabled=false;document.getElementById('selection-hint').textContent='选好了？确认后揭晓真实记录。';return;
  }
  const button=event.target.closest('button[data-action]');if(!button)return;
  const action=button.dataset.action;
  if(action==='start'){if(state.complete)renderResult();else renderQuestion();focusTitle();}
  if(action==='home'){renderHome();focusTitle();}
  if(action==='restart'){state=fresh(deck);selected=null;save();renderQuestion();focusTitle();}
  if(action==='confirm'&&selected){state=answer(deck,state,selected);selected=null;save();renderQuestion();ROOT.querySelector('.answer-box')?.scrollIntoView({block:'nearest'});}
  if(action==='next'){state=advance(deck,state);selected=null;save();state.complete?renderResult():renderQuestion();focusTitle();}
  if(['share','copy','download'].includes(action)){
    const status=document.getElementById('share-status');button.disabled=true;
    try{
      if(action==='download'){await downloadCard();status.textContent='成绩卡已生成。手机可在下载列表中保存图片。';}
      else if(action==='share'&&navigator.share){await navigator.share({title:'麦麦点餐挑战',text:`我答对了 ${score(deck,state)}/5 题，你能选对几道？历史实测题，非实时查价。`,url:`${deck.playUrl}?deck=${encodeURIComponent(deck.deckId)}`});status.textContent='已打开系统分享。';}
      else{await copyText(shareText(deck,state));status.textContent='已复制成绩和同题链接，附带历史数据说明。';}
    }catch(error){if(error.name!=='AbortError')status.textContent='浏览器暂未完成操作，可以用地址栏分享本页链接。';}
    finally{button.disabled=false;}
  }
});

async function boot(){
  try{
    const response=await fetch('./quiz.json');if(!response.ok)throw new Error('Deck unavailable');deck=await response.json();
    if(deck.mode!=='recorded'||deck.questions.length!==5)throw new Error('Invalid deck');
    const expected=new URL(location.href).searchParams.get('deck');
    if(expected&&expected!==deck.deckId){ROOT.innerHTML='<section class="loading"><h1>这份题库已更新。</h1><p>旧题库链接与当前版本不同，成绩不作跨版本比较。</p><a class="button primary" href="./">打开当前五道题</a></section>';return;}
    let saved;try{saved=JSON.parse(localStorage.getItem(KEY)||'null');}catch{storageWorks=false;}
    state=restore(deck,saved);renderHome();document.documentElement.dataset.ready='true';
  }catch{ROOT.innerHTML=`<section class="loading" role="alert"><h1>题库暂时没加载成功。</h1><p>请刷新重试，或直接阅读题目与证据。</p><a class="button primary" href="https://github.com/YEMIN11238/mcd-order-challenge/blob/main/docs/evidence.md">查看完整题库 ↗</a></section>`;}
}
boot();
