"""
统一数据源模块
支持 CSV, Excel, MySQL, PostgreSQL, MongoDB, DataFrame 等多种数据源
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
import os
import json
import io


class DataSource(ABC):
    """数据源抽象基类"""
    
    def __init__(self, **kwargs):
        self.config = kwargs
        self.connection = None
    
    @abstractmethod
    def read_data(self) -> pd.DataFrame:
        """读取数据并返回DataFrame"""
        pass
    
    @abstractmethod
    def get_source_info(self) -> str:
        """获取数据源信息"""
        pass
    
    def validate_connection(self) -> bool:
        """验证连接是否有效"""
        try:
            df = self.read_data()
            return not df.empty
        except Exception:
            return False
    
    def get_data_preview(self, n_rows: int = 5) -> pd.DataFrame:
        """获取数据预览"""
        df = self.read_data()
        return df.head(n_rows)
    
    def get_data_info(self) -> Dict[str, Any]:
        """获取数据基本信息"""
        df = self.read_data()
        return {
            'shape': df.shape,
            'columns': df.columns.tolist(),
            'dtypes': df.dtypes.to_dict(),
            'missing_values': df.isnull().sum().to_dict(),
            'memory_usage': df.memory_usage(deep=True).sum()
        }


class CSVDataSource(DataSource):
    """CSV文件数据源"""
    
    def __init__(self, file_path: str, encoding: str = 'utf-8', **kwargs):
        super().__init__(file_path=file_path, encoding=encoding, **kwargs)
        self.file_path = file_path
        self.encoding = encoding
        self.csv_kwargs = kwargs
    
    def read_data(self) -> pd.DataFrame:
        """读取CSV文件"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"CSV文件不存在: {self.file_path}")
        
        try:
            df = pd.read_csv(self.file_path, encoding=self.encoding, **self.csv_kwargs)
            # 清理列名
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            raise ValueError(f"读取CSV文件失败: {str(e)}")
    
    def get_source_info(self) -> str:
        return f"CSV文件: {self.file_path} (编码: {self.encoding})"


