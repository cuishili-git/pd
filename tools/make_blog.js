#!/usr/bin/env node
/**
 * 把 docs/ 下的 Markdown 教程编译成一套纯静态 HTML 博客。
 *
 *   node tools/make_blog.js
 *
 * 产物：
 *   index.html            博客首页（文章卡片列表）
 *   blog/00-新人教程.html   每篇一个页面，带侧边目录 / 上下篇 / 公式
 *
 * 特点：零运行时依赖（marked 只在本脚本构建时使用，已随仓库带在 tools/vendor/）；
 * 公式优先交给 MathJax CDN，离线时用内置轻量渲染兜底；图片走 ../docs/figures/ 相对路径，
 * 本地双击与 GitHub Pages 均可正常显示。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { marked } = require('./vendor/marked.cjs');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'blog');
const SITE = '局放信号源 V0 · 新人教程';

// 阅读顺序即首页顺序。desc 只用于首页卡片，正文全部取自 Markdown 原文。
const POSTS = [
  {
    src: 'docs/00-新人教程.md',
    slug: '00-新人教程',
    title: '从零做出第一个局放脉冲',
    sub: '新人教程 · 主线',
    tag: '入门必读',
    desc: '软件工程师视角的心智模型、逐个元件为什么在、物料与 1/4W 串联方案、四步上电、零射频验源、故障表与 10 条纠错记录。',
  },
  {
    src: 'docs/01-上电验收卡.md',
    slug: '01-上电验收卡',
    title: '上电验收卡（照着打勾）',
    sub: '现场操作卡',
    tag: '动手时翻',
    desc: '到货清点、200–250V 安全规程、Step 1–4 分步动作与判据、47kΩ 压降验源法、故障排查顺序。',
  },
  {
    src: 'docs/02-模拟源子项目.md',
    slug: '02-模拟源子项目',
    title: '模拟源子项目 V0–V3 方案',
    sub: '完整设计',
    tag: '背景',
    desc: '空间辐射 300–1500MHz、幅度可调的完整方案演进，最简雪崩版清单与原理，后续升级路线。',
  },
  {
    src: 'docs/03-参数推导与踩坑FAQ.md',
    slug: '03-参数推导与踩坑FAQ',
    title: '12 个「为什么」FAQ',
    sub: '原理答疑',
    tag: '原理',
    desc: '下拉电阻、钳位 0.8V、47kΩ 淬灭、双端口关断、τ 与 5τ、103/104 不可互换等高频疑问。',
  },
  {
    src: 'docs/04-元件参数计算手册.md',
    slug: '04-元件参数计算手册',
    title: '元件参数计算手册',
    sub: '能自己重算一遍',
    tag: '计算',
    desc: '7 个电容位 + 6 个电阻位逐个「公式 → 代入 → 结果 → 边界」；含验源判据 10V 的稳态自洽解。',
  },
  {
    src: 'docs/05-电路图图文讲解.md',
    slug: '05-电路图图文讲解',
    title: '电路图逐块图文讲解',
    sub: '照图施工',
    tag: '接线',
    desc: '总图拆成低压触发链 / 高压充电级 / 雪崩输出级三块，逐根线讲来龙去脉、参数、实物焊法与错接后果。',
  },
];

const CSS = `
:root{--ink:#1F2933;--muted:#5B6770;--line:#E1E7EC;--bg:#FFFFFF;--soft:#F7F9FB;
--accent:#2C5F7C;--accent-soft:#EAF2F7;--code:#F2F5F7;--red:#B03030;--green:#1D7A5F}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:"Microsoft YaHei","PingFang SC","Segoe UI",Arial,sans-serif;
 font-size:16px;line-height:1.85;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:0 28px}
header.top{border-bottom:1px solid var(--line);background:var(--bg)}
header.top .wrap{display:flex;align-items:center;justify-content:space-between;height:64px;gap:20px}
.brand{font-size:17px;font-weight:700;color:var(--ink);letter-spacing:.2px}
.brand span{color:var(--accent)}
nav.top a{margin-left:22px;font-size:14px;color:var(--muted)}
nav.top a:hover{color:var(--accent)}
.hero{padding:52px 0 34px;border-bottom:1px solid var(--line);background:var(--soft)}
.hero h1{font-size:32px;line-height:1.4;margin:0 0 12px;font-weight:700}
.hero p{margin:0;color:var(--muted);font-size:15px;max-width:760px}
.hero .meta{margin-top:18px;font-size:13px;color:var(--muted)}
.hero .meta b{color:var(--accent);font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:18px;padding:38px 0 60px}
.card{border:1px solid var(--line);border-radius:10px;padding:22px 22px 20px;background:var(--bg);
 transition:border-color .15s}
.card:hover{border-color:var(--accent);text-decoration:none}
.card .no{font-size:12px;color:var(--muted);letter-spacing:1px}
.card h2{font-size:19px;margin:8px 0 4px;line-height:1.45;color:var(--ink)}
.card .sub{font-size:13px;color:var(--accent);margin:0 0 12px}
.card p{font-size:14px;color:var(--muted);line-height:1.75;margin:0}
.card .foot{margin-top:16px;padding-top:12px;border-top:1px solid var(--line);
 font-size:12px;color:var(--muted);display:flex;justify-content:space-between}
.tag{display:inline-block;background:var(--accent-soft);color:var(--accent);
 border-radius:4px;padding:1px 8px;font-size:12px}
/* 文章页 */
.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:44px;padding:34px 0 70px}
aside.toc{position:sticky;top:24px;align-self:start;font-size:13px;max-height:calc(100vh - 48px);overflow:auto}
aside.toc .t{font-weight:700;color:var(--muted);letter-spacing:1px;font-size:12px;
 padding-bottom:10px;border-bottom:1px solid var(--line);margin-bottom:10px}
