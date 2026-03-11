"""
LLM客户端封装模块
统一管理与大语言模型的交互
"""

from langchain_deepseek import ChatDeepSeek
from langchain.schema import HumanMessage, SystemMessage
import yaml
import os


class LLMClient:
    def __init__(self, config_path=None):
        # 初始化LLM客户端,config_path: 配置文件路径，如果为None则使用默认配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        llm_config = config.get('LLM', {})
        
        self.chat_model = ChatDeepSeek(
            model=llm_config['MODEL'],
            temperature=llm_config['TEMPERATURE'],
            api_key=llm_config['API_KEY']
        )
    
    def chat(self, system_prompt, user_message):
        # 与LLM进行对话
        try:
            messages = [
                SystemMessage(content=system_prompt),  # 系统提示词
                HumanMessage(content=user_message)     # 用户消息
            ]
            response = self.chat_model.invoke(messages)
            return response.content   # LLM的回复
        except Exception as e:
            return f"LLM调用失败: {str(e)}"