# e739_analysis_complete.py

import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from matplotlib import font_manager
import yaml
import json
import os
import pandas as pd
import argparse
import warnings

# ==============================================================================
# 作者：重大专项项目组
# 日期：2025-12-11日
# ==============================================================================

# 导入自定义的回归模型模块
from .e739_models import OLSModel, WLSModel, RobustModel, MLEModel

plt.style.use('ggplot')

# ==============================================================================
# 辅助函数
# ==============================================================================

def load_config_from_file(file_path):
    """从指定的 YAML 文件路径动态加载配置。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"配置文件从 '{file_path}' 动态加载成功。")
        return config
    except FileNotFoundError:
        print(f"错误：配置文件未找到于 '{file_path}'。请确保文件存在。")
        return None
    except Exception as e:
        print(f"加载配置文件时发生错误: {e}")
        return None


def load_data_from_csv(csv_path, config):
    """
    根据配置从 CSV 文件中读取 S-N 数据，并进行健壮性检查。
    返回 S_data, N_data, Status_data
    """
    data_cfg = config['DATA']
    reg_cfg = config['REGRESSION']
    s_col = data_cfg['S_COLUMN_NAME']
    n_col = data_cfg['N_COLUMN_NAME']
    status_col = reg_cfg.get('STATUS_COLUMN_NAME', 'Status')

    try:
        df = pd.read_csv(csv_path)

        if s_col not in df.columns or n_col not in df.columns:
            print(f"错误：CSV 文件 '{csv_path}' 中缺少必要的列。")
            print(f"文件中实际读取到的列名：{df.columns.tolist()}")
            return None, None, None

        # 1. 数据类型检查
        try:
            S_data = pd.to_numeric(df[s_col], errors='raise').values.astype(float)
            N_data = pd.to_numeric(df[n_col], errors='raise').values.astype(float)
        except ValueError:
            print("错误：CSV 列中包含非数值数据，无法进行对数转换。")
            return None, None, None

        # 2. 对数前提检查
        if (S_data <= 0).any() or (N_data <= 0).any():
            print("错误：应力 (S) 或寿命 (N) 数据中包含小于或等于零的值，无法进行 Log10 转换。")
            return None, None, None

        # 3. 状态数据 (MLE需要)
        status_data = None
        if status_col in df.columns:
            status_data = pd.to_numeric(df[status_col], errors='coerce').fillna(1).values.astype(int)
            print(f"已检测到状态列 ('{status_col}')，用于 MLE 模型。")
        else:
            status_data = np.ones_like(S_data, dtype=int)
            if reg_cfg['METHOD_SELECTION'].upper() == 'MLE':
                warnings.warn("MLE 模型要求失效状态列，未找到 Status 列，默认所有样本为完全失效 (Status=1)。", UserWarning)

        print(f"数据成功从 '{csv_path}' 读取。总行数: {len(S_data)}")
        return S_data, N_data, status_data

    except FileNotFoundError:
        print(f"错误：数据文件未找到于 '{csv_path}'。")
        return None, None, None
    except Exception as e:
        print(f"读取 CSV 文件时发生错误: {e}")
        return None, None, None


def breusch_pagan_test(X, residuals):
    """简化的 Breusch-Pagan 检验 (异方差性检查)。"""
    res_sq = residuals ** 2
    _, _, r_sq_aux, _, _ = stats.linregress(X, res_sq)
    LM = len(X) * r_sq_aux
    p_value = 1 - stats.chi2.cdf(LM, 1)
    return LM, p_value


def calculate_e739_score(cfg, R_squared, sigma_total, k, bp_p_value):
    """根据配置参数计算 S-N 数据的综合品质分数。"""
    # ... (评分逻辑与原代码保持一致) ...
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

    # 2. Sigma Score
    Sigma_max_score = max_score * sigma_weight
    #sigma_penalty = min(sigma_total * sigma_penalty_factor, Sigma_max_score)
    #sigma_score = max(0, Sigma_max_score - sigma_penalty)
    #score_breakdown['sigma_score'] = sigma_score

    # 获取新的阈值
    sigma_E = score_cfg['SIGMA_EXCELLENT_THRESHOLD']  # 优秀线
    sigma_P = score_cfg['SIGMA_POOR_THRESHOLD']  # 及格线

    # ----------------------------------------------------
    # 2. Sigma Score (新的逻辑：基于分段线性奖励)
    # ----------------------------------------------------
    if sigma_total <= sigma_E:
        # 情况 1: 优秀线 (当前 0.0341 < 0.040) -> 获得满分
        sigma_score = Sigma_max_score

    elif sigma_total <= sigma_P:
        # 情况 2: 及格区 (Sigma_E < Sigma < Sigma_P)
        # 使用线性插值计算分数，Sigma_P 得分最低（例如 10%）
        min_pass_score = 0.1 * Sigma_max_score

        # 线性插值公式：Score = Min_Score + (Max_Score - Min_Score) * (X_max - X) / (X_max - X_min)
        sigma_score = min_pass_score + (Sigma_max_score - min_pass_score) * \
                      (sigma_P - sigma_total) / (sigma_P - sigma_E)

    else:
        # 情况 3: 不及格 (Sigma > Sigma_P) -> 得分快速下降
        # 超过 Sigma_P 后，分数快速衰減至 0，或直接设为 0
        # 设为最低分 0，表示分散性不可接受
        sigma_score = 0

    score_breakdown['sigma_score'] = max(0, sigma_score)  # 确保分数非负

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
    根据分析结果和评分，生成具体的改进建议。
    """
    suggestions = {}
    score_cfg = cfg['SCORING']

    k = results['analysis_summary']['样本总量 k']
    R_squared = results['regression_results']['拟合优度 R^2']
    sigma_total = results['regression_results']['残差标准差 sigma_total']
    bp_p_value = results['diagnostic_results']['BP_P_值']
    outlier_count = results['diagnostic_results']['残差离群点数量']
    influence_count = results['diagnostic_results']['高影响点数量 (Cooks_D)']

    # 1. R2 Score 改进建议 (目标 R2=1.0)
    R2_max_score = score_cfg['MAX_SCORE'] * score_cfg['R2_WEIGHT']
    if results['quality_score_results']['分数细项']['R2_score'] < R2_max_score:
        suggestions['R2_suggestion'] = (
            f"拟合优度 R^2 (当前 {R_squared:.4f})。建议通过排除 {outlier_count} 个离群点和 {influence_count} 个高影响点，"
            f"或检查数据是否位于稳定的线性疲劳区，以提高拟合度。"
        )
    else:
        suggestions['R2_suggestion'] = f"R^2 表现优异 ({R_squared:.4f})，保持当前数据品质。"

    # 2. Sigma Score 改进建议 (目标 Sigma=0)
    # 计算满分对应的最大可接受 Sigma
    Sigma_max_score = score_cfg['MAX_SCORE'] * score_cfg['SIGMA_WEIGHT']
    sigma_penalty_factor = score_cfg['SIGMA_PENALTY_FACTOR']
    # 理论上，Max_acceptable_sigma 是让分数恰好为 0 的 Sigma，
    # 但为了更合理的阈值，使用一个更严格的阈值，例如让分数达到 90%
    Target_sigma = Sigma_max_score / sigma_penalty_factor
    if sigma_total < Target_sigma:
        suggestions['Sigma_suggestion'] = (
            f"分散性表现较好(当前 Sigma_total: {sigma_total:.4f})，超过预设目标{Target_sigma:.4f} (若满分则Sigma为0)。"
            f"建议保持当前精度，属于高品质疲劳数据。"
        )
    else:
        # 实际 sigma (例如 0.0700) 差于目标 (0.0600)
        suggestions['Sigma_suggestion'] = (
            f"分散性偏大 (当前 Sigma_total: {sigma_total:.4f})。建议严格控制试样加工精度、表面处理和试验载荷的稳定性，"
            f"将 Sigma_total 降低到更接近于 {Target_sigma:.4f}。"
        )

    # 3. BP Score 改进建议 (目标 P-value > 阈值)
    BP_threshold = cfg['DESIGN']['BP_P_THRESHOLD']
    if bp_p_value < BP_threshold:
        suggestions['BP_suggestion'] = (
            f"异方差性显著 (P 值 {bp_p_value:.3f} < {BP_threshold:.2f})。残差分散不均匀，"
            f"建议尝试使用加权最小二乘法 (WLS)，或检查试验应力范围是否过大。"
        )
    else:
        suggestions['BP_suggestion'] = f"异方差性不显著 (P 值 {bp_p_value:.3f})，满足同方差假设。"

    # 4. K Score 改进建议 (目标 k >= 阈值)
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