aside.toc a{display:block;color:var(--muted);padding:4px 0;line-height:1.55}
aside.toc a:hover{color:var(--accent)}
aside.toc a.lv3{padding-left:14px;font-size:12px}
article{min-width:0}
article > h1{font-size:29px;line-height:1.45;margin:0 0 6px}
.article-sub{color:var(--muted);font-size:14px;margin:0 0 26px;padding-bottom:18px;border-bottom:1px solid var(--line)}
article h2{font-size:22px;margin:42px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line);scroll-margin-top:20px}
article h3{font-size:18px;margin:30px 0 10px;scroll-margin-top:20px}
article h4{font-size:16px;margin:22px 0 8px;color:var(--muted)}
article p{margin:0 0 14px}
article ul,article ol{padding-left:24px;margin:0 0 16px}
article li{margin:4px 0}
article blockquote{margin:16px 0;padding:10px 16px;background:var(--soft);
 border-left:3px solid var(--accent);color:var(--muted)}
article blockquote p{margin:0}
article table{border-collapse:collapse;width:100%;margin:16px 0 22px;font-size:14px;display:block;overflow-x:auto}
article th,article td{border:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}
article th{background:var(--soft);font-weight:600;white-space:nowrap}
article tr:nth-child(even) td{background:#FCFDFE}
article code{background:var(--code);border-radius:3px;padding:2px 5px;font-size:13px;
 font-family:Consolas,"Cascadia Mono",monospace}
article pre{background:#F4F7F9;border:1px solid var(--line);border-radius:8px;
 padding:16px 18px;overflow-x:auto;margin:16px 0 22px;line-height:1.6}
article pre code{background:none;padding:0;font-size:13px}
article img{max-width:100%;height:auto;display:block;margin:18px auto;border:1px solid var(--line);border-radius:8px}
article hr{border:0;border-top:1px solid var(--line);margin:34px 0}
.math{background:var(--soft);border:1px solid var(--line);border-radius:6px;
 padding:12px 16px;margin:16px 0;overflow-x:auto;text-align:center;
 font-family:"Cambria Math",Georgia,serif;font-size:16px;color:var(--ink)}
.math span.im{font-style:italic}
.math .frac{display:inline-flex;flex-direction:column;vertical-align:middle;text-align:center;margin:0 3px}
.math .frac i{font-style:normal;border-bottom:1px solid currentColor;padding:0 4px 2px}
.math .frac b{font-weight:400;padding:2px 4px 0}
.pager{display:flex;justify-content:space-between;gap:16px;margin-top:52px;
 padding-top:22px;border-top:1px solid var(--line);font-size:14px}
.pager a{display:block;max-width:46%}
.pager .dir{font-size:12px;color:var(--muted);display:block;margin-bottom:3px}
footer{border-top:1px solid var(--line);padding:22px 0 40px;color:var(--muted);font-size:13px}
footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
@media(max-width:900px){.layout{grid-template-columns:1fr;gap:0}aside.toc{position:static;max-height:none;
 margin-bottom:24px;padding:14px;background:var(--soft);border-radius:8px}.wrap{padding:0 18px}}
`;

// 公式渲染：纯本地递归解析 LaTeX 子集，不依赖任何 CDN，离线双击与 GitHub Pages 表现一致。
// 支持 \frac{}{}（可嵌套）、\text{}、上下标、希腊字母与常用运算符。
const FALLBACK_JS = String.raw`
(function(){
  var G={'\\times':'×','\\cdot':'·','\\approx':'≈','\\le':'≤','\\geq':'≥','\\ge':'≥',
    '\\neq':'≠','\\tau':'τ','\\mu':'μ','\\Omega':'Ω','\\pi':'π','\\parallel':'∥',
    '\\qquad':'　','\\quad':'　','\\,':' ','\;':' ','\!':'','\\ ':' ',
    '\\cdots':'…','\\infty':'∞','\\Rightarrow':'⇒','\\pm':'±','\\left':'','\\right':'',
    '\\%':'%','\\$':'$'};
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function render(src){
    var i=0;
    function group(){
      if(src[i]!=='{') return null;
      var d=0,out='';
      for(;i<src.length;i++){
        var c=src[i];
        if(c==='{'){d++; if(d>1) out+=c; continue;}
        if(c==='}'){d--; if(d===0){i++; return out;} out+=c; continue;}
        out+=c;
      }
      return out;
    }
    function skip(){while(src[i]===' ')i++;}
    function parse(){
      var out='';
      while(i<src.length){
        var c=src[i];
        if(c==='\\'){
          var m=/^\\([a-zA-Z]+|.)/.exec(src.slice(i));
          var tok=m?m[0]:'\\', cmd=m?m[1]:'';
          i+=tok.length;
          if(cmd==='frac'||cmd==='dfrac'||cmd==='tfrac'){
            skip(); var a=group()||''; skip(); var b=group()||'';
            out+='<span class="frac"><i>'+render(a)+'</i><b>'+render(b)+'</b></span>';
          }else if(cmd==='text'||cmd==='mathrm'||cmd==='boxed'||cmd==='operatorname'){
            skip(); var g=group(); out+= (g===null?'':esc(g));
          }else if(cmd==='sqrt'){
            skip(); var r=group(); out+='√'+(r===null?'':render(r));
          }else if(G['\\'+cmd]!==undefined){ out+=G['\\'+cmd]; }
          else if(/^[a-zA-Z]+$/.test(cmd)){ out+=cmd; }
          continue;
        }
        if(c==='^'||c==='_'){
          i++; var tag=(c==='^'?'sup':'sub'); skip();
          var g2=group(); var body=(g2===null?(src[i++]||''):g2);
          out+='<'+tag+'>'+render(body)+'</'+tag+'>';
          continue;
        }
        if(c==='{'){ var g3=group(); out+=(g3===null?'':render(g3)); continue; }
        if(c==='}'||c==='$'){ i++; continue; }
        out+=esc(c); i++;
      }
      return out;
    }
    return parse();
  }
  document.querySelectorAll('.math').forEach(function(el){
    el.innerHTML=render(el.getAttribute('data-tex')||el.textContent);
  });
})();
`;

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function slugify(text, used) {
  let s = text.replace(/<[^>]+>/g, '').replace(/[`#*]/g, '').trim()
    .replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fa5-]/g, '').toLowerCase();
  if (!s) s = 'sec';
  let base = s, i = 2;
  while (used.has(s)) s = base + '-' + (i++);
  used.add(s);
  return s;
}

