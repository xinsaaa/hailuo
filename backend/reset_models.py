"""
重置模型数据脚本
删除所有模型数据并重新初始化
"""
import sys
import os

# 添加backend目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from models import AIModel, engine
import json

def reset_models():
    """删除所有模型并重新初始化"""
    print("🔄 开始重置模型数据...")
    
    with Session(engine) as session:
        # 删除所有现有模型
        models = session.exec(select(AIModel)).all()
        count = len(models)
        for model in models:
            session.delete(model)
        session.commit()
        print(f"✅ 已删除 {count} 个旧模型")
    
    # 手动初始化（不依赖main.py，避免循环导入）
    print("🔄 正在初始化新模型...")
    
    default_models = [
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
    
    with Session(engine) as session:
        for model_data in default_models:
            model = AIModel(**model_data)
            session.add(model)
        session.commit()
        print(f"✅ 已添加 {len(default_models)} 个新模型")
    
    # 验证
    print("\n📊 验证结果:")
    with Session(engine) as session:
        models = session.exec(select(AIModel).order_by(AIModel.sort_order)).all()
        print(f"总计: {len(models)} 个模型\n")
        
        # 按系列分组显示
        series_23 = [m for m in models if '2_0' in m.model_id or '2_3' in m.model_id or '1_0' in m.model_id]
        series_31 = [m for m in models if '3_1' in m.model_id or 'beta_3' in m.model_id]
        
        print("2.3系列 (6个):")
        for model in series_23:
            print(f"  ✓ {model.model_id:25} | {model.display_name:15} | ¥{model.price:.2f}")
        
        print("\n3.1系列 (4个):")
        for model in series_31:
            print(f"  ✓ {model.model_id:25} | {model.display_name:15} | ¥{model.price:.2f}")
        
        # 检查关键模型
        print("\n🔍 关键检查:")
        hailuo_31 = session.exec(select(AIModel).where(AIModel.model_id == "hailuo_3_1")).first()
        hailuo_31_pro = session.exec(select(AIModel).where(AIModel.model_id == "hailuo_3_1_pro")).first()
        
        if hailuo_31:
            print(f"  ✅ hailuo_3_1 存在 - ¥{hailuo_31.price:.2f}")
        else:
            print("  ❌ hailuo_3_1 缺失！")
        
        if hailuo_31_pro:
            print(f"  ✅ hailuo_3_1_pro 存在 - ¥{hailuo_31_pro.price:.2f}")
        else:
            print("  ❌ hailuo_3_1_pro 缺失！")
        
        # 检查价格
        unique_prices = set(m.price for m in models)
        print(f"\n💰 价格种类: {len(unique_prices)} 种")
        print(f"  价格列表: {sorted(unique_prices)}")
        
        if len(unique_prices) == 1:
            print("  ⚠️  警告：所有模型价格相同！")
        else:
            print("  ✅ 价格设置正确")

if __name__ == "__main__":
    try:
        reset_models()
        print("\n✅ 重置完成！请重启后端服务。")
    except Exception as e:
        print(f"\n❌ 重置失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
