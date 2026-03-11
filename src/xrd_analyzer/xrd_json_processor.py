"""
XRD JSON数据处理器
基于pXrd-DFUN库的推理API进行JSON数据处理
用于将JSON格式的XRD数据转换为可用于评价的数组格式
"""

import json
import numpy as np
import sys
import os
from pathlib import Path


class XRDJSONProcessor:
    """XRD JSON数据处理器"""
    
    def __init__(self, pxrd_path=None):
        """
        初始化JSON处理器
        
        Args:
            pxrd_path: pXrd-DFUN库的路径，如果为None则尝试自动查找
        """
        self.pxrd_available = False
        self.api = None
        
        # 尝试导入pXrd-DFUN模块
        self._setup_pxrd_modules(pxrd_path)
    
    def _setup_pxrd_modules(self, pxrd_path):
        """设置pXrd-DFUN模块"""
        try:
            # 如果没有指定路径，尝试从多个可能的位置查找
            if pxrd_path is None:
                possible_paths = [
                    Path(__file__).parent.parent.parent.parent / "pXrd-DFUN-main",
                    Path(__file__).parent.parent.parent / "pXrd-DFUN-main", 
                    Path(__file__).parent / "pXrd-DFUN-main",
                    Path("pXrd-DFUN-main"),
                    Path("../pXrd-DFUN-main"),
                    Path("../../pXrd-DFUN-main")
                ]
                
                for path in possible_paths:
                    if path.exists():
                        pxrd_path = path
                        break
            
            if pxrd_path and Path(pxrd_path).exists():
                sys.path.insert(0, str(pxrd_path))
                print(f"添加pXrd-DFUN路径: {pxrd_path}")
                
                # 导入推理API
                from xrd_inference_api import XRDInferenceAPI
                
                # 创建API实例（不加载模型，只用于数据处理）
                self.api = XRDInferenceAPI(device='cpu')
                self.pxrd_available = True
                
                print("pXrd-DFUN推理API导入成功")
            else:
                print("未找到pXrd-DFUN库，JSON处理功能不可用")
                
        except ImportError as e:
            print(f"pXrd-DFUN模块导入失败: {e}")
            self.pxrd_available = False
    
    def is_available(self):
        """检查JSON处理功能是否可用"""
        return self.pxrd_available
    
    def process_json_to_array(self, json_data):
        """
        使用pXrd-DFUN原始API将JSON数据转换为XRD强度数组
        
        Args:
            json_data: JSON格式的XRD数据（字典或JSON字符串）
            
        Returns:
            tuple: (d_grid, intensity_array) 或 (None, None) 如果处理失败
        """
        if not self.pxrd_available:
            print("错误: pXrd-DFUN库不可用，无法处理JSON数据")
            return None, None
        
        try:
            # 如果输入是字符串，解析为字典
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            
            # 创建临时JSON文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp_file:
                json.dump(json_data, tmp_file, indent=2)
                temp_json_path = tmp_file.name
            
            try:
                # 使用pXrd-DFUN的推理API处理数据
                xrd_data = self.api.json_to_xrd_data(temp_json_path)
                
                if xrd_data is None:
                    print("错误: 无法从JSON数据中提取XRD数据")
                    return None, None
                
                # 预处理XRD数据
                processed_intensity = self.api.preprocess_xrd_data(
                    xrd_data['two_theta'], 
                    xrd_data['intensities'], 
                    xrd_data['wavelength']
                )
                
                # 获取d-spacing网格
                d_grid = self.api.d_grid
                
                print(f"pXrd-DFUN推理API处理成功:")
                print(f"- 原始数据点数: {len(xrd_data['two_theta'])}")
                print(f"- 2θ范围: {np.min(xrd_data['two_theta']):.2f}° - {np.max(xrd_data['two_theta']):.2f}°")
                print(f"- 波长: {xrd_data['wavelength']} Å")
                print(f"- 处理后数据点数: {len(processed_intensity)} (期望: {self.api.target_length})")
                print(f"- d-spacing范围: {np.min(d_grid):.4f} - {np.max(d_grid):.4f} Å")
                print(f"- 强度范围: {np.min(processed_intensity):.4f} - {np.max(processed_intensity):.4f}")
                print(f"- 非零数据点: {np.sum(processed_intensity > 0)} ({np.sum(processed_intensity > 0) / len(processed_intensity) * 100:.1f}%)")
                
                return d_grid, processed_intensity
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_json_path)
                except:
                    pass
            
        except Exception as e:
            print(f"pXrd-DFUN推理API处理失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def process_json_file(self, json_file_path):
        """
        从文件路径处理JSON数据
        
        Args:
            json_file_path: JSON文件路径
            
        Returns:
            tuple: (d_grid, intensity_array) 或 (None, None) 如果处理失败
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            return self.process_json_to_array(json_data)
            
        except Exception as e:
            print(f"JSON文件读取失败: {e}")
            return None, None
    
    def validate_json_data(self, json_data):
        """
        验证JSON数据格式是否适合处理
        
        Args:
            json_data: JSON数据
            
        Returns:
            tuple: (is_valid, message)
        """
        try:
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            
            if not isinstance(json_data, dict):
                return False, "JSON数据必须是字典格式"
            
            # 检查是否包含必要的字段（这里可以根据pXrd-DFUN的要求调整）
            required_fields = ['structure', 'lattice_parameters']  # 示例字段
            missing_fields = []
            
            for field in required_fields:
                if field not in json_data:
                    missing_fields.append(field)
            
            if missing_fields:
                return False, f"缺少必要字段: {', '.join(missing_fields)}"
            
            return True, "JSON数据格式有效"
            
        except json.JSONDecodeError:
            return False, "无效的JSON格式"
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    def get_processing_info(self, json_data):
        """
        获取JSON数据的处理信息
        
        Args:
            json_data: JSON数据
            
        Returns:
            dict: 包含数据信息的字典
        """
        try:
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            
            info = {
                'data_type': type(json_data).__name__,
                'keys': list(json_data.keys()) if isinstance(json_data, dict) else [],
                'size_estimate': len(str(json_data)),
                'pxrd_available': self.pxrd_available
            }
            
            return info
            
        except Exception as e:
            return {'error': str(e)}


# 便捷函数
def create_xrd_json_processor(pxrd_path=None):
    """创建XRD JSON处理器实例"""
    return XRDJSONProcessor(pxrd_path)


def process_xrd_json(json_data, pxrd_path=None):
    """
    便捷函数：处理XRD JSON数据
    
    Args:
        json_data: JSON数据
        pxrd_path: pXrd-DFUN库路径
        
    Returns:
        tuple: (d_grid, intensity_array) 或 (None, None)
    """
    processor = create_xrd_json_processor(pxrd_path)
    return processor.process_json_to_array(json_data)


if __name__ == "__main__":
    # 测试代码
    processor = create_xrd_json_processor()
    print(f"JSON处理器可用性: {processor.is_available()}")
    
    # 示例JSON数据测试
    sample_json = {
        "structure": "example",
        "lattice_parameters": {"a": 5.0, "b": 5.0, "c": 5.0}
    }
    
    is_valid, message = processor.validate_json_data(sample_json)
    print(f"数据验证: {is_valid}, {message}")
    
    info = processor.get_processing_info(sample_json)
    print(f"数据信息: {info}")