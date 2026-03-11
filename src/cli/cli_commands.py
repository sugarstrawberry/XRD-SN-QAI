"""
CLI命令实现
包含所有CLI命令的具体实现逻辑
"""

import sys
import os
from typing import Dict, Any, Optional, List

# 获取项目根目录并添加到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))  # 向上两级到pythonProject
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, project_root)

from src.cli.cli_utils import (
    get_database_config, create_evaluation_result,
    validate_file_exists, format_database_query_result, print_progress,
    print_status, handle_cli_error, load_config_file
)

try:
    from src.xrd_analyzer.xrd_evaluator import XRDEvaluator
    from src.sn_analyzer.sn_evaluator import SNEvaluator
    from src.common.data_sources import create_data_source
    from src.common.data_processor import DataProcessor
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保在pythonProject目录下运行CLI")
    print(f"当前目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    sys.exit(1)


class XRDCommands:
    """XRD相关命令"""
    
    def __init__(self):
        self.evaluator = XRDEvaluator("config/xrd_config.yaml")
    
    def evaluate_text(self, text: str, weights: Optional[Dict[str, float]] = None,
                     strictness: str = "标准") -> Dict[str, Any]:
        """评价文本数据"""
        try:
            print_progress("开始XRD文本评价...")
            
            # 使用默认权重或自定义权重
            if weights is None:
                weights = {
                    "信息完整性": 40,
                    "数据规范性": 15,
                    "内容一致性": 10,
                    "过程可追溯性": 20,
                    "智能可用性": 15
                }
            
            # 调用评价器
            result = self.evaluator.evaluate_text(text, weights, 90, 80, 70, strictness)
            
            print_status("XRD文本评价完成", "success")
            return create_evaluation_result(result, "XRD文本评价", "文本输入")
        
        except Exception as e:
            handle_cli_error(e, "XRD文本评价")
    
    def evaluate_file(self, file_path: str, weights: Optional[Dict[str, float]] = None,
                     strictness: str = "标准", enable_uncertainty: bool = True) -> Dict[str, Any]:
        """评价文件数据"""
        try:
            file_path = validate_file_exists(file_path)
            print_progress(f"开始评价文件: {file_path}")
            
            if weights is None:
                weights = {
                    "信息完整性": 40,
                    "数据规范性": 15,
                    "内容一致性": 10,
                    "过程可追溯性": 20,
                    "智能可用性": 15
                }
            
            # 根据文件类型选择评价方法
            if file_path.lower().endswith('.pdf'):
                with open(file_path, 'rb') as f:
                    result = self.evaluator.evaluate_pdf(f, weights, 90, 80, 70, strictness)
            elif file_path.lower().endswith('.json'):
                # JSON文件特殊处理，支持不确定性分析
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                result = self.evaluator.evaluate_json_data(json_data, weights, 90, 80, 70, strictness, enable_uncertainty)
            else:
                result = self.evaluator.evaluate_data_file(file_path, weights, 90, 80, 70, strictness)
            
            print_status("XRD文件评价完成", "success")
            return create_evaluation_result(result, "XRD文件评价", f"文件: {file_path}")
        
        except Exception as e:
            handle_cli_error(e, "XRD文件评价")
    
    def evaluate_json(self, json_data: str, weights: Optional[Dict[str, float]] = None,
                     strictness: str = "标准", enable_uncertainty: bool = True) -> Dict[str, Any]:
        """评价JSON格式的XRD数据"""
        try:
            print_progress("开始XRD JSON数据评价...")
            
            if weights is None:
                weights = {
                    "信息完整性": 40,
                    "数据规范性": 15,
                    "内容一致性": 10,
                    "过程可追溯性": 20,
                    "智能可用性": 15
                }
            
            # 调用评价器的JSON评价方法
            result = self.evaluator.evaluate_json_data(json_data, weights, 90, 80, 70, strictness, enable_uncertainty)
            
            print_status("XRD JSON数据评价完成", "success")
            return create_evaluation_result(result, "XRD JSON数据评价", "JSON输入")
        
        except Exception as e:
            handle_cli_error(e, "XRD JSON数据评价")
    
    def evaluate_database(self, db_type: str, query: Optional[str] = None,
                         table: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """评价数据库数据"""
        try:
            print_progress(f"连接到{db_type}数据库...")
            
            db_config = get_database_config(db_type)
            
            # 构建查询
            if query:
                final_query = query
            elif table:
                final_query = f"SELECT * FROM {table} LIMIT {limit}"
            else:
                # 默认查询
                if db_type.lower() == 'mysql':
                    final_query = f"SELECT * FROM xrd_experiments LIMIT {limit}"
                elif db_type.lower() == 'postgresql':
                    final_query = f"SELECT * FROM xrd_experiments LIMIT {limit}"
                else:
                    raise ValueError("MongoDB需要指定collection参数")
            
            # 创建数据源
            if db_type.lower() == 'mongodb':
                data_source = create_data_source(
                    'mongodb',
                    **db_config,
                    collection=table or 'xrd_experiments',
                    query={}
                )
            else:
                data_source = create_data_source(db_type, **db_config, query=final_query)
            
            processor = DataProcessor(data_source)
            df = processor.get_data()
            
            if df.empty:
                print_status("数据库中没有找到数据", "warning")
                return format_database_query_result([], db_type)
            
            print_status(f"从{db_type}获取到 {len(df)} 条记录", "success")
            
            # 转换为字典列表
            results = df.to_dict('records')
            return format_database_query_result(results, db_type)
        
        except Exception as e:
            handle_cli_error(e, f"{db_type}数据库查询")


class SNCommands:
    """S-N相关命令"""
    
    def __init__(self):
        self.evaluator = SNEvaluator("config/sn_config.yaml")
    
    def evaluate_text(self, text: str, comprehensive: bool = False) -> Dict[str, Any]:
        """评价S-N文本数据"""
        try:
            print_progress("开始S-N文本评价...")
            
            if comprehensive:
                print_status("使用综合评价模式 (LLM + E739)", "info")
                # 这里需要根据实际的综合评价方法调整
                result = self.evaluator.evaluate_text(text)
            else:
                result = self.evaluator.evaluate_text(text)
            
            print_status("S-N文本评价完成", "success")
            eval_type = "S-N综合评价" if comprehensive else "S-N文本评价"
            return create_evaluation_result(result, eval_type, "文本输入")
        
        except Exception as e:
            handle_cli_error(e, "S-N文本评价")
    
    def evaluate_file(self, file_path: str, comprehensive: bool = False) -> Dict[str, Any]:
        """评价S-N文件数据"""
        try:
            file_path = validate_file_exists(file_path)
            print_progress(f"开始评价文件: {file_path}")
            
            if comprehensive:
                print_status("使用综合评价模式 (LLM + E739)", "info")
                # 调用综合分析方法
                with open(file_path, 'rb') as f:
                    filename, data_count, result = self.evaluator.analyze_csv_comprehensive(f, "")
                print_status(f"处理了 {data_count} 个数据点", "info")
            else:
                # 提取文件内容进行文本评价
                extracted_text = self.evaluator.extract_csv_to_text(open(file_path, 'rb'))
                result = self.evaluator.evaluate_text(extracted_text)
            
            print_status("S-N文件评价完成", "success")
            eval_type = "S-N综合评价" if comprehensive else "S-N文件评价"
            return create_evaluation_result(result, eval_type, f"文件: {file_path}")
        
        except Exception as e:
            handle_cli_error(e, "S-N文件评价")
    
    def evaluate_database(self, db_type: str, query: Optional[str] = None,
                         table: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """评价数据库S-N数据"""
        try:
            print_progress(f"连接到{db_type}数据库...")
            
            db_config = get_database_config(db_type)
            
            # 构建查询
            if query:
                final_query = query
            elif table:
                final_query = f"SELECT * FROM {table} LIMIT {limit}"
            else:
                # 默认查询
                if db_type.lower() == 'mysql':
                    final_query = f"SELECT * FROM sn_fatigue_tests LIMIT {limit}"
                elif db_type.lower() == 'postgresql':
                    final_query = f"SELECT * FROM sn_fatigue_tests LIMIT {limit}"
                else:
                    raise ValueError("MongoDB需要指定collection参数")
            
            # 创建数据源
            if db_type.lower() == 'mongodb':
                data_source = create_data_source(
                    'mongodb',
                    **db_config,
                    collection=table or 'fatigue_tests',
                    query={}
                )
            else:
                data_source = create_data_source(db_type, **db_config, query=final_query)
            
            processor = DataProcessor(data_source)
            df = processor.get_data()
            
            if df.empty:
                print_status("数据库中没有找到S-N数据", "warning")
                return format_database_query_result([], db_type)
            
            print_status(f"从{db_type}获取到 {len(df)} 条S-N记录", "success")
            
            # 转换为字典列表
            results = df.to_dict('records')
            return format_database_query_result(results, db_type)
        
        except Exception as e:
            handle_cli_error(e, f"{db_type} S-N数据库查询")


class ConfigCommands:
    """配置管理命令"""
    
    def show_config(self, config_type: str = "xrd") -> Dict[str, Any]:
        """显示当前配置"""
        try:
            if config_type.lower() == "xrd":
                config_path = "config/xrd_config.yaml"
            elif config_type.lower() == "sn":
                config_path = "config/sn_config.yaml"
            else:
                raise ValueError("配置类型必须是 'xrd' 或 'sn'")
            
            config = load_config_file(config_path)
            
            return {
                'config_type': config_type.upper(),
                'config_path': config_path,
                'config_data': config,
                'timestamp': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        except Exception as e:
            handle_cli_error(e, "显示配置")


class DatabaseCommands:
    """数据库管理命令"""
    
    def test_connection(self, db_type: str = "all") -> Dict[str, Any]:
        """测试数据库连接"""
        try:
            results = {}
            
            if db_type.lower() == "all":
                db_types = ["mysql", "postgresql", "mongodb"]
            else:
                db_types = [db_type.lower()]
            
            for db in db_types:
                print_progress(f"测试{db}连接...")
                try:
                    config = get_database_config(db)
                    
                    if db == "mongodb":
                        data_source = create_data_source(
                            'mongodb',
                            **config,
                            collection='test',
                            query={}
                        )
                    else:
                        data_source = create_data_source(
                            db,
                            **config,
                            query="SELECT 1 as test"
                        )
                    
                    processor = DataProcessor(data_source)
                    if processor.data_source.validate_connection():
                        results[db] = {"status": "success", "message": "连接成功"}
                        print_status(f"{db}连接成功", "success")
                    else:
                        results[db] = {"status": "failed", "message": "连接失败"}
                        print_status(f"{db}连接失败", "error")
                
                except Exception as e:
                    results[db] = {"status": "error", "message": str(e)}
                    print_status(f"{db}连接错误: {e}", "error")
            
            return {
                'test_type': 'database_connection',
                'results': results,
                'timestamp': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        except Exception as e:
            handle_cli_error(e, "数据库连接测试")
    
    def query_database(self, db_type: str, query: str, limit: int = 100) -> Dict[str, Any]:
        """查询数据库"""
        try:
            print_progress(f"执行{db_type}查询...")
            
            config = get_database_config(db_type)
            
            if db_type.lower() == "mongodb":
                # MongoDB查询需要特殊处理
                import json
                try:
                    query_dict = json.loads(query)
                except:
                    query_dict = {}
                
                data_source = create_data_source(
                    'mongodb',
                    **config,
                    collection='xrd_experiments',  # 默认集合
                    query=query_dict
                )
            else:
                # 添加LIMIT限制
                if "LIMIT" not in query.upper():
                    query += f" LIMIT {limit}"
                
                data_source = create_data_source(db_type, **config, query=query)
            
            processor = DataProcessor(data_source)
            df = processor.get_data()
            
            print_status(f"查询完成，返回 {len(df)} 条记录", "success")
            
            results = df.to_dict('records')
            return format_database_query_result(results, db_type)
        
        except Exception as e:
            handle_cli_error(e, f"{db_type}数据库查询")