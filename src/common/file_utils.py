"""
文件处理工具模块
提供PDF、CSV等文件的读取和处理功能
"""

import PyPDF2
import pandas as pd
import json
import os
import yaml


def extract_text_from_pdf(pdf_file):
    """从PDF文件中提取文本"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        # 提取所有页面的文本
        for page_num in range(min(10, len(pdf_reader.pages))):  # 限制前10页
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        return text[:5000]  # 限制文本长度
    except Exception as e:
        return f"PDF解析失败: {str(e)}"


def read_sn_csv(file_obj):
    """读取S-N数据CSV文件"""
    try:
        if hasattr(file_obj, 'name') and os.path.exists(file_obj.name):
            df = pd.read_csv(file_obj.name)
        else:
            df = pd.read_csv(file_obj)

        # 检查列名，允许大小写变化
        df.columns = df.columns.str.strip()
        return df
        
        # 尝试找到应力幅和循环次数列
        s_col = None
        n_col = None

        possible_s = ['S', 's', 'stress', 'Stress', 'σ', 'sigma']
        possible_n = ['N', 'n', 'cycles', 'Cycles', 'Nf', 'life', 'Life']

        for col in df.columns:
            if col in possible_s:
                s_col = col
            if col in possible_n:
                n_col = col

        if s_col and n_col:
            # 重命名为标准列名
            df = df.rename(columns={s_col: 'S', n_col: 'N'})
            return df
        else:
            # 如果没有找到标准列名，假设第一列是S，第二列是N
            if len(df.columns) >= 2:
                df = df.rename(columns={df.columns[0]: 'S', df.columns[1]: 'N'})
                return df
            else:
                raise ValueError("CSV文件需要至少两列数据")

    except Exception as e:
        raise ValueError(f"读取S-N CSV文件失败: {str(e)}")


def save_results_to_json(results_dict, filename):
    """
    将结果字典保存到JSON文件
    Args:
        results_dict: 结果字典
        filename: 输出文件名
    """
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=4)
        print(f"结果已保存到: {filename}")
    except Exception as e:
        print(f"保存JSON文件失败: {e}")


def load_config(config_path):
    """加载YAML配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"配置文件未找到: {config_path}")
        return None
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return None
