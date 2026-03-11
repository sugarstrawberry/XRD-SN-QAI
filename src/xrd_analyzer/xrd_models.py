"""
XRD评分模型
包含评分标准、权重计算等核心逻辑
"""

import yaml


class XRDScoringModel:
    """XRD数据质量评分模型"""
    
    def __init__(self, config_path=None):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.criteria = self.config['CRITERIA']
        self.default_weights = self.config['SCORING']['WEIGHTS']
        self.grade_thresholds = self.config['SCORING']['GRADE_THRESHOLDS']
        self.strictness_levels = self.config['STRICTNESS_LEVELS']

    
    def generate_scoring_prompt(self, weights, A, B, C, strictness):
        """从配置文件生成评分提示词"""
        # 获取提示词模板
        template = self.config.get('PROMPTS', {}).get('SCORING_TEMPLATE', '')
        
        # 构建严格度描述
        strictness_description = self.strictness_levels.get(strictness, "采用标准评分标准。")
        
        # 构建评分标准部分
        criteria_section = ""
        for category, criteria in self.criteria.items():
            original_weight = self.default_weights[category]
            criteria_section += f"{category} (原始满分{original_weight}分):\n"
            if isinstance(criteria, dict):
                for sub_cat, sub_criteria in criteria.items():
                    criteria_section += f"  {sub_cat}: {sub_criteria}\n"
            else:
                criteria_section += f"{criteria}\n"
            criteria_section += "\n"
        
        # 构建权重部分
        weights_section = ""
        for category, weight in weights.items():
            weights_section += f"{category}: {weight}分\n"
        
        # 填充模板
        prompt = template.format(
            strictness_description=strictness_description,
            criteria_section=criteria_section,
            weights_section=weights_section,
            grade_A=A,
            grade_B=B,
            grade_C=C,
            grade_A_minus_1=A-1,
            grade_B_minus_1=B-1
        )
        
        return prompt

    
    def get_file_extraction_prompt(self):
        """获取文件提取提示词"""
        return self.config.get('PROMPTS', {}).get('FILE_EXTRACTION', '')
    
    def validate_weights(self, weights):
        # 验证权重配置
        total_weight = sum(weights.values())
        if total_weight != 100:
            return False, f"权重总和必须为100分，当前为{total_weight}分"
        return True, ""
    
    def validate_grade_thresholds(self, A, B, C):
        # 验证等级阈值
        try:
            A, B, C = int(A), int(B), int(C)
        except:
            return False, "请输入有效的整数分数"
        
        if A <= B:
            return False, "A级最低分必须大于B级最低分"
        elif B <= C:
            return False, "B级最低分必须大于C级最低分"
        elif A <= 0 or B <= 0 or C < 0:
            return False, "等级阈值必须大于0"
        elif A > 100 or B > 100 or C > 100:
            return False, "等级阈值不能超过100分"
        
        return True, ""