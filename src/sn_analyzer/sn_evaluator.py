"""
S-N疲劳数据质量评价器
负责S-N数据的分析和质量评估
集成LLM定性分析和E739定量统计分析
支持多种数据源：CSV、Excel、数据库等
"""

from ..common.llm_client import LLMClient
from ..common.file_utils import read_sn_csv
from ..common.data_processor import DataProcessor, create_processor_from_file
from .e739_integration import E739Integration
import pandas as pd
import os
import tempfile


class SNEvaluator:
    """S-N疲劳数据质量评价器"""
    
    def __init__(self, config_path=None):
        # 初始化评价器
        self.llm_client = LLMClient(config_path)
        self.e739_integration = E739Integration(config_path)
        # 从配置文件加载提示词
        self.config = self._load_config(config_path)
        self.sn_analysis_prompt = self._get_default_prompt()
        
    def _load_config(self, config_path):
        """加载配置文件"""
        if config_path and os.path.exists(config_path):
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}
    
    def _get_default_prompt(self):
        """获取默认S-N分析提示词"""
        prompt = self.config.get('PROMPTS', {}).get('DEFAULT_ANALYSIS', '')
        return prompt
    

    
    def set_custom_prompt(self, prompt):
        """设置自定义提示词"""
        self.sn_analysis_prompt = prompt
    
    def evaluate_text(self, text):
        # 调用LLM进行评价和打分
        llm_result = self.llm_client.chat(self.sn_analysis_prompt, text)
        return llm_result
    
    def extract_csv_to_text(self, csv_file):
        """
        将CSV文件内容转换为文本预览
        """
        try:
            df = read_sn_csv(csv_file)
            return self._csv_to_text_preview(df)
        except Exception as e:
            return f"提取失败: {str(e)}"
    

    def extract_data_file_to_text(self, file_path):
        """
        从数据文件提取文本预览
        """
        try:
            # 创建数据处理器
            processor = create_processor_from_file(file_path)
            
            # 获取数据预览
            preview_text = processor.get_preview_text(max_rows=10)
            
            return preview_text
            
        except Exception as e:
            return f"文件读取失败：{str(e)}"
    
    def _csv_to_text_preview(self, df, max_rows=50):
        """
        将DataFrame转换为文本预览
        """
        preview_lines = []

        # 添加基本信息
        preview_lines.append(f"数据点总数: {len(df)}")
        
        if 'S' in df.columns and 'N' in df.columns:
            preview_lines.append(f"应力水平数: {df['S'].nunique()}")
            preview_lines.append(f"应力范围: {df['S'].min()} - {df['S'].max()} MPa")
            preview_lines.append(f"寿命范围: {df['N'].min()} - {df['N'].max()} 循环")

            # 检查中止点
            runouts = df[df['N'] >= 1e7]
            if len(runouts) > 0:
                preview_lines.append(f"中止点数量: {len(runouts)} (N ≥ 10^7)")

            # 添加数据预览
            preview_lines.append("\n数据预览:")
            for i, (_, row) in enumerate(df.head(max_rows).iterrows()):
                preview_lines.append(f"S={row['S']} MPa, N={row['N']}")

            if len(df) > max_rows:
                preview_lines.append(f"... 还有 {len(df) - max_rows} 行数据未显示")
        else:
            # 如果不是标准S-N格式，显示通用预览
            preview_lines.append(f"列名: {', '.join(df.columns)}")
            preview_lines.append("\n数据预览:")
            preview_lines.append(df.head(max_rows).to_string())

        return "\n".join(preview_lines)
    
    def analyze_csv_with_metadata(self, csv_file, metadata_text):
        try:
            df = read_sn_csv(csv_file)
            # 将数据转换为文本格式
            data_lines = []
            for _, row in df.iterrows():
                data_lines.append(f"S={row['S']} MPa, N={row['N']}")
            
            data_text = "\n".join(data_lines)
            
            # 准备完整的消息
            user_message = f"""分析以下S-N疲劳试验数据：

试验数据：
{data_text}

元数据信息：
{metadata_text if metadata_text.strip() else "（未提供元数据）"}
请根据ASTM E466标准，对上述数据进行全面的数据质量评估。"""

            # 调用LLM分析
            final_result = self.evaluate_text(user_message)
            # 获取文件名
            filename = getattr(csv_file, 'name', 'uploaded_file.csv')
            if hasattr(csv_file, 'orig_name'):
                filename = csv_file.orig_name
            
            return filename, len(df), final_result

        except Exception as e:
            error_msg = f"分析失败：{str(e)}"
            return "未知文件", 0, error_msg
    
    def analyze_csv_comprehensive(self, csv_file, metadata_text=""):
        """
        综合分析CSV文件（LLM + E739）
        
        Args:
            csv_file: CSV文件对象
            metadata_text: 元数据文本
            
        Returns:
            tuple: (文件名, 数据点数, 分析结果)
        """
        try:
            # 1. 处理不同类型的文件对象
            temp_csv_path = None
            
            if hasattr(csv_file, 'name') and os.path.exists(csv_file.name):
                # 如果是真实的文件对象，直接使用其路径
                temp_csv_path = csv_file.name
                cleanup_needed = False
            else:
                # 如果是Gradio上传的文件，需要保存到临时位置
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
                    if hasattr(csv_file, 'read'):
                        # 文件对象有read方法
                        csv_content = csv_file.read()
                        if isinstance(csv_content, str):
                            csv_content = csv_content.encode('utf-8')
                        tmp_file.write(csv_content)
                        csv_file.seek(0)  # 重置文件指针
                    else:
                        # 可能是文件路径字符串
                        with open(csv_file, 'rb') as f:
                            tmp_file.write(f.read())
                    
                    temp_csv_path = tmp_file.name
                    cleanup_needed = True
            
            # 2. 读取CSV数据获取基本信息
            df = read_sn_csv(csv_file)
            
            # 3. 获取LLM分析结果
            data_lines = []
            for _, row in df.iterrows():
                data_lines.append(f"S={row['S']} MPa, N={row['N']}")
            
            data_text = "\n".join(data_lines)
            
            user_message = f"""请分析以下S-N疲劳试验数据：

试验数据：
{data_text}

元数据信息：
{metadata_text if metadata_text.strip() else "（未提供元数据）"}

请根据ASTM E466标准，对上述数据进行全面的数据质量评估。"""

            llm_result = self.evaluate_text(user_message)
            
            # 4. 获取E739统计分析结果
            e739_result = self.e739_integration.analyze_csv_data(temp_csv_path, metadata_text)
            
            # 5. 清理临时文件
            if cleanup_needed and temp_csv_path:
                try:
                    os.unlink(temp_csv_path)
                except:
                    pass  # 忽略清理失败
            
            # 6. 生成综合分析报告
            comprehensive_result = self.e739_integration.generate_comprehensive_report(e739_result, llm_result)
            
            # 获取文件名
            filename = getattr(csv_file, 'name', 'uploaded_file.csv')
            if hasattr(csv_file, 'orig_name'):
                filename = csv_file.orig_name
            
            return filename, len(df), comprehensive_result
            
        except Exception as e:
            error_msg = f"综合分析失败：{str(e)}"
            return "未知文件", 0, error_msg
    
    def analyze_data_file_comprehensive(self, file_path, metadata_text=""):
        """
        综合分析数据文件（Excel、JSON等）
        
        Args:
            file_path: 文件路径
            metadata_text: 元数据文本
            
        Returns:
            tuple: (文件名, 数据点数, 分析结果)
        """
        try:
            # 1. 创建数据处理器
            processor = create_processor_from_file(file_path)
            
            # 2. 验证数据
            is_valid, issues = processor.validate_for_sn()
            if not is_valid:
                return os.path.basename(file_path), 0, f"数据验证失败：\n" + "\n".join([f"- {issue}" for issue in issues])
            
            # 3. 获取数据
            df = processor.get_data()
            
            # 4. 为E739分析准备CSV文件
            temp_csv_path = processor.save_to_temp_csv()
            
            try:
                # 5. 获取LLM分析结果
                data_lines = []
                for _, row in df.iterrows():
                    try:
                        s_val = row.get('S', row.get('s', row.get('stress', 0)))
                        n_val = row.get('N', row.get('n', row.get('cycles', 0)))
                        if pd.notna(s_val) and pd.notna(n_val):
                            data_lines.append(f"S={s_val} MPa, N={n_val}")
                    except:
                        continue
                
                data_text = "\n".join(data_lines)
                
                user_message = f"""请分析以下S-N疲劳试验数据：

试验数据：
{data_text}

元数据信息：
{metadata_text if metadata_text.strip() else "（未提供元数据）"}

数据文件信息：
- 文件名: {os.path.basename(file_path)}
- 有效数据点: {len(data_lines)}

请根据ASTM E466和E739标准，对上述数据进行全面的数据质量评估。"""

                llm_result = self.evaluate_text(user_message)
                
                # 6. 获取E739统计分析结果
                e739_result = self.e739_integration.analyze_csv_data(temp_csv_path, metadata_text)
                
                # 7. 生成综合分析报告
                comprehensive_result = self.e739_integration.generate_comprehensive_report(e739_result, llm_result)
                
                return os.path.basename(file_path), len(data_lines), comprehensive_result
                
            finally:
                # 8. 清理临时文件
                try:
                    os.unlink(temp_csv_path)
                except:
                    pass
            
        except Exception as e:
            error_msg = f"综合分析失败：{str(e)}"
            return os.path.basename(file_path), 0, error_msg
    
    def get_e739_status(self):
        """
        获取E739系统状态
        
        Returns:
            dict: E739系统状态信息
        """
        return {
            "available": self.e739_integration.is_available(),
            "message": "E739统计分析系统已就绪" if self.e739_integration.is_available() else "E739统计分析系统不可用"
        }

    def analyze_csv_comprehensive_from_path(self, csv_path, metadata_text=""):
        """
        从CSV文件路径进行综合分析（用于数据库集成）
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(csv_path)
            
            # 验证数据格式
            if 'S' not in df.columns or 'N' not in df.columns:
                # 尝试自动识别列名
                stress_cols = [col for col in df.columns if any(name in col.lower() for name in ['stress', 's', 'sigma', '应力'])]
                cycle_cols = [col for col in df.columns if any(name in col.lower() for name in ['cycle', 'n', 'life', '寿命', '循环'])]
                
                if stress_cols and cycle_cols:
                    df = df.rename(columns={stress_cols[0]: 'S', cycle_cols[0]: 'N'})
                else:
                    return "数据格式错误：需要包含应力(S)和寿命(N)列"
            
            # 将数据转换为文本格式
            data_lines = []
            for _, row in df.iterrows():
                data_lines.append(f"S={row['S']} MPa, N={row['N']}")
            
            data_text = "\n".join(data_lines)
            
            # 准备完整的消息
            user_message = f"""请分析以下S-N疲劳试验数据：

