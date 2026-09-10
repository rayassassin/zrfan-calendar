# 刷卡优惠日历 · 爬虫与订阅

自动抓取 [真人范儿 · 每日刷卡指南](https://www.zrfan.com/category/zhinan/)，
把文章里散落的银行优惠解析成结构化日程，**按银行拆成独立日历**，
以具体时间点提醒（默认提前 10 分钟），供 Google 日历订阅。

- 仅依赖 **Python3 标准库 + curl**，服务器无需 `pip install`
- 每家银行一个 `.ics`，可单独订阅、单独开关
- UID 稳定，内容更新后日历就地刷新，不会重复创建

---

## 快速开始

```bash
python3 main.py              # 抓最近 7 篇 -> 生成 build/
python3 main.py -n 14        # 抓最近 14 篇
python3 main.py --force      # 忽略缓存重新抓取
python3 main.py -r 30        # 提前 30 分钟提醒
python3 validate.py build/ics  # 校验产出
```

产物在 `build/`：

```
build/
├── index.html        # 预览页：按银行浏览 + 一键订阅按钮
├── meta.json         # 本次生成的元信息
└── ics/
    ├── spdb.ics      # 浦发银行
    ├── icbc.ics      # 工商银行
    ├── ...
    └── all.ics       # 全部合并版
```

银行与文件名对照：

| 文件 | 银行 | 文件 | 银行 |
|---|---|---|---|
| `icbc.ics` | 工商银行 | `spdb.ics` | 浦发银行 |
| `abc.ics` | 农业银行 | `ceb.ics` | 光大银行 |
| `boc.ics` | 中国银行 | `cgb.ics` | 广发银行 |
| `ccb.ics` | 建设银行 | `cib.ics` | 兴业银行 |
| `bocom.ics` | 交通银行 | `hxb.ics` | 华夏银行 |
| `psbc.ics` | 邮储银行 | `citic.ics` | 中信银行 |
| `cmbc.ics` | 民生银行 | `cmb.ics` | 招商银行 |
| `pingan.ics` | 平安银行 | `czbank.ics` | 浙商银行 |
| `bob.ics` | 北京银行 | `bos.ics` | 上海银行 |
| `unionpay.ics` | 银联云闪付 | `other.ics` | 其他优惠 |

---

## 解析逻辑

文章按时间分节（`0点开始活动` / `9点30分开始活动` / `当日必做` / `小活动` …），
条目统一写成 `XX银行x活动名：`。脚本据此提取：

1. **银行**：从 `x` 前半段识别，支持简称（`建行生活APP` → 建设银行）和多银行条目
   （`中信、民生、浦发、农业银行x小米之家分期` 会同时进 4 个日历）
2. **时间**：优先取描述里的锚点（`每日9点30分起`、`周五10点起`），
   没有则回落到所属章节的时间
3. **循环**：`每日` → DAILY，`每周五` / `周四至周六` → WEEKLY，
   `每月15日` → MONTHLY，都不匹配则按「活动期内随时可参与」处理成全天事件
4. **截止**：识别 `9月30日截止`、`续期至12月31日截止` 等，作为 RRULE 的 UNTIL

跨文章去重：同一银行 + 活动 + 时间点，只保留**最新一篇文章**的版本
（描述最全、截止日期最新）。同一活动若在某篇里被识别成 `每日`、
在另一篇里是 `每周二`，取更具体的后者。已过截止日的活动直接丢弃。

---

## 部署到服务器

```bash
bash deploy.sh /opt/zrfan-calendar 8080
#               安装目录         端口
```

脚本会：拷贝代码 → 试跑一次 → 用 systemd（或 nohup）启动静态服务 →
写入 crontab（0 点主更新 + 6 点兜底）。

### Google 日历必须走 HTTPS

**http 链接 Google 日历会拒绝。** 三种解法任选：

**A. 服务器有域名** —— 用 certbot + nginx（推荐）

```bash
certbot --nginx -d calendar.yourdomain.com
cp nginx.conf.example /etc/nginx/conf.d/zrfan-calendar.conf
# 改里面的域名和证书路径，然后 nginx -t && nginx -s reload
```

**B. 只有裸 IP，没有域名** —— 服务器抓取 + GitHub Pages 托管（本项目实际采用）

zrfan.com 屏蔽了境外访问，GitHub Actions 的美国节点连不上它
（`curl: (7) Failed to connect`，TCP 都建立不了，`-k` 也救不了）。
所以抓取放在国内服务器做，再把结果推到 GitHub Pages 托管（自带 HTTPS）：

```
https://<你的用户名>.github.io/zrfan-calendar/ics/spdb.ics
```

链路：`crontab` 每天 **0 点**跑 `update_and_push.sh`（主更新）
→ `main.py` 抓取生成 `build/` → `push_pages.sh` 用 **Deploy Key** 推到 `gh-pages` 分支
→ GitHub Pages 自动重新部署。

**6 点兜底**：zrfan.com 当天指南的发布时间不固定，0 点时可能还没上线。
`catchup_if_missed.sh` 会在 6 点检查 `state/latest_article_date`——若最新文章仍不是当天，
就用 `--force` 绕过缓存强制补抓一次；已是当天则跳过，不重复抓。

- 服务器推送用**仓库 Deploy Key**（`/root/.ssh/zrfan_deploy`，仅授权本仓库、可写），
  服务器上不存放 GitHub 账号 token
- 曾经的 Actions 抓取 workflow 已移除（美国节点连不上 zrfan.com，无意义）

**C. 只想本地用** —— 不下发订阅，直接导入

Google 日历 → 设置 → 导入和导出 → 从计算机导入 → 选 `build/ics/*.ics`。
缺点是不会自动更新，需要手动重新导入。

### 订阅步骤（方案 A / B）

1. 打开预览页 `https://你的域名/`
2. 找到想要的银行，点「订阅到 Google 日历」
3. 或手动：Google 日历 → 其他日历 → `+` → 通过网址添加 →
   粘贴 `https://你的域名/ics/spdb.ics`

> `.ics` 必须返回 `Content-Type: text/calendar`，否则 Google 会静默失败。
> `serve.py` 和 `nginx.conf.example` 都已处理。

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `crawler.py` | 抓列表页与正文，本地缓存 6 小时，请求间隔 1 秒 |
| `parser.py` | 正文 → 结构化活动（银行 / 时间 / 循环 / 截止）+ 去重 |
| `ics_gen.py` | 活动 → 每家银行一个 ICS，含 VALARM 提醒 |
| `page.py` | 生成预览页 |
| `validate.py` | 校验 ICS 结构、行长、转义、UID 唯一性 |
| `serve.py` | 静态服务，修正 `.ics` 的 MIME 类型 |
| `main.py` | 串联以上全部 |
| `push_pages.sh` | 把 `build/` 推到 `gh-pages` 分支（Deploy Key 认证） |
| `update_and_push.sh` | 每日定时入口：抓取 → 推送，由 crontab 调用 |
| `catchup_if_missed.sh` | 6 点兜底：0 点没抓到当天指南时强制补抓 |
| `.github/workflows/monitor.yml` | 数据新鲜度监控 + 服务器诊断，过期自动建 issue 告警 |

## 可用性保障

### 数据新鲜度监控（GitHub Actions）

`monitor.yml` 每天 **01:00 UTC（= 09:00 北京时间）** 检查一次
`https://rayassassin.github.io/zrfan-calendar/meta.json` 里最新文章的日期：

- 最新日期 **早于昨天** → 判定更新失效：自动建 issue 并 `@` 提醒，同时让
  workflow 失败（GitHub 会邮件通知仓库所有者）
- 同时输出服务器诊断：ICMP / SSH 2525 / HTTP 8080 / zrfan.com 可达性，
  直接写进 issue 正文，省去逐项排查

手动验证告警通道：Actions → monitor → Run workflow → 勾选 `test_alert`。

> 注意：Actions 的美国节点**连不上 zrfan.com**（已验证两次），
> 所以监控只负责「发现问题 + 告警」，抓取仍必须由国内服务器完成。

### 服务器侧加固

`update_and_push.sh` 每次运行前会：

- 轮转 `logs/cron.log`（超 5MB 只留最后 2000 行）
- 清理 `raw/` 缓存（只留最近 30 篇）
- 磁盘使用率 ≥ 90% 时打印告警并列出占用最大的目录
- `main.py` 非 0 退出时**中止**，不再推送半成品

## 故障排查

服务器整机卡死时（SSH 能连但无 banner、HTTP 8080 无响应、cron 不执行）：

1. 登录**云厂商控制台**，用 VNC/远程连接（不依赖 SSH）登录，或直接强制重启实例
2. 重启后确认：`systemctl status cron`、`crontab -l`、`df -h`
3. 手动跑一次：`bash /opt/zrfan-calendar/update_and_push.sh`
4. 看日志：`tail -50 /opt/zrfan-calendar/logs/cron.log`

应急刷新（服务器不可用但本机能访问源站时）：本地跑
`python3 main.py -n 7 --force`，再把 `build/` 推到 `gh-pages` 分支。

---

## 调参

| 想改什么 | 改哪里 |
|---|---|
| 提醒提前量 | `main.py -r 分钟`，或 `ics_gen.REMIND_MINUTES` |
| 银行名 / 别名 | `parser.py` 的 `BANK_ALIASES` |
| 日历文件名 | `ics_gen.py` 的 `BANK_SLUG` |
| 抓取篇数 | `main.py -n`（默认 7） |
| 循环规则关键词 | `parser.py` 的 `DAILY_RE` / `WEEKLY_RE` / `MONTHLY_RE` |

---

## 注意

- 抓取频率请克制，`crawler.py` 已内置 1 秒间隔与 6 小时缓存
- 名额有限的抢购类活动（0 点、10 点场次）建议提前开好 APP，10 分钟提醒只是保底
- 日历内容来自第三方站点，活动规则、名额、截止时间**以银行官方页面为准**
