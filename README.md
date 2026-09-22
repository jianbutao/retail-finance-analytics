# 零售交易数据驱动的经营分析与风险信号识别

基于零售历史交易记录，构建从数据清洗、SQL对账、
经营分析到预测评估、规则信号与AI摘要的完整分析流程，
并通过Streamlit看板展示。

本项目用于学习、作品展示与面试演示，不是实时经营报告、
会计核算系统或经过业务验证的风险评级模型。

## 目录

- `src/retail_finance`：正式核心计算；函数不隐式保存数据或访问数据库。
- `config/project.json`：固定输入批次、历史归档、观察窗口；路径相对项目根目录。
- `notebooks/00`至`06`：研究过程与解释；旧探索结果保留，不作为应用运行入口。
- `scripts/validate_stage1.py`：不依赖Notebook内核的离线验收；不访问数据库。
- `scripts/validate_postgresql.py`、`sql`：原SQL对账流程，数据库导入不要重复执行。
- `tests`：小样本边界和时间泄漏测试。
- `docs/metric_dictionary.md`：唯一正式指标口径。
- `backups`：整理前本地副本，不提交Git。

原客户归档的`customer_segments.png`内容错误（实际是月度图），为保护历史证据未覆盖。使用配置中的`corrected_customer_plot`。03 Notebook的图对象引用已修复。旧Notebook中的分析代码作为历史实验保留；新功能以`src/retail_finance`为正式入口，暂未将所有探索单元格重写为模块调用。

## 本地运行（PowerShell，项目根目录）

已存在的项目虚拟环境不需要重新安装：

```powershell
& ".\.venv\Scripts\python.exe" -B -m unittest discover -s tests -v
& ".\.venv\Scripts\python.exe" -B scripts/validate_stage1.py
# 较慢：从原始Excel重新清洗，在内存中逐字段与原归档比较
& ".\.venv\Scripts\python.exe" -B scripts/validate_stage1.py --raw
```

脚本自身按文件位置定位项目，运行目录可改变。`--raw`不覆盖原始数据及清洗归档。验收结果写入新的`reports/stage1_validation`目录；成功标记仅在验证结束后生成。

新环境建议Python 3.13，使用`requirements.txt`安装已验证的直接依赖。当前没有在第二台电脑/全新环境安装验证；直接依赖清单不是完整锁文件。

## 数据与可复现边界

数据来源：UCI Online Retail II（https://archive.ics.uci.edu/dataset/502/online+retail+ii）。本地源文件为`data/raw/online_retail_II.xlsx`。
全期交易分析覆盖2009年12月至2011年12月，
最后一个月记录截至12月9日。

主要模块使用不同窗口：

- 经营与商品分析：历史全期。
- RFM：2010-12-01至2011-12-01，不含结束日。
- 预测测试：2011-09-05至2011-11-27，共12周。

不同窗口的结果不能混作同一时点的实时判断。

## 技术架构

原始Excel
→ Python清洗与分类
→ Parquet分析数据
→ PostgreSQL导入与对账
→ 经营分析、RFM、预测与规则信号
→ 归档结果和证据
→ Streamlit看板及人工对话生成的AI摘要

看板展示已归档结果，不在页面刷新时重新清洗或训练模型。

主要技术：
Python、pandas、NumPy、PostgreSQL、scikit-learn、
Matplotlib、Streamlit。


## 已实现功能

- 经营概况及月度交易趋势
- 商品贡献与客户金额集中分析
- RFM客户分群
- 按时间划分的预测实验
- 月度观察信号及触发规则解释
- 大额冲销案例敏感性分析
- 数据质量提示
- 带证据编号的预生成AI经营摘要

## 数据清洗与验证

- 识别并处理跨工作表重叠记录，保留表内重复记录。
- 区分商品正向交易与取消或冲销记录。
- 保留缺失客户编号交易的整体金额贡献。
- 校验清洗成果保存与重新读取的一致性。
- 对数据库与Python分析结果进行对账。
- SQL验证归档结果：306项检查，0项失败。

代码测试命令：

```powershell
python -m unittest discover -s tests -v
```

## 主要指标口径

| 指标 | 定义与边界 |
|---|---|
| 商品正向交易金额 | 按项目商品及正向交易分类规则汇总 |
| 商品取消金额 | 按取消或冲销规则汇总的金额绝对值 |
| 商品交易净额 | 正向金额减取消金额 |
| 取消金额占比 | 取消金额除以正向金额，不等于已证实的退款率 |
| 已识别购买客户 | 有客户编号且符合正向购买条件的去重客户 |
| RFM | 最近购买间隔、正向订单频次和交易金额特征 |

交易金额不是会计确认收入、利润或到账现金流。
详细口径见docs/metric_dictionary.md。

## 预测实验

采用按时间顺序划分的训练、验证与测试集，
比较上周金额、前四周平均和岭回归。

前四周平均由验证集比较选定。
测试采用逐周更新历史信息、预测下一周的方式。

| 测试指标 | 结果 |
|---|---:|
| MAE | 50,992.56 GBP |
| WAPE | 18.42% |
| 平均预测偏差 | -36,721.22 GBP |

平均偏差为负，表示平均低估。
WAPE不能转换为准确率。
已查看的测试集不再用于调参，历史表现不保证未来效果。

## AI摘要与追溯

当前采用人工对话生成方式，不依赖在线模型API。

保存内容包括：
- 生成时使用的要求与证据；
- 摘要正文；
- 生成与复核记录；
- 文件哈希。

证据编号用于追溯事实来源。
哈希用于识别文件变化，不证明摘要内容正确。
人工复核状态以生成记录为准。

## 本地运行

适用于已具备项目依赖和归档成果的环境：

```powershell
Set-Location -LiteralPath 'D:\Retail-finance'
& '.\.venv\Scripts\python.exe' -m streamlit run app.py
```

页面依赖config/project.json指定的本地数据与报告。
仅下载代码尚不代表可以启动：演示数据交付方案和
干净环境验证完成后，将补充首次安装与启动步骤。

## 项目限制

- 单个零售商的历史样本，不能直接推广到所有企业。
- 商品分类存在不确定性。
- 无记录不能自动解释为零销售或停业。
- 缺失客户编号影响客户结构解释。
- 取消未逐笔匹配原销售，无法证明付款、退款或取消原因。
- 规则阈值属于项目设定，未进行季节性调整。
- 分群使用金额指标，高贡献分群不是独立预测验证。
- AI摘要需要人工复核。
- 不输出综合企业风险分数。

## English Summary

This project builds an auditable retail analytics workflow covering
data cleaning, PostgreSQL reconciliation, customer segmentation,
one-week-ahead forecasting, rule-based review signals, and an
evidence-grounded AI summary presented through Streamlit.

A four-week moving average was selected using validation data.
Its test WAPE was 18.42%. Results describe historical transactions,
not profit, cash flow, confirmed customer churn, or a validated
enterprise risk rating.

[下载演示包](https://github.com/jianbutao/retail-finance-analytics/releases/download/v1.0.0/retail-finance-demo-v1.zip)
解压后按照包内README运行。
演示包包含必要归档成果；仅克隆源码仓库不能直接加载这些数据。
