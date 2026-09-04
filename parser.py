#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
刷卡指南正文 -> 结构化活动条目

文章结构：
  2026-9-4日周五刷卡指南
    提醒 / 新增活动 / 特别活动 / 当日必做 / 小活动（无时间点）
    0点开始活动 / 7点开始活动 / 9点30分开始活动 / 14点30分开始活动（有时间）
      XX银行x活动名：
        描述行...
"""
import re
from datetime import date, datetime, timedelta

# ---------- 银行识别 ----------
BANK_ALIASES = {
    '工商银行': ['工商银行', '工行', '工银'],
    '农业银行': ['农业银行', '农行', '农银'],
    '中国银行': ['中国银行', '中行'],
    '建设银行': ['建设银行', '建行', '建行生活'],
    '交通银行': ['交通银行', '交行'],
    '邮储银行': ['邮储银行', '邮政储蓄', '邮储'],
    '浦发银行': ['浦发银行', '浦发', '浦大喜奔'],
    '光大银行': ['光大银行', '光大'],
    '广发银行': ['广发银行', '广发'],
    '兴业银行': ['兴业银行', '兴业', '兴业生活'],
    '华夏银行': ['华夏银行', '华夏', '华彩生活'],
    '中信银行': ['中信银行', '中信'],
    '民生银行': ['民生银行', '民生', '全民生活'],
    '招商银行': ['招商银行', '招商', '招行', '掌上生活'],
    '平安银行': ['平安银行', '平安'],
    '浙商银行': ['浙商银行', '浙商'],
    '北京银行': ['北京银行', '掌上京彩'],
    '上海银行': ['上海银行'],
    '银联云闪付': ['银联云闪付', '云闪付', '银联'],
    '其他优惠': ['淘宝', '京东', '支付宝', '微信', '中国移动', '中移动', '抖音', '美团'],
}
# 别名按长度倒序，保证「建设银行」优先于「建行」
_ALIAS_LIST = sorted(
    [(std, al) for std, als in BANK_ALIASES.items() for al in als],
    key=lambda x: -len(x[1])
)

# ---------- 章节识别 ----------
SECTION_TIME_RE = re.compile(r'^(\d{1,2})点(半|\d{1,2}分)?开始活动$')
SECTION_UNTIMED = {'提醒', '新增活动', '特别活动', '当日必做', '小活动', '注意事项', '活动预告'}

# 条目行：形如「XX银行x活动名：」或「XX银行-活动名：」
ITEM_SPLIT_RE = re.compile(r'[xX×＊*·\-—–]\s*')
ITEM_END_RE = re.compile(r'[：:]\s*$')

# 描述中的时间锚点，如「每日9点30分起」「周五10点起」「13点起」
TIME_ANCHOR_RE = re.compile(
    r'(\d{1,2})\s*点\s*(半|\d{1,2}\s*分)?\s*(?:起|开始|开抢|开领|开售|抢|可抢|可领|兑换|放|上线)?'
)
# 星期表达
WEEK_CN = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
WEEKDAY_ABBREV = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']

DAILY_RE = re.compile(r'每日|每天|天天')
WEEKLY_RE = re.compile(r'每?\s*周\s*([一二三四五六日天])')
WEEK_RANGE_RE = re.compile(r'每?\s*周\s*([一二三四五六日天])\s*[至到\-~]\s*周?\s*([一二三四五六日天])')
WEEKEND_RE = re.compile(r'周六周日|周日周六|每周末|周末')
# 必须有「每」字，否则截止日期里的「10月31日截止」会被误读成「每月31日」
MONTHLY_RE = re.compile(r'每\s*月\s*(\d{1,2})\s*[日号]')

# 截止日期：「9月30日截止」「26年12月31日截止」「续期至12月31日截止」「10月17日截止」
DEADLINE_RE = re.compile(
    r'(?:续期至|延长至|延期至|至)?\s*(?:(\d{2,4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]\s*(?:截止|结束|到期|前)'
)


def norm_bank(text):
    """从条目标题的银行部分提取标准银行名，支持多银行。"""
    found = []
    pos = []
    for std, al in _ALIAS_LIST:
        idx = text.find(al)
        if idx >= 0:
            if any(abs(idx - p) < len(al) for p in pos):
                continue
            found.append(std)
            pos.append(idx)
    if not found:
        return ['其他优惠']
    # 「其他优惠」只在确实没有银行时出现
    banks = [b for b in found if b != '其他优惠']
    return banks if banks else ['其他优惠']


def parse_time(anchor_str, default_hour=None, default_minute=0):
    """把「9点30分」/「10点」/「9点半」解析成 (hour, minute)。"""
    m = re.match(r'^\s*(\d{1,2})\s*点\s*(半|\d{1,2}\s*分)?', anchor_str)
    if not m:
        return (default_hour, default_minute)
    hour = int(m.group(1))
    if hour < 6:
        hour = 0  # 0点/凌晨时段保持 0
    minute = 0
    if m.group(2):
        if m.group(2) == '半':
            minute = 30
        else:
            minute = int(re.sub(r'\D', '', m.group(2)) or 0)
    return (hour, minute)


def parse_deadline(text, ref_year):
    """解析截止日期，返回 date 或 None。"""
    best = None
    for m in DEADLINE_RE.finditer(text):
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        year = int(y) if y else ref_year
        if y and len(y) == 2:
            year = 2000 + int(y)
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            continue
        try:
            dt = date(year, mo, d)
        except ValueError:
            continue
        if best is None or dt > best:
            best = dt
    return best


def parse_rule(text, art_weekday):
    """
    解析循环规则。
    返回 (freq, bydays, monthday)
      freq: 'DAILY' / 'WEEKLY' / 'MONTHLY' / 'ONCE'
    """
    t = text
    # 每周五 / 周X
    rng = WEEK_RANGE_RE.search(t)
    if rng:
        a, b = WEEK_CN[rng.group(1)], WEEK_CN[rng.group(2)]
        days = list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(0, b + 1))
        return ('WEEKLY', [WEEKDAY_ABBREV[d] for d in days], None)
    if WEEKEND_RE.search(t):
        return ('WEEKLY', ['SA', 'SU'], None)
    wk = WEEKLY_RE.search(t)
    if wk and not DAILY_RE.search(t):
        d = WEEK_CN[wk.group(1)]
        return ('WEEKLY', [WEEKDAY_ABBREV[d]], None)
    if DAILY_RE.search(t):
        return ('DAILY', None, None)
    mo = MONTHLY_RE.search(t)
    if mo:
        return ('MONTHLY', None, int(mo.group(1)))
    return ('ONCE', None, None)


def parse_article(article):
    """
    解析单篇文章，返回活动条目列表。
    article: {'title','url','year','month','day','content','post_id'}
    """
    art_date = date(article['year'], article['month'], article['day'])
    lines = [l.strip() for l in article['content'].split('\n') if l.strip()]

    events = []
    section = None        # 当前章节名
    section_time = None   # (hour, minute) 或 None
    cur = None            # 当前条目

    def flush():
        nonlocal cur
        if cur and cur['desc_lines']:
            events.append(cur)
        cur = None

    for line in lines:
        # 1) 章节行
        m = SECTION_TIME_RE.match(line)
        if m:
            flush()
            section = line
            section_time = parse_time(line)
            continue
        if line in SECTION_UNTIMED and len(line) <= 6:
            flush()
            section = line
            section_time = None
            continue

        # 2) 条目标题行：含银行关键词 + x 分隔 + 冒号结尾
        is_item = False
        if ITEM_END_RE.search(line) and len(line) <= 60:
            head = line.split('：')[0].split(':')[0]
            if ITEM_SPLIT_RE.search(head):
                is_item = True
            elif norm_bank(head) != ['其他优惠'] and len(head) <= 30:
                is_item = True
        if is_item:
            flush()
            head = ITEM_END_RE.sub('', line).strip()
            parts = ITEM_SPLIT_RE.split(head, 1)
            bank_part = parts[0].strip()
            act_name = parts[1].strip() if len(parts) > 1 else head
            banks = norm_bank(bank_part)
            cur = {
                'banks': banks,
                'activity': act_name,
                'raw_title': head,
                'section': section,
                'section_time': section_time,
                'desc_lines': [],
                'art_date': art_date,
                'source_url': article['url'],
                'source_title': article['title'],
            }
            continue

        # 3) 描述行
        if cur is not None:
            cur['desc_lines'].append(line)

    flush()
    return events


def build_schedules(events):
    """
    把条目展开为具体日程：确定开始时间、循环规则、截止日期。
    每个条目可能对应多个时间点（如「9点起抽奖、10点起抢、11点起抢」）。
    """
    out = []
    for ev in events:
        desc = '\n'.join(ev['desc_lines'])
        deadline = parse_deadline(desc, ev['art_date'].year)

        # 收集描述中的时间锚点
        anchors = []          # (hour, minute, 触发文本片段)
        for m in TIME_ANCHOR_RE.finditer(desc):
            frag = m.group(0)
            # 后面必须紧跟「起/开始/抢/领」等，或是行首明确时间
            tail = desc[m.end():m.end() + 6]
            if not re.match(r'^(起|开始|开抢|可抢|抢|可领|领|开领|兑换|放|上线|截止|结束)', tail):
                # 允许「9点30分起」这类已被正则吃掉「起」的情况
                if not re.search(r'(起|开始|抢|领)$', frag):
                    continue
            h, mi = parse_time(frag)
            if h is None:
                continue
            if (h, mi) not in [(a[0], a[1]) for a in anchors]:
                anchors.append((h, mi, frag))

        # 循环规则（从整条描述推断）
        freq, bydays, monthday = parse_rule(desc, ev['art_date'].weekday())
        # 无时间点章节（当日必做/小活动/提醒）本质是「每天记得做」，按每日提醒处理
        if freq == 'ONCE' and ev['section_time'] is None:
            freq = 'DAILY'
            bydays, monthday = None, None

        # 确定时间点集合
        if anchors:
            times = [(h, m) for h, m, _ in anchors]
        elif ev['section_time']:
            times = [ev['section_time']]
        else:
            times = [(9, 0)]  # 无时间点章节，默认早上 9 点提醒

        for (h, mi) in times:
            out.append({
                'banks': ev['banks'],
                'activity': ev['activity'],
                'raw_title': ev['raw_title'],
                'section': ev['section'],
                'hour': h,
                'minute': mi,
                'freq': freq,
                'bydays': bydays,
                'monthday': monthday,
                'deadline': deadline,
                'desc': desc,
                'art_date': ev['art_date'],
                'source_url': ev['source_url'],
                'source_title': ev['source_title'],
                'untimed': ev['section_time'] is None and not anchors,
            })
    return out


def dedupe(schedules, today=None):
    """
    跨文章去重：同一银行+活动+时间点+循环规则 只保留最新一篇文章的版本
    （最新文章的描述最全、截止日期最新）。同时丢弃已过期的活动。
    """
    today = today or date.today()
    groups = {}
    for s in schedules:
        # 过期活动直接丢弃
        if s['deadline'] and s['deadline'] < today:
            continue
        key = (tuple(s['banks']), s['activity'], s['hour'], s['minute'])
        groups.setdefault(key, []).append(s)

    # 同一活动可能既被识别成 DAILY 又被识别成 WEEKLY（不同文章措辞不同）。
    # WEEKLY/MONTHLY 更具体，优先级更高；DAILY 最宽泛。
    priority = {'WEEKLY': 0, 'MONTHLY': 1, 'DAILY': 2, 'ONCE': 3}
    out = []
    for key, items in groups.items():
        items.sort(key=lambda s: (priority[s['freq']], -s['art_date'].toordinal()))
        top = dict(items[0])
        if top['freq'] == 'WEEKLY':
            # 合并同一时间点下所有星期（如周二、周四都有场次）
            days = []
            for s in items:
                if s['freq'] == 'WEEKLY':
                    for d in (s['bydays'] or []):
                        if d not in days:
                            days.append(d)
            top['bydays'] = sorted(days, key=WEEKDAY_ABBREV.index)
        out.append(top)

    out.sort(key=lambda s: (s['banks'][0], s['hour'], s['minute'], s['activity']))
    return out


def parse_all(articles, today=None):
    events = []
    for a in articles:
        events.extend(parse_article(a))
    return dedupe(build_schedules(events), today=today)


if __name__ == '__main__':
    import crawler
    arts = crawler.crawl(max_articles=7)
    sch = parse_all(arts)
    print(f"共解析 {len(sch)} 条日程\n")
    from collections import Counter
    c = Counter()
    for s in sch:
        for b in s['banks']:
            c[b] += 1
    for b, n in c.most_common():
        print(f"  {b:8s} {n:4d}")
    print('\n--- 样例（浦发）---')
    for s in sch:
        if '浦发银行' in s['banks']:
            print(f"[{s['hour']:02d}:{s['minute']:02d}] {s['freq']:8s} {s['raw_title'][:40]} | 截止{s['deadline']}")
