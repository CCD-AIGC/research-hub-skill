# 来源、配置与复用

## 国内

使用随包附带的 last30days-cn v4.0.0-cn 运行时，原始许可与来源说明见 `engines/cn/LICENSE` 和 `references/engines.json`。尝试微博、小红书、B站、知乎、抖音、微信公众号、百度、头条。

已有配置通常来自 `~/.config/last30days-cn/.env` 或进程环境。引擎可用的可选设置包括 WEIBO_COOKIE、ZHIHU_COOKIE、BILIBILI_COOKIE、TIKHUB_API_KEY、WECHAT_API_KEY、BAIDU_API_KEY、XIAOHONGSHU_API_BASE。小红书本地服务和公开网页兜底是否可用，以本轮返回为准。未经用户要求，不运行登录或创建配置。不要在回复、报告或公开仓库中放密钥/Cookie。

## 海外

使用 mvanhorn/last30days-skill 3.31.0 的固定代码快照；详细提交记录见 `references/engines.json`，MIT 许可见 `engines/global/LICENSE`。查询 Reddit、Hacker News、GitHub、YouTube、X 等来源，可用范围由引擎诊断决定。Hacker News 与公共 GitHub 通道无需 API Key；Reddit 可能受限；YouTube 使用可选 yt-dlp。

已有配置通常来自 `~/.config/last30days/.env` 或进程环境，配置服务可能按用量收费。统一入口不自行开通付费来源。X、TikTok、Instagram 等按已配置后端运行；统一入口默认不提取浏览器 Cookie，也不替用户完成第三方注册。

## RSS

内置 14 个原站订阅。JSON 格式如下；也接受标准 OPML。`--feeds` 替换内置清单。

```json
[
  {"name": "Your source", "url": "https://example.com/feed.xml", "group": "创业与市场"}
]
```

每源最多读取 3 MB，默认 12 秒超时、6 路并发；quick/default/deep 最多保留每源 8/15/30 条匹配记录。只读 HTTP(S)，不处理嵌入凭据的链接、XML DTD 或实体声明。数据中的 HTML 只取文本。

匹配标题与摘要中的 `--rss-query`，多个词组是 OR；英文按词边界匹配，中文按明确词组匹配。发布日期优先，其次仅有更新时间会标记 updated-only。日期未知条目可保留，但不能支撑近期性断言。订阅当前返回的条目数不等于窗口内所有发文，不能据此下“没有讨论”的结论。

## 配置隔离、超时和升级

`--public-only` 忽略已保存的引擎配置和环境 API Key，并关闭浏览器提取，适合安装验收；底层平台仍可能返回风控或零结果。三路运行相互隔离，单路超时只记录失败并保留其他结果。原始日志只放运行目录，不打包发布。

默认使用随包引擎。明确需要切换外部版本时，可设置 RESEARCH_HUB_CN_ENGINE 或 RESEARCH_HUB_GLOBAL_ENGINE，值为 skill 根目录或 last30days.py 的绝对路径。切换后要重新验收 JSON 兼容性。海外运行时要求 Python 3.12+。原有独立技能不受本入口安装或升级影响。
