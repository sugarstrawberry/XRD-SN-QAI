"""
CLI工具函数
提供通用的CLI辅助功能
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    current_file = Path(__file__).resolve()
    # 从 src/cli/cli_utils.py 向上找到项目根目录
    return current_file.parent.parent.parent


def add_src_to_path():
    """将src目录添加到Python路径"""
    project_root = get_project_root()
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def load_config_file(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    try:
        project_root = get_project_root()
        full_path = project_root / config_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {full_path}")
        
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            import yaml
            with open(full_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        elif config_path.endswith('.json'):
            with open(full_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path}")
    
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        sys.exit(1)


def save_output(data: str, output_path: Optional[str] = None):
    """保存输出到文件或标准输出"""
    if output_path:
        try:
            project_root = get_project_root()
            if not os.path.isabs(output_path):
                output_path = project_root / output_path
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(data)
            print(f"结果已保存到: {output_path}")
        except Exception as e:
            print(f"保存文件失败: {e}")
            sys.exit(1)
    else:
        print(data)


def validate_file_exists(file_path: str) -> str:
    """验证文件是否存在"""
    project_root = get_project_root()
    
    if not os.path.isabs(file_path):
        full_path = project_root / file_path
    else:
        full_path = Path(file_path)
    
    if not full_path.exists():
        raise FileNotFoundError(f"文件不存在: {full_path}")
    
    return str(full_path)


def get_database_config(db_type: str) -> Dict[str, Any]:
    """获取数据库配置"""
    configs = {
        'mysql': {
            'host': 'localhost',
            'port': 3306,
            'database': 'xrd_lab',
            'user': 'root',
            'password': '1234'
        },
        'postgresql': {
            'host': 'localhost',
            'port': 5432,
            'database': 'materials_lab_dev',
            'user': 'postgres',
            'password': '1234'
        },
        'mongodb': {
            'host': 'localhost',
            'port': 27017,
            'database': 'materials_mongo_dev',
            'username': None,
            'password': None
        }
    }
    
    if db_type.lower() not in configs:
        raise ValueError(f"不支持的数据库类型: {db_type}")
    
    return configs[db_type.lower()]


def create_evaluation_result(evaluator_result: str, eval_type: str, data_source: str = "文本输入") -> Dict[str, Any]:
    """创建标准化的评价结果"""
    try:
        # 尝试解析评价器返回的结果
        # 这里需要根据实际的评价器输出格式进行调整
        result = {
            'evaluation_type': eval_type,
            'data_source': data_source,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'raw_result': evaluator_result
        }
        
        # 尝试从结果中提取结构化信息
        if '总分' in evaluator_result:
            # 简单的分数提取逻辑
            lines = evaluator_result.split('\n')
            for line in lines:
                if '总分' in line:
                    try:
                        score_part = line.split('总分')[1].strip()
                        score = float(score_part.split()[0].replace(':', ''))
                        result['total_score'] = score
                        
                        # 等级判定
                        if score >= 90:
                            result['grade'] = 'A'
                        elif score >= 80:
                            result['grade'] = 'B'
                        elif score >= 70:
                            result['grade'] = 'C'
                        else:
                            result['grade'] = 'D'
                        break
                    except:
                        pass
        
        return result
    
    except Exception as e:
        return {
            'evaluation_type': eval_type,
            'data_source': data_source,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': str(e),
            'raw_result': evaluator_result
        }


def parse_weights_string(weights_str: str) -> Dict[str, float]:
    """解析权重字符串"""
    weights = {}
    try:
        pairs = weights_str.split(',')
        for pair in pairs:
            key, value = pair.split('=')
            weights[key.strip()] = float(value.strip())
        return weights
    except Exception as e:
        raise ValueError(f"权重格式错误: {e}")


def format_database_query_result(results: list, db_type: str) -> Dict[str, Any]:
    """格式化数据库查询结果"""
    return {
        'database_type': db_type,
        'record_count': len(results),
        'database_results': results,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def print_progress(message: str):
    """打印进度信息"""
    print(f"{message}")


def print_status(message: str, status: str = "info"):
    """打印状态信息"""
    icons = {
        'info': 'ℹ️ ',
        'success': '✅',
        'warning': '⚠️ ',
        'error': '❌'
    }
    icon = icons.get(status, 'ℹ️ ')
    print(f"{icon} {message}")


def handle_cli_error(error: Exception, context: str = ""):
    """处理CLI错误"""
    error_msg = f"{context}: {str(error)}" if context else str(error)
    print(f"❌ {error_msg}")
    sys.exit(1)