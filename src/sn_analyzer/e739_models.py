"""
S-N疲劳数据统计分析模型
基于ASTM E739标准的回归分析模型
"""

import numpy as np
from scipy import stats
from abc import ABC, abstractmethod
import pandas as pd
import warnings

# 尝试导入 statsmodels 和 lifelines 库
try:
    import statsmodels.api as sm
    from statsmodels.formula.api import ols as sm_ols
    from statsmodels.robust.robust_linear_model import RLM
    SM_AVAILABLE = True
except ImportError:
    SM_AVAILABLE = False

try:
    from lifelines import LogNormalAFTFitter
    LF_AVAILABLE = True
except ImportError:
    LF_AVAILABLE = False


# ----------------------------------------------------------------------
# 抽象基类 (Abstract Base Class)
# ----------------------------------------------------------------------
class BaseE739Model(ABC):
    """S-N疲劳数据回归模型的抽象基类"""

    def __init__(self, log_N, log_S, config, analysis_data, status_data=None):
        self.log_N = log_N
        self.log_S = log_S
        self.k = len(log_N)
        self.df = self.k - 2
        self.config = config
        self.analysis_data = analysis_data
        self.status_data = status_data  # 仅MLE需要

        self.intercept = None
        self.slope = None
        self.R_squared = None
        self.sigma_total = None
        self.log_S_hat = None
        self.residuals = None
        self.model_type = "Base"

    @abstractmethod
    def fit(self):
        """执行具体的回归拟合过程"""
        pass

    def calculate_metrics(self):
        """计算残差、R^2 和 sigma_total（使用 OLS 定义以便于评分比较）"""
        self.log_S_hat = self.intercept + self.slope * self.log_N
        self.residuals = self.log_S - self.log_S_hat
        SSE = np.sum(self.residuals ** 2)
        SST = np.sum((self.log_S - np.mean(self.log_S)) ** 2)
        SSR = np.sum((self.log_S_hat - np.mean(self.log_S)) ** 2)

        if SST > 1e-9:
            self.R_squared = SSR / SST
        else:
            self.R_squared = 1.0

        # 根据ASTM E739的定义，使用k-2的自由度
        self.sigma_total = np.sqrt(SSE / self.df)


# 1. 普通最小二乘法 (OLS)
# ----------------------------------------------------------------------
class OLSModel(BaseE739Model):
    def __init__(self, log_N, log_S, config, analysis_data, status_data=None):
        super().__init__(log_N, log_S, config, analysis_data)
        self.model_type = "OLS"

    def fit(self):
        """使用scipy.stats执行OLS回归"""
        slope, intercept, r_value, _, _ = stats.linregress(self.log_N, self.log_S)
        self.intercept = intercept
        self.slope = slope
        self.calculate_metrics()
        return self


# 2. 加权最小二乘法 (WLS)
# ----------------------------------------------------------------------
class WLSModel(BaseE739Model):
    def __init__(self, log_N, log_S, config, analysis_data, status_data=None):
        super().__init__(log_N, log_S, config, analysis_data)
        self.model_type = "WLS"

    def fit(self):
        """执行WLS回归，使用OLS残差的倒数作为权重（简化异方差修正）"""
        if not SM_AVAILABLE:
            warnings.warn("WLS模型需要 'statsmodels' 库，已回退到 OLS。", UserWarning)
            return OLSModel(self.log_N, self.log_S, self.config, self.analysis_data).fit()

        # 1. 首先进行一个OLS拟合以估计权重
        data = pd.DataFrame({'log_S': self.log_S, 'log_N': self.log_N})
        ols_model = sm_ols('log_S ~ log_N', data=data).fit()

        # 2. 估计权重：权重与残差平方的倒数成比例
        residuals_sq = ols_model.resid ** 2
        # 为了避免除以零和处理极端值，添加一个小的常数项
        weights = 1.0 / (residuals_sq + 1e-6)

        # 3. WLS拟合
        wls_model = sm.WLS(self.log_S, sm.add_constant(self.log_N), weights=weights).fit()

        self.intercept = wls_model.params[0]
        self.slope = wls_model.params[1]

        self.calculate_metrics()
        return self


# 3. 稳健回归 (Robust Regression)
# ----------------------------------------------------------------------
class RobustModel(BaseE739Model):
    def __init__(self, log_N, log_S, config, analysis_data, status_data=None):
        super().__init__(log_N, log_S, config, analysis_data)
        self.model_type = "Robust(HuberT)"

    def fit(self):
        """执行 HuberT 稳健回归"""
        if not SM_AVAILABLE:
            warnings.warn("Robust模型需要 'statsmodels' 库，已回退到 OLS。", UserWarning)
            return OLSModel(self.log_N, self.log_S, self.config, self.analysis_data).fit()

        # RLM (Robust Linear Model)，使用 HuberT 损失函数
        rlm_model = RLM(self.log_S, sm.add_constant(self.log_N), M=sm.robust.norms.HuberT()).fit()

        self.intercept = rlm_model.params[0]
        self.slope = rlm_model.params[1]

        self.calculate_metrics()
        return self


# 4. 最大似然估计 (MLE) - 使用 Lifelines 库 (Log-Normal AFT)
# ----------------------------------------------------------------------
class MLEModel(BaseE739Model):
    def __init__(self, log_N, log_S, config, analysis_data, status_data=None):
        super().__init__(log_N, log_S, config, analysis_data, status_data)
        self.model_type = "MLE (Log-Normal AFT)"
        self.N_data = 10 ** self.log_N

    def fit(self):
        """执行 Log-Normal AFT 模型的 MLE 回归 (用于存活数据)"""
        if not LF_AVAILABLE:
            warnings.warn("MLE 模型需要 'lifelines' 库，已回退到 OLS。", UserWarning)
            return OLSModel(self.log_N, self.log_S, self.config, self.analysis_data).fit()

        # 1. 构建 DataFrame (lifelines 要求)
        data = pd.DataFrame({
            'N': self.N_data,
            'Status': self.status_data,
            'log_S': self.log_S  # 使用 log_S 作为协变量
        })

        # 2. 拟合模型: N ~ log_S
        try:
            # AFT 模型： log(T) = Intercept + slope * X + error
            # T = N (寿命), X = log_S (应力对数)
            self.AFT_fitter = LogNormalAFTFitter().fit(
                data['N'],
                event_observed=data['Status'],
                formula="log_S"
            )
        except Exception as e:
            warnings.warn(f"MLE 拟合失败: {e}", UserWarning)
            return OLSModel(self.log_N, self.log_S, self.config, self.analysis_data).fit()

        # 3. 提取疲劳方程的参数 (转换为 log S = I + m * log N 形式)
        # LogNormal AFT 的参数是 log(N) = I' + m' * log(S) 形式
        intercept_prime = self.AFT_fitter.params_.loc['Intercept', 'lambda_']
        slope_prime = self.AFT_fitter.params_.loc['log_S', 'lambda_']

        # 转换为 S-N 形式: log S = I + m * log N
        if abs(slope_prime) > 1e-6:
            self.slope = 1.0 / slope_prime
            self.intercept = -intercept_prime / slope_prime
        else:
            # 几乎水平线，斜率接近无限，回退到 OLS
            return OLSModel(self.log_N, self.log_S, self.config, self.analysis_data).fit()

        # 4. 提取 sigma_total (对数尺度下的尺度参数)
        self.sigma_total = self.AFT_fitter.params_.loc['Intercept', 'sigma_']

        self.calculate_metrics()
        return self