试验数据：
{data_text}

元数据信息：
{metadata_text if metadata_text.strip() else "（未提供元数据）"}

请根据ASTM E466标准，对上述数据进行全面的数据质量评估。"""

            # 调用LLM分析
            llm_result = self.evaluate_text(user_message)
            
            # 提取LLM评分
            llm_score, llm_grade, llm_dimensions = self._extract_llm_score(llm_result)
            
            # 如果E739可用，进行统计分析
            e739_status = self.get_e739_status()
            e739_result = ""
            
            if e739_status["available"]:
                try:
                    e739_result = self.e739_integration.analyze_sn_data(csv_path, metadata_text)
                except Exception as e:
                    e739_result = f"E739统计分析失败：{str(e)}"
            
            # 计算综合评分
            comprehensive_score, comprehensive_grade, score_explanation = self._calculate_comprehensive_score(
                llm_score, llm_grade, e739_result
            )

            return combined_result
            
        except Exception as e:
            return f"综合分析失败：{str(e)}"
    

    
    def _csv_to_text_preview(self, df, max_rows=50):
        """
        将DataFrame转换为文本预览
        
        Args:
            df: DataFrame对象
            max_rows: 最大显示行数
            
        Returns:
            str: 文本预览
        """
        preview_lines = []

        # 添加基本信息
        preview_lines.append(f"数据点总数: {len(df)}")
        preview_lines.append(f"应力水平数: {df['S'].nunique()}")
        preview_lines.append(f"应力范围: {df['S'].min()} - {df['S'].max()} MPa")
        preview_lines.append(f"寿命范围: {df['N'].min()} - {df['N'].max()} 循环")

        # 检查中止点
        runouts = df[df['N'] >= 1e7]
        if len(runouts) > 0:
            preview_lines.append(f"中止点数量: {len(runouts)} (N ≥ 10^7)")

        # 添加数据预览
        preview_lines.append("\n数据预览:")
        for i, (_, row) in enumerate(df.head(max_rows).iterrows()):
            preview_lines.append(f"S={row['S']} MPa, N={row['N']}")

        if len(df) > max_rows:
            preview_lines.append(f"... 还有 {len(df) - max_rows} 行数据未显示")

        return "\n".join(preview_lines)
    
    def extract_data_file_to_text(self, file_path):
        """
        从数据文件中提取S-N信息（支持CSV、Excel等）
        
        Args:
            file_path: 数据文件路径
            
        Returns:
            str: 提取的信息
        """
        try:
            # 创建数据处理器
            processor = create_processor_from_file(file_path)
            
            # 验证数据是否适用于S-N分析
            is_valid, issues = processor.validate_for_sn()
            
            if not is_valid:
                return f"数据验证失败：\n" + "\n".join([f"- {issue}" for issue in issues])
            
            # 获取数据预览
            preview_text = processor.get_preview_text(max_rows=20)
            
            return preview_text
            
        except Exception as e:
            return f"数据文件分析失败：{str(e)}"
    
    def analyze_data_file_with_metadata(self, file_path, metadata_text):
        """
        分析数据文件并结合元数据（支持多种格式）
        
        Args:
            file_path: 数据文件路径
            metadata_text: 元数据文本
            
        Returns:
            tuple: (文件名, 数据点数, 分析结果)
        """
        try:
            # 创建数据处理器
            processor = create_processor_from_file(file_path)
            
            # 验证数据
            is_valid, issues = processor.validate_for_sn()
            if not is_valid:
                error_msg = "数据验证失败：\n" + "\n".join([f"- {issue}" for issue in issues])
                return os.path.basename(file_path), 0, error_msg
            
            # 获取数据
            df = processor.get_data()
            
            # 尝试识别S-N列
            s_columns = ['S', 's', 'stress', 'Stress', 'σ', 'sigma', '应力']
            n_columns = ['N', 'n', 'cycles', 'Cycles', 'Nf', 'life', 'Life', '寿命', '循环']
            
            s_col = None
            n_col = None
            
            for col in df.columns:
                if col in s_columns or any(s_name in col.lower() for s_name in ['stress', 'sigma']):
                    s_col = col
                if col in n_columns or any(n_name in col.lower() for n_name in ['cycle', 'life']):
                    n_col = col
            
            if not s_col or not n_col:
                return os.path.basename(file_path), len(df), "无法识别S-N数据列，请检查列名格式"
            
            # 将数据转换为文本格式
            data_lines = []
            for _, row in df.iterrows():
                try:
                    s_val = row[s_col]
                    n_val = row[n_col]
                    if pd.notna(s_val) and pd.notna(n_val):
                        data_lines.append(f"S={s_val} MPa, N={n_val}")
                except:
                    continue
            
            if not data_lines:
                return os.path.basename(file_path), len(df), "数据中没有有效的S-N数据点"
            
            data_text = "\n".join(data_lines)
            
            # 准备完整的消息
            user_message = f"""请分析以下S-N疲劳试验数据：

