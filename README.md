# WhyLoseMoney

IBKR 投资组合分析工具 — 搞清楚你的钱是怎么亏的。

分析你的 Interactive Brokers 交易历史，检测常见亏钱模式（追高、重仓、没止损等），并将交易记录与新闻事件、聊天记录进行对照分析。

## 功能特性

- 导入 IBKR Flex Query XML 交易数据
- 投资概览仪表盘（KPI、累计盈亏曲线、持仓分布）
- 盈亏分析（按股票/月度/持仓周期）
- **亏钱原因检测**：追高买入、频繁交易、仓位集中、没止损、逆势操作
- 事件时间线：K线 + 交易标记 + 新闻 + 聊天记录叠加
- Gemini / 群聊记录导入与 ticker 提取
- Finnhub 新闻关联分析

## 前置要求

- Python 3.9+
- IBKR 账户（Flex Query 功能）

## 安装

```bash
git clone https://github.com/tens1x/whylosemoney.git
cd whylosemoney
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## 使用方式

### 启动仪表盘

```bash
streamlit run src/whylosemoney/app/main.py
```

浏览器自动打开 http://localhost:8501

### 导入数据

1. 在侧边栏上传 IBKR Flex Query XML 文件
2. 点击「解析并预览」确认数据
3. 点击「确认导入数据库」

### 导出 IBKR Flex Query

1. 登录 IBKR 账户管理 → Reports → Flex Queries
2. 创建新的 Activity Flex Query
3. 勾选以下部分：
   - **Trades** — 所有字段
   - **Open Positions** — 所有字段
   - **Cash Transactions** — 所有字段
4. 格式选 XML，日期范围选所需时段
5. 运行并下载 XML 文件

### 导入 Gemini 聊天记录

1. 前往 [Google Takeout](https://takeout.google.com/)
2. 选择 Gemini Apps 数据
3. 导出为 JSON 格式
4. 在侧边栏上传 JSON 文件

也支持纯文本聊天记录（.txt），格式：
```
[2024-01-15 10:30] user: NVDA looks good, AI is the future
[2024-01-15 10:32] user: $AAPL earnings next week
```

### 设置

在「设置」页面配置：
- Finnhub API Key（获取新闻数据，免费注册：https://finnhub.io）
- 检测阈值（追高涨幅%、频繁交易次数、集中度%、止损%）

## 页面说明

| 页面 | 功能 |
|------|------|
| 概览 | KPI 卡片、累计盈亏曲线、按股票盈亏柱状图、当前持仓表 |
| 持仓 | 持仓详情表、仓位分布饼图、集中度预警 |
| 交易 | 可筛选排序的交易历史表、CSV 导出 |
| 盈亏分析 | 盈亏总览 / 持仓周期散点图 / **亏钱原因检测** |
| 事件时间线 | K线图 + 交易标记 + 新闻蓝点 + 聊天橙点 + 叙事分析 |
| 设置 | API Key、检测阈值配置 |

## 开发

```bash
# 运行测试
pytest -v

# 代码结构
src/whylosemoney/
├── models.py          # SQLAlchemy ORM 模型
├── db.py              # 数据库操作
├── ibkr/              # IBKR 数据解析
├── market/            # 市场数据（yfinance + Finnhub）
├── analysis/          # 盈亏分析 + 亏钱原因检测
├── chat/              # 聊天记录解析
└── app/               # Streamlit 仪表盘
```

## 许可证

MIT
