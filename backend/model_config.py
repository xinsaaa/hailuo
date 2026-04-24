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
                "price": 0.99,
                "price_10s": 1.49,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.99, "10": 1.49, "per_second": 0.17},
                        "1080p": {"6": 1.29, "10": 1.89, "per_second": 0.22}
                    },
                    "single_image": {
                        "768p": {"6": 0.99, "10": 1.49, "per_second": 0.17},
                        "1080p": {"6": 1.29, "10": 1.89, "per_second": 0.22}
                    },
                    "dual_image": {
                        "768p": {"6": 0.99, "10": 1.49, "per_second": 0.17},
                        "1080p": {"6": 1.29, "10": 1.89, "per_second": 0.22}
                    }
                })
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
                "price": 0.79,
                "price_10s": 1.19,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.79, "10": 1.19, "per_second": 0.13},
                        "1080p": {"6": 0.99, "10": 1.49, "per_second": 0.17}
                    },
                    "single_image": {
                        "768p": {"6": 0.79, "10": 1.19, "per_second": 0.13},
                        "1080p": {"6": 0.99, "10": 1.49, "per_second": 0.17}
                    },
                    "dual_image": {
                        "768p": {"6": 0.79, "10": 1.19, "per_second": 0.13},
                        "1080p": {"6": 0.99, "10": 1.49, "per_second": 0.17}
                    }
                })
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
                "price": 1.19,
                "price_10s": 1.79,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 1.19, "10": 1.79, "per_second": 0.20},
                        "1080p": {"6": 1.49, "10": 2.19, "per_second": 0.25}
                    },
                    "single_image": {
                        "768p": {"6": 1.19, "10": 1.79, "per_second": 0.20},
                        "1080p": {"6": 1.49, "10": 2.19, "per_second": 0.25}
                    },
                    "dual_image": {
                        "768p": {"6": 1.49, "10": 2.19, "per_second": 0.25},
                        "1080p": {"6": 1.79, "10": 2.59, "per_second": 0.30}
                    }
                })
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
                "price": 1.59,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 1.39, "10": 1.59, "per_second": 0.18},
                        "1080p": {"6": 1.59, "10": 1.99, "per_second": 0.22}
                    },
                    "single_image": {
                        "768p": {"6": 1.39, "10": 1.59, "per_second": 0.18},
                        "1080p": {"6": 1.59, "10": 1.99, "per_second": 0.22}
                    },
                    "dual_image": {
                        "768p": {"6": 1.59, "10": 1.99, "per_second": 0.22},
                        "1080p": {"6": 1.99, "10": 2.49, "per_second": 0.28}
                    }
                })
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
                "price": 2.99,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 2.49, "10": 2.99, "per_second": 0.35},
                        "1080p": {"6": 2.99, "10": 3.79, "per_second": 0.42}
                    },
                    "single_image": {
                        "768p": {"6": 2.49, "10": 2.99, "per_second": 0.35},
                        "1080p": {"6": 2.99, "10": 3.79, "per_second": 0.42}
                    },
                    "dual_image": {
                        "768p": {"6": 2.99, "10": 3.79, "per_second": 0.42},
                        "1080p": {"6": 3.49, "10": 4.49, "per_second": 0.50}
                    }
                })
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
                "price": 0.69,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.69, "10": 0.69, "per_second": 0.09},
                        "1080p": {"6": 0.89, "10": 0.89, "per_second": 0.11}
                    },
                    "single_image": {
                        "768p": {"6": 0.69, "10": 0.69, "per_second": 0.09},
                        "1080p": {"6": 0.89, "10": 0.89, "per_second": 0.11}
                    },
                    "dual_image": {
                        "768p": {"6": 0.69, "10": 0.69, "per_second": 0.09},
                        "1080p": {"6": 0.89, "10": 0.89, "per_second": 0.11}
                    }
                })
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
                "price": 0.35,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.35, "10": 0.35, "per_second": 0.05},
                        "1080p": {"6": 0.45, "10": 0.45, "per_second": 0.06}
                    },
                    "single_image": {
                        "768p": {"6": 0.35, "10": 0.35, "per_second": 0.05},
                        "1080p": {"6": 0.45, "10": 0.45, "per_second": 0.06}
                    },
                    "dual_image": {
                        "768p": {"6": 0.35, "10": 0.35, "per_second": 0.05},
                        "1080p": {"6": 0.45, "10": 0.45, "per_second": 0.06}
                    }
                })
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
                "price": 0.59,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.59, "per_second": 0.10}
                    },
                    "single_image": {
                        "768p": {"6": 0.59, "per_second": 0.10}
                    },
                    "dual_image": {
                        "768p": {"6": 0.59, "per_second": 0.10}
                    }
                })
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
                "price": 0.59,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.59, "per_second": 0.10}
                    },
                    "single_image": {
                        "768p": {"6": 0.59, "per_second": 0.10}
                    },
                    "dual_image": {
                        "768p": {"6": 0.59, "per_second": 0.10}
                    }
                })
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
                "price": 0.49,
                "pricing_matrix": json.dumps({
                    "text": {
                        "768p": {"6": 0.49, "per_second": 0.08}
                    },
                    "single_image": {
                        "768p": {"6": 0.49, "per_second": 0.08}
                    },
                    "dual_image": {
                        "768p": {"6": 0.49, "per_second": 0.08}
                    }
                })
            },
            {
                "model_id": "seedance_2_0_fast",
                "name": "SeeDance 2.0 Fast",
                "display_name": "SeeDance 2.0 Fast",
                "description": "SeeDance舞蹈视频生成，极速版",
                "features": json.dumps(["480P-720P", "4s-15s", "首尾帧", "21:9/16:9/4:3/1:1/3:4/9:16"]),
                "badge": "NEW",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 11,
                "price": 0.79,
                "pricing_matrix": json.dumps({
                    "text": {
                        "480p": {"per_second": 0.08},
                        "720p": {"per_second": 0.12}
                    },
                    "single_image": {
                        "480p": {"per_second": 0.10},
                        "720p": {"per_second": 0.15}
                    },
                    "dual_image": {
                        "480p": {"per_second": 0.12},
                        "720p": {"per_second": 0.18}
                    }
                })
            },
            {
                "model_id": "seedance_2_0",
                "name": "SeeDance 2.0",
                "display_name": "SeeDance 2.0",
                "description": "SeeDance舞蹈视频生成，高清版",
                "features": json.dumps(["480P-1080P", "4s-15s", "首尾帧", "21:9/16:9/4:3/1:1/3:4/9:16"]),
                "badge": "NEW",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 12,
                "price": 0.99,
                "pricing_matrix": json.dumps({
                    "text": {
                        "480p": {"per_second": 0.08},
                        "720p": {"per_second": 0.12},
                        "1080p": {"per_second": 0.18}
                    },
                    "single_image": {
                        "480p": {"per_second": 0.10},
                        "720p": {"per_second": 0.15},
                        "1080p": {"per_second": 0.22}
                    },
                    "dual_image": {
                        "480p": {"per_second": 0.12},
                        "720p": {"per_second": 0.18},
                        "1080p": {"per_second": 0.26}
                    }
                })
            },
            {
                "model_id": "kling_3_0",
                "name": "Kling 3.0",
                "display_name": "可灵 3.0",
                "description": "可灵最新旗舰，电影级画质，运动流畅自然",
                "features": json.dumps(["1080P", "5s-10s", "单图/双图"]),
                "badge": "NEW",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 11,
                "price": 1.49,
                "platform": "kling",
                "pricing_matrix": json.dumps({
                    "single_image": {
                        "720p": {"5": 1.29, "10": 2.49, "per_second": 0.26},
                        "1080p": {"5": 1.49, "10": 2.89, "per_second": 0.30}
                    },
                    "dual_image": {
                        "720p": {"5": 1.99, "10": 3.49, "per_second": 0.40},
                        "1080p": {"5": 2.29, "10": 3.99, "per_second": 0.46}
                    },
                    "text": {
                        "720p": {"5": 0.99, "10": 1.89, "per_second": 0.20},
                        "1080p": {"5": 1.19, "10": 2.29, "per_second": 0.24}
                    }
                })
            },
            {
                "model_id": "kling_2_6",
                "name": "Kling 2.6",
                "display_name": "可灵 2.6",
                "description": "可灵高性能版本，细节丰富，动作精准",
                "features": json.dumps(["1080P", "5s-10s", "单图/双图"]),
                "badge": None,
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 12,
                "price": 1.19,
                "platform": "kling",
                "pricing_matrix": json.dumps({
                    "single_image": {
                        "720p": {"5": 0.99, "10": 1.89, "per_second": 0.20},
                        "1080p": {"5": 1.19, "10": 2.29, "per_second": 0.24}
                    },
                    "dual_image": {
                        "720p": {"5": 1.49, "10": 2.69, "per_second": 0.30},
                        "1080p": {"5": 1.79, "10": 3.29, "per_second": 0.36}
                    },
                    "text": {
                        "720p": {"5": 0.79, "10": 1.49, "per_second": 0.16},
                        "1080p": {"5": 0.99, "10": 1.89, "per_second": 0.20}
                    }
                })
            },
            {
                "model_id": "kling_2_5_turbo",
                "name": "Kling 2.5 Turbo",
                "display_name": "可灵 2.5 Turbo",
                "description": "可灵专业版，极速生成，高性价比",
                "features": json.dumps(["1080P", "5s-10s", "单图/双图"]),
                "badge": "PRO",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 13,
                "price": 0.99,
                "platform": "kling",
                "pricing_matrix": json.dumps({
                    "single_image": {
                        "720p": {"5": 0.79, "10": 1.49, "per_second": 0.16},
                        "1080p": {"5": 0.99, "10": 1.89, "per_second": 0.20}
                    },
                    "dual_image": {
                        "720p": {"5": 1.19, "10": 2.19, "per_second": 0.24},
                        "1080p": {"5": 1.49, "10": 2.69, "per_second": 0.30}
                    },
                    "text": {
                        "720p": {"5": 0.59, "10": 1.09, "per_second": 0.12},
                        "1080p": {"5": 0.79, "10": 1.49, "per_second": 0.16}
                    }
                })
            },
            {
                "model_id": "kling_lip_sync",
                "name": "Kling Lip Sync",
                "display_name": "可灵对口型",
                "description": "可灵数字人/视频对口型，支持文本转语音驱动",
                "features": json.dumps(["对口型", "文本配音", "音频驱动"]),
                "badge": "NEW",
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 14,
                "price": 2.99,
                "price_per_second": 0.30,
                "platform": "kling",
                "model_type": "lip_sync"
            },
            # ============ GPT Image 2 文生图模型 ============
            {
                "model_id": "gptimage_pro_flex",
                "name": "nova-image-pro-flex",
                "display_name": "GPT Image 2",
                "description": "OpenAI 旗舰文生图，支持文字渲染，精准控制",
                "features": json.dumps(["文字渲染", "精准控制", "2K画质"]),
                "badge": "NEW",
                "supports_last_frame": False,
                "is_default": True,
                "is_enabled": True,
                "sort_order": 20,
                "price": 0.50,
                "platform": "gptimage",
                "model_type": "text_to_image"
            },
            {
                "model_id": "gptimage_pro",
                "name": "nova-image-pro",
                "display_name": "GPT Image 2 Pro",
                "description": "更多宽高比支持，更丰富细节",
                "features": json.dumps(["11种宽高比", "4K画质", "极致细节"]),
                "badge": "PRO",
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 21,
                "price": 0.80,
                "platform": "gptimage",
                "model_type": "text_to_image"
            },
        ]
    
    @staticmethod
    def get_models_by_series(series: str = "all") -> List[str]:
        """根据系列获取模型ID列表，用于前端过滤"""
        series_mapping = {
            "2.3": ["hailuo_2_3", "hailuo_2_3_fast", "hailuo_2_0", "hailuo_1_0", "hailuo_1_0_director", "hailuo_1_0_live"],
            "3.1": ["hailuo_3_1", "hailuo_3_1_pro", "beta_3_1", "beta_3_1_fast"],
            "kling": ["kling_3_0", "kling_2_6", "kling_2_5_turbo", "kling_lip_sync"],
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
