"""
CLI参数解析器
使用argparse构建命令行接口
"""

import argparse
import sys
import os
from typing import Dict, Any

# 获取项目根目录并添加到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))  # 向上两级到pythonProject
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, project_root)

from src.cli.cli_commands import XRDCommands, SNCommands, ConfigCommands, DatabaseCommands
from src.cli.output_formatter import format_output
from src.cli.cli_utils import save_output, parse_weights_string, handle_cli_error


def create_parser() -> argparse.ArgumentParser:
    """创建主命令解析器"""
    parser = argparse.ArgumentParser(
        prog='材料数据质量评价系统CLI',
        description='材料数据质量评价系统的命令行接口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python cli.py xrd evaluate --text "样品信息：Al2O3..."
  python cli.py sn evaluate --file data.csv --comprehensive
  python cli.py db test --mysql
  python cli.py config show --type xrd
        """
    )
    
    # 全局参数
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'table', 'csv', 'report'],
        default='table',
        help='输出格式 (默认: table)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='输出文件路径 (默认: 标准输出)'
    )
    
    # 创建子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # XRD命令
    create_xrd_parser(subparsers)
    
    # S-N命令
    create_sn_parser(subparsers)
    
    # 配置命令
    create_config_parser(subparsers)
    
    # 数据库命令
    create_db_parser(subparsers)
    
    return parser


def create_xrd_parser(subparsers):
    """创建XRD命令解析器"""
    xrd_parser = subparsers.add_parser('xrd', help='XRD数据评价命令')
    xrd_subparsers = xrd_parser.add_subparsers(dest='xrd_action', help='XRD操作')
    
    # XRD evaluate命令
    evaluate_parser = xrd_subparsers.add_parser('evaluate', help='评价XRD数据')
    
    # 数据源选择（互斥）
    data_group = evaluate_parser.add_mutually_exclusive_group(required=True)
    data_group.add_argument('--text', help='要评价的文本数据')
    data_group.add_argument('--file', help='要评价的文件路径')
    data_group.add_argument('--json', help='JSON格式的XRD数据')
    data_group.add_argument('--database', choices=['mysql', 'postgresql', 'mongodb'], help='数据库类型')
    
    # 数据库相关参数
    evaluate_parser.add_argument('--query', help='自定义数据库查询语句')
    evaluate_parser.add_argument('--table', help='数据库表名或MongoDB集合名')
    evaluate_parser.add_argument('--limit', type=int, default=10, help='数据库查询限制条数')
    
    # 评价参数
    evaluate_parser.add_argument(
        '--weights',
        help='自定义权重 (格式: "信息完整性=40,数据规范性=15")'
    )
    evaluate_parser.add_argument(
        '--strictness',
        choices=['宽松', '标准', '严格', '科研级'],
        default='标准',
        help='评价严格度'
    )
    
    # 不确定性分析参数
    evaluate_parser.add_argument(
        '--no-uncertainty',
        action='store_true',
        help='禁用不确定性分析 (仅对JSON数据有效)'
    )


def create_sn_parser(subparsers):
    """创建S-N命令解析器"""
    sn_parser = subparsers.add_parser('sn', help='S-N疲劳数据评价命令')
    sn_subparsers = sn_parser.add_subparsers(dest='sn_action', help='S-N操作')
    
    # S-N evaluate命令
    evaluate_parser = sn_subparsers.add_parser('evaluate', help='评价S-N数据')
    
    # 数据源选择（互斥）
    data_group = evaluate_parser.add_mutually_exclusive_group(required=True)
    data_group.add_argument('--text', help='要评价的文本数据')
    data_group.add_argument('--file', help='要评价的文件路径')
    data_group.add_argument('--database', choices=['mysql', 'postgresql', 'mongodb'], help='数据库类型')
    
    # 数据库相关参数
    evaluate_parser.add_argument('--query', help='自定义数据库查询语句')
    evaluate_parser.add_argument('--table', help='数据库表名或MongoDB集合名')
    evaluate_parser.add_argument('--limit', type=int, default=10, help='数据库查询限制条数')
    
    # S-N特有参数
    evaluate_parser.add_argument(
        '--comprehensive',
        action='store_true',
        help='使用综合评价模式 (LLM + E739统计分析)'
    )


def create_config_parser(subparsers):
    """创建配置命令解析器"""
    config_parser = subparsers.add_parser('config', help='配置管理命令')
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='配置操作')
    
    # config show命令
    show_parser = config_subparsers.add_parser('show', help='显示当前配置')
    show_parser.add_argument(
        '--type',
        choices=['xrd', 'sn'],
        default='xrd',
        help='配置类型'
    )


def create_db_parser(subparsers):
    """创建数据库命令解析器"""
    db_parser = subparsers.add_parser('db', help='数据库管理命令')
    db_subparsers = db_parser.add_subparsers(dest='db_action', help='数据库操作')
    
    # db test命令
    test_parser = db_subparsers.add_parser('test', help='测试数据库连接')
    test_group = test_parser.add_mutually_exclusive_group()
    test_group.add_argument('--all', action='store_true', help='测试所有数据库')
    test_group.add_argument('--mysql', action='store_true', help='测试MySQL')
    test_group.add_argument('--postgresql', action='store_true', help='测试PostgreSQL')
    test_group.add_argument('--mongodb', action='store_true', help='测试MongoDB')
    
    # db query命令
    query_parser = db_subparsers.add_parser('query', help='查询数据库')
    query_parser.add_argument(
        'database',
        choices=['mysql', 'postgresql', 'mongodb'],
        help='数据库类型'
    )
    query_parser.add_argument('query', help='查询语句')
    query_parser.add_argument('--limit', type=int, default=100, help='结果限制条数')


def execute_command(args) -> Dict[str, Any]:
    """执行命令并返回结果"""
    try:
        if args.command == 'xrd':
            return execute_xrd_command(args)
        elif args.command == 'sn':
            return execute_sn_command(args)
        elif args.command == 'config':
            return execute_config_command(args)
        elif args.command == 'db':
            return execute_db_command(args)
        else:
            raise ValueError(f"未知命令: {args.command}")
    
    except Exception as e:
        handle_cli_error(e, "命令执行")


def execute_xrd_command(args) -> Dict[str, Any]:
    """执行XRD命令"""
    xrd_commands = XRDCommands()
    
    if args.xrd_action == 'evaluate':
        # 解析权重
        weights = None
        if args.weights:
            weights = parse_weights_string(args.weights)
        
        # 确定是否启用不确定性分析
        enable_uncertainty = not args.no_uncertainty
        
        if args.text:
            return xrd_commands.evaluate_text(args.text, weights, args.strictness)
        elif args.file:
            return xrd_commands.evaluate_file(args.file, weights, args.strictness, enable_uncertainty)
        elif args.json:
            return xrd_commands.evaluate_json(args.json, weights, args.strictness, enable_uncertainty)
        elif args.database:
            return xrd_commands.evaluate_database(
                args.database, args.query, args.table, args.limit
            )
    
    raise ValueError(f"未知XRD操作: {args.xrd_action}")


def execute_sn_command(args) -> Dict[str, Any]:
    """执行S-N命令"""
    sn_commands = SNCommands()
    
    if args.sn_action == 'evaluate':
        if args.text:
            return sn_commands.evaluate_text(args.text, args.comprehensive)
        elif args.file:
            return sn_commands.evaluate_file(args.file, args.comprehensive)
        elif args.database:
            return sn_commands.evaluate_database(
                args.database, args.query, args.table, args.limit
            )
    
    raise ValueError(f"未知S-N操作: {args.sn_action}")


def execute_config_command(args) -> Dict[str, Any]:
    """执行配置命令"""
    config_commands = ConfigCommands()
    
    if args.config_action == 'show':
        return config_commands.show_config(args.type)
    
    raise ValueError(f"未知配置操作: {args.config_action}")


def execute_db_command(args) -> Dict[str, Any]:
    """执行数据库命令"""
    db_commands = DatabaseCommands()
    
    if args.db_action == 'test':
        if args.all or not any([args.mysql, args.postgresql, args.mongodb]):
            return db_commands.test_connection("all")
        elif args.mysql:
            return db_commands.test_connection("mysql")
        elif args.postgresql:
            return db_commands.test_connection("postgresql")
        elif args.mongodb:
            return db_commands.test_connection("mongodb")
    
    elif args.db_action == 'query':
        return db_commands.query_database(args.database, args.query, args.limit)
    
    raise ValueError(f"未知数据库操作: {args.db_action}")


def main():
    """CLI主入口函数"""
    parser = create_parser()
    
    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    # 执行命令
    result = execute_command(args)
    
    # 格式化输出
    formatted_output = format_output(result, args.format)
    
    # 保存或打印结果
    save_output(formatted_output, args.output)


if __name__ == '__main__':
    main()