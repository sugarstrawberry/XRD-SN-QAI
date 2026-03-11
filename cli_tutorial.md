# CLI使用教程 - 材料数据质量评价系统

## 🚀 快速开始

### 安装依赖
```bash
pip install tabulate click
```

### 查看帮助
```bash
python cli.py --help
```

## 📋 命令概览

### 主要命令结构
```bash
python cli.py <command> <action> [options]
```

**可用命令**：
- `xrd` - XRD数据评价
- `sn` - S-N疲劳数据评价  
- `config` - 配置管理
- `db` - 数据库管理

**输出格式**：
- `--format json` - JSON格式（适合程序处理）
- `--format table` - 表格格式（默认，适合阅读）
- `--format csv` - CSV格式（适合Excel）
- `--format report` - 详细报告格式

## 🔬 XRD数据评价

### 文本评价
```bash
# 基础文本评价
python cli.py xrd evaluate --text "样品信息：Al2O3，Sigma-Aldrich，压片制样
辐射源：CuKα，40kV，40mA
扫描参数：10-90°，0.02°，步进扫描
仪器信息：Bruker D8 Advance"

# 自定义权重
python cli.py xrd evaluate --text "..." --weights "信息完整性=50,数据规范性=20,内容一致性=10,过程可追溯性=15,智能可用性=5"

# 设置严格度
python cli.py xrd evaluate --text "..." --strictness 严格

# JSON格式输出
python cli.py xrd evaluate --text "..." --format json

# 保存到文件
python cli.py xrd evaluate --text "..." --output result.json
```

### 文件评价
```bash
# PDF文件评价
python cli.py xrd evaluate --file sample.pdf

# CSV文件评价
python cli.py xrd evaluate --file data.csv --format table

# Excel文件评价
python cli.py xrd evaluate --file experiment.xlsx --format report
```

### 数据库评价
```bash
# MySQL数据库
python cli.py xrd evaluate --database mysql

# 自定义查询
python cli.py xrd evaluate --database mysql --query "SELECT * FROM xrd_experiments WHERE data_quality='high'"

# PostgreSQL数据库
python cli.py xrd evaluate --database postgresql --limit 5

# MongoDB数据库
python cli.py xrd evaluate --database mongodb --table xrd_experiments
```

## 📈 S-N疲劳数据评价

### 基础LLM评价
```bash
# 文本评价
python cli.py sn evaluate --text "材料信息：HSLA-350，高强度低合金钢
试验条件：频率20Hz，温度25°C，应力比R=-1
数据点：应力幅470MPa，失效周期46293次"

# 文件评价
python cli.py sn evaluate --file fatigue_data.csv

# 数据库评价
python cli.py sn evaluate --database postgresql --table sn_fatigue_tests
```

### 综合评价（LLM + E739）
```bash
# 综合文件评价
python cli.py sn evaluate --file fatigue_data.csv --comprehensive

# 综合数据库评价
python cli.py sn evaluate --database mysql --comprehensive --limit 20

# 详细报告格式
python cli.py sn evaluate --file data.csv --comprehensive --format report
```

## ⚙️ 配置管理

### 查看配置
```bash
# 查看XRD配置
python cli.py config show --type xrd

# 查看S-N配置
python cli.py config show --type sn --format json

# 表格格式显示
python cli.py config show --type xrd --format table
```

## 🗄️ 数据库管理

### 连接测试
```bash
# 测试所有数据库
python cli.py db test --all

# 测试特定数据库
python cli.py db test --mysql
python cli.py db test --postgresql
python cli.py db test --mongodb

# JSON格式输出
python cli.py db test --all --format json
```

### 数据库查询
```bash
# MySQL查询
python cli.py db query mysql "SELECT COUNT(*) FROM xrd_experiments"

# PostgreSQL查询
python cli.py db query postgresql "SELECT material_type, COUNT(*) FROM sn_fatigue_tests GROUP BY material_type"

# 限制结果数量
python cli.py db query mysql "SELECT * FROM xrd_experiments" --limit 5

# CSV格式输出
python cli.py db query postgresql "SELECT * FROM sn_fatigue_tests WHERE test_status='completed'" --format csv
```

## 🎯 实际使用场景

