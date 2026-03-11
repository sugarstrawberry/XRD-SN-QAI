"""
CLI输出格式化工具
支持多种输出格式：JSON、表格、CSV、报告
"""

import json
import csv
import io
from typing import Dict, Any, List
from tabulate import tabulate


class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def format_json(data: Dict[str, Any], indent: int = 2) -> str:
        """格式化为JSON"""
        return json.dumps(data, ensure_ascii=False, indent=indent)
    
    @staticmethod
    def format_table(data: Dict[str, Any]) -> str:
        """格式化为表格"""
        if 'evaluation_details' in data:
            # XRD/S-N评价结果表格
            details = data['evaluation_details']
            table_data = []
            
            for dimension, info in details.items():
                if isinstance(info, dict) and 'score' in info:
                    weight = info.get('weight', 'N/A')
                    if isinstance(weight, (int, float)):
                        weight = f"{weight}%"
                    table_data.append([
                        dimension,
                        info['score'],
                        weight
                    ])
            
            headers = ["评价维度", "得分", "权重"]
            table = tabulate(table_data, headers=headers, tablefmt="grid")
            
            # 添加总分和等级
            result = f"\n评价结果:\n{table}\n"
            result += f"\n总分: {data.get('total_score', 'N/A')}"
            if 'grade' in data:
                result += f" ({data['grade']}级)"
            
            if 'suggestions' in data:
                result += f"\n改进建议: {data['suggestions']}"
            
            return result
        
        elif 'database_results' in data:
            # 数据库查询结果表格
            results = data['database_results']
            if isinstance(results, list) and results:
                headers = list(results[0].keys())
                table_data = [[row[col] for col in headers] for row in results]
                return tabulate(table_data, headers=headers, tablefmt="grid")
        
        # 默认键值对表格
        table_data = [[k, v] for k, v in data.items()]
        return tabulate(table_data, headers=["项目", "值"], tablefmt="grid")
    
    @staticmethod
    def format_csv(data: Dict[str, Any]) -> str:
        """格式化为CSV"""
        output = io.StringIO()
        
        if 'evaluation_details' in data:
            # 评价结果CSV
            writer = csv.writer(output)
            writer.writerow(["评价维度", "得分", "权重"])
            
            details = data['evaluation_details']
            for dimension, info in details.items():
                if isinstance(info, dict) and 'score' in info:
                    weight = info.get('weight', '')
                    writer.writerow([dimension, info['score'], weight])
            
            # 添加总分行
            writer.writerow(["总分", data.get('total_score', ''), ''])
            writer.writerow(["等级", data.get('grade', ''), ''])
        
        elif 'database_results' in data:
            # 数据库结果CSV
            results = data['database_results']
            if isinstance(results, list) and results:
                writer = csv.writer(output)
                headers = list(results[0].keys())
                writer.writerow(headers)
                for row in results:
                    writer.writerow([row[col] for col in headers])
        
        else:
            # 通用CSV
            writer = csv.writer(output)
            writer.writerow(["项目", "值"])
            for k, v in data.items():
                writer.writerow([k, v])
        
        return output.getvalue()
    
    @staticmethod
    def format_report(data: Dict[str, Any]) -> str:
        """格式化为详细报告"""
        report = []
        report.append("=" * 60)
        report.append("📋 材料数据质量评价报告")
        report.append("=" * 60)
        
        # 基本信息
        if 'evaluation_type' in data:
            report.append(f"评价类型: {data['evaluation_type']}")
        
        if 'timestamp' in data:
            report.append(f"评价时间: {data['timestamp']}")
        
        if 'data_source' in data:
            report.append(f"数据来源: {data['data_source']}")
        
        report.append("")
        
        # 评价结果
        if 'evaluation_details' in data:
            report.append("详细评价结果:")
            report.append("-" * 40)
            
            details = data['evaluation_details']
            for dimension, info in details.items():
                if isinstance(info, dict):
                    report.append(f"\n🔹 {dimension}:")
                    report.append(f"   得分: {info.get('score', 'N/A')}")
                    if 'weight' in info:
                        report.append(f"   权重: {info['weight']}%")
                    if 'description' in info:
                        report.append(f"   说明: {info['description']}")
            
            report.append("")
            report.append("综合评价:")
            report.append(f"   总分: {data.get('total_score', 'N/A')}")
            if 'grade' in data:
                report.append(f"   等级: {data['grade']}级")
        
        # 改进建议
        if 'suggestions' in data:
            report.append("")
            report.append("💡 改进建议:")
            report.append(f"   {data['suggestions']}")
        
        # E739分析结果
        if 'e739_results' in data:
            report.append("")
            report.append("📈 E739统计分析结果:")
            report.append("-" * 40)
            e739 = data['e739_results']
            for key, value in e739.items():
                report.append(f"   {key}: {value}")
        
        # 不确定性分析结果
        if 'uncertainty_analysis' in data:
            report.append("")
            report.append("🔬 不确定性分析结果:")
            report.append("-" * 40)
            uncertainty = data['uncertainty_analysis']
            
            if 'global_uncertainty' in uncertainty:
                report.append(f"   全局不确定性: {uncertainty['global_uncertainty']:.4f}")
            
            if 'top_5_predictions' in uncertainty:
                report.append("")
                report.append("   Top-5 空间群预测:")
                for pred in uncertainty['top_5_predictions']:
                    space_group = pred['label'] + 1
                    prob = pred['probability']
                    std = pred['std_dev']
                    report.append(f"   {pred['rank']}. 空间群 {space_group:3d}: {prob:.4f} ± {std:.4f}")
                
                if uncertainty['top_5_predictions']:
                    top_pred = uncertainty['top_5_predictions'][0]
                    report.append(f"\n   ✓ 最可能的空间群: {top_pred['label'] + 1}")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    @staticmethod
    def format_error(error_msg: str, error_type: str = "错误") -> str:
        """格式化错误信息"""
        return f"❌ {error_type}: {error_msg}"
    
    @staticmethod
    def format_success(message: str) -> str:
        """格式化成功信息"""
        return f"✅ {message}"
    
    @staticmethod
    def format_info(message: str) -> str:
        """格式化信息"""
        return f"ℹ️  {message}"
    
    @staticmethod
    def format_warning(message: str) -> str:
        """格式化警告"""
        return f"⚠️  {message}"


def format_output(data: Dict[str, Any], format_type: str = "json") -> str:
    """
    格式化输出数据
    
    Args:
        data: 要格式化的数据
        format_type: 输出格式 ('json', 'table', 'csv', 'report')
    
    Returns:
        格式化后的字符串
    """
    formatter = OutputFormatter()
    
    if format_type.lower() == 'json':
        return formatter.format_json(data)
    elif format_type.lower() == 'table':
        return formatter.format_table(data)
    elif format_type.lower() == 'csv':
        return formatter.format_csv(data)
    elif format_type.lower() == 'report':
        return formatter.format_report(data)
    else:
        return formatter.format_json(data)  # 默认JSON格式