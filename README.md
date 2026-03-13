# WhyLoseMoney

一个基于 CLI 的个人支出追踪与分析工具，帮助你了解钱都花到哪里去了。

## 功能特性

- 提供带彩色表格和菜单导航的交互式 TUI
- 支持添加、查看、分析和删除支出
- 支持带断点续传的 CSV 批量导入
- 支持可配置设置（货币、日期格式、每页条数）
- 提供操作审计历史记录
- 支持跨平台运行（macOS、Linux、Windows）

## 安装

### 从 PyPI 安装（推荐）

```bash
pip install whylosemoney
```

### 使用 pipx（隔离环境）

```bash
pipx install whylosemoney
```

### 从源码安装

```bash
git clone https://github.com/tens1x/whylosemoney.git
cd whylosemoney
pip install -e .[dev]
```

## 使用方式

### 交互模式

```bash
whylosemoney
```

启动交互式 TUI，提供菜单导航、分页列表和带颜色的输出。

### CLI 模式

```bash
# Add an expense
whylosemoney add --amount 35.6 --category food --note "lunch" --date 2026-03-11

# List expenses with optional date range
whylosemoney list --from 2026-03-01 --to 2026-03-31

# Analyze spending
whylosemoney analyze --period monthly

# Import from CSV
whylosemoney import --file expenses.csv
whylosemoney import --file expenses.csv --resume

# Delete an expense
whylosemoney delete --id <expense-uuid>
```

### CSV 导入格式

```csv
amount,category,date,note
35.6,food,2026-03-11,lunch
12.0,transport,2026-03-12,metro
```

## 配置

设置保存在 `~/.whylosemoney/config.json`：

| 设置项 | 默认值 | 说明 |
|---------|---------|-------------|
| currency | CNY | 显示货币 |
| date_format | %Y-%m-%d | 日期显示格式 |
| page_size | 20 | 列表视图每页条数 |
| default_category | other | 默认支出分类 |
| custom_categories | [] | 用户自定义分类 |

你可以通过 TUI 的设置菜单交互式修改这些设置，也可以直接手动编辑配置文件。

## 数据存储

- 支出数据：`~/.whylosemoney/data.json`
- 配置文件：`~/.whylosemoney/config.json`
- 审计日志：`~/.whylosemoney/history.jsonl`

## 开发

```bash
pip install -e .[dev]
pytest -v
```

## 许可证

MIT
