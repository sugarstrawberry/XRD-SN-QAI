"""
XRD数据质量评价器
负责XRD数据的信息提取和质量评分
支持多种数据源：PDF、CSV、Excel、数据库等
集成不确定性分析功能
"""

from ..common.llm_client import LLMClient
from ..common.file_utils import extract_text_from_pdf
from ..common.data_processor import DataProcessor, create_processor_from_file
from .xrd_models import XRDScoringModel
from .uncertainty_integration import integrate_uncertainty_analysis
import tempfile
import os
import json


class XRDEvaluator:
    """XRD数据质量评价器"""
    
    def __init__(self, config_path=None, uncertainty_model_path=None):
        self.llm_client = LLMClient(config_path)
        self.scoring_model = XRDScoringModel(config_path)
        self.uncertainty_model_path = uncertainty_model_path
        
        # 从配置文件获取信息提取提示词
        self.extraction_prompt = self.scoring_model.get_file_extraction_prompt()
        
        # 确保提示词不为空
        if not self.extraction_prompt:
            raise ValueError("配置文件中缺少FILE_EXTRACTION提示词，请检查xrd_config.yaml文件")
    
    def extract_info_from_pdf(self, pdf_file):
        # 提取文本
        pdf_text = extract_text_from_pdf(pdf_file)
        if pdf_text.startswith("PDF解析失败"):
            return pdf_text
        # 发送给大模型提取关键信息
        extracted_info = self.llm_client.chat(
            self.extraction_prompt,
            f"从以下XRD报告中提取信息：\n\n{pdf_text[:5000]}..."
        )
        
        return f"从PDF提取的信息：\n{extracted_info}\n\n（请核对并补充完整信息）"
    
    def extract_info_from_data_file(self, file_path):
        """
        从数据文件中提取XRD信息（支持CSV、Excel等）
        
        Args:
            file_path: 数据文件路径
            
        Returns:
            str: 提取的信息
        """
        try:
            # 创建数据处理器
            processor = create_processor_from_file(file_path)
            
            # 验证数据是否适用于XRD分析
            is_valid, issues = processor.validate_for_xrd()
            
            if not is_valid:
                return f"数据验证失败：\n" + "\n".join([f"- {issue}" for issue in issues])
            
            # 获取数据预览
            preview_text = processor.get_preview_text(max_rows=10)
            
            # 使用LLM分析数据内容
            analysis_prompt = f"""请分析以下XRD数据文件内容，提取关键的XRD实验信息：

{preview_text}

请提取以下信息：
1. 样品信息：材料成分、样品标识、制备工艺
2. 辐射源：靶材类型、管电压、管电流
3. 扫描参数：扫描范围(2θ)、步长、扫描模式
4. 仪器信息：仪器型号、制造商
5. 数据格式：数据文件格式
6. 数据完整性：数据点数量、缺失情况
7. 单位标注：2θ单位、强度单位
8. 测试信息：校准信息、测试环境
9. 特征标签：相标注、PDF卡片号

如果某项信息在数据中没有明确体现，请写"未在数据中体现"。
请以结构化格式输出提取的信息。"""
            
            extracted_info = self.llm_client.chat(
                "你是一个专业的XRD数据分析专家，擅长从数据文件中提取XRD实验的关键信息。",
                analysis_prompt
            )
            
            return f"从数据文件提取的信息：\n{extracted_info}\n\n原始数据预览：\n{preview_text[:500]}..."
            
        except Exception as e:
            return f"数据文件分析失败：{str(e)}"
    
    def evaluate_text(self, text, weights, A, B, C, strictness):
        # 验证权重
        is_valid, error_msg = self.scoring_model.validate_weights(weights)
        if not is_valid:
            return f"评分失败：{error_msg}"
        
        # 验证等级阈值
        is_valid, error_msg = self.scoring_model.validate_grade_thresholds(A, B, C)
        if not is_valid:
            return f"评分失败：{error_msg}"
        
        # 生成评分提示词
        scoring_prompt = self.scoring_model.generate_scoring_prompt(weights, A, B, C, strictness)
        
        # 调用LLM进行评分
        result = self.llm_client.chat(scoring_prompt, text)
        return result
    
    def evaluate_data_file(self, file_path, weights, A, B, C, strictness):
        """
        直接评价数据文件（CSV、Excel等）
        
        Args:
            file_path: 数据文件路径
            weights: 权重字典
            A, B, C: 等级阈值
            strictness: 严格度
            
        Returns:
            str: 评价结果
        """
        # 验证权重
        is_valid, error_msg = self.scoring_model.validate_weights(weights)
        if not is_valid:
            return f"评分失败：{error_msg}"
        
        try:
            # 创建数据处理器
            processor = create_processor_from_file(file_path)
            
            # 验证数据
            is_valid, issues = processor.validate_for_xrd()
            if not is_valid:
                return f"数据验证失败：\n" + "\n".join([f"- {issue}" for issue in issues])
            
            # 获取数据预览
            preview_text = processor.get_preview_text(max_rows=15)
            
            # 生成评分提示词
            scoring_prompt = self.scoring_model.generate_scoring_prompt(weights, A, B, C, strictness)
            
            # 组合提示词
            combined_prompt = f"""{scoring_prompt}

基于以下XRD数据文件内容，进行评分：

{preview_text}

请根据数据文件中的信息，按照XRD数据质量评估标准进行详细评分。
"""
            
            # 调用LLM进行评分
            result = self.llm_client.chat(combined_prompt, "基于上述XRD数据文件内容进行质量评分。")
            return result
            
        except Exception as e:
            return f"数据文件评分失败：{str(e)}"
    
    def evaluate_pdf(self, pdf_file, weights, A, B, C, strictness):
        # 直接评价PDF文件
        # 验证权重
        is_valid, error_msg = self.scoring_model.validate_weights(weights)
        if not is_valid:
            return f"评分失败：{error_msg}"
        
        # 提取PDF文本
        pdf_text = self.extract_info_from_pdf(pdf_file)
        
        # 生成评分提示词
        scoring_prompt = self.scoring_model.generate_scoring_prompt(weights, A, B, C, strictness)
        # 调用LLM进行评分
        result = self.llm_client.chat(scoring_prompt, pdf_text)
        return result
    
    def evaluate_json_data(self, json_data, weights, A, B, C, strictness, enable_uncertainty=True):
        """
        评价JSON格式的XRD数据，并可选择性地集成不确定性分析
        
        Args:
            json_data: XRD数据字典或JSON字符串
            weights: 权重字典
            A, B, C: 等级阈值
            strictness: 严格度
            enable_uncertainty: 是否启用不确定性分析
            
        Returns:
            str: 评价结果（可能包含不确定性分析）
        """
        # 验证权重
        is_valid, error_msg = self.scoring_model.validate_weights(weights)
        if not is_valid:
            return f"评分失败：{error_msg}"
        
        try:
            # 如果输入是字符串，解析为字典
            if isinstance(json_data, str):
                data_dict = json.loads(json_data)
            else:
                data_dict = json_data
            
            # 验证JSON数据格式
            required_fields = ['two_theta_values', 'intensities']
            missing_fields = [field for field in required_fields if field not in data_dict]
            if missing_fields:
                return f"JSON数据格式错误，缺少必需字段: {missing_fields}"
            
            # 生成数据描述用于LLM评分
            data_description = self._generate_json_description(data_dict)
            
            # 生成评分提示词
            scoring_prompt = self.scoring_model.generate_scoring_prompt(weights, A, B, C, strictness)
            
            # 组合提示词
            combined_prompt = f"""{scoring_prompt}

基于以下XRD JSON数据内容，进行评分：

{data_description}

请根据JSON数据中的信息，按照XRD数据质量评估标准进行详细评分。
"""
            
            # 调用LLM进行评分
            result = self.llm_client.chat(combined_prompt, "基于上述XRD JSON数据内容进行质量评分。")
            
            # 如果启用不确定性分析，则集成分析结果
            if enable_uncertainty:
                try:
                    result = integrate_uncertainty_analysis(result, data_dict, self.uncertainty_model_path)
                except Exception as e:
                    print(f"⚠️  不确定性分析失败: {e}")
                    result += f"\n\n⚠️  不确定性分析失败: {e}"
            
            return result
            
        except json.JSONDecodeError as e:
            return f"JSON解析失败：{str(e)}"
        except Exception as e:
            return f"JSON数据评分失败：{str(e)}"
    
    def _generate_json_description(self, data_dict):
        """
        生成JSON数据的描述文本用于LLM分析
        
        Args:
            data_dict: XRD数据字典
            
        Returns:
            str: 数据描述文本
        """
        description = []
        description.append("XRD JSON数据分析:")
        description.append("-" * 30)
        
        # 基本信息
        two_theta = data_dict.get('two_theta_values', [])
        intensities = data_dict.get('intensities', [])
        wavelength = data_dict.get('wavelength', 'N/A')
        
        description.append(f"数据点数量: {len(two_theta)}")
        if two_theta:
            description.append(f"2θ扫描范围: {min(two_theta):.2f}° - {max(two_theta):.2f}°")
        if intensities:
            description.append(f"强度范围: {min(intensities):.2f} - {max(intensities):.2f}")
        description.append(f"X射线波长: {wavelength} Å")
        
        # 样品信息
        if 'sample_info' in data_dict:
            sample_info = data_dict['sample_info']
            description.append(f"样品信息: {sample_info}")
        
        # 实验参数
        if 'experimental_conditions' in data_dict:
            exp_conditions = data_dict['experimental_conditions']
            description.append(f"实验条件: {exp_conditions}")
        
        # 仪器信息
        if 'instrument_info' in data_dict:
            instrument_info = data_dict['instrument_info']
            description.append(f"仪器信息: {instrument_info}")
        
        # 数据质量指标
        if two_theta and intensities and len(two_theta) == len(intensities):
            import numpy as np
            intensities_array = np.array(intensities)
            noise_level = np.std(intensities_array) / np.mean(intensities_array) if np.mean(intensities_array) > 0 else 0
            description.append(f"信噪比估计: {1/noise_level:.2f}" if noise_level > 0 else "信噪比估计: 很高")
            
            # 峰的数量估计（简单的峰检测）
            peaks_count = 0
            for i in range(1, len(intensities_array) - 1):
                if (intensities_array[i] > intensities_array[i-1] and 
                    intensities_array[i] > intensities_array[i+1] and 
                    intensities_array[i] > np.mean(intensities_array) * 1.2):
                    peaks_count += 1
            description.append(f"检测到的峰数量: {peaks_count}")
        
        return "\n".join(description)