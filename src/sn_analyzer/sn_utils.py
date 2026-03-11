"""
S-N分析工具函数
提供S-N数据分析相关的辅助功能
"""

import numpy as np
from scipy import stats
import pandas as pd


def breusch_pagan_test(X, residuals):
    """
    简化的 Breusch-Pagan 检验 (异方差性检查)
    
    Args:
        X: 自变量
        residuals: 残差
        
    Returns:
        tuple: (LM统计量, p值)
    """
    res_sq = residuals ** 2
    _, _, r_sq_aux, _, _ = stats.linregress(X, res_sq)
    LM = len(X) * r_sq_aux
    p_value = 1 - stats.chi2.cdf(LM, 1)
    return LM, p_value


def calculate_e739_score(cfg, R_squared, sigma_total, k, bp_p_value):
    """
    根据配置参数计算 S-N 数据的综合品质分数
    
    Args:
        cfg: 配置字典
        R_squared: 决定系数
        sigma_total: 残差标准差
        k: 样本量
        bp_p_value: BP检验p值
        
    Returns:
        tuple: (总分, 分数细项)
    """
    score_cfg = cfg['SCORING']
    max_score = score_cfg['MAX_SCORE']

    R2_weight = score_cfg['R2_WEIGHT']
    sigma_weight = score_cfg['SIGMA_WEIGHT']
    bp_weight = score_cfg['BP_WEIGHT']
    k_weight = score_cfg['K_WEIGHT']

    sigma_penalty_factor = score_cfg['SIGMA_PENALTY_FACTOR']
    min_k_threshold = score_cfg['MIN_K_THRESHOLD']

    score_breakdown = {}

    # 1. R^2 Score
    R2_max_score = max_score * R2_weight
    R2_score = R_squared * R2_max_score
    score_breakdown['R2_score'] = R2_score

    # 2. Sigma Score (基于分段线性奖励)
    Sigma_max_score = max_score * sigma_weight
    sigma_E = score_cfg['SIGMA_EXCELLENT_THRESHOLD']  # 优秀线
    sigma_P = score_cfg['SIGMA_POOR_THRESHOLD']  # 及格线

    if sigma_total <= sigma_E:
        # 优秀线 -> 获得满分
        sigma_score = Sigma_max_score
    elif sigma_total <= sigma_P:
        # 及格区 - 线性插值
        min_pass_score = 0.1 * Sigma_max_score
        sigma_score = min_pass_score + (Sigma_max_score - min_pass_score) * \
                      (sigma_P - sigma_total) / (sigma_P - sigma_E)
    else:
        # 不及格
        sigma_score = 0

    score_breakdown['sigma_score'] = max(0, sigma_score)

    # 3. BP Score
    BP_max_score = max_score * bp_weight
    BP_threshold = cfg['DESIGN']['BP_P_THRESHOLD']

    BP_score = BP_max_score
    if bp_p_value < BP_threshold:
        penalty_factor = (bp_p_value / BP_threshold)
        BP_score = max(0, BP_max_score * penalty_factor)

    score_breakdown['BP_score'] = BP_score

    # 4. K Score
    K_max_score = max_score * k_weight
    if k >= min_k_threshold:
        K_score = K_max_score
    else:
        K_score = K_max_score * (k / min_k_threshold)
    score_breakdown['K_score'] = K_score

    total_score = R2_score + sigma_score + BP_score + K_score
    final_score = min(total_score, max_score)

    return final_score, score_breakdown


