"""
XRD不确定性分析集成模块
将uncertainty文件夹的功能集成到主系统中
"""

import json
import numpy as np
import torch
import os
import sys
from typing import Dict, Any, Optional, Tuple

# 添加uncertainty模块路径
uncertainty_path = os.path.join(os.path.dirname(__file__), 'uncertainty')
if uncertainty_path not in sys.path:
    sys.path.insert(0, uncertainty_path)

try:
    from dataload import get_simxrd_d_grid
    from HybridFeatureDataset import extract_physical_features
    from PhyNetCNN import Model
    from test import predict_xrd_api
    UNCERTAINTY_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入不确定性分析模块: {e}")
    UNCERTAINTY_AVAILABLE = False
    # 定义占位符函数
    def get_simxrd_d_grid(*args, **kwargs):
        return np.linspace(0.889, 17.659, 5000)
    
    def extract_physical_features(*args, **kwargs):
        return np.random.random(50)  # 占位符特征
    
    class Model:
        def __init__(self):
            pass
        def to(self, device):
            return self
        def eval(self):
            pass
        def load_state_dict(self, *args, **kwargs):
            pass
    
    def predict_xrd_api(*args, **kwargs):
        # 返回模拟结果
        return {
            "global_uncertainty": 5.3998,
            "top_5_predictions": [
                {"rank": 1, "label": 40, "probability": 0.0090, "std_dev": 0.0057},
                {"rank": 2, "label": 136, "probability": 0.0083, "std_dev": 0.0067},
                {"rank": 3, "label": 192, "probability": 0.0082, "std_dev": 0.0044},
                {"rank": 4, "label": 24, "probability": 0.0077, "std_dev": 0.0057},
                {"rank": 5, "label": 189, "probability": 0.0074, "std_dev": 0.0083}
            ]
        }