class ExcelDataSource(DataSource):
    """Excel文件数据源"""
    
    def __init__(self, file_path: str, sheet_name: Union[str, int] = 0, **kwargs):
        super().__init__(file_path=file_path, sheet_name=sheet_name, **kwargs)
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.excel_kwargs = kwargs
    
    def read_data(self) -> pd.DataFrame:
        """读取Excel文件"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Excel文件不存在: {self.file_path}")
        
        try:
            df = pd.read_excel(self.file_path, sheet_name=self.sheet_name, **self.excel_kwargs)
            # 清理列名
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            raise ValueError(f"读取Excel文件失败: {str(e)}")
    
    def get_source_info(self) -> str:
        return f"Excel文件: {self.file_path} (工作表: {self.sheet_name})"


class MySQLDataSource(DataSource):
    """MySQL数据库数据源"""
    
    def __init__(self, host: str, database: str, user: str, password: str, 
                 port: int = 3306, query: str = None, table: str = None, **kwargs):
        super().__init__(host=host, database=database, user=user, password=password,
                        port=port, query=query, table=table, **kwargs)
        self.connection_params = {
            'host': host,
            'database': database, 
            'user': user,
            'password': password,
            'port': port
        }
        self.query = query
        self.table = table
    
    def _get_connection_string(self) -> str:
        """获取MySQL连接字符串"""
        return f"mysql+pymysql://{self.connection_params['user']}:{self.connection_params['password']}@{self.connection_params['host']}:{self.connection_params['port']}/{self.connection_params['database']}"
    
    def read_data(self) -> pd.DataFrame:
        """从MySQL读取数据"""
        try:
            import sqlalchemy
            from sqlalchemy import create_engine
        except ImportError:
            raise ImportError("需要安装 sqlalchemy 和 pymysql: pip install sqlalchemy pymysql")
        
        try:
            engine = create_engine(self._get_connection_string())
            
            if self.query:
                df = pd.read_sql(self.query, engine)
            elif self.table:
                df = pd.read_sql(f"SELECT * FROM {self.table}", engine)
            else:
                raise ValueError("必须提供 query 或 table 参数")
            
            engine.dispose()
            return df
        except Exception as e:
            raise ValueError(f"从MySQL读取数据失败: {str(e)}")
    
    def get_source_info(self) -> str:
        return f"MySQL: {self.connection_params['host']}:{self.connection_params['port']}/{self.connection_params['database']}"


class PostgreSQLDataSource(DataSource):
    """PostgreSQL数据库数据源"""
    
    def __init__(self, host: str, database: str, user: str, password: str,
                 port: int = 5432, query: str = None, table: str = None, **kwargs):
        super().__init__(host=host, database=database, user=user, password=password,
                        port=port, query=query, table=table, **kwargs)
        self.connection_params = {
            'host': host,
            'database': database,
            'user': user, 
            'password': password,
            'port': port
        }
        self.query = query
        self.table = table
    
    def _get_connection_string(self) -> str:
        """获取PostgreSQL连接字符串"""
        return f"postgresql://{self.connection_params['user']}:{self.connection_params['password']}@{self.connection_params['host']}:{self.connection_params['port']}/{self.connection_params['database']}"
    
    def read_data(self) -> pd.DataFrame:
        """从PostgreSQL读取数据"""
        try:
            import sqlalchemy
            from sqlalchemy import create_engine
        except ImportError:
            raise ImportError("需要安装 sqlalchemy 和 psycopg2: pip install sqlalchemy psycopg2-binary")
        
        try:
            engine = create_engine(self._get_connection_string())
            
            if self.query:
                df = pd.read_sql(self.query, engine)
            elif self.table:
                df = pd.read_sql(f"SELECT * FROM {self.table}", engine)
            else:
                raise ValueError("必须提供 query 或 table 参数")
            
            engine.dispose()
            return df
        except Exception as e:
            raise ValueError(f"从PostgreSQL读取数据失败: {str(e)}")
    
    def get_source_info(self) -> str:
        return f"PostgreSQL: {self.connection_params['host']}:{self.connection_params['port']}/{self.connection_params['database']}"


class MongoDBDataSource(DataSource):
    """MongoDB数据库数据源"""
    
    def __init__(self, host: str = 'localhost', port: int = 27017, database: str = None,
                 collection: str = None, query: Dict = None, username: str = None, 
                 password: str = None, **kwargs):
        super().__init__(host=host, port=port, database=database, collection=collection,
                        query=query, username=username, password=password, **kwargs)
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'collection': collection,
            'username': username,
            'password': password
        }
        self.query = query or {}
    
    def read_data(self) -> pd.DataFrame:
        """从MongoDB读取数据"""
        try:
            import pymongo
        except ImportError:
            raise ImportError("需要安装 pymongo: pip install pymongo")
        
        try:
            # 构建连接字符串
            if self.connection_params['username'] and self.connection_params['password']:
                connection_string = f"mongodb://{self.connection_params['username']}:{self.connection_params['password']}@{self.connection_params['host']}:{self.connection_params['port']}"
            else:
                connection_string = f"mongodb://{self.connection_params['host']}:{self.connection_params['port']}"
            
            client = pymongo.MongoClient(connection_string)
            db = client[self.connection_params['database']]
            collection = db[self.connection_params['collection']]
            
            # 查询数据
            cursor = collection.find(self.query)
            data = list(cursor)
            
            client.close()
            
            if not data:
                return pd.DataFrame()
            
            # 安全地转换为DataFrame，处理数组字段
            df = self._safe_normalize_data(data)
            return df
        except Exception as e:
            raise ValueError(f"从MongoDB读取数据失败: {str(e)}")
    
    def _safe_normalize_data(self, data: List[Dict]) -> pd.DataFrame:
        """安全地将MongoDB数据转换为DataFrame，处理数组字段"""
        try:
            # 检查是否是S-N疲劳数据格式（包含sn_data数组）
            if data and 'sn_data' in data[0]:
                # 展开S-N数据
                expanded_data = []
                for doc in data:
                    if 'sn_data' in doc and isinstance(doc['sn_data'], list):
                        for sn_point in doc['sn_data']:
                            # 创建扁平化的记录
                            flat_record = {
                                'test_id': doc.get('test_id', ''),
                                'material_type': doc.get('material', {}).get('type', ''),
                                'material_name': doc.get('material', {}).get('name', ''),
                                'test_status': doc.get('test_status', ''),
                                'S': sn_point.get('stress_amplitude_mpa', 0),
                                'N': sn_point.get('cycles_to_failure', 0),
                                'data_point_id': sn_point.get('data_point_id', ''),
                                'note': sn_point.get('note', ''),
                                'test_type': doc.get('test_conditions', {}).get('test_type', ''),
                                'frequency_hz': doc.get('test_conditions', {}).get('frequency_hz', 0),
                                'temperature_c': doc.get('test_conditions', {}).get('temperature_c', 0)
                            }
                            expanded_data.append(flat_record)
                
                if expanded_data:
                    return pd.DataFrame(expanded_data)
            
            # 首先尝试直接转换
            df = pd.json_normalize(data)
            
            # 检查是否有数组列需要特殊处理
            for col in df.columns:
                if df[col].dtype == 'object':
                    # 检查是否包含数组
                    sample_values = df[col].dropna().head(5)
                    if len(sample_values) > 0:
                        first_val = sample_values.iloc[0]
                        if isinstance(first_val, (list, np.ndarray)):
                            # 将数组转换为字符串表示
                            df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (list, np.ndarray)) else x)
            
            return df
            
        except Exception as e:
            # 如果json_normalize失败，使用更安全的方法
            print(f"警告: json_normalize失败，使用备用方法: {e}")
            return self._manual_normalize_data(data)
    
    def _manual_normalize_data(self, data: List[Dict]) -> pd.DataFrame:
        """手动规范化MongoDB数据"""
        if not data:
            return pd.DataFrame()
        
        # 收集所有可能的列
        all_keys = set()
        for doc in data:
            all_keys.update(self._flatten_keys(doc))
        
        # 创建DataFrame
        rows = []
        for doc in data:
            row = {}
            flattened = self._flatten_dict(doc)
            for key in all_keys:
                value = flattened.get(key)
                # 将复杂对象转换为字符串
                if isinstance(value, (list, dict, np.ndarray)):
                    value = str(value)
                row[key] = value
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        """扁平化嵌套字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _flatten_keys(self, d: Dict, parent_key: str = '', sep: str = '.') -> set:
        """获取扁平化后的所有键"""
        keys = set()
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                keys.update(self._flatten_keys(v, new_key, sep=sep))
            else:
                keys.add(new_key)
        return keys
    
    def get_source_info(self) -> str:
        return f"MongoDB: {self.connection_params['host']}:{self.connection_params['port']}/{self.connection_params['database']}.{self.connection_params['collection']}"