试验数据：
{data_text}

元数据信息：
{metadata_text if metadata_text.strip() else "（未提供元数据）"}

数据文件信息：
- 文件名: {os.path.basename(file_path)}
- 应力列: {s_col}
- 寿命列: {n_col}
- 有效数据点: {len(data_lines)}

请根据ASTM E466和E739标准，对上述数据进行全面的数据质量评估。"""

            # 调用LLM分析
            result = self.evaluate_text(user_message)
            
            return os.path.basename(file_path), len(data_lines), result

        except Exception as e:
            error_msg = f"分析失败：{str(e)}"
            return os.path.basename(file_path), 0, error_msg
    
    def analyze_csv_comprehensive(self, csv_file, metadata_text):
        """
        综合分析CSV文件：结合LLM评价和E739统计分析
        
        Args:
            csv_file: CSV文件对象
            metadata_text: 元数据文本
            
        Returns:
            tuple: (文件名, 数据点数, 综合分析结果)
        """
        try:
            # 1. 处理不同类型的文件对象
            temp_csv_path = None
            
            if hasattr(csv_file, 'name') and os.path.exists(csv_file.name):
                # 如果是真实的文件对象，直接使用其路径
                temp_csv_path = csv_file.name
                cleanup_needed = False
            else:
                # 如果是Gradio上传的文件，需要保存到临时位置
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
                    if hasattr(csv_file, 'read'):
                        # 文件对象有read方法
                        csv_content = csv_file.read()
                        if isinstance(csv_content, str):
                            csv_content = csv_content.encode('utf-8')
                        tmp_file.write(csv_content)
                        csv_file.seek(0)  # 重置文件指针
                    else:
                        # 可能是文件路径字符串
                        with open(csv_file, 'rb') as f:
                            tmp_file.write(f.read())
                    
                    temp_csv_path = tmp_file.name
                    cleanup_needed = True
            
            # 2. 获取LLM分析结果（现有功能）
            filename, data_count, llm_result = self.analyze_csv_with_metadata(csv_file, metadata_text)
            
            # 3. 获取E739统计分析结果（新增功能）
            e739_result = self.e739_integration.analyze_csv_data(temp_csv_path, metadata_text)
            
            # 4. 清理临时文件
            if cleanup_needed and temp_csv_path:
                try:
                    os.unlink(temp_csv_path)
                except:
                    pass  # 忽略清理失败
            
            # 5. 生成综合分析报告
            comprehensive_result = self.e739_integration.generate_comprehensive_report(e739_result, llm_result)
            
            return filename, data_count, comprehensive_result
            
        except Exception as e:
            error_msg = f"综合分析失败：{str(e)}"
            return "未知文件", 0, error_msg
    
    def analyze_data_file_comprehensive(self, file_path, metadata_text):
        """
        综合分析数据文件：结合LLM评价和E739统计分析（支持多种格式）
        
        Args:
            file_path: 数据文件路径
            metadata_text: 元数据文本
            
        Returns:
            tuple: (文件名, 数据点数, 综合分析结果)
        """
        try:
            # 1. 获取LLM分析结果
            filename, data_count, llm_result = self.analyze_data_file_with_metadata(file_path, metadata_text)
            
            # 2. 如果数据验证失败，直接返回LLM结果
            if data_count == 0:
                return filename, data_count, llm_result
            
            # 3. 为E739分析准备CSV文件
            processor = create_processor_from_file(file_path)
            temp_csv_path = processor.save_to_temp_csv()
            
            try:
                # 4. 获取E739统计分析结果
                e739_result = self.e739_integration.analyze_csv_data(temp_csv_path, metadata_text)
                
                # 5. 生成综合分析报告
                comprehensive_result = self.e739_integration.generate_comprehensive_report(e739_result, llm_result)
                
                return filename, data_count, comprehensive_result
                
            finally:
                # 6. 清理临时文件
                try:
                    os.unlink(temp_csv_path)
                except:
                    pass
            
        except Exception as e:
            error_msg = f"综合分析失败：{str(e)}"
            return os.path.basename(file_path), 0, error_msg
    
    def get_e739_status(self):
        """
        获取E739系统状态
        
        Returns:
            dict: E739系统状态信息
        """
        return {
            "available": self.e739_integration.is_available(),
            "message": "E739统计分析系统已就绪" if self.e739_integration.is_available() else "E739统计分析系统不可用"
        }