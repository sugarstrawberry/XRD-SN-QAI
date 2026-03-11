"""
统一数据处理器
为XRD和S-N模块提供统一的数据处理接口
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Union, List, Tuple
import tempfile
import os
from .data_sources import DataSource, create_data_source_from_file, create_data_source


class DataProcessor:
    """统一数据处理器"""
    
    def __init__(self, data_source: DataSource):
        """
        初始化数据处理器
        
        Args:
            data_source: 数据源实例
        """
        self.data_source = data_source
        self._cached_data = None
    
    def get_data(self, use_cache: bool = True) -> pd.DataFrame:
        """
        获取数据
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            pd.DataFrame: 数据
        """
        if use_cache and self._cached_data is not None:
            return self._cached_data.copy()
        
        self._cached_data = self.data_source.read_data()
        return self._cached_data.copy()
    
    def get_data_info(self) -> Dict[str, Any]:
        """获取数据基本信息"""
        df = self.get_data()
        
        info = {
            'source_info': self.data_source.get_source_info(),
            'shape': df.shape,
            'columns': df.columns.tolist(),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'missing_values': df.isnull().sum().to_dict(),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024,
            'numeric_columns': df.select_dtypes(include=[np.number]).columns.tolist(),
            'text_columns': df.select_dtypes(include=['object']).columns.tolist(),
            'datetime_columns': df.select_dtypes(include=['datetime64']).columns.tolist()
        }
        
        # 添加数值统计
        numeric_df = df.select_dtypes(include=[np.number])
        if not numeric_df.empty:
            info['numeric_stats'] = {
                col: {
                    'mean': float(numeric_df[col].mean()) if not numeric_df[col].isna().all() else None,
                    'std': float(numeric_df[col].std()) if not numeric_df[col].isna().all() else None,
                    'min': float(numeric_df[col].min()) if not numeric_df[col].isna().all() else None,
                    'max': float(numeric_df[col].max()) if not numeric_df[col].isna().all() else None,
                    'missing_count': int(numeric_df[col].isna().sum())
                }
                for col in numeric_df.columns
            }
        
        return info
    
    def get_preview_text(self, max_rows: int = 10) -> str:
        """
        获取数据预览文本
        
        Args:
            max_rows: 最大行数
            
        Returns:
            str: 预览文本
        """
        df = self.get_data()
        info = self.get_data_info()
        
        preview_lines = []
        
        # 基本信息
        preview_lines.append(f"数据源: {info['source_info']}")
        preview_lines.append(f"数据形状: {info['shape'][0]} 行 × {info['shape'][1]} 列")
        preview_lines.append(f"内存使用: {info['memory_usage_mb']:.2f} MB")
        
        # 列信息
        preview_lines.append(f"\n列信息:")
        for col in df.columns:
            dtype = info['dtypes'][col]
            missing = info['missing_values'][col]
            missing_pct = (missing / len(df)) * 100 if len(df) > 0 else 0
            preview_lines.append(f"  {col}: {dtype} (缺失: {missing}/{len(df)}, {missing_pct:.1f}%)")
        
        # 数值统计
        if 'numeric_stats' in info and info['numeric_stats']:
            preview_lines.append(f"\n数值统计:")
            for col, stats in info['numeric_stats'].items():
                if stats['mean'] is not None:
                    preview_lines.append(f"  {col}: 均值={stats['mean']:.2f}, 标准差={stats['std']:.2f}")
        
        # 数据预览
        preview_lines.append(f"\n数据预览 (前{min(max_rows, len(df))}行):")
        preview_df = df.head(max_rows).fillna('NaN')
        
        # 转换为简洁的文本格式
        for i, (_, row) in enumerate(preview_df.iterrows()):
            row_text = ", ".join([f"{col}={str(val)[:50]}" for col, val in row.items()])
            preview_lines.append(f"  行{i+1}: {row_text}")
        
        if len(df) > max_rows:
            preview_lines.append(f"  ... 还有 {len(df) - max_rows} 行数据")
        
        return "\n".join(preview_lines)
    
    def save_to_temp_csv(self) -> str:
        """
        将数据保存到临时CSV文件
        
        Returns:
            str: 临时文件路径
        """
        df = self.get_data()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
            df.to_csv(tmp_file.name, index=False)
            return tmp_file.name
    
    def validate_for_xrd(self) -> Tuple[bool, List[str]]:
        """
        验证数据是否适用于XRD分析
        
        Returns:
            Tuple[bool, List[str]]: (是否有效, 问题列表)
        """
        df = self.get_data()
        issues = []
        
        # 检查基本要求
        if df.empty:
            issues.append("数据为空")
            return False, issues
        
        # 检查XRD相关列
        xrd_related_columns = [
            '样品', '材料', '成分', 'sample', 'material', 'composition',
            '辐射源', '射线', 'radiation', 'source', 'x-ray',
            '扫描', 'scan', '2θ', '2theta', 'angle',
            '仪器', 'instrument', 'equipment',
            '强度', 'intensity', 'counts'
        ]
        
        found_xrd_columns = []
        for col in df.columns:
            col_lower = col.lower()
            for xrd_col in xrd_related_columns:
                if xrd_col.lower() in col_lower:
                    found_xrd_columns.append(col)
                    break
        
        if not found_xrd_columns:
            issues.append("未找到XRD相关的列名")
        
        # 检查数据质量
        missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
        if missing_ratio > 0.5:
            issues.append(f"数据缺失率过高: {missing_ratio:.1%}")
        
        return len(issues) == 0, issues
    
    def validate_for_sn(self) -> Tuple[bool, List[str]]:
        """
        验证数据是否适用于S-N分析
        
        Returns:
            Tuple[bool, List[str]]: (是否有效, 问题列表)
        """
        df = self.get_data()
        issues = []
        
        # 检查基本要求
        if df.empty:
            issues.append("数据为空")
            return False, issues
        
        if len(df) < 3:
            issues.append("S-N分析至少需要3个数据点")
        
        # 检查S-N相关列
        s_columns = ['S', 's', 'stress', 'Stress', 'σ', 'sigma', '应力']
        n_columns = ['N', 'n', 'cycles', 'Cycles', 'Nf', 'life', 'Life', '寿命', '循环']
        
        s_col = None
        n_col = None
        
        for col in df.columns:
            if col in s_columns or any(s_name in col.lower() for s_name in ['stress', 'sigma']):
                s_col = col
            if col in n_columns or any(n_name in col.lower() for n_name in ['cycle', 'life']):
                n_col = col
        
        if not s_col:
            issues.append("未找到应力(S)相关列")
        if not n_col:
            issues.append("未找到寿命(N)相关列")
        
        # 检查数值数据
        if s_col and n_col:
            try:
                s_data = pd.to_numeric(df[s_col], errors='coerce')
                n_data = pd.to_numeric(df[n_col], errors='coerce')
                
                if s_data.isna().all():
                    issues.append(f"应力列 '{s_col}' 不包含有效数值")
                elif (s_data <= 0).any():
                    issues.append(f"应力列 '{s_col}' 包含非正数值")
                
                if n_data.isna().all():
                    issues.append(f"寿命列 '{n_col}' 不包含有效数值")
                elif (n_data <= 0).any():
                    issues.append(f"寿命列 '{n_col}' 包含非正数值")
                    
            except Exception as e:
                issues.append(f"数值验证失败: {str(e)}")
        
        return len(issues) == 0, issues


class MultiSourceDataManager:
    """多数据源管理器"""
    
    def __init__(self):
        """初始化管理器"""
        self.processors: Dict[str, DataProcessor] = {}
    
    def add_source(self, name: str, data_source: DataSource) -> DataProcessor:
        """
        添加数据源
        
        Args:
            name: 数据源名称
            data_source: 数据源实例
            
        Returns:
            DataProcessor: 数据处理器
        """
        processor = DataProcessor(data_source)
        self.processors[name] = processor
        return processor
    
    def add_file_source(self, name: str, file_path: str, **kwargs) -> DataProcessor:
        """
        添加文件数据源
        
        Args:
            name: 数据源名称
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            DataProcessor: 数据处理器
        """
        data_source = create_data_source_from_file(file_path, **kwargs)
        return self.add_source(name, data_source)
    
    def add_database_source(self, name: str, db_type: str, **kwargs) -> DataProcessor:
        """
        添加数据库数据源
        
        Args:
            name: 数据源名称
            db_type: 数据库类型 ('mysql', 'postgresql', 'mongodb')
            **kwargs: 数据库连接参数
            
        Returns:
            DataProcessor: 数据处理器
        """
        data_source = create_data_source(db_type, **kwargs)
        return self.add_source(name, data_source)
    
    def get_processor(self, name: str) -> Optional[DataProcessor]:
        """获取数据处理器"""
        return self.processors.get(name)
    
    def list_sources(self) -> List[str]:
        """列出所有数据源名称"""
        return list(self.processors.keys())
    
    def remove_source(self, name: str) -> bool:
        """移除数据源"""
        if name in self.processors:
            del self.processors[name]
            return True
        return False
    
    def get_all_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源信息"""
        return {
            name: processor.get_data_info()
            for name, processor in self.processors.items()
        }


# 便捷函数
def create_processor_from_file(file_path: str, **kwargs) -> DataProcessor:
    """
    从文件创建数据处理器
    
    Args:
        file_path: 文件路径
        **kwargs: 额外参数
        
    Returns:
        DataProcessor: 数据处理器
    """
    data_source = create_data_source_from_file(file_path, **kwargs)
    return DataProcessor(data_source)


def create_processor_from_dataframe(df: pd.DataFrame, name: str = "DataFrame") -> DataProcessor:
    """
    从DataFrame创建数据处理器
    
    Args:
        df: DataFrame
        name: 名称
        
    Returns:
        DataProcessor: 数据处理器
    """
    data_source = create_data_source('dataframe', dataframe=df, name=name)
    return DataProcessor(data_source)