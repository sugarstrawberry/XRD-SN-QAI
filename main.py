"""
材料数据质量评价系统主程序
整合XRD和S-N数据评价功能
"""

import gradio as gr
import os
import sys
import pandas as pd

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.xrd_analyzer.xrd_evaluator import XRDEvaluator
from src.xrd_analyzer.xrd_utils import (
    load_example_data, update_weight_sum, auto_adjust_weights_to_100,
    reset_default_weights, validate_grade_thresholds_display, reset_default_grade_levels
)
from src.sn_analyzer.sn_evaluator import SNEvaluator
from src.common.data_sources import create_data_source
from src.common.data_processor import DataProcessor


class MaterialDataEvaluationSystem:
    """材料数据质量评价系统"""
    
    def __init__(self):
        """初始化系统"""
        # 配置文件路径
        self.xrd_config_path = "config/xrd_config.yaml"
        self.sn_config_path = "config/sn_config.yaml"
        self.db_config_path = "config/database_config.yaml"
        
        # 初始化评价器
        self.xrd_evaluator = XRDEvaluator(self.xrd_config_path)
        self.sn_evaluator = SNEvaluator(self.sn_config_path)
        
        # 加载示例数据
        self.examples = load_example_data()
        
        # MySQL数据库配置
        self.mysql_config = {
            'host': 'localhost',
            'port': 3306,
            'database': 'xrd_lab',
            'user': 'root',
            'password': '1234'
        }
        
        # S-N数据库配置（可以使用相同数据库或不同数据库）
        self.sn_mysql_config = {
            'host': 'localhost',
            'port': 3306,
            'database': 'xrd_lab',  # 使用相同数据库，不同表
            'user': 'root',
            'password': '1234'
        }
        
        # MongoDB数据库配置
        self.mongodb_config = {
            'host': 'localhost',
            'port': 27017,
            'database': 'materials_mongo_dev',
            'username': None,  # 如果需要认证，设置用户名
            'password': None   # 如果需要认证，设置密码
        }
        
        # PostgreSQL数据库配置
        self.postgresql_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'materials_lab_dev',
            'user': 'postgres',
            'password': '1234'
        }
        
        # 界面组件引用
        self.e739_status_display = None
        
        # 存储当前使用的提示词
        self.current_xrd_prompt = None
        self.current_sn_prompt = None
    
    def create_interface(self):
        """创建Gradio界面"""
        with gr.Blocks(theme=gr.themes.Soft(), title="材料数据质量评价系统") as demo:
            gr.Markdown("""
            # 材料数据质量评价系统
            """)
            
            with gr.Tabs():
                # XRD数据评价标签页
                self._create_xrd_tab()
                
                # S-N数据评价标签页
                self._create_sn_tab()
            
            # 在界面创建完成后初始化E739状态
            demo.load(self._update_e739_status, outputs=[self.e739_status_display])
        
        return demo
    
    def _create_xrd_tab(self):
        """创建XRD数据评价标签页"""
        with gr.TabItem("XRD数据评价系统"):
            # 严格度选择
            with gr.Accordion("严格度选择", open=False):
                strictness = gr.Radio(
                    choices=["宽松", "标准", "严格", "科研级"],
                    value="标准",
                    label="不同严格度会影响评分标准"
                )

            # 权重配置区域
            with gr.Accordion("评分权重配置", open=False):
                with gr.Row():
                    with gr.Column(scale=2):
                        weight_completeness = gr.Slider(
                            minimum=0, maximum=100, value=40, step=1,
                            label="信息完整性"
                        )
                        weight_normative = gr.Slider(
                            minimum=0, maximum=100, value=15, step=1,
                            label="数据规范性"
                        )
                    with gr.Column(scale=2):
                        weight_consistency = gr.Slider(
                            minimum=0, maximum=100, value=10, step=1,
                            label="内容一致性"
                        )
                        weight_traceability = gr.Slider(
                            minimum=0, maximum=100, value=20, step=1,
                            label="过程可追溯性"
                        )
                    with gr.Column(scale=1):
                        weight_usability = gr.Slider(
                            minimum=0, maximum=100, value=15, step=1,
                            label="智能可用性"
                        )

                # 权重总和显示和按钮
                with gr.Row():
                    with gr.Column(scale=2):
                        weight_sum_display = gr.Markdown("总权重: 100分 (符合要求)")
                    with gr.Column(scale=1):
                        auto_adjust_btn = gr.Button("自动调整", variant="secondary", size="sm")
                    with gr.Column(scale=1):
                        reset_btn = gr.Button("重置默认", variant="secondary", size="sm")

                # 绑定权重更新
                for weight_slider in [weight_completeness, weight_normative, weight_consistency,
                                      weight_traceability, weight_usability]:
                    weight_slider.change(
                        update_weight_sum,
                        inputs=[weight_completeness, weight_normative, weight_consistency,
                                weight_traceability, weight_usability],
                        outputs=[weight_sum_display]
                    )

                auto_adjust_btn.click(
                    auto_adjust_weights_to_100,
                    inputs=[weight_completeness, weight_normative, weight_consistency,
                            weight_traceability, weight_usability],
                    outputs=[weight_completeness, weight_normative, weight_consistency,
                             weight_traceability, weight_usability, weight_sum_display]
                )

                reset_btn.click(
                    reset_default_weights,
                    outputs=[weight_completeness, weight_normative, weight_consistency,
                             weight_traceability, weight_usability, weight_sum_display]
                )

            # 等级配置区域
            with gr.Accordion("等级划分配置", open=False):
                with gr.Row():
                    A = gr.Number(label="A级最低分", value=70, precision=0, minimum=0, maximum=100, step=1)
                    B = gr.Number(label="B级最低分", value=50, precision=0, minimum=0, maximum=100, step=1)
                    C = gr.Number(label="C级最低分", value=0, precision=0, minimum=0, maximum=100, step=1)
                
                grade_warning = gr.Markdown("")

                # 绑定验证函数
                for grade_input in [A, B, C]:
                    grade_input.change(
                        validate_grade_thresholds_display,
                        inputs=[A, B, C],
                        outputs=[grade_warning]
                    )

                with gr.Row():
                    reset_grade_btn = gr.Button("重置为默认等级划分", variant="secondary")
                    reset_grade_btn.click(
                        reset_default_grade_levels,
                        outputs=[A, B, C]
                    )

            # 数据源选择区域
            with gr.Accordion("数据源选择", open=True):
                with gr.Tabs():
                    # 文件上传标签页
                    with gr.TabItem("文件分析"):
                        with gr.Row():
                            file_upload = gr.File(
                                label="支持格式: PDF、CSV、Excel (.xlsx/.xls)、JSON",
                                file_types=[".pdf", ".csv", ".xlsx", ".xls", ".json"],
                                file_count="single"
                            )

                        with gr.Row():
                            extract_btn = gr.Button("提取信息到文本框", variant="secondary")
                            direct_score_btn = gr.Button("直接分析评分", variant="primary")
                            clear_file_btn = gr.Button("清除", variant="stop")
                    
                    # MySQL数据库标签页
                    with gr.TabItem("MySQL数据库"):
                        with gr.Row():
                            db_query = gr.Textbox(
                                label="SQL查询语句（可选）",
                                placeholder="留空则查询所有XRD实验数据，或输入自定义SQL查询",
                                lines=2
                            )
                        
                        with gr.Row():
                            db_extract_btn = gr.Button("从数据库提取到文本框", variant="primary")
                            db_check_btn = gr.Button("检查连接", variant="secondary", size="sm")
                        
                        db_status = gr.Markdown("数据库状态：未连接")
                    
                    # MongoDB数据库标签页
                    with gr.TabItem("MongoDB数据库"):
                        with gr.Row():
                            mongo_collection = gr.Textbox(
                                label="集合名称",
                                placeholder="xrd_experiments",
                                value="xrd_experiments",
                                lines=1
                            )
                        
                        with gr.Row():
                            mongo_query = gr.Textbox(
                                label="MongoDB查询条件（JSON格式，可选）",
                                placeholder='{"status": "approved", "data_quality": "high"}',
                                lines=2
                            )
                        
                        with gr.Row():
                            mongo_extract_btn = gr.Button("从MongoDB提取到文本框", variant="primary")
                            mongo_check_btn = gr.Button("检查连接", variant="secondary", size="sm")
                        
                        mongo_status = gr.Markdown("MongoDB状态：未连接")
                    
                    # PostgreSQL数据库标签页
                    with gr.TabItem("PostgreSQL数据库"):
                        with gr.Row():
                            pg_query = gr.Textbox(
                                label="SQL查询语句（可选）",
                                placeholder="留空则查询所有XRD实验数据，或输入自定义SQL查询",
                                lines=2
                            )
                        
                        with gr.Row():
                            pg_extract_btn = gr.Button("从PostgreSQL提取到文本框", variant="primary")
                            pg_check_btn = gr.Button("检查连接", variant="secondary", size="sm")
                        
                        pg_status = gr.Markdown("PostgreSQL状态：未连接")

            # 示例按钮
            with gr.Row():
                example1 = gr.Button("示例1：高质量标准样品", size="sm")
                example2 = gr.Button("示例2：文献图像数据", size="sm")
                example3 = gr.Button("示例3：不完整数据", size="sm")

            # 输入输出区域和提示词区域并排布局
            with gr.Row():
                with gr.Column(scale=7):  # 左侧占70%
                    # 输入区
                    input_box = gr.Textbox(
                        label="请输入XRD实验数据描述",
                        placeholder="直接输入XRD数据描述 或 使用上方按钮从PDF提取",
                        lines=5,
                        max_lines=8
                    )
                    
                    # 输出对话框
                    chatbot = gr.Chatbot(
                        label="质量评价结果",
                        height=400,
                        bubble_full_width=False,
                        show_copy_button=True
                    )
                
                with gr.Column(scale=3):  # 右侧占30%
                    xrd_prompt_box = gr.Textbox(
                        label="XRD评分提示词设置",
                        placeholder="将显示当前使用的提示词，可以修改...",
                        lines=20,
                        max_lines=25,
                        value=self._get_default_xrd_prompt()
                    )
                    
                    with gr.Row():
                        reset_prompt_btn = gr.Button("恢复默认", size="sm", variant="secondary")
                        apply_prompt_btn = gr.Button("应用修改", size="sm", variant="primary")
                    
                    # 提示词状态显示
                    xrd_prompt_status = gr.Markdown("", visible=False)

            # 按钮
            with gr.Row():
                submit_btn = gr.Button("文本评分", variant="primary")
                clear_btn = gr.Button("清除结果")

            # 绑定XRD相关事件
            self._bind_xrd_events(
                submit_btn, input_box, chatbot, clear_btn,
                weight_completeness, weight_normative, weight_consistency,
                weight_traceability, weight_usability, A, B, C, strictness,
                file_upload, extract_btn, direct_score_btn, clear_file_btn,
                db_query, db_extract_btn, db_check_btn, db_status,
                mongo_collection, mongo_query, mongo_extract_btn, mongo_check_btn, mongo_status,
                pg_query, pg_extract_btn, pg_check_btn, pg_status,
                example1, example2, example3,
                xrd_prompt_box, reset_prompt_btn, apply_prompt_btn, xrd_prompt_status
            )
    
    def _create_sn_tab(self):
        """创建S-N数据评价标签页"""
        with gr.TabItem("S-N数据评价系统"):
            gr.Markdown("""
            **ASTM E466**：恒幅疲劳试验标准\n
            **ASTM E739**：S-N数据统计分析标准""")
            
            # 数据源选择区域
            with gr.Accordion("数据源选择", open=True):
                with gr.Tabs():
                    # 文件上传标签页
                    with gr.TabItem("文件分析"):
                        with gr.Row():
                            data_file = gr.File(
                                label="支持格式: CSV、Excel (.xlsx/.xls)、JSON",
                                file_types=[".csv", ".xlsx", ".xls", ".json"],
                                file_count="single"
                            )

                        # E739系统状态显示
                        self.e739_status_display = gr.Markdown("**E739统计分析系统**: 检查中...")
                        
                        with gr.Row():
                            extract_data_btn = gr.Button("提取信息到文本框", variant="primary")
                            clear_data_btn = gr.Button("清除", variant="stop")
                    
                    # MySQL数据库标签页
                    with gr.TabItem("MySQL数据库"):
                        with gr.Row():
                            sn_db_query = gr.Textbox(
                                label="SQL查询语句（可选）",
                                placeholder="留空则查询所有S-N疲劳试验数据，或输入自定义SQL查询",
                                lines=2
                            )
                        
                        with gr.Row():
                            sn_db_extract_btn = gr.Button("从数据库提取到文本框", variant="primary")
                            sn_db_check_btn = gr.Button("检查连接", variant="secondary", size="sm")
                        
                        sn_db_status = gr.Markdown("数据库状态：未连接")
                    
                    # MongoDB数据库标签页
                    with gr.TabItem("MongoDB数据库"):
                        with gr.Row():
                            sn_mongo_collection = gr.Textbox(
                                label="集合名称",
                                placeholder="fatigue_tests",
                                value="fatigue_tests",
                                lines=1
                            )
                        
                        with gr.Row():
                            sn_mongo_query = gr.Textbox(
                                label="MongoDB查询条件（JSON格式，可选）",
                                placeholder='{"test_status": "completed", "data_quality": "validated"}',
                                lines=2
                            )
                        
                        with gr.Row():
                            sn_mongo_extract_btn = gr.Button("从MongoDB提取到文本框", variant="primary")
                            sn_mongo_check_btn = gr.Button("检查连接", variant="secondary", size="sm")
                        
                        sn_mongo_status = gr.Markdown("MongoDB状态：未连接")
                    
                    # PostgreSQL数据库标签页
                    with gr.TabItem("PostgreSQL数据库"):
                        with gr.Row():
                            sn_pg_query = gr.Textbox(
                                label="SQL查询语句（可选）",
                                placeholder="留空则查询所有S-N疲劳试验数据，或输入自定义SQL查询",
                                lines=2
                            )
                        
                        with gr.Row():
                            sn_pg_extract_btn = gr.Button("从PostgreSQL提取到文本框", variant="primary")
                            sn_pg_check_btn = gr.Button("检查连接", variant="secondary", size="sm")
                        
                        sn_pg_status = gr.Markdown("PostgreSQL状态：未连接")

            # 输入输出区域和提示词区域并排布局
            with gr.Row():
                with gr.Column(scale=7):  # 左侧占70%
                    # 输入区
                    input_box1 = gr.Textbox(
                        label="请输入S-N实验数据描述",
                        placeholder="输入S-N数据描述及元数据 或 使用上方按钮从csv文件中提取",
                        lines=5,
                        max_lines=8
                    )
                    
                    # 输出对话框
                    chatbot1 = gr.Chatbot(
                        label="质量评价结果",
                        height=400,
                        bubble_full_width=False,
                        show_copy_button=True
                    )
                
                with gr.Column(scale=3):  # 右侧占30%
                    sn_prompt_box = gr.Textbox(
                        label="S-N评分提示词设置",
                        lines=20,
                        max_lines=25,
                        value=self._get_default_sn_prompt()
                    )
                    
                    with gr.Row():
                        reset_sn_prompt_btn = gr.Button("恢复默认", size="sm", variant="secondary")
                        apply_sn_prompt_btn = gr.Button("应用修改", size="sm", variant="primary")
                    
                    # S-N提示词状态显示
                    sn_prompt_status = gr.Markdown("", visible=False)

            # 按钮
            with gr.Row():
                submit_btn1 = gr.Button("元数据评分(LLM)")
                comprehensive_btn = gr.Button("综合评价(LLM + E739)", variant="primary")
                clear_btn1 = gr.Button("清除结果")

            # 绑定S-N相关事件
            self._bind_sn_events(
                submit_btn1, input_box1, chatbot1, clear_btn1,
                data_file, extract_data_btn, comprehensive_btn, clear_data_btn,
                sn_db_query, sn_db_extract_btn, sn_db_check_btn, sn_db_status,
                sn_mongo_collection, sn_mongo_query, sn_mongo_extract_btn, sn_mongo_check_btn, sn_mongo_status,
                sn_pg_query, sn_pg_extract_btn, sn_pg_check_btn, sn_pg_status,
                sn_prompt_box, reset_sn_prompt_btn, apply_sn_prompt_btn, sn_prompt_status
            )
    
    def _bind_xrd_events(self, submit_btn, input_box, chatbot, clear_btn,
                        weight_completeness, weight_normative, weight_consistency,
                        weight_traceability, weight_usability, A, B, C, strictness,
                        file_upload, extract_btn, direct_score_btn, clear_file_btn,
                        db_query, db_extract_btn, db_check_btn, db_status,
                        mongo_collection, mongo_query, mongo_extract_btn, mongo_check_btn, mongo_status,
                        pg_query, pg_extract_btn, pg_check_btn, pg_status,
                        example1, example2, example3,
                        xrd_prompt_box, reset_prompt_btn, apply_prompt_btn, xrd_prompt_status):
        """绑定XRD相关事件"""
        
        def on_submit(xrd_text, chat_history, w1, w2, w3, w4, w5, A, B, C, strictness):
            """处理XRD文本评分"""
            if not xrd_text.strip():
                return "", chat_history

            weights = {
                "信息完整性": w1,
                "数据规范性": w2,
                "内容一致性": w3,
                "过程可追溯性": w4,
                "智能可用性": w5
            }

            # 使用当前设置的提示词进行评价
            if self.current_xrd_prompt:
                # 如果有自定义提示词，使用自定义提示词
                result = self.xrd_evaluator.llm_client.chat(self.current_xrd_prompt, xrd_text)
            else:
                # 否则使用默认评价方法
                result = self.xrd_evaluator.evaluate_text(xrd_text, weights, A, B, C, strictness)
            
            chat_history.append((f"XRD数据评分（{strictness}）\n{weights}\n{xrd_text}", result))
            return "", chat_history

        def extract_from_file(file_obj):
            """从文件提取信息到文本框"""
            if file_obj is None:
                return "请先上传文件"
            
            file_name = getattr(file_obj, 'name', 'unknown_file')
            file_path = file_name.lower()
            
            if file_path.endswith('.pdf'):
                return self.xrd_evaluator.extract_info_from_pdf(file_obj)
            elif file_path.endswith('.json'):
                # JSON文件特殊处理，显示数据概览
                try:
                    import json
                    with open(file_obj.name, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    
                    # 生成JSON数据的描述
                    description = self.xrd_evaluator._generate_json_description(json_data)
                    return f"JSON文件数据概览：\n{description}\n\n注意：此文件将自动进行不确定性分析"
                except Exception as e:
                    return f"JSON文件读取失败：{str(e)}"
            elif file_path.endswith(('.csv', '.xlsx', '.xls')):
                return self.xrd_evaluator.extract_info_from_data_file(file_obj.name)
            else:
                return "不支持的文件格式，请上传PDF、CSV、Excel或JSON文件"

        def direct_score_from_file(file_obj, chat_history, w1, w2, w3, w4, w5, A, B, C, strictness):
            """直接从文件分析评分"""
            if file_obj is None:
                return chat_history

            weights = {
                "信息完整性": w1,
                "数据规范性": w2,
                "内容一致性": w3,
                "过程可追溯性": w4,
                "智能可用性": w5
            }

            file_name = getattr(file_obj, 'name', 'unknown_file')
            processing_msg = f"正在分析文件：{file_name}..."
            chat_history.append((f"📄 {file_name}", processing_msg))

            file_path = file_name.lower()
            
            if file_path.endswith('.pdf'):
                result = self.xrd_evaluator.evaluate_pdf(file_obj, weights, A, B, C, strictness)
            elif file_path.endswith('.json'):
                # JSON文件特殊处理，支持不确定性分析
                import json
                try:
                    with open(file_obj.name, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                    result = self.xrd_evaluator.evaluate_json_data(json_data, weights, A, B, C, strictness, enable_uncertainty=True)
                except Exception as e:
                    result = f"JSON文件处理失败：{str(e)}"
            elif file_path.endswith(('.csv', '.xlsx', '.xls')):
                result = self.xrd_evaluator.evaluate_data_file(file_obj.name, weights, A, B, C, strictness)
            else:
                result = "不支持的文件格式，请上传PDF、CSV、Excel或JSON文件"
            
            chat_history[-1] = (f"📄 {file_name}", result)
            return chat_history

        def clear_file():
            return None, ""

        def clear_chat():
            return []
        
        def check_db_connection():
            """检查数据库连接状态"""
            success, message = self._test_mysql_connection()
            status_color = "green" if success else "red"
            return f'<span style="color: {status_color}">数据库状态：{message}</span>'
        
        def extract_from_db(query_text):
            """从数据库提取数据到文本框"""
            extracted = self._extract_from_mysql(query_text)
            return extracted
        


        # 绑定事件
        submit_btn.click(
            on_submit,
            inputs=[input_box, chatbot, weight_completeness, weight_normative,
                    weight_consistency, weight_traceability, weight_usability, A, B, C, strictness],
            outputs=[input_box, chatbot]
        )

        input_box.submit(
            on_submit,
            inputs=[input_box, chatbot, weight_completeness, weight_normative,
                    weight_consistency, weight_traceability, weight_usability, A, B, C, strictness],
            outputs=[input_box, chatbot]
        )

        clear_btn.click(clear_chat, outputs=[chatbot])

        extract_btn.click(extract_from_file, [file_upload], [input_box])

        direct_score_btn.click(
            direct_score_from_file,
            inputs=[file_upload, chatbot, weight_completeness, weight_normative,
                    weight_consistency, weight_traceability, weight_usability, A, B, C, strictness],
            outputs=[chatbot]
        )

        clear_file_btn.click(clear_file, outputs=[file_upload, input_box])

        # 数据库相关事件
        db_extract_btn.click(extract_from_db, inputs=[db_query], outputs=[input_box])
        db_check_btn.click(check_db_connection, outputs=[db_status])
        
        # MongoDB相关事件
        def check_mongo_connection():
            """检查MongoDB连接状态"""
            success, message = self._test_mongodb_connection()
            status_color = "green" if success else "red"
            return f'<span style="color: {status_color}">MongoDB状态：{message}</span>'
        
        def extract_from_mongo(collection_name, query_text):
            """从MongoDB提取数据到文本框"""
            extracted = self._extract_from_mongodb(collection_name, query_text)
            return extracted
        
        mongo_extract_btn.click(extract_from_mongo, inputs=[mongo_collection, mongo_query], outputs=[input_box])
        mongo_check_btn.click(check_mongo_connection, outputs=[mongo_status])
        
        # PostgreSQL相关事件
        def check_pg_connection():
            """检查PostgreSQL连接状态"""
            success, message = self._test_postgresql_connection()
            status_color = "green" if success else "red"
            return f'<span style="color: {status_color}">PostgreSQL状态：{message}</span>'
        
        def extract_from_pg(query_text):
            """从PostgreSQL提取数据到文本框"""
            extracted = self._extract_from_postgresql(query_text)
            return extracted
        
        pg_extract_btn.click(extract_from_pg, inputs=[pg_query], outputs=[input_box])
        pg_check_btn.click(check_pg_connection, outputs=[pg_status])

        # 示例按钮
        example1.click(lambda: self.examples["example1"], outputs=input_box)
        example2.click(lambda: self.examples["example2"], outputs=input_box)
        example3.click(lambda: self.examples["example3"], outputs=input_box)
        
        # 提示词相关事件
        reset_prompt_btn.click(self._reset_xrd_prompt, outputs=[xrd_prompt_box])
        apply_prompt_btn.click(self._apply_xrd_prompt, inputs=[xrd_prompt_box], outputs=[xrd_prompt_status])
        
        # 权重变化时更新提示词
        def update_xrd_prompt_on_weight_change(w1, w2, w3, w4, w5, A, B, C, strictness):
            weights = {
                "信息完整性": w1,
                "数据规范性": w2,
                "内容一致性": w3,
                "过程可追溯性": w4,
                "智能可用性": w5
            }
            prompt = self.xrd_evaluator.scoring_model.generate_scoring_prompt(weights, A, B, C, strictness)
            self.current_xrd_prompt = prompt
            return prompt
        
        # 绑定权重和等级变化事件到提示词更新
        for component in [weight_completeness, weight_normative, weight_consistency, 
                         weight_traceability, weight_usability, A, B, C, strictness]:
            component.change(
                update_xrd_prompt_on_weight_change,
                inputs=[weight_completeness, weight_normative, weight_consistency,
                       weight_traceability, weight_usability, A, B, C, strictness],
                outputs=[xrd_prompt_box]
            )
    
    def _update_e739_status(self):
        """更新E739系统状态"""
        status = self.sn_evaluator.get_e739_status()
        if status["available"]:
            return "**E739统计分析系统**: 已就绪 (可使用综合分析功能)"
        else:
            return "**E739统计分析系统**: 不可用 (仅支持LLM快速分析)"
    
    def _get_default_xrd_prompt(self):
        """获取默认XRD提示词"""
        # 使用默认权重生成提示词
        default_weights = {
            "信息完整性": 40,
            "数据规范性": 15,
            "内容一致性": 10,
            "过程可追溯性": 20,
            "智能可用性": 15
        }
        prompt = self.xrd_evaluator.scoring_model.generate_scoring_prompt(
            default_weights, 70, 50, 0, "标准"
        )
        self.current_xrd_prompt = prompt
        return prompt
    
    def _get_default_sn_prompt(self):
        """获取默认S-N提示词"""
        prompt = self.sn_evaluator.sn_analysis_prompt
        self.current_sn_prompt = prompt
        return prompt
    
    def _reset_xrd_prompt(self):
        """重置XRD提示词为默认值"""
        return self._get_default_xrd_prompt()
    
    def _reset_sn_prompt(self):
        """重置S-N提示词为默认值"""
        return self._get_default_sn_prompt()
    
    def _apply_xrd_prompt(self, custom_prompt):
        """应用自定义XRD提示词"""
        if custom_prompt.strip():
            self.current_xrd_prompt = custom_prompt
            return gr.update(value="✅ XRD提示词已成功更新", visible=True)
        else:
            return gr.update(value="❌ 提示词不能为空", visible=True)
    
    def _apply_sn_prompt(self, custom_prompt):
        """应用自定义S-N提示词"""
        if custom_prompt.strip():
            self.current_sn_prompt = custom_prompt
            self.sn_evaluator.set_custom_prompt(custom_prompt)
            return gr.update(value="✅ S-N提示词已成功更新", visible=True)
        else:
            return gr.update(value="❌ 提示词不能为空", visible=True)
    

    
    def _test_mysql_connection(self):
        """测试MySQL数据库连接"""
        try:
            # 简单的连接测试，不依赖特定表
            mysql_source = create_data_source(
                'mysql',
                **self.mysql_config,
                query="SELECT 1 as test"
            )
            processor = DataProcessor(mysql_source)
            df = processor.get_data()
            
            # 尝试检查XRD表是否存在
            try:
                mysql_source = create_data_source(
                    'mysql',
                    **self.mysql_config,
                    query="SELECT COUNT(*) as total FROM xrd_experiments"
                )
                processor = DataProcessor(mysql_source)
                df = processor.get_data()
                count = df.iloc[0]['total']
                return True, f"数据库连接成功！当前有 {count} 条XRD实验记录"
            except:
                return True, "数据库连接成功！但xrd_experiments表不存在，请先创建表"
                
        except Exception as e:
            return False, f"数据库连接失败：{str(e)}"
    
    def _extract_from_mysql(self, custom_query=""):
        """从MySQL数据库提取XRD数据"""
        try:
            # 如果没有自定义查询，使用默认查询
            if not custom_query.strip():
                # 先检查表是否存在
                try:
                    mysql_source = create_data_source(
                        'mysql',
                        **self.mysql_config,
                        query="SHOW TABLES LIKE 'xrd_experiments'"
                    )
                    processor = DataProcessor(mysql_source)
                    df = processor.get_data()
                    
                    if df.empty:
                        return "xrd_experiments表不存在，请先创建表并插入数据"
                    
                    # 表存在，查询数据
                    query = """
                        SELECT 
                            CONCAT('样品信息：', IFNULL(sample_name, '未知'), '，', IFNULL(material_composition, '未知'), '，', IFNULL(preparation_process, '未知')) as sample_info,
                            CONCAT('辐射源：', IFNULL(radiation_source, '未知'), '，', IFNULL(tube_voltage_kv, 0), 'kV，', IFNULL(tube_current_ma, 0), 'mA') as radiation_info,
                            CONCAT('扫描参数：', IFNULL(scan_range_start, 0), '-', IFNULL(scan_range_end, 0), '°，', IFNULL(step_size, 0), '°，', IFNULL(scan_mode, '未知')) as scan_info,
                            CONCAT('仪器信息：', IFNULL(manufacturer, '未知'), ' ', IFNULL(instrument_model, '未知')) as instrument_info
                        FROM xrd_experiments
                        ORDER BY created_at DESC
                        LIMIT 5
                    """
                except Exception as e:
                    return f"检查表结构失败：{str(e)}"
            else:
                query = custom_query
            
            mysql_source = create_data_source(
                'mysql',
                **self.mysql_config,
                query=query
            )
            
            processor = DataProcessor(mysql_source)
            df = processor.get_data()
            
            if df.empty:
                return "数据库中没有找到数据"
            
            # 如果是默认查询，格式化输出
            if not custom_query.strip():
                result_lines = []
                for i, row in df.iterrows():
                    result_lines.append(f"=== XRD实验记录 {i+1} ===")
                    for col in row.index:
                        result_lines.append(row[col])
                    result_lines.append("")
                
                return "\n".join(result_lines)
            else:
                # 自定义查询，返回表格格式
                return df.to_string(index=False)
                
        except Exception as e:
            return f"数据库查询失败：{str(e)}"
    

    
    def _test_sn_mysql_connection(self):
        """测试S-N MySQL数据库连接"""
        try:
            # 简单的连接测试，不依赖特定表
            mysql_source = create_data_source(
                'mysql',
                **self.sn_mysql_config,
                query="SELECT 1 as test"
            )
            processor = DataProcessor(mysql_source)
            df = processor.get_data()
            
            # 尝试检查S-N表是否存在
            try:
                mysql_source = create_data_source(
                    'mysql',
                    **self.sn_mysql_config,
                    query="SELECT COUNT(*) as total FROM sn_fatigue_tests"
                )
                processor = DataProcessor(mysql_source)
                df = processor.get_data()
                count = df.iloc[0]['total']
                return True, f"数据库连接成功！当前有 {count} 条S-N疲劳试验记录"
            except:
                return True, "数据库连接成功！但sn_fatigue_tests表不存在，请先创建表"
                
        except Exception as e:
            return False, f"数据库连接失败：{str(e)}"
    
    def _extract_from_sn_mysql(self, custom_query=""):
        """从MySQL数据库提取S-N数据"""
        try:
            # 如果没有自定义查询，使用默认查询
            if not custom_query.strip():
                # 先检查表是否存在
                try:
                    mysql_source = create_data_source(
                        'mysql',
                        **self.sn_mysql_config,
                        query="SHOW TABLES LIKE 'sn_fatigue_tests'"
                    )
                    processor = DataProcessor(mysql_source)
                    df = processor.get_data()
                    
                    if df.empty:
                        return "sn_fatigue_tests表不存在，请先创建表并插入数据"
                    
                    # 表存在，查询数据
                    query = """
                        SELECT 
                            CONCAT('试验信息：', IFNULL(test_id, '未知'), '，', IFNULL(material_type, '未知'), '，', IFNULL(test_standard, 'ASTM E466')) as test_info,
                            CONCAT('试验条件：频率', IFNULL(test_frequency, 0), 'Hz，温度', IFNULL(temperature, 25), '°C，应力比R=', IFNULL(stress_ratio, 0)) as test_conditions,
                            CONCAT('数据点：应力幅', IFNULL(stress_amplitude, 0), 'MPa，失效周期', IFNULL(cycles_to_failure, 0), '次') as data_point,
                            CONCAT('试验状态：', IFNULL(test_status, '未知')) as status_info
                        FROM sn_fatigue_tests
                        ORDER BY created_at DESC
                        LIMIT 5
                    """
                except Exception as e:
                    return f"检查表结构失败：{str(e)}"
            else:
                query = custom_query
            
            mysql_source = create_data_source(
                'mysql',
                **self.sn_mysql_config,
                query=query
            )
            
            processor = DataProcessor(mysql_source)
            df = processor.get_data()
            
            if df.empty:
                return "数据库中没有找到S-N疲劳试验数据"
            
            # 如果是默认查询，格式化输出
            if not custom_query.strip():
                result_lines = []
                for i, row in df.iterrows():
                    result_lines.append(f"=== S-N试验记录 {i+1} ===")
                    for col in row.index:
                        result_lines.append(row[col])
                    result_lines.append("")
                
                return "\n".join(result_lines)
            else:
                # 自定义查询，返回表格格式
                return df.to_string(index=False)
                
        except Exception as e:
            return f"S-N数据库查询失败：{str(e)}"
    
    def _test_mongodb_connection(self):
        """测试MongoDB数据库连接"""
        try:
            # 简单的连接测试
            mongo_source = create_data_source(
                'mongodb',
                **self.mongodb_config,
                collection='test',
                query={}
            )
            processor = DataProcessor(mongo_source)
            
            # 尝试连接并获取数据库信息
            if processor.data_source.validate_connection():
                # 尝试检查XRD集合是否存在
                try:
                    mongo_source = create_data_source(
                        'mongodb',
                        **self.mongodb_config,
                        collection='xrd_experiments',
                        query={}
                    )
                    processor = DataProcessor(mongo_source)
                    df = processor.get_data()
                    count = len(df)
                    return True, f"MongoDB连接成功！xrd_experiments集合有 {count} 条记录"
                except:
                    return True, "MongoDB连接成功！但xrd_experiments集合不存在或为空"
            else:
                return False, "MongoDB连接失败"
                
        except Exception as e:
            return False, f"MongoDB连接失败：{str(e)}"
    
    def _extract_from_mongodb(self, collection_name, query_text=""):
        """从MongoDB提取XRD数据"""
        try:
            import json
            
            # 解析查询条件
            if query_text.strip():
                try:
                    query = json.loads(query_text)
                except json.JSONDecodeError:
                    return f"查询条件JSON格式错误：{query_text}"
            else:
                # 默认查询条件 - 更宽松的条件
                query = {}  # 查询所有数据
            
            mongo_source = create_data_source(
                'mongodb',
                **self.mongodb_config,
                collection=collection_name or 'xrd_experiments',
                query=query
            )
            
            processor = DataProcessor(mongo_source)
            df = processor.get_data()
            
            if df.empty:
                return f"MongoDB集合 {collection_name or 'xrd_experiments'} 中没有找到匹配的数据\n查询条件: {query}"
            
            # 调试：显示DataFrame的基本信息
            debug_info = f"DataFrame形状: {df.shape}\n"
            debug_info += f"DataFrame列: {list(df.columns)}\n"
            
            # 格式化输出XRD数据
            result_lines = [debug_info]
            
            for i, row in df.head(5).iterrows():  # 限制显示前5条
                result_lines.append(f"=== XRD实验记录 {i+1} ===")
                
                # 调试：显示这一行的所有数据
                result_lines.append("--- 原始数据 ---")
                for col in df.columns:
                    try:
                        if row[col] is not None and str(row[col]) != 'nan':  # 更安全的非空检查
                            result_lines.append(f"{col}: {row[col]}")
                    except:
                        result_lines.append(f"{col}: [无法显示]")
                result_lines.append("--- 格式化数据 ---")
                
                # 提取_id
                try:
                    if '_id' in row and row['_id'] is not None:
                        result_lines.append(f"实验ID: {row['_id']}")
                except:
                    pass
                
                # 尝试解析嵌套的JSON字段
                for field_name in ['sample', 'instrument', 'conditions', 'data_info', 'quality_metrics']:
                    try:
                        if field_name in row and row[field_name] is not None:
                            field_value = row[field_name]
                            
                            # 如果是字符串，尝试解析为JSON
                            if isinstance(field_value, str):
                                try:
                                    field_value = json.loads(field_value)
                                except:
                                    pass
                            
                            # 如果是字典，提取信息
                            if isinstance(field_value, dict):
                                if field_name == 'sample':
                                    sample_parts = []
                                    for key in ['name', 'composition', 'preparation', 'cas_number', 'supplier']:
                                        if key in field_value and field_value[key] is not None:
                                            sample_parts.append(str(field_value[key]))
                                    if sample_parts:
                                        result_lines.append(f"样品信息：{', '.join(sample_parts)}")
                                
                                elif field_name == 'instrument':
                                    instrument_parts = []
                                    for key in ['manufacturer', 'model']:
                                        if key in field_value and field_value[key] is not None:
                                            instrument_parts.append(str(field_value[key]))
                                    if instrument_parts:
                                        result_lines.append(f"仪器信息：{' '.join(instrument_parts)}")
                                
                                elif field_name == 'conditions':
                                    condition_parts = []
                                    if 'radiation_source' in field_value and field_value['radiation_source'] is not None:
                                        condition_parts.append(f"辐射源{field_value['radiation_source']}")
                                    if 'voltage' in field_value and field_value['voltage'] is not None:
                                        condition_parts.append(f"{field_value['voltage']}kV")
                                    if 'current' in field_value and field_value['current'] is not None:
                                        condition_parts.append(f"{field_value['current']}mA")
                                    if 'scan_range' in field_value and isinstance(field_value['scan_range'], dict):
                                        scan_range = field_value['scan_range']
                                        if 'start' in scan_range and 'end' in scan_range:
                                            condition_parts.append(f"扫描范围{scan_range['start']}-{scan_range['end']}°")
                                    if 'step_size' in field_value and field_value['step_size'] is not None:
                                        condition_parts.append(f"步长{field_value['step_size']}°")
                                    if 'scan_mode' in field_value and field_value['scan_mode'] is not None:
                                        condition_parts.append(str(field_value['scan_mode']))
                                    if condition_parts:
                                        result_lines.append(f"测试条件：{', '.join(condition_parts)}")
                                
                                elif field_name == 'data_info':
                                    data_parts = []
                                    if 'format' in field_value and field_value['format'] is not None:
                                        formats = field_value['format']
                                        if isinstance(formats, list):
                                            data_parts.append(f"格式: {', '.join(map(str, formats))}")
                                        else:
                                            data_parts.append(f"格式: {formats}")
                                    if 'data_points' in field_value and field_value['data_points'] is not None:
                                        data_parts.append(f"数据点: {field_value['data_points']}")
                                    if 'missing_rate' in field_value and field_value['missing_rate'] is not None:
                                        data_parts.append(f"缺失率: {field_value['missing_rate']}")
                                    if 'units' in field_value and isinstance(field_value['units'], dict):
                                        units = field_value['units']
                                        if 'angle' in units and 'intensity' in units:
                                            data_parts.append(f"单位: {units['angle']}, {units['intensity']}")
                                    if data_parts:
                                        result_lines.append(f"数据信息：{', '.join(data_parts)}")
                            
                            else:
                                # 如果不是字典，直接显示
                                result_lines.append(f"{field_name}: {field_value}")
                    except Exception as e:
                        result_lines.append(f"{field_name}: [解析错误: {e}]")
                
                # 添加其他简单字段
                for field_name in ['status', 'data_quality', 'notes', 'experiment_date']:
                    try:
                        if field_name in row and row[field_name] is not None and str(row[field_name]) != 'nan':
                            result_lines.append(f"{field_name}: {row[field_name]}")
                    except:
                        pass
                
                result_lines.append("")
            
            if len(df) > 5:
                result_lines.append(f"... 还有 {len(df) - 5} 条记录")
            
            return "\n".join(result_lines)
                
        except Exception as e:
            return f"MongoDB查询失败：{str(e)}\n请检查连接和数据格式"
            return f"MongoDB查询失败：{str(e)}"
    
    def _extract_sn_from_mongodb(self, collection_name, query_text=""):
        """从MongoDB提取S-N数据"""
        try:
            import json
            
            # 解析查询条件
            if query_text.strip():
                try:
                    query = json.loads(query_text)
                except json.JSONDecodeError:
                    return f"查询条件JSON格式错误：{query_text}"
            else:
                # 默认查询条件
                query = {
                    "test_status": "completed",
                    "data_quality": "validated"
                }
            
            mongo_source = create_data_source(
                'mongodb',
                **self.mongodb_config,
                collection=collection_name or 'fatigue_tests',
                query=query
            )
            
            processor = DataProcessor(mongo_source)
            df = processor.get_data()
            
            if df.empty:
                return f"MongoDB集合 {collection_name or 'fatigue_tests'} 中没有找到匹配的S-N数据"
            
            # 格式化输出S-N数据
            result_lines = []
            
            # 检查数据格式：是否已经被展开为S和N列
            if 'S' in df.columns and 'N' in df.columns:
                # 数据已经被展开，直接使用S和N列
                for i, row in df.head(20).iterrows():  # 显示前20条
                    s_val = row.get('S', 0)
                    n_val = row.get('N', 0)
                    result_lines.append(f"S={s_val} MPa, N={int(n_val)}")
                
                if len(df) > 20:
                    result_lines.append(f"... 还有 {len(df) - 20} 条数据点")
            
            else:
                # 数据未展开，尝试从嵌套结构中提取
                for i, row in df.head(5).iterrows():
                    result_lines.append(f"=== S-N试验记录 {i+1} ===")
                    
                    # 提取关键字段
                    if 'material_type' in row:
                        result_lines.append(f"材料：{row.get('material_type', '未知')}")
                    elif 'material' in row and isinstance(row['material'], dict):
                        material_info = row['material']
                        result_lines.append(f"材料信息：{material_info.get('type', '未知')}，{material_info.get('grade', '未知')}")
                    
                    if 'test_type' in row:
                        result_lines.append(f"试验类型：{row.get('test_type', '未知')}")
                    elif 'test_conditions' in row and isinstance(row['test_conditions'], dict):
                        conditions = row['test_conditions']
                        result_lines.append(f"试验条件：频率{conditions.get('frequency_hz', 0)}Hz，温度{conditions.get('temperature_c', 25)}°C")
                    
                    # 提取S-N数据点
                    if 'S' in row and 'N' in row:
                        result_lines.append(f"数据点：S={row['S']} MPa, N={int(row['N'])}")
                    elif 'results' in row and isinstance(row['results'], dict):
                        results = row['results']
                        result_lines.append(f"数据点：应力幅{results.get('stress_amplitude', 0)}MPa，失效周期{results.get('cycles_to_failure', 0)}次")
                    
                    result_lines.append("")
                
                if len(df) > 5:
                    result_lines.append(f"... 还有 {len(df) - 5} 条记录")
            
            return "\n".join(result_lines)
                
        except Exception as e:
            return f"MongoDB S-N数据查询失败：{str(e)}"
    
    def _test_postgresql_connection(self):
        """测试PostgreSQL数据库连接"""
        try:
            # 简单的连接测试
            pg_source = create_data_source(
                'postgresql',
                **self.postgresql_config,
                query="SELECT 1 as test"
            )
            processor = DataProcessor(pg_source)
            df = processor.get_data()
            
            # 尝试检查XRD表是否存在
            try:
                pg_source = create_data_source(
                    'postgresql',
                    **self.postgresql_config,
                    query="SELECT COUNT(*) as total FROM xrd_experiments"
                )
                processor = DataProcessor(pg_source)
                df = processor.get_data()
                count = df.iloc[0]['total']
                return True, f"PostgreSQL连接成功！当前有 {count} 条XRD实验记录"
            except:
                return True, "PostgreSQL连接成功！但xrd_experiments表不存在，请先创建表"
                
        except Exception as e:
            return False, f"PostgreSQL连接失败：{str(e)}"
    
    def _extract_from_postgresql(self, custom_query=""):
        """从PostgreSQL数据库提取XRD数据"""
        try:
            # 如果没有自定义查询，使用默认查询
            if not custom_query.strip():
                # 先检查表是否存在
                try:
                    pg_source = create_data_source(
                        'postgresql',
                        **self.postgresql_config,
                        query="SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'xrd_experiments') as table_exists"
                    )
                    processor = DataProcessor(pg_source)
                    df = processor.get_data()
                    
                    if not df.iloc[0]['table_exists']:
                        return "xrd_experiments表不存在，请先创建表并插入数据"
                    
                    # 表存在，查询数据
                    query = """
                        SELECT 
                            '样品信息：' || COALESCE(sample_name, '未知') || '，' || COALESCE(material_composition, '未知') || '，' || COALESCE(preparation_process, '未知') as sample_info,
                            '辐射源：' || COALESCE(radiation_source, '未知') || '，' || COALESCE(tube_voltage_kv::text, '0') || 'kV，' || COALESCE(tube_current_ma::text, '0') || 'mA' as radiation_info,
                            '扫描参数：' || COALESCE(scan_range_start::text, '0') || '-' || COALESCE(scan_range_end::text, '0') || '°，' || COALESCE(step_size::text, '0') || '°，' || COALESCE(scan_mode, '未知') as scan_info,
                            '仪器信息：' || COALESCE(manufacturer, '未知') || ' ' || COALESCE(instrument_model, '未知') as instrument_info
                        FROM xrd_experiments
                        ORDER BY created_at DESC
                        LIMIT 5
                    """
                except Exception as e:
                    return f"检查表结构失败：{str(e)}"
            else:
                query = custom_query
            
            pg_source = create_data_source(
                'postgresql',
                **self.postgresql_config,
                query=query
            )
            
            processor = DataProcessor(pg_source)
            df = processor.get_data()
            
            if df.empty:
                return "PostgreSQL数据库中没有找到数据"
            
            # 如果是默认查询，格式化输出
            if not custom_query.strip():
                result_lines = []
                for i, row in df.iterrows():
                    result_lines.append(f"=== XRD实验记录 {i+1} ===")
                    for col in row.index:
                        result_lines.append(row[col])
                    result_lines.append("")
                
                return "\n".join(result_lines)
            else:
                # 自定义查询，返回表格格式
                return df.to_string(index=False)
                
        except Exception as e:
            return f"PostgreSQL数据库查询失败：{str(e)}"
    
    def _extract_sn_from_postgresql(self, custom_query=""):
        """从PostgreSQL数据库提取S-N数据"""
        try:
            # 如果没有自定义查询，使用默认查询
            if not custom_query.strip():
                # 先检查表是否存在
                try:
                    pg_source = create_data_source(
                        'postgresql',
                        **self.postgresql_config,
                        query="SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sn_fatigue_tests') as table_exists"
                    )
                    processor = DataProcessor(pg_source)
                    df = processor.get_data()
                    
                    if not df.iloc[0]['table_exists']:
                        return "sn_fatigue_tests表不存在，请先创建表并插入数据"
                    
                    # 表存在，查询数据
                    query = """
                        SELECT 
                            '试验信息：' || COALESCE(test_id, '未知') || '，' || COALESCE(material_type, '未知') || '，' || COALESCE(test_standard, 'ASTM E466') as test_info,
                            '试验条件：频率' || COALESCE(test_frequency::text, '0') || 'Hz，温度' || COALESCE(temperature::text, '25') || '°C，应力比R=' || COALESCE(stress_ratio::text, '0') as test_conditions,
                            '数据点：应力幅' || COALESCE(stress_amplitude::text, '0') || 'MPa，失效周期' || COALESCE(cycles_to_failure::text, '0') || '次' as data_point,
                            '试验状态：' || COALESCE(test_status, '未知') as status_info
                        FROM sn_fatigue_tests
                        ORDER BY created_at DESC
                        LIMIT 5
                    """
                except Exception as e:
                    return f"检查表结构失败：{str(e)}"
            else:
                query = custom_query
            
            pg_source = create_data_source(
                'postgresql',
                **self.postgresql_config,
                query=query
            )
            
            processor = DataProcessor(pg_source)
            df = processor.get_data()
            
            if df.empty:
                return "PostgreSQL数据库中没有找到S-N疲劳试验数据"
            
            # 如果是默认查询，格式化输出
            if not custom_query.strip():
                result_lines = []
                for i, row in df.iterrows():
                    result_lines.append(f"=== S-N试验记录 {i+1} ===")
                    for col in row.index:
                        result_lines.append(row[col])
                    result_lines.append("")
                
                return "\n".join(result_lines)
            else:
                # 自定义查询，返回表格格式
                return df.to_string(index=False)
                
        except Exception as e:
            return f"PostgreSQL S-N数据库查询失败：{str(e)}"
    


    
    def _bind_sn_events(self, submit_btn1, input_box1, chatbot1, clear_btn1,
                       data_file, extract_data_btn, comprehensive_btn, clear_data_btn,
                       sn_db_query, sn_db_extract_btn, sn_db_check_btn, sn_db_status,
                       sn_mongo_collection, sn_mongo_query, sn_mongo_extract_btn, sn_mongo_check_btn, sn_mongo_status,
                       sn_pg_query, sn_pg_extract_btn, sn_pg_check_btn, sn_pg_status,
                       sn_prompt_box, reset_sn_prompt_btn, apply_sn_prompt_btn, sn_prompt_status):
        """绑定S-N相关事件"""
        
        def on_submit_sn(sn_text, chat_history):
            """处理S-N文本提交"""
            if not sn_text.strip():
                return "", chat_history
            
            # 使用当前设置的提示词进行评价
            if self.current_sn_prompt:
                # 如果有自定义提示词，使用自定义提示词
                result = self.sn_evaluator.llm_client.chat(self.current_sn_prompt, sn_text)
            else:
                # 否则使用默认评价方法
                result = self.sn_evaluator.evaluate_text(sn_text)
            
            # 添加到聊天历史
            chat_history.append((sn_text, result))
            
            # 返回空字符串清空文本框，更新聊天历史
            return "", chat_history

        def extract_data_to_textbox(file_obj, current_text):
            """提取数据文件内容到文本框（追加到现有内容）"""
            if file_obj is None:
                return current_text + "\n\n请先上传数据文件"
            
            file_name = getattr(file_obj, 'name', 'unknown_file')
            file_path = file_name.lower()
            
            if file_path.endswith('.csv'):
                extracted_info = self.sn_evaluator.extract_csv_to_text(file_obj)
            elif file_path.endswith(('.xlsx', '.xls', '.json')):
                extracted_info = self.sn_evaluator.extract_data_file_to_text(file_obj.name)
            else:
                extracted_info = "不支持的文件格式，请上传CSV、Excel或JSON文件"
            
            # 如果文本框为空，直接返回提取的信息
            if not current_text.strip():
                return extracted_info
            
            # 如果文本框有内容，追加提取的信息
            return current_text + "\n\n" + "="*50 + "\n从数据文件提取的信息：\n" + "="*50 + "\n" + extracted_info

        def analyze_data_comprehensive(file_obj, metadata_text, chat_history):
            """综合分析数据文件 - LLM + E739统计分析"""
            if file_obj is None:
                return "", chat_history
            
            file_name = getattr(file_obj, 'name', 'unknown_file')
            file_path = file_name.lower()
            
            if file_path.endswith('.csv'):
                filename, data_count, result = self.sn_evaluator.analyze_csv_comprehensive(file_obj, metadata_text)
            elif file_path.endswith(('.xlsx', '.xls', '.json')):
                filename, data_count, result = self.sn_evaluator.analyze_data_file_comprehensive(file_obj.name, metadata_text)
            else:
                filename = file_name
                data_count = 0
                result = "不支持的文件格式，请上传CSV、Excel或JSON文件"
            
            user_message = f"数据综合分析 (LLM + E739)\n文件：{filename}\n数据点数：{data_count}"
            chat_history.append((user_message, result))
            
            # 返回空字符串清空文本框，更新聊天历史
            return "", chat_history
        


        def clear_all_sn():
            return None, ""

        def clear_chat():
            return []
        
        def check_sn_db_connection():
            """检查S-N数据库连接状态"""
            success, message = self._test_sn_mysql_connection()
            status_color = "green" if success else "red"
            return f'<span style="color: {status_color}">数据库状态：{message}</span>'
        
        def extract_from_sn_db(query_text):
            """从S-N数据库提取数据到文本框"""
            extracted = self._extract_from_sn_mysql(query_text)
            return extracted
        


        # 绑定事件
        submit_btn1.click(on_submit_sn, [input_box1, chatbot1], [input_box1, chatbot1])
        input_box1.submit(on_submit_sn, [input_box1, chatbot1], [input_box1, chatbot1])
        clear_btn1.click(clear_chat, None, chatbot1)
        extract_data_btn.click(extract_data_to_textbox, [data_file, input_box1], [input_box1])
        comprehensive_btn.click(analyze_data_comprehensive, [data_file, input_box1, chatbot1], [input_box1, chatbot1])
        clear_data_btn.click(clear_all_sn, [], [data_file])
        
        # S-N数据库相关事件
        sn_db_check_btn.click(check_sn_db_connection, outputs=[sn_db_status])
        sn_db_extract_btn.click(extract_from_sn_db, inputs=[sn_db_query], outputs=[input_box1])
        
        # S-N MongoDB相关事件
        def check_sn_mongo_connection():
            """检查S-N MongoDB连接状态"""
            success, message = self._test_mongodb_connection()
            status_color = "green" if success else "red"
            return f'<span style="color: {status_color}">MongoDB状态：{message}</span>'
        
        def extract_from_sn_mongo(collection_name, query_text):
            """从MongoDB提取S-N数据到文本框"""
            extracted = self._extract_sn_from_mongodb(collection_name, query_text)
            return extracted
        
        sn_mongo_extract_btn.click(extract_from_sn_mongo, inputs=[sn_mongo_collection, sn_mongo_query], outputs=[input_box1])
        sn_mongo_check_btn.click(check_sn_mongo_connection, outputs=[sn_mongo_status])
        
        # S-N PostgreSQL相关事件
        def check_sn_pg_connection():
            """检查S-N PostgreSQL连接状态"""
            success, message = self._test_postgresql_connection()
            status_color = "green" if success else "red"
            return f'<span style="color: {status_color}">PostgreSQL状态：{message}</span>'
        
        def extract_from_sn_pg(query_text):
            """从PostgreSQL提取S-N数据到文本框"""
            extracted = self._extract_sn_from_postgresql(query_text)
            return extracted
        
        sn_pg_extract_btn.click(extract_from_sn_pg, inputs=[sn_pg_query], outputs=[input_box1])
        sn_pg_check_btn.click(check_sn_pg_connection, outputs=[sn_pg_status])
        
        # S-N提示词相关事件
        reset_sn_prompt_btn.click(self._reset_sn_prompt, outputs=[sn_prompt_box])
        apply_sn_prompt_btn.click(self._apply_sn_prompt, inputs=[sn_prompt_box], outputs=[sn_prompt_status])



def main():
    """主函数"""
    # 创建系统实例
    system = MaterialDataEvaluationSystem()
    
    # 创建界面
    demo = system.create_interface()
    
    # 启动应用
    demo.launch()


if __name__ == "__main__":
    main()