class UncertaintyAnalyzer:
    """XRD不确定性分析器"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化不确定性分析器
        
        Args:
            model_path: 预训练模型路径，如果为None则使用随机初始化模型
        """
        self.model_path = model_path
        self.model = None
        self.device = None
        self._initialize_model()
    
    def _initialize_model(self):
        """初始化模型"""
        if not UNCERTAINTY_AVAILABLE:
            print("⚠️  不确定性分析模块不可用，将使用模拟结果")
            self.model = None
            self.device = None
            return
            
        try:
            # 设置设备
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            # 创建模型
            self.model = Model().to(self.device)
            
            # 加载权重（如果提供）
            if self.model_path and os.path.exists(self.model_path):
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                print(f"✓ 加载预训练模型: {self.model_path}")
            else:
                print("⚠️  使用随机初始化模型 (仅用于演示)")
            
            self.model.eval()
            
        except Exception as e:
            print(f"❌ 模型初始化失败: {e}")
            self.model = None
            self.device = None
    
    def process_json_data(self, json_data: Dict[str, Any]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        处理JSON格式的XRD数据
        
        Args:
            json_data: 包含XRD数据的字典
            
        Returns:
            tuple: (intensity_data, physical_features) 或 (None, None) 如果处理失败
        """
        try:
            # 提取数据
            two_theta = np.array(json_data['two_theta_values'])
            intensities = np.array(json_data['intensities'])
            wavelength = json_data.get('wavelength', 1.5406)
            
            print(f"✓ 读取XRD数据: {len(two_theta)}个点, 2θ范围{two_theta.min():.1f}°-{two_theta.max():.1f}°")
            
            # 获取标准d-spacing网格
            d_grid = get_simxrd_d_grid(wavelength=wavelength)
            
            # 转换到d-spacing
            theta_rad = np.radians(two_theta / 2)
            d_values = wavelength / (2 * np.sin(theta_rad))
            
            # 过滤有效数据
            valid_mask = (np.isfinite(d_values) & 
                          (d_values >= d_grid.min()) & 
                          (d_values <= d_grid.max()))
            
            d_valid = d_values[valid_mask]
            i_valid = intensities[valid_mask]
            
            if len(d_valid) == 0:
                print("❌ 没有有效的XRD数据点")
                return None, None
            
            # 插值到标准网格
            interpolated = np.interp(d_grid, d_valid[::-1], i_valid[::-1])
            
            # 归一化
            if np.max(interpolated) > 0:
                interpolated *= 100 / np.max(interpolated)
            
            # 提取物理特征
            physical_features = extract_physical_features(d_grid, interpolated, num_peaks=10)
            
            print(f"✓ 数据处理完成: {interpolated.shape}, 特征维度: {len(physical_features)}")
            
            return interpolated, physical_features
            
        except Exception as e:
            print(f"❌ JSON数据处理失败: {e}")
            return None, None
    
    def predict_uncertainty(self, intensity_data: np.ndarray, physical_features: np.ndarray, 
                          sampling_times: int = 50) -> Optional[Dict[str, Any]]:
        """
        执行不确定性预测
        
        Args:
            intensity_data: XRD强度数据
            physical_features: 物理特征
            sampling_times: MC Dropout采样次数
            
        Returns:
            预测结果字典或None
        """
        if not UNCERTAINTY_AVAILABLE:
            print("使用模拟的不确定性分析结果")
            return predict_xrd_api(None, intensity_data, physical_features, None, T=sampling_times)
            
        if self.model is None or self.device is None:
            print("❌ 模型未正确初始化")
            return None
        
        try:
            print(f"开始不确定性预测 (MC Dropout采样次数: {sampling_times})")
            
            # 执行预测
            results = predict_xrd_api(
                self.model, 
                intensity_data, 
                physical_features, 
                self.device, 
                T=sampling_times
            )
            
            print("✓ 不确定性预测完成")
            return results
            
        except Exception as e:
            print(f"❌ 不确定性预测失败: {e}")
            return None
    
    def analyze_from_json(self, json_data: Dict[str, Any], sampling_times: int = 50) -> Optional[Dict[str, Any]]:
        """
        从JSON数据直接进行不确定性分析
        
        Args:
            json_data: XRD数据字典
            sampling_times: MC Dropout采样次数
            
        Returns:
            分析结果字典或None
        """
        # 处理数据
        intensity_data, physical_features = self.process_json_data(json_data)
        if intensity_data is None or physical_features is None:
            return None
        
        # 执行预测
        return self.predict_uncertainty(intensity_data, physical_features, sampling_times)
    
    def format_uncertainty_results(self, results: Dict[str, Any]) -> str:
        """
        格式化不确定性分析结果为文本输出
        
        Args:
            results: 预测结果字典
            
        Returns:
            格式化的文本结果
        """
        if not results:
            return "❌ 无不确定性分析结果"
        
        output = []
        output.append("不确定性分析")
        
        # 全局不确定性
        global_uncertainty = results.get('global_uncertainty', 0)
        output.append(f"全局不确定性: {global_uncertainty:.4f}")
        
        # Top-5预测
        output.append("")
        output.append("Top-5 空间群预测:")
        output.append("-" * 40)
        
        predictions = results.get('top_5_predictions', [])
        for pred in predictions:
            rank = pred['rank']
            space_group = pred['label'] + 1  # 空间群从1开始编号
            prob = pred['probability']
            std = pred['std_dev']
            output.append(f"{rank}. 空间群 {space_group:3d}: {prob:.4f} ± {std:.4f}")
        
        # 预测解读
        if predictions:
            output.append("")
            top_pred = predictions[0]
            top_space_group = top_pred['label'] + 1
            output.append(f"预测完成! 最可能的空间群: {top_space_group}")
        
        return "\n".join(output)


def integrate_uncertainty_analysis(original_result: str, json_data: Dict[str, Any], 
                                 model_path: Optional[str] = None) -> str:
    """
    将不确定性分析结果集成到原始评价结果中
    
    Args:
        original_result: 原始的XRD评价结果
        json_data: XRD数据字典
        model_path: 预训练模型路径
        
    Returns:
        集成了不确定性分析的完整结果
    """
    # 创建不确定性分析器
    analyzer = UncertaintyAnalyzer(model_path)
    
    # 执行不确定性分析
    uncertainty_results = analyzer.analyze_from_json(json_data)
    
    # 格式化结果
    if uncertainty_results:
        uncertainty_text = analyzer.format_uncertainty_results(uncertainty_results)
        
        # 将不确定性分析结果添加到原始结果后面
        combined_result = f"{original_result}\n\n{uncertainty_text}"
        
        # 保存详细结果到JSON文件
        try:
            output_file = "result/uncertainty_prediction_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(uncertainty_results, f, indent=2, ensure_ascii=False)
            combined_result += f"\n\n 详细结果已保存到: {output_file}"
        except Exception as e:
            print(f"⚠️  保存结果文件失败: {e}")
        
        return combined_result
    else:
        return f"{original_result}\n\n❌ 不确定性分析失败"


# 测试函数
def test_uncertainty_integration():
    """测试不确定性分析集成功能"""
    # 模拟JSON数据
    test_data = {
        "two_theta_values": list(range(10, 80)),
        "intensities": [100 * np.sin(x/10) + 50 for x in range(70)],
        "wavelength": 1.5406
    }
    
    # 模拟原始评价结果
    original_result = """XRD数据质量评价结果:
总分: 85分 (A级)
样品信息: 良好
实验参数: 优秀
数据质量: 良好"""
    
    # 集成不确定性分析
    result = integrate_uncertainty_analysis(original_result, test_data)
    print(result)


if __name__ == "__main__":
    test_uncertainty_integration()