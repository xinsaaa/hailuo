"""
AI模型配置管理：统一的模型定义，避免重复代码
"""
import json
from typing import List, Dict, Any


class ModelConfigManager:
    """模型配置管理器"""
    
    @staticmethod
    def get_default_models() -> List[Dict[str, Any]]:
        """获取默认模型配置，统一维护避免重复定义"""
        return [
            {
                "model_id": "hailuo_2_3",
                "name": "Hailuo 2.3",
                "display_name": "海螺 2.3",
                "description": "表现力全面升级，更稳定，更真实",
                "features": json.dumps(["768P-1080P", "6s-10s", "仅首帧"]),
                "badge": "NEW",
                "supports_last_frame": False,
                "is_default": True,
                "is_enabled": True,
                "sort_order": 1,
                "price": 0.99
            },
            {
                "model_id": "hailuo_2_3_fast",
                "name": "Hailuo 2.3-Fast",
                "display_name": "海螺 2.3-Fast",
                "description": "生成速度更快，超高性价比",
                "features": json.dumps(["768P-1080P", "6s-10s", "仅首帧"]),
                "badge": "NEW",
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 2,
                "price": 0.79
            },
            {
                "model_id": "hailuo_2_0",
                "name": "Hailuo 2.0",
                "display_name": "海螺 2.0",
                "description": "最佳效果、超清画质、精准响应",
                "features": json.dumps(["首尾帧", "仅尾帧", "512P-1080P", "6s-10s"]),
                "badge": "NEW",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 3,
                "price": 1.19
            },
            {
                "model_id": "hailuo_3_1",
                "name": "Hailuo 3.1",
                "display_name": "海螺 3.1",
                "description": "最新版本，极致画质，智能优化",
                "features": json.dumps(["1080P", "首尾帧", "10s", "智能优化"]),
                "badge": "HOT",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 4,
                "price": 1.59
            },
            {
                "model_id": "hailuo_3_1_pro",
                "name": "Hailuo 3.1-Pro",
                "display_name": "海螺 3.1-Pro",
                "description": "专业版本，极致细节，完美画质",
                "features": json.dumps(["4K", "首尾帧", "15s", "专业调色"]),
                "badge": "PRO",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 5,
                "price": 2.99
            },
            {
                "model_id": "beta_3_1",
                "name": "Beta 3.1",
                "display_name": "Beta 3.1",
                "description": "音画同步，高保真，精准控制",
                "features": json.dumps(["音画同出", "首尾帧", "720P-1080P", "8s"]),
                "badge": "BETA",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 6,
                "price": 0.69
            },
            {
                "model_id": "beta_3_1_fast",
                "name": "Beta 3.1 Fast",
                "display_name": "Beta 3.1 Fast",
                "description": "音画同步，更高速，更高性价比",
                "features": json.dumps(["音画同出", "首尾帧", "720P-1080P", "8s"]),
                "badge": "5折",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 7,
                "price": 0.35
            },
            {
                "model_id": "hailuo_1_0_director",
                "name": "Hailuo 1.0-Director",
                "display_name": "海螺 1.0-Director",
                "description": "像专业导演一样控制镜头运动",
                "features": json.dumps(["720P", "6s", "仅首帧"]),
                "badge": None,
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 8,
                "price": 0.59
            },
            {
                "model_id": "hailuo_1_0_live",
                "name": "Hailuo 1.0-Live",
                "display_name": "海螺 1.0-Live",
                "description": "角色表现增强，稳定、流畅、生动",
                "features": json.dumps(["720P", "6s", "仅首帧"]),
                "badge": None,
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 9,
                "price": 0.59
            },
            {
                "model_id": "hailuo_1_0",
                "name": "Hailuo 1.0",
                "display_name": "海螺 1.0",
                "description": "01系列的基础图生视频模型",
                "features": json.dumps(["720P", "6s", "仅首帧"]),
                "badge": None,
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 10,
                "price": 0.49
            }
        ]
    
    @staticmethod
    def get_models_by_series(series: str = "all") -> List[str]:
        """根据系列获取模型ID列表，用于前端过滤"""
        series_mapping = {
            "2.3": ["hailuo_2_3", "hailuo_2_3_fast", "hailuo_2_0", "hailuo_1_0", "hailuo_1_0_director", "hailuo_1_0_live"],
            "3.1": ["hailuo_3_1", "hailuo_3_1_pro", "beta_3_1", "beta_3_1_fast"],
            "all": [model["model_id"] for model in ModelConfigManager.get_default_models()]
        }
        return series_mapping.get(series, series_mapping["all"])
    
    @staticmethod
    def validate_model_config(model_data: Dict[str, Any]) -> tuple[bool, str]:
        """验证模型配置的完整性和正确性"""
        required_fields = [
            "model_id", "name", "display_name", "description", 
            "features", "sort_order", "price"
        ]
        
        for field in required_fields:
            if field not in model_data:
                return False, f"缺少必需字段: {field}"
        
        # 验证价格
        if not isinstance(model_data["price"], (int, float)) or model_data["price"] < 0:
            return False, "价格必须是非负数"
        
        # 验证排序顺序
        if not isinstance(model_data["sort_order"], int) or model_data["sort_order"] < 0:
            return False, "排序顺序必须是非负整数"
        
        return True, "配置有效"


# 全局模型配置管理器
model_config = ModelConfigManager()