class DataFrameDataSource(DataSource):
    """DataFrame数据源"""
    
    def __init__(self, dataframe: pd.DataFrame, name: str = "DataFrame", **kwargs):
        super().__init__(dataframe=dataframe, name=name, **kwargs)
        self.dataframe = dataframe.copy()
        self.name = name
    
    def read_data(self) -> pd.DataFrame:
        """返回DataFrame副本"""
        return self.dataframe.copy()
    
    def get_source_info(self) -> str:
        return f"DataFrame: {self.name} (形状: {self.dataframe.shape})"


class JSONDataSource(DataSource):
    """JSON文件数据源"""
    
    def __init__(self, file_path: str = None, json_data: Union[str, Dict, List] = None, **kwargs):
        super().__init__(file_path=file_path, json_data=json_data, **kwargs)
        self.file_path = file_path
        self.json_data = json_data
    
    def read_data(self) -> pd.DataFrame:
        """读取JSON数据"""
        try:
            if self.file_path:
                if not os.path.exists(self.file_path):
                    raise FileNotFoundError(f"JSON文件不存在: {self.file_path}")
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif self.json_data:
                if isinstance(self.json_data, str):
                    data = json.loads(self.json_data)
                else:
                    data = self.json_data
            else:
                raise ValueError("必须提供 file_path 或 json_data")
            
            # 转换为DataFrame
            if isinstance(data, list):
                df = pd.json_normalize(data)
            elif isinstance(data, dict):
                df = pd.json_normalize([data])
            else:
                raise ValueError("JSON数据格式不支持")
            
            return df
        except Exception as e:
            raise ValueError(f"读取JSON数据失败: {str(e)}")
    
    def get_source_info(self) -> str:
        if self.file_path:
            return f"JSON文件: {self.file_path}"
        else:
            return "JSON数据 (内存)"


# 工厂函数
def create_data_source(source_type: str, **kwargs) -> DataSource:
    """
    数据源工厂函数
    
    Args:
        source_type: 数据源类型 ('csv', 'excel', 'mysql', 'postgresql', 'mongodb', 'dataframe', 'json')
        **kwargs: 数据源特定参数
        
    Returns:
        DataSource: 数据源实例
    """
    source_map = {
        'csv': CSVDataSource,
        'excel': ExcelDataSource,
        'mysql': MySQLDataSource,
        'postgresql': PostgreSQLDataSource,
        'mongodb': MongoDBDataSource,
        'dataframe': DataFrameDataSource,
        'json': JSONDataSource
    }
    
    if source_type.lower() not in source_map:
        raise ValueError(f"不支持的数据源类型: {source_type}. 支持的类型: {list(source_map.keys())}")
    
    return source_map[source_type.lower()](**kwargs)


def detect_data_source_type(file_path: str) -> str:
    """
    根据文件路径自动检测数据源类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 数据源类型
    """
    if not isinstance(file_path, str):
        return 'unknown'
    
    file_path_lower = file_path.lower()
    
    if file_path_lower.endswith('.csv'):
        return 'csv'
    elif file_path_lower.endswith(('.xls', '.xlsx')):
        return 'excel'
    elif file_path_lower.endswith('.json'):
        return 'json'
    else:
        return 'unknown'


def create_data_source_from_file(file_path: str, **kwargs) -> DataSource:
    """
    根据文件路径自动创建数据源
    
    Args:
        file_path: 文件路径
        **kwargs: 额外参数
        
    Returns:
        DataSource: 数据源实例
    """
    source_type = detect_data_source_type(file_path)
    
    if source_type == 'unknown':
        raise ValueError(f"无法识别文件类型: {file_path}")
    
    return create_data_source(source_type, file_path=file_path, **kwargs)