def setup_chinese_font(cfg):
    """设置 Matplotlib 中文字体，解决乱码问题。"""
    font_path = cfg['OUTPUT'].get('FONT_PATH')
    if font_path and os.path.exists(font_path):
        font_prop = font_manager.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['axes.unicode_minus'] = False
    else:
        if 'SimHei' in font_manager.findSystemFonts(fontext='ttf'):
            plt.rcParams['font.family'] = 'SimHei'
            plt.rcParams['axes.unicode_minus'] = False


def save_results_to_json(results_dict, filename):
    """将结果字典保存到 JSON 文件中。"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=4)
        print(f"\n[--- 结果已成功保存到 JSON 文件: {filename} ---]")
    except Exception as e:
        print(f"\n错误：保存 JSON 文件失败: {e}")


def save_figure_to_png(fig, filename):
    """将 Matplotlib 图表保存为 PNG 文件。"""
    try:
        fig.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[--- 图表已成功保存到 PNG 文件: {filename} ---]")
    except Exception as e:
        print(f"\n错误：保存 PNG 文件失败: {e}")


def select_regression_model(config, log_N, log_S, initial_diagnosis, status_data):
    """
    根据配置中的 METHOD_SELECTION 选择或自适应选择回归模型。
    """
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


# ==============================================================================
# 主分析函数
# ==============================================================================
def run_e739_analysis(config_file_path, csv_file_path, json_file_path):
    cfg = load_config_from_file(config_file_path)
    if not cfg:
        return

    # --- 导入数据 ---
    data_result = load_data_from_csv(csv_file_path, cfg)
    if data_result[0] is None:
        return

    S_data, N_data, status_data = data_result

    log_S = np.log10(S_data)
    log_N = np.log10(N_data)
    k = len(S_data)

    if k < 3:
        print("错误：有效样本量 k 必须大于等于 3 才能进行回归分析。")
        return

    df = k - 2

    # --- 1. 运行初始 OLS 和诊断 (用于自适应选择和评分) ---
    # 使用 OLS 结果作为基准诊断
    ols_diag = stats.linregress(log_N, log_S)
    log_S_hat_ols = ols_diag.intercept + ols_diag.slope * log_N
    residuals_ols = log_S - log_S_hat_ols

    SSE_ols = np.sum(residuals_ols ** 2)
    sigma_total_ols = np.sqrt(SSE_ols / df)

    LM, bp_p_value = breusch_pagan_test(log_N, residuals_ols)
    standardized_residuals_ols = residuals_ols / sigma_total_ols

    outlier_threshold = cfg['DESIGN']['OUTLIER_SIGMA_THRESHOLD']
    outlier_indices = np.where(np.abs(standardized_residuals_ols) > outlier_threshold)[0]

    X_matrix = np.vstack([np.ones(k), log_N]).T
    H = X_matrix @ np.linalg.inv(X_matrix.T @ X_matrix) @ X_matrix.T
    leverage = np.diag(H)
    cooks_D = (standardized_residuals_ols ** 2 / 2) * (leverage / (1 - leverage))
    cooks_threshold = cfg['DESIGN']['COOKS_D_THRESHOLD_FACTOR'] / k
    high_influence_indices = np.where(cooks_D > cooks_threshold)[0]

    initial_diagnosis = {
        "BP_P_值": bp_p_value,
        "残差离群点数量": len(outlier_indices),
        "高影响点数量 (Cooks_D)": len(high_influence_indices),
    }

    # --- 2. 选择并拟合最终回归模型 ---
    model_instance = select_regression_model(cfg, log_N, log_S, initial_diagnosis, status_data)
    model_instance.fit()

    # 提取最终回归结果
    intercept = model_instance.intercept
    slope = model_instance.slope
    R_squared = model_instance.R_squared
    sigma_total = model_instance.sigma_total
    residuals = model_instance.residuals
    log_S_hat = model_instance.log_S_hat

    R_squared_adj = 1 - (1 - R_squared) * (k - 1) / (k - 2)

    # --- 3. 重新计算诊断结果（使用最终模型的残差）---
    # 重新计算标准化残差和离群点
    standardized_residuals = residuals / sigma_total
    outlier_indices_final = np.where(np.abs(standardized_residuals) > outlier_threshold)[0]

    # --- 4. 输出报告与分数计算 ---
    # 注意：评分仍基于 OLS 初始诊断的 BP P 值和最终模型的 R^2, sigma_total
    final_score, breakdown = calculate_e739_score(cfg, R_squared, sigma_total, k, bp_p_value)

    improvement_suggestions = get_improvement_suggestions(cfg, {
        "analysis_summary": {"样本总量 k": k},
        "regression_results": {"拟合优度 R^2": R_squared, "残差标准差 sigma_total": sigma_total},
        "diagnostic_results": {"BP_P_值": bp_p_value, "残差离群点数量": len(outlier_indices_final),
                               "高影响点数量 (Cooks_D)": len(high_influence_indices)},
        "quality_score_results": {"分数细项": breakdown}
    })

    # VI. 收集诊断结果和评分结果到字典 (JSON 准备)
    results = {
        "analysis_summary": {
            "样本总量 k": k,
            "疲劳数据 S (MPa)": S_data.tolist(),
            "疲劳数据 N (周期)": N_data.tolist()
        },
        "regression_method": model_instance.model_type,  # 记录最终使用的方法
        "regression_results": {
            "截距 intercept": intercept,
            "斜率 slope": slope,
            "拟合优度 R^2": R_squared,
            "拟合优度 R^2 (调整后)": R_squared_adj,
            "残差标准差 sigma_total": sigma_total,
            "中值曲线方程": f"log10(S) = {intercept:.4f} + ({slope:.4f}) * log10(N)"
        },
        "diagnostic_results": {
            "BP_P_值": bp_p_value,
            "异方差性结论": "存在显著异方差" if bp_p_value < cfg['DESIGN']['BP_P_THRESHOLD'] else "同方差假设成立",
            "残差离群点数量": len(outlier_indices_final),  # 使用最终模型的离群点数
            "高影响点数量 (Cooks_D)": len(high_influence_indices),
            "Cooks_D_阈值": cooks_threshold
        },
        "quality_score_results": {
            "总分": final_score,
            "满分": cfg['SCORING']['MAX_SCORE'],
            "分数细项": breakdown
        },
        "improvement_suggestions": improvement_suggestions
    }

    # VII. 保存结果到 JSON 文件
    save_results_to_json(results, json_file_path)

    # --- 屏幕输出报告 ---
    print("=" * 60)
    print(f"| ASTM E739 综合分析报告 (样本量 k={k})")
    print(f"| 回归方法: {model_instance.model_type}")
    print("=" * 60)

    print(f"1. 中值 S-N 曲线 (Ps=50%): log10(S) = {intercept:.4f} + ({slope:.4f}) * log10(N)")
    print(f"2. 拟合优度 R^2: {R_squared:.4f} (Adj. R^2: {R_squared_adj:.4f})")
    print(f"3. 整体残差标准差 (sigma_total): {sigma_total:.4f}")

    print("\n--- 诊断结果摘要 ---")
    print(f"异方差性 BP 检验 P 值: {bp_p_value:.3f}")
    print(f"残差离群点 (> {outlier_threshold} sigma): {len(outlier_indices_final)} 个")
    print(f"高影响点 (> Cook's D {cooks_threshold:.4f}): {len(high_influence_indices)} 个")

    print("\n" + "=" * 60)
    print(f"| 数据品质综合评分结果: 总分 {final_score:.2f}/{cfg['SCORING']['MAX_SCORE']}")
    print("=" * 60)

    print(f"{'维度':<16} {'分数':>8} {'占比':>8} {'改进建议':<20}")
    print("-" * 120)

    for dimension, score in breakdown.items():
        weight = cfg['SCORING'][dimension.replace('_score', '').upper() + '_WEIGHT']
        suggestion_key = dimension.replace('_score', '_suggestion')
        suggestion = improvement_suggestions.get(suggestion_key, "无")
        print(f"{dimension:<16}: {score:>8.2f} ({weight * 100:.0f}%): {suggestion}")

    print("-" * 120)

    # e739_analysis_complete.py (第 VIII 节: 可视化模块)

    # VIII. 可视化模块 和 图表保存
    if cfg['OUTPUT']['VISUALIZATION_ENABLED']:
        setup_chinese_font(cfg)
        print("\n[--- 执行增强型可视化模块 ---]")

        # --- 绘图数据准备 (使用最终模型的参数) ---
        ps_95 = cfg['DESIGN']['PS_DESIGN_95']
        alpha_critical = cfg['DESIGN']['ALPHA_CRITICAL']

        # 计算 T 临界值
        t_critical_95_side = stats.t.ppf(ps_95, df=df)
        t_critical_95_double = stats.t.ppf(1 - alpha_critical / 2, df=df)

        # 绘制曲线的 N 范围
        N_range = np.logspace(np.min(log_N), np.max(log_N), 100)
        Log_N_range = np.log10(N_range)

        # 中值曲线
        S_median_plot = 10 ** (intercept + slope * Log_N_range)
        # 95% 设计曲线
        S_95_design_plot = 10 ** (intercept + slope * Log_N_range - t_critical_95_side * sigma_total)

        # 预测区间计算
        SS_logN = np.sum((log_N - np.mean(log_N)) ** 2)
        SE_pred = sigma_total * np.sqrt(1 + 1 / k + (log_N - np.mean(log_N)) ** 2 / SS_logN)

        # 对 N 进行排序以便绘制平滑的预测区间
        sort_indices = np.argsort(log_N)
        log_S_hat_sorted = log_S_hat[sort_indices]
        N_data_sorted = N_data[sort_indices]
        SE_pred_sorted = SE_pred[sort_indices]

        S_upper_95_pred = 10 ** (log_S_hat_sorted + t_critical_95_double * SE_pred_sorted)
        S_lower_95_pred = 10 ** (log_S_hat_sorted - t_critical_95_double * SE_pred_sorted)

        # =================================================================
        # 创建多图结构
        # =================================================================
        fig, axes = plt.subplots(3, 1, figsize=(10, 15))

        # --- 計算各分項的滿分 ---
        max_score = cfg['SCORING']['MAX_SCORE']
        r2_max = max_score * cfg['SCORING']['R2_WEIGHT']
        sigma_max = max_score * cfg['SCORING']['SIGMA_WEIGHT']
        bp_max = max_score * cfg['SCORING']['BP_WEIGHT']
        k_max = max_score * cfg['SCORING']['K_WEIGHT']

        # 1. 组合总得分和回归方法
        total_score_and_method_text = f"总得分: {final_score:.2f}/{max_score} | 回归方法: {model_instance.model_type}"

        # 2. 回归方程
        regression_equation_text = f"回归方程: Log(S) = {intercept:.4f} + ({slope:.4f}) * Log(N)"

        # 3. 在 breakdown_text 中包含分项满分
        breakdown_text = (
            f"拟合优度R2分: {breakdown['R2_score']:.2f}/{r2_max:.0f} | "
            f"整体残差标准差σ分: {breakdown['sigma_score']:.2f}/{sigma_max:.0f} | "
            f"异方差BP分: {breakdown['BP_score']:.2f}/{bp_max:.0f} | "
            f"样本量K分: {breakdown['K_score']:.2f}/{k_max:.0f}"
        )

        # --- 设置主标题 ---
        fig.suptitle(f'疲劳数据质量诊断（依据ASTM E739标准）', fontsize=16, y=1.0)

        # 1. 突出显示总得分和回归方法
        fig.text(0.5, 0.975, total_score_and_method_text,
                 fontsize=11, color='darkred',
                 ha='center', va='top', weight='bold')

        # 2. 显示回归方程
        fig.text(0.5, 0.955, regression_equation_text,
                 fontsize=10, color='darkblue',
                 ha='center', va='top')

        # 3. 显示分项得分细则 (得分/满分)
        fig.text(0.5, 0.935, breakdown_text,
                 fontsize=9, color='darkgreen',
                 ha='center', va='top',
                 bbox=dict(boxstyle="round,pad=0.5", fc="aliceblue", alpha=0.6))

        # 调整子图布局，为新增的顶部信息框留出足够的空间 (从 0.92 调整到 0.90)
        plt.subplots_adjust(top=0.95)

        # -------------------------------------------------------------
        # 子图 1: S-N 曲线和设计曲线 (Log-Log)
        # -------------------------------------------------------------
        ax1 = axes[0]
        normal_indices = set(range(k)) - set(high_influence_indices) - set(outlier_indices_final)

        # 绘制正常数据点
        ax1.scatter(N_data[list(normal_indices)], S_data[list(normal_indices)],
                    label='原始数据点', color='black', marker='o', alpha=0.6)

        # 标记离群点
        if len(outlier_indices_final) > 0:
            ax1.scatter(N_data[outlier_indices_final], S_data[outlier_indices_final],
                        color='blue', marker='v', s=100, linewidth=2, label='离群点 ( > 3 Sigma)')

        # 标记高影响点
        if len(high_influence_indices) > 0:
            ax1.scatter(N_data[high_influence_indices], S_data[high_influence_indices],
                        color='red', marker='s', facecolors='none', edgecolors='red',
                        s=150, linewidth=2, label='高影响点 (Cook\'s D)')

        # 绘制曲线
        ax1.plot(N_range, S_median_plot, label='中值曲线 (Ps=50%)', color='blue', linestyle='-')
        ax1.plot(N_range, S_95_design_plot, label=f'设计曲线 (Ps={int(ps_95 * 100)}%)', color='red', linestyle='--')

        # 绘制预测区间
        ax1.fill_between(N_data_sorted, S_lower_95_pred, S_upper_95_pred,
                         color='gray', alpha=0.3, label='95% 预测区间')

        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.set_title('S-N 曲线与设计曲线 (Log-Log)')
        ax1.set_xlabel('疲劳寿命 N (周期)')
        ax1.set_ylabel('应力幅 S (MPa)')
        ax1.legend()
        ax1.grid(True, which="both", ls="--")

        # -------------------------------------------------------------
        # 子图 2: 残差 vs 拟合值 (检查异方差性)
        # -------------------------------------------------------------
        ax2 = axes[1]
        ax2.scatter(log_S_hat, standardized_residuals, color='green', alpha=0.7)
        ax2.axhline(0, color='black', linestyle='-')
        ax2.axhline(outlier_threshold, color='red', linestyle=':', label='3 Sigma 阈值')
        ax2.axhline(-outlier_threshold, color='red', linestyle=':')

        ax2.set_title('标准化残差 vs 预测 Log S (检查异方差性)')
        ax2.set_xlabel('预测 Log S (log S_hat)')
        ax2.set_ylabel('标准化残差')
        ax2.legend()
        ax2.grid(True, which="major", ls="--")

        # -------------------------------------------------------------
        # 子图 3: 残差的正态概率图
        # -------------------------------------------------------------
        ax3 = axes[2]
        stats.probplot(residuals, dist="norm", plot=ax3)
        ax3.get_lines()[1].set_color('red')  # 设置拟合直线颜色
        ax3.set_title('残差的正态概率图 (Normal Probability Plot)')
        ax3.set_xlabel('理论分位数 (Normal)')
        ax3.set_ylabel('排序残差')

        # 最终布局调整
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        # --- 保存图表 ---
        base_name = os.path.splitext(json_file_path)[0]
        png_file_path = f"{base_name}_report.png"

        save_figure_to_png(fig, png_file_path)

        # plt.show() # 如果需要自动弹出窗口，请取消注释

        print("\n图表已生成（S-N 曲线、残差图、正态概率图）")

    else:
        print("\n[--- 可视化模块已跳过 (VISUALIZATION_ENABLED=False) ---]")

    print("=" * 60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ASTM E739 S-N 疲劳数据品质分析工具")
    parser.add_argument('--config', type=str, default='config/config_e739.yaml', help='配置文件路径 (默认: config_e739.yaml)')
    parser.add_argument('--input_csv', type=str, default='data/SN-S-4.csv',
                        help='输入 CSV 数据文件路径 (默认: sn_fatigue_data.csv)')
    parser.add_argument('--output_json', type=str, default='result/e739_report_results.json',
                        help='输出 JSON 报告文件路径 (默认: e739_report_results.json)')

    args = parser.parse_args()

    run_e739_analysis(args.config, args.input_csv, args.output_json)