/** Markdown 预处理：公式保护 → 链接/图片路径重写 → marked → 给标题挂 id */
function renderMarkdown(md) {
  // 0) 页面标题由模板给出，去掉源文档开头自带的 H1，避免同页出现两个大标题
  md = md.replace(/^\s{0,3}#[ \t]+[^\n]*\r?\n/, '');

  const stash = [];
  const hold = (tex, display) => {
    const i = stash.push({ tex, display }) - 1;
    return `\n\nMATHBLOCK${i}ENDMATHBLOCK\n\n`;
  };

  // 1) $$...$$ 块（允许跨行）
  md = md.replace(/\$\$([\s\S]*?)\$\$/g, (_, tex) => hold(tex.trim(), true));
  // 2) 行内 $...$（排除已占位块）
  md = md.replace(/(?<![\w$])\$([^\n$]+?)\$(?![\w$])/g,
    (_, tex) => /[\\^_{}]/.test(tex) ? hold(tex.trim(), false) : `$${tex}$`);

  // 3) 路径重写：输出页位于 blog/，源文档位于 docs/
  md = md.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (m, alt, href) => {
    if (/^https?:/.test(href) || href.startsWith('../docs/')) return m;
    if (href.startsWith('figures/')) return `![${alt}](../docs/${href})`;
    if (href.startsWith('docs/figures/')) return `![${alt}](../${href})`;
    return m;
  });
  md = md.replace(/\]\(([^)]*?\.md)(#[^)]*)?\)/g, (m, file, hash) => {
    const base = path.basename(file, '.md');
    const known = POSTS.find(p => p.slug === base);
    return known ? `](${known.slug}.html${hash || ''})` : m;
  });
  // 普通链接里的 figures/ 也要加 ../docs/（图片已在上面处理过）
  md = md.replace(/(?<!!)\[([^\]]*)\]\((figures\/[^)]+|docs\/figures\/[^)]+)\)/g,
    (m, alt, href) => `[${alt}](${href.startsWith('docs/') ? '../' + href : '../docs/' + href})`);

  let html = marked.parse(md, { gfm: true, breaks: false });

  // marked 新版会把中文路径百分号编码；还原成原文件名，避免 Pages 与本地双击出现歧义
  html = html.replace(/(href|src)="([^"]*%[0-9A-Fa-f]{2}[^"]*)"/g, (m, attr, url) => {
    try { return `${attr}="${decodeURIComponent(url)}"`; } catch (_) { return m; }
  });

  // 4) 还原公式占位
  html = html.replace(/<p>\s*MATHBLOCK(\d+)ENDMATHBLOCK\s*<\/p>/g, (_, i) => {
    const { tex, display } = stash[+i];
    return display
      ? `<div class="math" data-tex="${esc(tex)}">${esc(tex)}</div>`
      : `<span class="math" data-tex="${esc(tex)}" style="display:inline;padding:1px 6px">${esc(tex)}</span>`;
  });

  // 5) 给 h2/h3 挂 id，同时生成目录
  const used = new Set(), toc = [];
  html = html.replace(/<h([23])>([\s\S]*?)<\/h\1>/g, (m, lv, inner) => {
    const id = slugify(inner, used);
    toc.push({ lv: +lv, id, text: inner.replace(/<[^>]+>/g, '') });
    return `<h${lv} id="${id}">${inner}</h${lv}>`;
  });
  return { html, toc, hasMath: stash.length > 0 };
}