def get_improvement_suggestions(cfg, results):
    """
    根据分析结果和评分，生成具体的改进建议
    
    Args:
        cfg: 配置字典
        results: 分析结果字典
        
    Returns:
        dict: 改进建议字典
    """
    suggestions = {}
    score_cfg = cfg['SCORING']

    k = results['analysis_summary']['样本总量 k']
    R_squared = results['regression_results']['拟合优度 R^2']
    sigma_total = results['regression_results']['残差标准差 sigma_total']
    bp_p_value = results['diagnostic_results']['BP_P_值']
    outlier_count = results['diagnostic_results']['残差离群点数量']
    influence_count = results['diagnostic_results']['高影响点数量 (Cooks_D)']

    # 1. R2 Score 改进建议
    R2_max_score = score_cfg['MAX_SCORE'] * score_cfg['R2_WEIGHT']
    if results['quality_score_results']['分数细项']['R2_score'] < R2_max_score:
        suggestions['R2_suggestion'] = (
            f"拟合优度 R^2 (当前 {R_squared:.4f})。建议通过排除 {outlier_count} 个离群点和 {influence_count} 个高影响点，"
            f"或检查数据是否位于稳定的线性疲劳区，以提高拟合度。"
        )
    else:
        suggestions['R2_suggestion'] = f"R^2 表现优异 ({R_squared:.4f})，保持当前数据品质。"

    # 2. Sigma Score 改进建议
    Sigma_max_score = score_cfg['MAX_SCORE'] * score_cfg['SIGMA_WEIGHT']
    sigma_penalty_factor = score_cfg['SIGMA_PENALTY_FACTOR']
    Target_sigma = Sigma_max_score / sigma_penalty_factor
    
    if sigma_total < Target_sigma:
        suggestions['Sigma_suggestion'] = (
            f"分散性表现较好(当前 Sigma_total: {sigma_total:.4f})，超过预设目标{Target_sigma:.4f}。"
            f"建议保持当前精度，属于高品质疲劳数据。"
        )
    else:
        suggestions['Sigma_suggestion'] = (
            f"分散性偏大 (当前 Sigma_total: {sigma_total:.4f})。建议严格控制试样加工精度、表面处理和试验载荷的稳定性，"
            f"将 Sigma_total 降低到更接近于 {Target_sigma:.4f}。"
        )

    # 3. BP Score 改进建议
    BP_threshold = cfg['DESIGN']['BP_P_THRESHOLD']
    if bp_p_value < BP_threshold:
        suggestions['BP_suggestion'] = (
            f"异方差性显著 (P 值 {bp_p_value:.3f} < {BP_threshold:.2f})。残差分散不均匀，"
            f"建议尝试使用加权最小二乘法 (WLS)，或检查试验应力范围是否过大。"
        )
    else:
        suggestions['BP_suggestion'] = f"异方差性不显著 (P 值 {bp_p_value:.3f})，满足同方差假设。"

    # 4. K Score 改进建议
    min_k_threshold = score_cfg['MIN_K_THRESHOLD']
    if k < min_k_threshold:
        needed_k = min_k_threshold - k
        suggestions['K_suggestion'] = (
            f"样本量不足 (当前 k={k})。要达到最低阈值 {min_k_threshold}，"
            f"建议补充采集至少 {needed_k} 个新的有效样本。"
        )
    else:
        suggestions['K_suggestion'] = f"样本量充足 (k={k})，满足最低阈值要求。"

    return suggestions


def select_regression_model(config, log_N, log_S, initial_diagnosis, status_data):
    """
    根据配置中的 METHOD_SELECTION 选择或自适应选择回归模型
    
    Args:
        config: 配置字典
        log_N: 对数寿命数据
        log_S: 对数应力数据
        initial_diagnosis: 初始诊断结果
        status_data: 状态数据
        
    Returns:
        模型实例
    """
    from .e739_models import OLSModel, WLSModel, RobustModel, MLEModel
    
    method_selection = config['REGRESSION']['METHOD_SELECTION'].upper()

    bp_p_value = initial_diagnosis.get('BP_P_值', 1.0)
    bp_threshold = config['DESIGN']['BP_P_THRESHOLD']
    outlier_count = initial_diagnosis.get('残差离群点数量', 0)
    influence_count = initial_diagnosis.get('高影响点数量 (Cooks_D)', 0)

    # 1. 自适应选择逻辑
    if method_selection == 'ADAPTIVE':
        chosen_method = 'OLS'

        if bp_p_value < bp_threshold:
            chosen_method = 'WLS'
            print("【自适应选择】检测到异方差性显著，自动切换至 WLS (加权最小二乘法)。")

        elif outlier_count > 0 or influence_count > 0:
            chosen_method = 'ROBUST'
            print("【自适应选择】检测到离群点或高影响点，自动切换至 Robust (稳健回归)。")

        else:
            print("【自适应选择】数据符合OLS假设，选用 OLS。")

    # 2. 手动选择逻辑
    else:
        chosen_method = method_selection
        print(f"【手动选择】根据配置文件，选用 {chosen_method}。")

    # 实例化模型
    model_map = {
        'OLS': OLSModel,
        'WLS': WLSModel,
        'ROBUST': RobustModel,
        'MLE': MLEModel
    }

    ModelClass = model_map.get(chosen_method, OLSModel)

    if chosen_method == 'MLE':
        return ModelClass(log_N, log_S, config, initial_diagnosis, status_data=status_data)
    else:
        return ModelClass(log_N, log_S, config, initial_diagnosis)