### 场景1：快速数据质量检查
```bash
# 检查单个XRD样品
python cli.py xrd evaluate --text "样品：Al2O3，仪器：Bruker D8" --format table

# 输出：
# ✅ XRD数据质量评价完成
# 
# 📊 评价结果:
# ┌─────────────────┬───────┬────────┐
# │ 评价维度        │ 得分  │ 权重   │
# ├─────────────────┼───────┼────────┤
# │ 信息完整性      │ 65    │ 40%    │
# │ 数据规范性      │ 45    │ 15%    │
# │ 内容一致性      │ 80    │ 10%    │
# │ 过程可追溯性    │ 50    │ 20%    │
# │ 智能可用性      │ 40    │ 15%    │
# └─────────────────┴───────┴────────┘
# 
# 🏆 总分: 58.5 (D级)
# 💡 改进建议: 需要补充详细的实验参数和数据格式信息
```

### 场景2：数据库数据评价
```bash
# 评价数据库中的S-N数据
python cli.py sn evaluate --database postgresql --comprehensive --format report

# 输出：
# 🔍 从PostgreSQL查询S-N数据...
# 📊 找到 10 条疲劳试验记录
# ℹ️  使用综合评价模式 (LLM + E739)
# ✅ S-N数据库评价完成
# 
# ============================================================
# 📋 材料数据质量评价报告
# ============================================================
# 评价类型: S-N综合评价
# 评价时间: 2024-01-15 14:30:25
# 数据来源: 数据库: PostgreSQL
# 
# 📊 详细评价结果:
# ----------------------------------------
# 
# 🔹 试验条件完整性:
#    得分: 88
#    权重: 25%
# 
# 🔹 试样信息完整性:
#    得分: 82
#    权重: 20%
# 
# 🏆 综合评价:
#    总分: 85.6
#    等级: B级
# 
# 📈 E739统计分析结果:
# ----------------------------------------
#    S-N曲线拟合质量: R² = 0.95
#    离群点检测: 发现 2 个异常值
#    数据分散性: 中等
# ============================================================
```

### 场景3：配置查看
```bash
# 查看当前XRD配置
python cli.py config show --type xrd --format table

# 输出：
# ┌─────────────────┬───────┬─────────────────┐
# │ 项目            │ 值    │                 │
# ├─────────────────┼───────┼─────────────────┤
# │ config_type     │ XRD   │                 │
# │ config_path     │ config/xrd_config.yaml │
# └─────────────────┴───────┴─────────────────┘
```

### 场景4：管道和自动化
```bash
# 获取评分并进行条件判断
score=$(python cli.py xrd evaluate --text "..." --format json | jq -r '.total_score // 0')
if (( $(echo "$score > 80" | bc -l) )); then
    echo "数据质量合格"
else
    echo "数据质量需要改进"
fi

# 批量处理多个文件
for file in *.pdf; do
    echo "处理文件: $file"
    python cli.py xrd evaluate --file "$file" --format json > "${file%.pdf}_result.json"
done

# 定时任务（crontab）
# 每天凌晨2点评价数据库中的新数据
# 0 2 * * * cd /path/to/project && python cli.py sn evaluate --database mysql --format json > daily_report.json
```

## 🔧 高级用法

### 环境变量配置
```bash
# 设置数据库密码
export DB_PASSWORD="1234"

# 设置默认输出格式
export CLI_DEFAULT_FORMAT="table"
```

### 错误处理
```bash
# CLI会返回适当的退出码
python cli.py xrd evaluate --text "invalid data"
echo $?  # 非0表示错误

# 错误信息会输出到stderr
python cli.py xrd evaluate --file nonexistent.pdf 2>error.log
```

### 性能优化
```bash
# 限制数据库查询结果
python cli.py db query mysql "SELECT * FROM large_table" --limit 100

# 使用JSON格式减少格式化开销
python cli.py sn evaluate --database postgresql --format json
```

## 📝 注意事项

1. **文件路径**: 支持相对路径和绝对路径
2. **数据库连接**: 确保数据库服务已启动且配置正确
3. **权重格式**: 权重必须是数字，总和建议为100
4. **输出重定向**: 使用`--output`参数保存结果到文件
5. **错误处理**: CLI会提供详细的错误信息和建议

## 🆘 常见问题

**Q: 命令找不到？**
A: 确保在项目根目录下运行，且Python路径正确

**Q: 数据库连接失败？**
A: 运行 `python cli.py db test --all` 检查连接状态

**Q: 权重格式错误？**
A: 使用格式：`"维度1=权重1,维度2=权重2"`，权重为数字

**Q: 文件格式不支持？**
A: 目前支持PDF、CSV、Excel文件，其他格式请转换后使用

现在你可以通过命令行高效地使用材料数据质量评价系统了！