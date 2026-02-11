"""
验证模型数据脚本
检查数据库中的模型是否正确
"""
import sys
import os

# 添加backend目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from models import AIModel, engine

def verify_models():
    """验证模型数据"""
    print("🔍 开始验证模型数据...\n")
    
    with Session(engine) as session:
        models = session.exec(select(AIModel).order_by(AIModel.sort_order)).all()
        
        # 基本检查
        print(f"📊 模型总数: {len(models)}")
        
        if len(models) != 10:
            print(f"❌ 错误：应该有10个模型，但只找到{len(models)}个")
            return False
        else:
            print("✅ 模型数量正确\n")
        
        # 检查关键模型
        print("🔍 检查关键模型:")
        required_models = [
            "hailuo_2_3",
            "hailuo_2_3_fast", 
            "hailuo_2_0",
            "hailuo_3_1",
            "hailuo_3_1_pro",
            "beta_3_1",
            "beta_3_1_fast",
            "hailuo_1_0_director",
            "hailuo_1_0_live",
            "hailuo_1_0"
        ]
        
        all_found = True
        for model_id in required_models:
            model = session.exec(select(AIModel).where(AIModel.model_id == model_id)).first()
            if model:
                print(f"  ✅ {model_id:25} - ¥{model.price:.2f}")
            else:
                print(f"  ❌ {model_id:25} - 缺失！")
                all_found = False
        
        if not all_found:
            print("\n❌ 有模型缺失！")
            return False
        else:
            print("\n✅ 所有必需模型都存在\n")
        
        # 检查价格
        print("💰 价格检查:")
        expected_prices = {
            "hailuo_2_3": 0.99,
            "hailuo_2_3_fast": 0.79,
            "hailuo_2_0": 1.19,
            "hailuo_3_1": 1.59,
            "hailuo_3_1_pro": 2.99,
            "beta_3_1": 0.69,
            "beta_3_1_fast": 0.35,
            "hailuo_1_0_director": 0.59,
            "hailuo_1_0_live": 0.59,
            "hailuo_1_0": 0.49
        }
        
        price_correct = True
        for model_id, expected_price in expected_prices.items():
            model = session.exec(select(AIModel).where(AIModel.model_id == model_id)).first()
            if model:
                if abs(model.price - expected_price) < 0.01:  # 浮点数比较
                    print(f"  ✅ {model_id:25} - ¥{model.price:.2f}")
                else:
                    print(f"  ❌ {model_id:25} - ¥{model.price:.2f} (应该是 ¥{expected_price:.2f})")
                    price_correct = False
        
        if not price_correct:
            print("\n❌ 价格设置不正确！")
            return False
        else:
            print("\n✅ 所有价格设置正确\n")
        
        # 按系列分组
        print("📋 按系列分组:")
        
        series_23 = [m for m in models if '2_0' in m.model_id or '2_3' in m.model_id or '1_0' in m.model_id]
        series_31 = [m for m in models if '3_1' in m.model_id or 'beta_3' in m.model_id]
        
        print(f"\n2.3系列 ({len(series_23)}个):")
        if len(series_23) != 6:
            print(f"  ❌ 应该有6个模型，但只有{len(series_23)}个")
            price_correct = False
        else:
            print("  ✅ 数量正确")
        for model in series_23:
            print(f"    - {model.model_id:25} | {model.display_name:15} | ¥{model.price:.2f}")
        
        print(f"\n3.1系列 ({len(series_31)}个):")
        if len(series_31) != 4:
            print(f"  ❌ 应该有4个模型，但只有{len(series_31)}个")
            price_correct = False
        else:
            print("  ✅ 数量正确")
        for model in series_31:
            print(f"    - {model.model_id:25} | {model.display_name:15} | ¥{model.price:.2f}")
        
        # 检查价格多样性
        print("\n💰 价格多样性:")
        unique_prices = set(m.price for m in models)
        print(f"  不同价格数量: {len(unique_prices)}")
        print(f"  价格列表: {sorted(unique_prices)}")
        
        if len(unique_prices) == 1:
            print("  ❌ 所有模型价格相同！这是错误的！")
            return False
        elif len(unique_prices) < 8:
            print(f"  ⚠️  警告：价格种类较少（{len(unique_prices)}种）")
        else:
            print("  ✅ 价格多样性正常")
        
        # 检查sort_order
        print("\n🔢 排序检查:")
        sort_orders = [m.sort_order for m in models]
        expected_orders = list(range(1, 11))
        
        if sort_orders == expected_orders:
            print("  ✅ 排序正确 (1-10)")
        else:
            print(f"  ❌ 排序错误")
            print(f"    期望: {expected_orders}")
            print(f"    实际: {sort_orders}")
            return False
        
        # 检查默认模型
        print("\n⭐ 默认模型:")
        default_models = [m for m in models if m.is_default]
        if len(default_models) == 1:
            print(f"  ✅ {default_models[0].model_id} ({default_models[0].display_name})")
        elif len(default_models) == 0:
            print("  ❌ 没有设置默认模型")
            return False
        else:
            print(f"  ⚠️  警告：有{len(default_models)}个默认模型")
        
        # 检查启用状态
        print("\n🔓 启用状态:")
        enabled_count = len([m for m in models if m.is_enabled])
        if enabled_count == len(models):
            print(f"  ✅ 所有{enabled_count}个模型都已启用")
        else:
            print(f"  ⚠️  只有{enabled_count}/{len(models)}个模型启用")
        
        print("\n" + "="*60)
        print("✅ 验证通过！模型数据正确！")
        print("="*60)
        
        return True

if __name__ == "__main__":
    try:
        success = verify_models()
        if success:
            print("\n✅ 所有检查通过！")
            print("\n📝 下一步:")
            print("   1. 确保后端服务正在运行")
            print("   2. 测试API: curl http://localhost:8000/api/models")
            print("   3. 在浏览器中测试前端功能")
            sys.exit(0)
        else:
            print("\n❌ 验证失败！请运行 reset_models.py 重置数据库")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 验证过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
