#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结构化活动 -> 每家银行一个 ICS 日历文件

设计要点：
- 仅依赖 Python3 标准库，服务器无需 pip install
- 时区固定 Asia/Shanghai（UTC+8，中国无夏令时），事件以 UTC 输出，无需 VTIMEZONE
- DAILY/WEEKLY/MONTHLY 用 RRULE 展开到活动截止日；ONCE 转成跨天全天事件
- UID 稳定：同一活动更新后 UID 不变，Google 日历会就地更新而非重复创建
"""
import os
import re
import hashlib
from datetime import date, datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
UTC = timezone.utc

# 标准银行名 -> (文件名 slug, 日历名)
BANK_SLUG = {
    '工商银行': ('icbc', '工商银行'),
    '农业银行': ('abc', '农业银行'),
    '中国银行': ('boc', '中国银行'),
    '建设银行': ('ccb', '建设银行'),
    '交通银行': ('bocom', '交通银行'),
    '邮储银行': ('psbc', '邮储银行'),
    '浦发银行': ('spdb', '浦发银行'),
    '光大银行': ('ceb', '光大银行'),
    '广发银行': ('cgb', '广发银行'),
    '兴业银行': ('cib', '兴业银行'),
    '华夏银行': ('hxb', '华夏银行'),
    '中信银行': ('citic', '中信银行'),
    '民生银行': ('cmbc', '民生银行'),
    '招商银行': ('cmb', '招商银行'),
    '平安银行': ('pingan', '平安银行'),
    '浙商银行': ('czbank', '浙商银行'),
    '北京银行': ('bob', '北京银行'),
    '上海银行': ('bos', '上海银行'),
    '银联云闪付': ('unionpay', '银联云闪付'),
    '其他优惠': ('other', '其他优惠'),
}

WEEKDAY_ABBREV = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
REMIND_MINUTES = 10        # 提前 10 分钟提醒
DEFAULT_SPAN_DAYS = 30     # 无截止日期时，默认只铺 30 天
DESC_MAX = 900             # 描述截断长度


def esc(text):
    """ICS 文本转义。"""
    if text is None:
        return ''
    t = str(text)
    t = t.replace('\\', '\\\\')
    t = t.replace(';', '\\;')
    t = t.replace(',', '\\,')
    t = t.replace('\r\n', '\n').replace('\r', '\n')
    t = t.replace('\n', '\\n')
    return t


def fold(line):
    """
    RFC5545 行折叠：单行不超过 75 字节（UTF-8），续行以空格开头。
    关键：转义序列（\\n、\\, 、\\; 、\\\\）是 2 个字符的原子，
    不能从中间断开，否则解析器会把 "\\" 和 "n" 拼不回去。
    """
    if len(line.encode('utf-8')) <= 73:
        return line
    # 切分成原子：转义序列整体，或单个字符
    atoms, i = [], 0
    while i < len(line):
        if line[i] == '\\' and i + 1 < len(line):
            atoms.append(line[i:i + 2])
            i += 2
        else:
            atoms.append(line[i])
            i += 1

    parts, cur = [], ''
    for a in atoms:
        if len(cur.encode('utf-8')) + len(a.encode('utf-8')) > 73:
            parts.append(cur)
            cur = ' ' + a
        else:
            cur += a
    if cur:
        parts.append(cur)
    return '\r\n'.join(parts)


def to_utc_naive(d, hour, minute):
    """本地日期+时间 -> UTC datetime。"""
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=CST).astimezone(UTC)


def fmt_dt(dt):
    return dt.strftime('%Y%m%dT%H%M%SZ')


def fmt_date(d):
    return d.strftime('%Y%m%d')


def next_weekday(start, abbrev):
    """从 start 起（含当天）找到下一个匹配的星期。"""
    target = WEEKDAY_ABBREV.index(abbrev)
    delta = (target - start.weekday()) % 7
    return start + timedelta(days=delta)


def next_monthday(start, day):
    """从 start 起找到下一个 >= start 的每月 day 日。"""
    y, m = start.year, start.month
    try:
        cand = date(y, m, day)
    except ValueError:
        cand = None
    if cand and cand >= start:
        return cand
    m += 1
    if m > 12:
        y, m = y + 1, 1
    while True:
        try:
            return date(y, m, day)
        except ValueError:
            m += 1
            if m > 12:
                y, m = y + 1, 1


def make_uid(bank, s):
    # banks 也要进 hash：同一活动可能既有单银行版本又有多银行版本
    # （如「中信x小米分期」与「中信、民生、浦发x小米分期」），否则 UID 会撞车
    banks = ','.join(s['banks'])
    raw = f"{bank}|{banks}|{s['activity']}|{s['hour']:02d}:{s['minute']:02d}|{s['freq']}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest() + '@zrfan-card-guide'


def build_event(bank, s, today):
    """生成单个 VEVENT 文本块。"""
    uid = make_uid(bank, s)
    deadline = s['deadline']
    lines = ['BEGIN:VEVENT', f'UID:{uid}']

    # 描述：活动详情 + 截止 + 来源
    desc = s['desc'].strip()
    if len(desc) > DESC_MAX:
        desc = desc[:DESC_MAX] + '…'
    tail = []
    if deadline:
        tail.append(f'活动截止：{deadline.strftime("%Y-%m-%d")}')
    tail.append(f'来源：{s["source_title"]} {s["source_url"]}')
    full_desc = desc + ('\n\n' + '\n'.join(tail) if desc else '\n'.join(tail))

    freq = s['freq']

    if freq == 'ONCE':
        # 活动期内随时可参与 -> 全天事件，铺到截止日，不设闹钟
        start_d = max(s['art_date'], today)
        end_d = deadline or (start_d + timedelta(days=DEFAULT_SPAN_DAYS))
        if end_d <= start_d:
            end_d = start_d + timedelta(days=1)
        summary = f'{bank}｜{s["activity"]}（期内可参与）'
        lines += [
            f'DTSTART;VALUE=DATE:{fmt_date(start_d)}',
            f'DTEND;VALUE=DATE:{fmt_date(end_d + timedelta(days=1))}',
            f'SUMMARY:{esc(summary)}',
            f'DESCRIPTION:{esc(full_desc)}',
            'TRANSP:TRANSPARENT',
        ]
    else:
        # 有明确时间点的循环事件
        start_d = today if today > s['art_date'] else s['art_date']
        if freq == 'WEEKLY' and s['bydays']:
            start_d = next_weekday(start_d, s['bydays'][0])
        elif freq == 'MONTHLY' and s['monthday']:
            start_d = next_monthday(start_d, s['monthday'])

        dtstart = to_utc_naive(start_d, s['hour'], s['minute'])
        dtend = dtstart + timedelta(minutes=30)

        rrule = [f'FREQ={freq}']
        if freq == 'WEEKLY' and s['bydays']:
            rrule.append('BYDAY=' + ','.join(s['bydays']))
        if freq == 'MONTHLY' and s['monthday']:
            rrule.append(f'BYMONTHDAY={s["monthday"]}')

        end_d = deadline or (start_d + timedelta(days=DEFAULT_SPAN_DAYS))
        # UNTIL 取活动截止日当天 23:59:59（UTC+8）
        until = datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, tzinfo=CST).astimezone(UTC)
        if until < dtstart:  # 截止日早于首次触发，说明该活动已不可参与
            return None
        rrule.append('UNTIL=' + fmt_dt(until))

        hhmm = f'{s["hour"]:02d}:{s["minute"]:02d}'
        wd_note = ''
        if freq == 'WEEKLY' and s['bydays']:
            cn = {'MO': '周一', 'TU': '周二', 'WE': '周三', 'TH': '周四',
                  'FR': '周五', 'SA': '周六', 'SU': '周日'}
            wd_note = ''.join(cn.get(d, d) for d in s['bydays'])
        elif freq == 'MONTHLY':
            wd_note = f'每月{s["monthday"]}日'
        elif freq == 'DAILY':
            wd_note = '每日'

        summary = f'{bank}｜{hhmm} {s["activity"]}'
        if wd_note:
            summary = f'[{wd_note}] ' + summary

        lines += [
            f'DTSTART:{fmt_dt(dtstart)}',
            f'DTEND:{fmt_dt(dtend)}',
            'RRULE:' + ';'.join(rrule),
            f'SUMMARY:{esc(summary)}',
            f'DESCRIPTION:{esc(full_desc)}',
            'TRANSP:OPAQUE',
            # 提前 10 分钟提醒
            'BEGIN:VALARM',
            'ACTION:DISPLAY',
            f'TRIGGER:-PT{REMIND_MINUTES}M',
            f'DESCRIPTION:{esc(summary)}',
            'END:VALARM',
        ]

    lines += [
        f'URL:{s["source_url"]}',
        f'CATEGORIES:{esc(bank)}',
        'END:VEVENT',
    ]
    return '\r\n'.join(fold(x) for x in lines)


def build_calendar(events, cal_name, cal_desc):
    now = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    head = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//zrfan card guide//ZH-CN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{esc(cal_name)}',
        f'X-WR-CALDESC:{esc(cal_desc)}',
        'X-WR-TIMEZONE:Asia/Shanghai',
        'REFRESH-INTERVAL;VALUE=DURATION:PT12H',
    ]
    # head 里 X-WR-CALDESC 也可能超长，同样需要折叠
    return '\r\n'.join([fold(x) for x in head] + events + ['END:VCALENDAR']) + '\r\n'


def generate(schedules, out_dir, today=None):
    """按银行分组生成 ICS 文件，返回 [{bank, slug, file, count}]。"""
    today = today or date.today()
    os.makedirs(out_dir, exist_ok=True)

    by_bank = {}
    for s in schedules:
        for b in s['banks']:
            by_bank.setdefault(b, []).append(s)

    result = []
    for bank, items in by_bank.items():
        slug, name = BANK_SLUG.get(bank, ('other', bank))
        items = sorted(items, key=lambda x: (x['hour'], x['minute'], x['activity']))
        vevents = []
        for s in items:
            ev = build_event(bank, s, today)
            if ev:
                vevents.append(ev)
        if not vevents:
            continue
        n_timed = sum(1 for s in items if s['freq'] != 'ONCE')
        cal_name = f'刷卡指南·{name}'
        cal_desc = (f'{name}信用卡/借记卡优惠提醒，共 {len(vevents)} 项'
                    f'（{n_timed} 项定点提醒）。数据来源 zrfan.com 每日刷卡指南')
        content = build_calendar(vevents, cal_name, cal_desc)
        path = os.path.join(out_dir, f'{slug}.ics')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        result.append({
            'bank': bank, 'slug': slug, 'file': path,
            'count': len(vevents), 'timed': n_timed,
            'cal_name': cal_name,
        })

    # 合并日历：每个活动只按其主银行生成一次，方便一次性导入
    seen, all_ve = set(), []
    for s in schedules:
        key = (tuple(s['banks']), s['activity'], s['hour'], s['minute'])
        if key in seen:
            continue
        seen.add(key)
        ev = build_event(s['banks'][0], s, today)
        if ev:
            all_ve.append(ev)
    if all_ve:
        content = build_calendar(
            all_ve, '刷卡指南·全部银行',
            f'全部银行优惠提醒合并版，共 {len(all_ve)} 项。数据来源 zrfan.com 每日刷卡指南')
        with open(os.path.join(out_dir, 'all.ics'), 'w', encoding='utf-8', newline='') as f:
            f.write(content)

    result.sort(key=lambda x: -x['count'])
    return result


if __name__ == '__main__':
    import crawler
    import parser as ps
    arts = crawler.crawl(max_articles=7)
    sch = ps.parse_all(arts)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build', 'ics')
    res = generate(sch, out)
    print(f'生成 {len(res)} 个日历：')
    for r in res:
        print(f"  {r['bank']:8s} {r['slug']:10s} {r['count']:3d} 项（定点 {r['timed']:3d}）")
