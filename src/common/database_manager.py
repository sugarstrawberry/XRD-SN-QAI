"""
数据库连接管理器
简化数据库连接和查询操作
"""

import yaml
import os
from typing import Dict, Any, Optional, List
from .data_sources import create_data_source, DataSource
from .data_processor import DataProcessor


class DatabaseManager:
    """数据库连接管理器"""
    
    def __init__(self, config_path: str = "config/database_config.yaml"):
        """
        初始化数据库管理器
        
        Args:
            config_path: 数据库配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._connections = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """加载数据库配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 处理环境变量
            self._resolve_environment_variables(config)
            return config
        except FileNotFoundError:
            print(f"警告: 数据库配置文件未找到: {self.config_path}")
            return {}
        except Exception as e:
            print(f"加载数据库配置失败: {e}")
            return {}
    
    def _resolve_environment_variables(self, config: Dict[str, Any]):
        """解析配置中的环境变量"""
        def resolve_value(value):
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                return os.getenv(env_var, value)
            elif isinstance(value, dict):
                for k, v in value.items():
                    value[k] = resolve_value(v)
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value
        
        for key, value in config.items():
            config[key] = resolve_value(value)
    
    def get_mysql_source(self, environment: str = 'development', 
                        query: str = None, table: str = None) -> DataSource:
        """
        获取MySQL数据源
        
        Args:
            environment: 环境名称 ('development' 或 'production')
            query: SQL查询语句
            table: 表名（如果不使用query）
            
        Returns:
            DataSource: MySQL数据源
        """
        mysql_config = self.config.get('mysql', {}).get(environment, {})
        
        if not mysql_config:
            raise ValueError(f"MySQL {environment} 环境配置未找到")
        
        return create_data_source(
            'mysql',
            host=mysql_config['host'],
            port=mysql_config['port'],
            database=mysql_config['database'],
            user=mysql_config['user'],
            password=mysql_config['password'],
            query=query,
            table=table
        )
    
    def get_postgresql_source(self, environment: str = 'development',
                            query: str = None, table: str = None) -> DataSource:
        """
        获取PostgreSQL数据源
        
        Args:
            environment: 环境名称
            query: SQL查询语句
            table: 表名
            
        Returns:
            DataSource: PostgreSQL数据源
        """
        pg_config = self.config.get('postgresql', {}).get(environment, {})
        
        if not pg_config:
            raise ValueError(f"PostgreSQL {environment} 环境配置未找到")
        
        return create_data_source(
            'postgresql',
            host=pg_config['host'],
            port=pg_config['port'],
            database=pg_config['database'],
            user=pg_config['user'],
            password=pg_config['password'],
            query=query,
            table=table
        )
    
    def get_mongodb_source(self, environment: str = 'development',
                          collection: str = None, query: Dict = None) -> DataSource:
        """
        获取MongoDB数据源
        
        Args:
            environment: 环境名称
            collection: 集合名称
            query: MongoDB查询条件
            
        Returns:
            DataSource: MongoDB数据源
        """
        mongo_config = self.config.get('mongodb', {}).get(environment, {})
        
        if not mongo_config:
            raise ValueError(f"MongoDB {environment} 环境配置未找到")
        
        return create_data_source(
            'mongodb',
            host=mongo_config['host'],
            port=mongo_config['port'],
            database=mongo_config['database'],
            username=mongo_config.get('username'),
            password=mongo_config.get('password'),
            collection=collection,
            query=query or {}
        )
    
    def get_xrd_data(self, environment: str = 'development', 
                    date_from: str = None, material_filter: str = None) -> DataProcessor:
        """
        获取XRD数据处理器
        
        Args:
            environment: 环境名称
            date_from: 起始日期 (YYYY-MM-DD)
            material_filter: 材料过滤条件
            
        Returns:
            DataProcessor: 数据处理器
        """
        # 根据配置的优先级尝试不同数据源
        xrd_sources = self.config.get('data_source_mapping', {}).get('xrd_sources', [])
        
        for source_config in sorted(xrd_sources, key=lambda x: x['priority']):
            try:
                db_type = source_config['type']
                env = source_config.get('environment', environment)
                
                if db_type == 'postgresql':
                    query_template = self.config['postgresql']['queries']['xrd_with_joins']
                    query = query_template.replace('$1', f"'{date_from or '2024-01-01'}'")
                    
                    if material_filter:
                        query += f" AND s.material_composition ILIKE '%{material_filter}%'"
                    
                    data_source = self.get_postgresql_source(env, query=query)
                    
                elif db_type == 'mysql':
                    query_template = self.config['mysql']['queries']['xrd_experiments']
                    query = query_template % f"'{date_from or '2024-01-01'}'"
                    
                    if material_filter:
                        query += f" AND material_composition LIKE '%{material_filter}%'"
                    
                    data_source = self.get_mysql_source(env, query=query)
                    
                elif db_type == 'mongodb':
                    mongo_query = {
                        "experiment_date": {"$gte": date_from or "2024-01-01"},
                        "status": "approved"
                    }
                    
                    if material_filter:
                        mongo_query["sample.composition"] = {
                            "$regex": material_filter, "$options": "i"
                        }
                    
                    data_source = self.get_mongodb_source(
                        env, 
                        collection='xrd_experiments',
                        query=mongo_query
                    )
                
                # 测试连接
                processor = DataProcessor(data_source)
                if processor.data_source.validate_connection():
                    print(f"✅ 成功连接到 {db_type} ({env})")
                    return processor
                
            except Exception as e:
                print(f"❌ {db_type} ({env}) 连接失败: {e}")
                continue
        
        raise Exception("所有XRD数据源连接失败")
    
    def get_sn_data(self, environment: str = 'development',
                   material_type: str = None, min_stress: float = None) -> DataProcessor:
        """
        获取S-N疲劳数据处理器
        
        Args:
            environment: 环境名称
            material_type: 材料类型过滤
            min_stress: 最小应力值
            
        Returns:
            DataProcessor: 数据处理器
        """
        sn_sources = self.config.get('data_source_mapping', {}).get('sn_sources', [])
        
        for source_config in sorted(sn_sources, key=lambda x: x['priority']):
            try:
                db_type = source_config['type']
                env = source_config.get('environment', environment)
                
                if db_type == 'postgresql':
                    query = self.config['postgresql']['queries']['fatigue_analysis']
                    
                    conditions = []
                    if material_type:
                        conditions.append(f"m.material_name ILIKE '%{material_type}%'")
                    if min_stress:
                        conditions.append(f"ft.stress_amplitude >= {min_stress}")
                    
                    if conditions:
                        query += " AND " + " AND ".join(conditions)
                    
                    data_source = self.get_postgresql_source(env, query=query)
                    
                elif db_type == 'mysql':
                    query = self.config['mysql']['queries']['sn_fatigue_data']
                    
                    conditions = []
                    if material_type:
                        conditions.append(f"material_type LIKE '%{material_type}%'")
                    if min_stress:
                        conditions.append(f"stress_amplitude >= {min_stress}")
                    
                    if conditions:
                        query += " AND " + " AND ".join(conditions)
                    
                    data_source = self.get_mysql_source(env, query=query)
                    
                elif db_type == 'mongodb':
                    mongo_query = {
                        "test_status": "completed",
                        "results.stress_amplitude": {"$gt": 0},
                        "results.cycles_to_failure": {"$gt": 0}
                    }
                    
                    if material_type:
                        mongo_query["material.type"] = {
                            "$regex": material_type, "$options": "i"
                        }
                    if min_stress:
                        mongo_query["results.stress_amplitude"]["$gte"] = min_stress
                    
                    data_source = self.get_mongodb_source(
                        env,
                        collection='fatigue_tests',
                        query=mongo_query
                    )
                
                # 测试连接
                processor = DataProcessor(data_source)
                if processor.data_source.validate_connection():
                    print(f"✅ 成功连接到 {db_type} ({env})")
                    return processor
                
            except Exception as e:
                print(f"❌ {db_type} ({env}) 连接失败: {e}")
                continue
        
        raise Exception("所有S-N数据源连接失败")
    
    def test_all_connections(self) -> Dict[str, Dict[str, bool]]:
        """
        测试所有数据库连接
        
        Returns:
            Dict: 连接测试结果
        """
        results = {}
        
        # 测试MySQL连接
        results['mysql'] = {}
        for env in ['development', 'production']:
            try:
                source = self.get_mysql_source(env, table='information_schema.tables')
                processor = DataProcessor(source)
                results['mysql'][env] = processor.data_source.validate_connection()
            except Exception as e:
                results['mysql'][env] = False
                print(f"MySQL {env}: {e}")
        
        # 测试PostgreSQL连接
        results['postgresql'] = {}
        for env in ['development', 'production']:
            try:
                source = self.get_postgresql_source(env, table='information_schema.tables')
                processor = DataProcessor(source)
                results['postgresql'][env] = processor.data_source.validate_connection()
            except Exception as e:
                results['postgresql'][env] = False
                print(f"PostgreSQL {env}: {e}")
        
        # 测试MongoDB连接
        results['mongodb'] = {}
        for env in ['development', 'production']:
            try:
                source = self.get_mongodb_source(env, collection='test', query={})
                processor = DataProcessor(source)
                results['mongodb'][env] = processor.data_source.validate_connection()
            except Exception as e:
                results['mongodb'][env] = False
                print(f"MongoDB {env}: {e}")
        
        return results


# 便捷函数
def get_database_manager(config_path: str = "config/database_config.yaml") -> DatabaseManager:
    """获取数据库管理器实例"""
    return DatabaseManager(config_path)