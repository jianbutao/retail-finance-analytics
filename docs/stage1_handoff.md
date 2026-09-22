# 第一阶段交接：工程整理与回归验证
> 本文为第一阶段的历史交接记录，不代表当前完成状态。
> 最新功能与运行状态请参阅README.md和ENVIRONMENT_CHECK.md。

## 本次实际完成

- 已确认06 Notebook落盘，整理前的notebooks/scripts/sql完整复制到`backups/stage1_20260918`。
- 新增固定版本配置和指标字典；模块路径基于文件位置，不依赖当前工作目录。
- 抽取清洗、经营指标、客户/商品结构、RFM、预测、评估和独立图函数。
- 修复03 Notebook在创建客户图前就捕获旧fig的问题。保留历史错误图片，另外生成正确图片。
- 删除05 Notebook一个完全重复的展示单元格；01探索Notebook历史重复保留，不作为正式应用入口。
- 06改为固定归档，清除过期输出，缩短打印；全部三个代码单元格在独立进程中执行通过。仅准备证据与提示词，不调用模型。
- 01_database_setup.sql补齐schema初始化；未在数据库执行，也未重复导入。
- 新增README、直接依赖清单、.gitignore。未初始化Git或上传任何文件。

## 验收证据

- `python -B -m unittest discover -s tests -v`：14项通过。
- `scripts/validate_stage1.py --raw`：8组通过。最终报告：
  `reports/stage1_validation/20260918T115715_932402Z/summary.json`。
- 从原Excel重建；保留行和被排除行按`source_sheet + source_excel_row`对齐，全部字段与历史Parquet严格数值比较。忽略归档前后pandas存储类型差异，不忽略字段值。
- 对经营指标、商品结构、客户TopN金额、RFM全部字段与分群、周度数据、验证/测试逐周预测及评估指标进行归档对比。浮点汇总容差绝对值1e-7 GBP，相对值1e-12；不是把结果四舍五入后再比较。
- 14项小样本测试覆盖跨表次数不一致、表内重复保留、特殊交易、三位单价、缺失周、目标周及未来数据泄漏、空/零分母/错位评估、RFM边界及分位点重合。
- 新的客户分群图已打开检查；六组标签、人数与净额一致。
- 所有7个Notebook代码单元格完成Python语法检查。这不等于全部Notebook已重新执行；02/03/05的核心结果由独立脚本重算验证。

## 操作位置、目的和知识

| 位置 | 操作 | 目的 | 专业知识 |
|---|---|---|---|
| `config/project.json` | 阅读固定批次与窗口，不随意改历史配置 | 保证同一输入可追溯 | 数据血缘、版本管理 |
| `docs/metric_dictionary.md` | 核对金额、客户、取消比例、窗口 | 防止看板和报告口径漂移 | 指标定义、分母、会计含义边界 |
| `src/retail_finance` | 阅读输入输出明确的函数 | 让看板和脚本复用，不依赖Notebook内存 | 模块化、职责分离 |
| VS Code PowerShell | 执行下方测试命令 | 检查改动是否破坏规则 | 单元测试、回归测试 |
| `reports/stage1_validation` | 查看JSON报告和正确分群图 | 检查真实结果而非仅看程序无报错 | 可审计性、图表QA |

从任意目录执行（当前电脑）：

```powershell
& "D:\Retail-finance\.venv\Scripts\python.exe" -B -m unittest discover -s "D:\Retail-finance\tests" -v
& "D:\Retail-finance\.venv\Scripts\python.exe" -B "D:\Retail-finance\scripts\validate_stage1.py"
```

两条命令本次已执行过，用户不必重复。第二条只读取现有数据并在新目录保存验收报告，不重导数据库。需要重建Excel时再加`--raw`。

## 安全边界与未完成项

- 原Excel、原清洗批次、原业务/客户/预测归档未修改。旧归档错误图已注明，不再作为交付图片。
- 整理期间没有更改已选择模型，没有查看新的未来样本，也没有基于测试集调参。
- 旧研究Notebook仍有历史路径和过程代码。它们不是新正式运行入口，不应在应用中执行；没有宣称全部历史Notebook可跨电脑直接运行。
- `requirements.txt`为当前验证环境的直接依赖清单，不是完整传递依赖锁；未在新电脑重新安装验证。
- 目前脚本依赖本地固定归档作对照。陌生用户从零生成全部归档、演示样例与最终运行流程尚待交付阶段补齐。
- 经营风险信号、完整AI证据包、模型调用与审核、Streamlit和最终GitHub发布均未实施。

下一阶段：先实现带明确规则和证据的经营风险信号，再构建跨模块AI摘要。不同历史窗口必须在页面和摘要中标注，不能混作同一天的实时判断。
