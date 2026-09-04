#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ICS 产出校验：结构配对、行长限制、转义完整性、时间合法性。"""
import os
import re
import sys
from datetime import datetime

MAX_BYTES = 75


def check_file(path):
    errors = []
    # newline='' 保留原始 CRLF，否则 Python 会把 \r\n 统一成 \n
    with open(path, encoding='utf-8', newline='') as f:
        raw = f.read()

    # 1) 行结束符统一 CRLF
    lines = raw.split('\r\n')
    if raw.replace('\r\n', '').strip() and '\r\n' not in raw:
        errors.append('未使用 CRLF 行结束符')

    # 2) 行长
    for i, ln in enumerate(lines, 1):
        if len(ln.encode('utf-8')) > MAX_BYTES:
            errors.append(f'第 {i} 行超长：{len(ln.encode("utf-8"))} 字节')

    # 3) 还原折叠后，检查转义序列没有被拆坏
    #    注意：. 会匹配 \r，必须先规范化换行，否则捕获值会带上尾随 \r
    unfolded = re.sub(r'\r\n[ \t]', '', raw).replace('\r\n', '\n')
    bad = re.findall(r'\\(?!n|,|;|\\)', unfolded)
    if bad:
        errors.append(f'存在非法转义：{set(bad)}')

    # 4) 结构配对
    for tag in ('VCALENDAR', 'VEVENT', 'VALARM'):
        b = len(re.findall(rf'^BEGIN:{tag}$', unfolded, re.M))
        e = len(re.findall(rf'^END:{tag}$', unfolded, re.M))
        if b != e:
            errors.append(f'{tag} 标签不配对：BEGIN {b} / END {e}')

    # 5) 必需字段
    uids = re.findall(r'^UID:(.+)$', unfolded, re.M)
    if len(uids) != len(set(uids)):
        errors.append('存在重复 UID')
    for m in re.finditer(r'^DTSTART[^:]*:(.+)$', unfolded, re.M):
        v = m.group(1)
        try:
            if 'VALUE=DATE' in m.group(0):
                datetime.strptime(v, '%Y%m%d')
            else:
                datetime.strptime(v, '%Y%m%dT%H%M%SZ')
        except ValueError:
            errors.append(f'DTSTART 格式非法：{v}')

    # 6) UNTIL 必须晚于 DTSTART
    for blk in re.findall(r'BEGIN:VEVENT\r\n(.*?)END:VEVENT', raw, re.S):
        ds = re.search(r'^DTSTART:(\d{8}T\d{6}Z)', blk, re.M)
        un = re.search(r'UNTIL=(\d{8}T\d{6}Z)', blk)
        if ds and un and un.group(1) < ds.group(1):
            errors.append(f'UNTIL 早于 DTSTART：{un.group(1)} < {ds.group(1)}')

    n_events = len(re.findall(r'^BEGIN:VEVENT$', unfolded, re.M))
    return n_events, errors


def main(d):
    if not os.path.isdir(d):
        print(f'目录不存在：{d}')
        return 1
    total, failed = 0, 0
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.ics'):
            continue
        n, errs = check_file(os.path.join(d, fn))
        total += n
        if errs:
            failed += 1
            print(f'[FAIL] {fn}')
            for e in errs[:5]:
                print(f'       - {e}')
        else:
            print(f'[ OK ] {fn:<16s} {n:3d} 个事件')
    print(f'\n合计 {total} 个事件，{failed} 个文件有问题')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'build/ics'))