function shell({ title, body, toc, prev, next, hasMath, sub, home }) {
  const tocHtml = toc && toc.length
    ? `<aside class="toc"><div class="t">本页目录</div>${toc.map(t =>
        `<a class="${t.lv === 3 ? 'lv3' : ''}" href="#${t.id}">${esc(t.text)}</a>`).join('')}</aside>` : '';
  const pager = (prev || next) ? `<div class="pager">
    ${prev ? `<a href="${prev.slug}.html"><span class="dir">← 上一篇</span>${esc(prev.title)}</a>` : '<span></span>'}
    ${next ? `<a href="${next.slug}.html" style="text-align:right"><span class="dir">下一篇 →</span>${esc(next.title)}</a>` : '<span></span>'}
  </div>` : '';
  const article = toc ? `<div class="wrap layout">${tocHtml}<article>
    <h1>${esc(title)}</h1><div class="article-sub">${esc(sub || '')}</div>
    ${body}${pager}</article></div>` : body;

  return `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} · ${SITE}</title>
<meta name="description" content="${esc(sub || SITE)}">
<style>${CSS}</style></head><body>
<header class="top"><div class="wrap">
  <div class="brand">${home ? SITE : `<a href="../index.html">${SITE}</a>`}</div>
  <nav class="top"><a href="${home ? 'blog/00-新人教程.html' : '../blog/00-新人教程.html'}">开始阅读</a>
  <a href="https://github.com/cuishili-git/pd">GitHub 源码</a></nav>
</div></header>
${article}
<footer><div class="wrap"><span>局放信号模拟源 V0 · 200–250V / 100Hz · 纯单机 DIY 记录</span>
<span>静态博客 · 由 <code>tools/make_blog.js</code> 从 Markdown 生成</span></div></footer>
<script>${FALLBACK_JS}</script>
</body></html>`;
}

