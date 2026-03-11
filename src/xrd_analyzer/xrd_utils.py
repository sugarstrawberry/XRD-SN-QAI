"""
XRD分析工具函数
提供XRD相关的辅助功能
"""


def load_example_data():
    """加载示例数据"""
    examples = {
        "example1": """样品信息：Al2O3，Sigma-Aldrich CAS号1344-28-1，压片制样
辐射源：CuKα，40kV，40mA
扫描参数：10-90°，0.02°，步进扫描，1秒/点
仪器信息：Bruker D8 Advance
数据格式：提供.raw原始文件和CSV格式，4001点，数据对缺失率0%
单位标注：列名"2theta_deg"，"intensity_cps"
内容一致性：无外部参照，样品信息完整
测试信息：提供Si校准证书，记录室温、粉末压片
特征标签：有相标注和PDF卡片号""",

        "example2": """样品信息：Fe3O4，文献DOI:10.1234/example
辐射源：仅写"CuKα"，无电压电流
扫描参数：从图像可读出扫描范围约10-80°，但缺少步长和扫描模式参数
仪器信息：缺失
数据格式：300DPI图像，峰位可辨识
单位标注：坐标轴清晰标注2θ(°)和Intensity(a.u.)
内容一致性：有文献参照
测试信息：未说明校准和环境
特征标签：有相标注""",

        "example3": """样品信息：仅写"未知样品"
辐射源：缺失
扫描参数：缺失
仪器信息：缺失
数据格式：低质量图像，大部分峰位无法辨识
单位标注：坐标轴模糊
内容一致性：无外部参照，样品信息不完整
测试信息：缺失
特征标签：无标签"""
    }
    return examples


def update_weight_sum(completeness, normative, consistency, traceability, usability):
    # 更新权重总和显示
    total = completeness + normative + consistency + traceability + usability
    if total == 100:
        return f"总权重: {total}分 (符合要求)"
    else:
        return f"总权重: {total}分 (必须调整为100分才能执行评分)"


def auto_adjust_weights_to_100(w1, w2, w3, w4, w5):
    # 自动调整权重总和为100分
    weights = [w1, w2, w3, w4, w5]
    current_sum = sum(weights)

    if current_sum == 0:
        # 如果总和为0，则按默认比例分配
        return [40, 15, 10, 20, 15, "总权重: 100分 (符合要求)"]

    # 按比例调整每个权重
    factor = 100 / current_sum
    adjusted_weights = [round(w * factor) for w in weights]

    # 由于四舍五入可能导致总和不是100，调整最后一个权重
    adjusted_sum = sum(adjusted_weights)
    if adjusted_sum != 100:
        adjusted_weights[-1] += 100 - adjusted_sum

    return [adjusted_weights[0], adjusted_weights[1], adjusted_weights[2],
            adjusted_weights[3], adjusted_weights[4], "总权重: 100分 (符合要求)"]


def reset_default_weights():
    """重置为默认权重"""
    return [40, 15, 10, 20, 15, "总权重: 100分 (符合要求)"]


def validate_grade_thresholds_display(a_score, b_score, c_score):
    """
    验证等级阈值并返回显示信息
    
    Args:
        a_score, b_score, c_score: 等级阈值
        
    Returns:
        str: 验证结果显示文本
    """
    try:
        a_score = int(a_score) if a_score is not None else 70
        b_score = int(b_score) if b_score is not None else 50
        c_score = int(c_score) if c_score is not None else 0
    except:
        return "**警告**：请输入有效的整数分数！"

    # 验证等级阈值是否有效
    if a_score <= b_score:
        return "**警告**：A级最低分必须大于B级最低分！请重新输入。"
    elif b_score <= c_score:
        return "**警告**：B级最低分必须大于C级最低分！请重新输入。"
    elif a_score <= c_score:
        return "**警告**：A级最低分必须大于C级最低分！请重新输入。"
    elif a_score <= 0 or b_score <= 0 or c_score < 0:
        return "**警告**：等级阈值必须大于0！请重新输入。"
    elif a_score > 100 or b_score > 100 or c_score > 100:
        return "**警告**：等级阈值不能超过100分！请重新输入。"
    else:
        if c_score == 0:
            return "等级范围设置为：A ≥ {}分, B ≥ {}分, C ≥ {}分".format(a_score, b_score, c_score)
        else:
            return "等级范围设置为：A ≥ {}分, B ≥ {}分, C ≥ {}分, D < {}分".format(a_score, b_score, c_score, c_score)


def reset_default_grade_levels():
    """重置为默认等级划分"""
    return [70, 50, 0]