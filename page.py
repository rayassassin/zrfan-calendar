#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成按银行分类的预览页 index.html（纯静态，无外部依赖）。"""
import os
import json
import html
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>刷卡优惠日历 · 按银行订阅</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
       background:#f5f6f8;color:#1c1e21;line-height:1.6;padding:32px 20px 64px}
  .wrap{max-width:1080px;margin:0 auto}
  header{margin-bottom:28px}
  h1{font-size:26px;font-weight:600;letter-spacing:-.3px}
  .sub{color:#65676b;font-size:14px;margin-top:8px}
  .sub a{color:#1a73e8;text-decoration:none}
  .sub a:hover{text-decoration:underline}
  .stats{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0 8px}
  .stat{background:#fff;border:1px solid #e3e5e8;border-radius:10px;padding:14px 18px;min-width:110px}
  .stat b{display:block;font-size:22px;font-weight:600;color:#1a73e8}
  .stat span{font-size:12px;color:#65676b}
  .toolbar{display:flex;gap:10px;align-items:center;margin:24px 0 16px;flex-wrap:wrap}
  #q{flex:1;min-width:200px;padding:9px 14px;border:1px solid #d8dade;border-radius:8px;font-size:14px;outline:none}
  #q:focus{border-color:#1a73e8}
  .hint{font-size:12px;color:#8a8d91}
  .bank{background:#fff;border:1px solid #e3e5e8;border-radius:12px;margin-bottom:14px;overflow:hidden}
  .bank-hd{display:flex;align-items:center;gap:12px;padding:14px 18px;cursor:pointer;user-select:none}
  .bank-hd:hover{background:#fafbfc}
  .bank-hd h2{font-size:16px;font-weight:600;min-width:88px}
  .cnt{font-size:12px;color:#65676b;background:#f0f2f5;padding:2px 9px;border-radius:20px}
  .hd-right{margin-left:auto;display:flex;gap:8px;align-items:center}
  .btn{padding:6px 13px;border-radius:7px;font-size:13px;border:1px solid #d8dade;background:#fff;
       color:#1c1e21;cursor:pointer;text-decoration:none;display:inline-block;white-space:nowrap}
  .btn:hover{border-color:#1a73e8;color:#1a73e8}
  .btn.pri{background:#1a73e8;color:#fff;border-color:#1a73e8}
  .btn.pri:hover{background:#1765cc;color:#fff}
  .arrow{color:#8a8d91;font-size:12px;transition:transform .2s}
  .bank.collapsed .arrow{transform:rotate(-90deg)}
  .bank.collapsed .ev-list{display:none}
  .ev-list{list-style:none;border-top:1px solid #f0f2f5}
  .ev{display:flex;gap:12px;padding:10px 18px;font-size:13.5px;border-bottom:1px solid #f7f8f9;align-items:baseline}
  .ev:last-child{border-bottom:none}
  .ev:hover{background:#fafbfc}
  .t{font-variant-numeric:tabular-nums;font-weight:600;color:#1a73e8;min-width:46px}
  .t.all{color:#8a8d91;font-weight:400;font-size:12px}
  .act{flex:1}
  .act .d{color:#65676b;font-size:12px;margin-top:3px;display:-webkit-box;
          -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .tags{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;max-width:230px}
  .tag{font-size:11px;padding:1px 7px;border-radius:4px;background:#e8f0fe;color:#1a73e8;white-space:nowrap}
  .tag.o{background:#f0f2f5;color:#65676b}
  .tag.m{background:#fef7e0;color:#b06000}
  .more{padding:9px 18px;font-size:13px;color:#1a73e8;cursor:pointer;background:#fafbfc;text-align:center}
  .more:hover{background:#f0f2f5}
  footer{margin-top:36px;font-size:12px;color:#8a8d91;line-height:1.9}
  .toast{position:fixed;bottom:28px;left:50%;transform:translateX(-50%) translateY(80px);
         background:#1c1e21;color:#fff;padding:11px 22px;border-radius:8px;font-size:14px;
         opacity:0;transition:all .25s;pointer-events:none;z-index:99}
  .toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
  @media(max-width:640px){body{padding:20px 12px 48px}.hd-right{width:100%;margin-left:0;
    justify-content:flex-end}.tags{max-width:none;justify-content:flex-start}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>刷卡优惠日历</h1>
    <div class="sub">
      自动抓取 <a href="https://www.zrfan.com/category/zhinan/" target="_blank">真人范儿 · 每日刷卡指南</a>
      ，按银行拆分为独立日历，可单独订阅 ·
      生成于 __GEN_TIME__
    </div>
    <div class="stats">
      <div class="stat"><b>__N_BANK__</b><span>银行日历</span></div>
      <div class="stat"><b>__N_EV__</b><span>活动总数</span></div>
      <div class="stat"><b>__N_TIMED__</b><span>定点提醒</span></div>
      <div class="stat"><b>__N_SRC__</b><span>分析文章</span></div>
    </div>
  </header>

  <div class="toolbar">
    <input id="q" placeholder="搜索银行或活动，例如：浦发、星巴克、加油">
    <span class="hint">提醒提前 __REMIND__ 分钟</span>
    <a class="btn" href="ics/all.ics" download>下载合并日历</a>
  </div>

  <div id="banks">__BANKS__</div>

  <footer>
    数据来源：zrfan.com 每日刷卡指南，每日自动更新。<br>
    订阅后 Google 日历约每 12 小时刷新一次；活动以原文为准，名额有限的活动请提前打开 APP 准备。<br>
    日历内容仅供参考，具体活动规则、名额与截止时间请以银行官方页面为准。
  </footer>
</div>
<div class="toast" id="toast"></div>

<script>
var BASE = (function(){
  var p = window.location.href.split('?')[0].split('#')[0];
  return p.substring(0, p.lastIndexOf('/') + 1);
})();

function gcal(slug){
  return 'https://calendar.google.com/calendar/r?cid=' + encodeURIComponent(BASE + 'ics/' + slug + '.ics');
}
// 订阅链接依赖部署域名，运行时按当前页面基址拼接
document.querySelectorAll('.btn.pri[data-slug]').forEach(function(a){
  a.href = 'https://calendar.google.com/calendar/r?cid=' +
           encodeURIComponent(BASE + 'ics/' + a.dataset.slug + '.ics');
});
function toast(msg){
  var t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(t._h); t._h = setTimeout(function(){ t.classList.remove('on'); }, 2000);
}
function copy(url){
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(function(){ toast('订阅链接已复制'); });
  } else {
    var ta = document.createElement('textarea');
    ta.value = url; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast('订阅链接已复制'); } catch(e){ toast('复制失败，请手动复制'); }
    document.body.removeChild(ta);
  }
}
document.querySelectorAll('.bank-hd').forEach(function(hd){
  hd.addEventListener('click', function(e){
    if (e.target.closest('a') || e.target.closest('button')) return;
    hd.parentElement.classList.toggle('collapsed');
  });
});
document.querySelectorAll('.more').forEach(function(m){
  m.addEventListener('click', function(){
    var list = m.parentElement.querySelector('.ev-list');
    list.querySelectorAll('.ev.hidden').forEach(function(x){ x.classList.remove('hidden'); });
    m.remove();
  });
});
document.getElementById('q').addEventListener('input', function(e){
  var k = e.target.value.trim().toLowerCase();
  document.querySelectorAll('.bank').forEach(function(b){
    var hit = !k || b.dataset.k.indexOf(k) >= 0;
    b.style.display = hit ? '' : 'none';
  });
});
</script>
</body>
</html>
"""


def _freq_tag(s):
    if s['freq'] == 'DAILY':
        return '<span class="tag">每日</span>'
    if s['freq'] == 'WEEKLY' and s['bydays']:
        cn = {'MO': '周一', 'TU': '周二', 'WE': '周三', 'TH': '周四',
              'FR': '周五', 'SA': '周六', 'SU': '周日'}
        return '<span class="tag">' + ''.join(cn.get(d, d) for d in s['bydays']) + '</span>'
    if s['freq'] == 'MONTHLY':
        return '<span class="tag m">每月%s日</span>' % s['monthday']
    return '<span class="tag o">期内可参与</span>'


def build(schedules, calendars, articles, out_dir, remind=10, today=None):
    by_slug = {}
    for s in schedules:
        for b in s['banks']:
            by_slug.setdefault(b, []).append(s)

    blocks = []
    for c in calendars:
        bank, slug = c['bank'], c['slug']
        items = sorted(by_slug.get(bank, []),
                       key=lambda x: (x['freq'] == 'ONCE', x['hour'], x['minute'], x['activity']))
        lis = []
        for idx, s in enumerate(items):
            hidden = ' hidden' if idx >= 8 else ''
            if s['freq'] == 'ONCE':
                t = '<span class="t all">全天</span>'
            else:
                t = '<span class="t">%02d:%02d</span>' % (s['hour'], s['minute'])
            desc = html.escape(s['desc'][:150])
            dl = ('<span class="tag o">至 %s</span>' % s['deadline'].strftime('%m-%d')
                  if s['deadline'] else '')
            lis.append(
                '<li class="ev%s">%s<div class="act"><div>%s</div><div class="d">%s</div></div>'
                '<div class="tags">%s%s</div></li>'
                % (hidden, t, html.escape(s['activity']), desc, _freq_tag(s), dl)
            )
        more = ('<div class="more">展开剩余 %d 项</div>' % (len(items) - 8)) if len(items) > 8 else ''
        keys = (bank + ' ' + ' '.join(s['activity'] for s in items)).lower()
        blocks.append(
            '<div class="bank" data-slug="%s" data-k="%s">'
            '<div class="bank-hd"><span class="arrow">▼</span><h2>%s</h2>'
            '<span class="cnt">%d 项 · 定点 %d</span>'
            '<div class="hd-right">'
            '<button class="btn" onclick="copy(BASE+\'ics/%s.ics\')">复制链接</button>'
            '<a class="btn pri" data-slug="%s" href="#" target="_blank" rel="noopener">订阅到 Google 日历</a>'
            '</div></div>'
            '<ul class="ev-list">%s</ul>%s</div>'
            % (slug, html.escape(keys), html.escape(bank), c['count'], c['timed'],
               slug, slug, ''.join(lis), more)
        )

    n_timed = sum(1 for s in schedules if s['freq'] != 'ONCE')
    now = datetime.now(CST).strftime('%Y-%m-%d %H:%M')
    page = (TPL
            .replace('__BANKS__', ''.join(blocks))
            .replace('__GEN_TIME__', now)
            .replace('__N_BANK__', str(len(calendars)))
            .replace('__N_EV__', str(len(schedules)))
            .replace('__N_TIMED__', str(n_timed))
            .replace('__N_SRC__', str(len(articles)))
            .replace('__REMIND__', str(remind)))

    path = os.path.join(out_dir, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(page)
    return path
