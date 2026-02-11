"""
重置模型数据脚本
删除所有模型数据并重新初始化
"""
from sqlmodel import Session, select
from models import AIModel, engine

def reset_models():
    """删除所有模型并重新初始化"""
    with Session(engine) as session:
        # 删除所有现有模型
        models = session.exec(select(AIModel)).all()
        for model in models:
            session.delete(model)
        session.commit()
        print(f"✅ 已删除 {len(models)} 个旧模型")
    
    # 重新初始化
    from main import init_default_models
    init_default_models()
    print("✅ 模型数据已重新初始化")
    
    # 验证
    with Session(engine) as session:
        models = session.exec(select(AIModel).order_by(AIModel.sort_order)).all()
        print(f"\n📊 当前模型列表 ({len(models)}个):")
        for model in models:
            print(f"  - {model.model_id:25} | {model.display_name:15} | ¥{model.price:.2f} | sort:{model.sort_order}")

if __name__ == "__main__":
    reset_models()