function build() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const built = [];
  POSTS.forEach((p, i) => {
    const abs = path.join(ROOT, p.src);
    if (!fs.existsSync(abs)) { console.error('MISSING', p.src); process.exitCode = 1; return; }
    const md = fs.readFileSync(abs, 'utf8');
    const { html, toc, hasMath } = renderMarkdown(md);
    const out = shell({
      title: p.title, sub: `${p.sub} · ${p.tag}`, body: html, toc, hasMath,
      prev: POSTS[i - 1], next: POSTS[i + 1],
    });
    fs.writeFileSync(path.join(OUT_DIR, p.slug + '.html'), out, 'utf8');
    built.push({ ...p, sections: toc.length, hasMath });
  });

  // 首页
  const hero = `<section class="hero"><div class="wrap">
    <h1>局放信号源 V0 · 新人教程</h1>
    <p>一台能在 300–1500MHz 空间辐射脉冲的雪崩源，从「电容为什么是 10nF」到「万用表怎么判断它在放电」，
    全部按软件工程师能自己推一遍的方式写清楚。不看示波器、不买射频仪器也能验源。</p>
    <div class="meta">版本 <b>100Hz / 200–250V / ZTX415</b> &nbsp;·&nbsp; ${built.length} 篇 &nbsp;·&nbsp;
    配套 4 张接线图 + 5 张局部图与曲线 &nbsp;·&nbsp; 参数可重算脚本 <code>tools/calc_params.py</code></div>
  </div></section>`;
  const cards = `<div class="wrap"><div class="cards">${built.map((p, i) => `
    <a class="card" href="blog/${p.slug}.html">
      <div class="no">${String(i + 1).padStart(2, '0')} / ${String(built.length).padStart(2, '0')}</div>
      <h2>${esc(p.title)}</h2><div class="sub">${esc(p.sub)}</div>
      <p>${esc(p.desc)}</p>
      <div class="foot"><span class="tag">${esc(p.tag)}</span><span>${p.sections} 节${p.hasMath ? ' · 含公式' : ''}</span></div>
    </a>`).join('')}</div></div>`;
  fs.writeFileSync(path.join(ROOT, 'index.html'),
    shell({ title: '首页', body: hero + cards, home: true }), 'utf8');

  console.log('生成完成：');
  console.log('  index.html（博客首页）');
  built.forEach(p => console.log(`  blog/${p.slug}.html  ${p.sections} 节${p.hasMath ? ' [公式]' : ''}`));
}

build();
