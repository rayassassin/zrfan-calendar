#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键运行：抓取 -> 解析 -> 生成 ICS -> 生成预览页 -> 校验

仅依赖 Python3 标准库 + curl，服务器上无需 pip install。

用法：
    python3 main.py              # 抓最近 7 篇
    python3 main.py -n 14        # 抓最近 14 篇
    python3 main.py --force      # 忽略缓存重新抓取
"""
import os
import sys
import json
import argparse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crawler
import parser as ps
import ics_gen
import page
import validate

HERE = os.path.dirname(os.path.abspath(__file__))


def run(n_articles=7, out_dir=None, force=False, remind=10):
    out_dir = out_dir or os.path.join(HERE, 'build')
    ics_dir = os.path.join(out_dir, 'ics')

    print('=' * 56)
    print('[1/5] 抓取文章')
    arts = crawler.crawl(max_articles=n_articles, force=force)
    if not arts:
        print('抓取失败，终止')
        return 1
    print(f'      获取 {len(arts)} 篇：{arts[0]["title"]} ~ {arts[-1]["title"]}')

    print('[2/5] 解析活动')
    sch = ps.parse_all(arts)
    timed = sum(1 for s in sch if s['freq'] != 'ONCE')
    print(f'      解析出 {len(sch)} 项活动（定点提醒 {timed} 项）')

    print('[3/5] 生成 ICS')
    ics_gen.REMIND_MINUTES = remind  # 必须在 generate 之前设置
    cals = ics_gen.generate(sch, ics_dir, today=date.today())
    print(f'      生成 {len(cals)} 个银行日历 + all.ics')

    print('[4/5] 生成预览页')
    p = page.build(sch, cals, arts, out_dir, remind=remind)
    print(f'      {p}')

    print('[5/5] 校验')
    failed = 0
    for fn in sorted(os.listdir(ics_dir)):
        if fn.endswith('.ics'):
            _, errs = validate.check_file(os.path.join(ics_dir, fn))
            if errs:
                failed += 1
                print(f'      [FAIL] {fn}: {errs[:3]}')
    if failed:
        print(f'      有 {failed} 个文件校验未通过')
        return 1
    print('      全部通过')

    meta = {
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'articles': [{'title': a['title'], 'url': a['url'],
                      'date': f"{a['year']}-{a['month']:02d}-{a['day']:02d}"} for a in arts],
        'n_events': len(sch),
        'n_timed': timed,
        'calendars': [{'bank': c['bank'], 'slug': c['slug'],
                       'count': c['count'], 'timed': c['timed']} for c in cals],
        'remind_minutes': remind,
    }
    with open(os.path.join(out_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 记录本次抓到的最新文章日期，供「6 点兜底」判断当天指南是否已发布
    latest = date(arts[-1]['year'], arts[-1]['month'], arts[-1]['day'])
    state_dir = os.path.join(HERE, 'state')
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, 'latest_article_date'), 'w', encoding='utf-8') as f:
        f.write(latest.isoformat())
    print(f'      最新文章日期：{latest.isoformat()}')

    print('=' * 56)
    print(f'完成：{len(cals)} 个日历 / {len(sch)} 项活动 / 输出目录 {out_dir}')
    return 0


def main():
    ap = argparse.ArgumentParser(description='zrfan 刷卡指南 -> 银行日历')
    ap.add_argument('-n', '--articles', type=int, default=7, help='抓取最近 N 篇指南（默认 7）')
    ap.add_argument('-o', '--out', default=None, help='输出目录（默认 ./build）')
    ap.add_argument('-r', '--remind', type=int, default=10, help='提前提醒分钟数（默认 10）')
    ap.add_argument('--force', action='store_true', help='忽略缓存强制重新抓取')
    a = ap.parse_args()
    sys.exit(run(a.articles, a.out, a.force, a.remind))


if __name__ == '__main__':
    main()
