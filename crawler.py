#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zrfan.com 每日刷卡指南 爬虫
- 抓取分类页列表，筛选标题形如「2026-9-4日周五刷卡指南」的文章
- 抓取文章正文 HTML，本地缓存，避免重复请求
"""
import os
import re
import time
import json
import hashlib
import subprocess

BASE = "https://www.zrfan.com"
CATEGORY = "/category/zhinan/"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 标题形如：2026-9-4日周五刷卡指南
TITLE_RE = re.compile(
    r'(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\s*日\s*周\s*(?P<w>[一二三四五六日天])?\s*刷卡指南'
)
WEEKDAY_MAP = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)


def fetch(url, cache_key=None, ttl=6 * 3600, force=False):
    """带本地缓存的 HTTP GET，默认 6 小时缓存。"""
    cache_key = cache_key or hashlib.md5(url.encode()).hexdigest()
    path = os.path.join(CACHE_DIR, cache_key + ".html")
    if not force and os.path.exists(path):
        if time.time() - os.path.getmtime(path) < ttl:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read()
    # macOS 自带 Python 缺 CA 证书，urllib 会 SSL 校验失败，改用系统 curl
    base = [
        "curl", "-sSL", "--compressed", "--max-time", "30",
        "-A", UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: zh-CN,zh;q=0.9",
    ]

    def run(insecure=False):
        cmd = base + (["-k"] if insecure else []) + [url]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=45)
        except Exception as e:
            print(f"  [!] 请求异常 {url}: {e}")
            return ""
        if r.returncode != 0:
            err = r.stderr.decode('utf-8', 'ignore')
            if not insecure:
                print(f"  [!] curl 失败({r.returncode}) {url}: {err[:160].strip()}")
            return ""
        return r.stdout.decode("utf-8", errors="ignore")

    html = run()
    if not html.strip():
        # zrfan.com 的 TLS 配置没有下发中间证书（TrustAsia DV TLS RSA CA 2024），
        # 浏览器能靠 AIA 补全，但 curl / GitHub Actions 这类干净环境会直接失败。
        # 公开页面、无登录无隐私，此时降级跳过验证是合理的。
        html = run(insecure=True)
        if html.strip():
            print(f"  [!] 已跳过证书校验（站点证书链不完整）：{url}")
    if not html.strip():
        return ""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    time.sleep(1.0)  # 礼貌抓取，别压对方服务器
    return html


def parse_list(html):
    """从分类页解析出文章链接与标题。"""
    items = []
    # WordPress begin 主题：h2.entry-title > a
    for m in re.finditer(
        r'<h2[^>]*class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.S
    ):
        url, title_html = m.group(1), m.group(2)
        title = re.sub(r'<[^>]+>', '', title_html)
        title = title.replace('&nbsp;', ' ').strip()
        items.append({'url': url, 'title': title})
    if not items:
        # 兜底：任意指向数字型 post id 的链接
        for m in re.finditer(r'href="(https?://(?:www\.)?zrfan\.com/(\d{3,5})\.html)"[^>]*>([^<]{4,80})</a>',
                             html):
            items.append({'url': m.group(1), 'title': m.group(3).strip()})
    seen, out = set(), []
    for it in items:
        url = it['url'].strip()
        if url.startswith('//'):          # 协议相对 URL
            url = 'https:' + url
        elif url.startswith('/'):
            url = BASE + url
        if not url.startswith('http'):
            continue
        it['url'] = url
        if url in seen:
            continue
        seen.add(url)
        out.append(it)
    return out


def is_guide(title):
    m = TITLE_RE.search(title)
    if not m:
        return None
    return {
        'year': int(m.group('y')),
        'month': int(m.group('m')),
        'day': int(m.group('d')),
        'weekday_cn': m.group('w'),
        'title': title,
    }


def extract_content(html):
    """提取文章正文纯文本（保留换行）。"""
    import html as html_mod
    m = re.search(
        r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)'
        r'<div[^>]*class="[^"]*(?:post-navigation|entry-footer|author|comments)',
        html, re.S
    )
    if not m:
        m = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</article>', html, re.S)
    if not m:
        return ""
    c = m.group(1)
    c = re.sub(r'<script.*?</script>', '', c, flags=re.S)
    c = re.sub(r'<style.*?</style>', '', c, flags=re.S)
    c = re.sub(r'<br\s*/?>', '\n', c)
    c = re.sub(r'</(p|div|h1|h2|h3|h4|h5|li|tr|td)>', '\n', c)
    c = re.sub(r'<[^>]+>', '', c)
    c = html_mod.unescape(c)
    c = c.replace('\u00a0', ' ')
    c = re.sub(r'[ \t]+', ' ', c)
    lines = [l.strip() for l in c.split('\n')]
    return '\n'.join([l for l in lines if l])


def crawl(max_articles=7, max_pages=3, force=False):
    """抓取最近 max_articles 篇指南文章。"""
    guides = []
    for page in range(1, max_pages + 1):
        url = BASE + CATEGORY if page == 1 else f"{BASE}{CATEGORY}page/{page}/"
        print(f"[列表] {url}")
        html = fetch(url, cache_key=f"list_p{page}", force=force)
        if not html:
            break
        for it in parse_list(html):
            g = is_guide(it['title'])
            if g:
                g['url'] = it['url']
                guides.append(g)
        if len(guides) >= max_articles:
            break
        # 没有下一页就停
        if f'page/{page + 1}/' not in html:
            break

    # 按日期倒序去重
    guides.sort(key=lambda g: (g['year'], g['month'], g['day']), reverse=True)
    guides = guides[:max_articles]
    guides.sort(key=lambda g: (g['year'], g['month'], g['day']))

    for g in guides:
        print(f"[正文] {g['title']}")
        html = fetch(g['url'], cache_key=f"post_{os.path.basename(g['url'])}", force=force)
        g['content'] = extract_content(html)
        g['post_id'] = os.path.basename(g['url']).replace('.html', '')
        # 落一份可读文本，方便排查
        with open(os.path.join(RAW_DIR, f"{g['post_id']}.txt"), "w", encoding="utf-8") as f:
            f.write(g['title'] + "\n" + g['url'] + "\n\n" + g['content'])
    return guides


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    force = '--force' in sys.argv
    gs = crawl(max_articles=n, force=force)
    print(f"\n共抓取 {len(gs)} 篇：")
    for g in gs:
        print(f"  {g['year']}-{g['month']:02d}-{g['day']:02d} {g['title']} -> {len(g['content'])} 字")
