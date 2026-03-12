"""
启动时自动恢复模块
用于处理断电、崩溃等异常情况导致的订单状态异常
"""
import asyncio
from datetime import datetime, timedelta
from sqlmodel import Session, select
from backend.models import JimengOrder, engine
from backend.admin_jimeng_account import _load_jimeng_accounts, _save_jimeng_accounts


def fix_account_task_counts():
    """修复账号任务计数（断电后可能不准确）"""
    print("[RECOVERY] 修复账号任务计数...")

    try:
        data = _load_jimeng_accounts()

        # 重置所有账号的任务计数为 0
        for account in data.get("accounts", []):
            old_count = account.get("current_tasks", 0)
            account["current_tasks"] = 0
            if old_count > 0:
                print(f"[RECOVERY] 账号 {account.get('display_name', account.get('account_id'))} 任务计数: {old_count} -> 0")

        _save_jimeng_accounts(data)
        print("[RECOVERY] ✓ 账号任务计数已重置")
        return True
    except Exception as e:
        print(f"[RECOVERY] ✗ 修复账号任务计数失败: {e}")
        return False


def recover_stuck_orders():
    """恢复卡住的订单"""
    print("[RECOVERY] 检查卡住的订单...")

    try:
        with Session(engine) as session:
            # 查找所有 processing 或 generating 状态的订单
            stuck_orders = session.exec(
                select(JimengOrder).where(
                    JimengOrder.status.in_(["processing", "generating"])
                )
            ).all()

            if not stuck_orders:
                print("[RECOVERY] ✓ 没有卡住的订单")
                return []

            print(f"[RECOVERY] 找到 {len(stuck_orders)} 个卡住的订单")

            recovered_order_ids = []

            for order in stuck_orders:
                # 检查订单创建时间，如果超过 30 分钟还在处理中，认为是异常
                time_elapsed = datetime.utcnow() - order.created_at

                if time_elapsed > timedelta(minutes=30):
                    # 超时订单标记为失败并退款
                    print(f"[RECOVERY] 订单 #{order.id} 超时（{time_elapsed}），标记为失败")
                    order.status = "failed"
                    order.error_message = "服务重启导致任务中断，已自动退款"

                    # 退款（检查是否已退款）
                    from backend.models import User, Transaction
                    user = session.get(User, order.user_id)
                    if user and order.cost > 0:
                        user.balance += order.cost
                        session.add(user)

                        # 记录退款交易
                        refund = Transaction(
                            user_id=order.user_id,
                            amount=order.cost,
                            bonus=0,
                            type="refund"
                        )
                        session.add(refund)
                        print(f"[RECOVERY] 订单 #{order.id} 已退款 {order.cost} 元")
                else:
                    # 未超时的订单重置为 pending，稍后重新处理
                    print(f"[RECOVERY] 订单 #{order.id} 重置为 pending 状态")
                    order.status = "pending"
                    order.progress = 0
                    recovered_order_ids.append(order.id)

                session.add(order)

            session.commit()

            print(f"[RECOVERY] ✓ 已处理 {len(stuck_orders)} 个卡住的订单")
            print(f"[RECOVERY] - 重置为 pending: {len(recovered_order_ids)} 个")
            print(f"[RECOVERY] - 标记为失败: {len(stuck_orders) - len(recovered_order_ids)} 个")

            return recovered_order_ids

    except Exception as e:
        print(f"[RECOVERY] ✗ 恢复订单失败: {e}")
        import traceback
        traceback.print_exc()
        return []


async def resubmit_pending_orders():
    """重新提交 pending 状态的订单"""
    print("[RECOVERY] 重新提交待处理订单...")

    try:
        with Session(engine) as session:
            pending_orders = session.exec(
                select(JimengOrder).where(
                    JimengOrder.status == "pending"
                ).order_by(JimengOrder.created_at)
            ).all()

            if not pending_orders:
                print("[RECOVERY] ✓ 没有待处理订单")
                return

            print(f"[RECOVERY] 找到 {len(pending_orders)} 个待处理订单")

            # 导入后台处理函数
            from backend.jimeng_background import process_jimeng_order

            # 重新提交所有 pending 订单
            for order in pending_orders:
                print(f"[RECOVERY] 重新提交订单 #{order.id}")
                asyncio.create_task(process_jimeng_order(order.id))
                await asyncio.sleep(0.5)  # 避免同时提交太多

            print(f"[RECOVERY] ✓ 已重新提交 {len(pending_orders)} 个订单")

    except Exception as e:
        print(f"[RECOVERY] ✗ 重新提交订单失败: {e}")
        import traceback
        traceback.print_exc()


def check_database_integrity():
    """检查数据库完整性"""
    print("[RECOVERY] 检查数据库完整性...")

    try:
        import sqlite3
        from backend.models import sqlite_file_name

        conn = sqlite3.connect(sqlite_file_name)
        cursor = conn.cursor()

        # 执行完整性检查
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()

        conn.close()

        if result[0] == "ok":
            print("[RECOVERY] ✓ 数据库完整性检查通过")
            return True
        else:
            print(f"[RECOVERY] ✗ 数据库完整性检查失败: {result[0]}")
            return False

    except Exception as e:
        print(f"[RECOVERY] ✗ 数据库检查失败: {e}")
        return False


async def startup_recovery():
    """启动时执行完整恢复流程"""
    print("\n" + "="*60)
    print("[RECOVERY] 开始启动恢复流程...")
    print("="*60 + "\n")

    # 1. 检查数据库完整性
    if not check_database_integrity():
        print("[RECOVERY] ⚠️  数据库可能损坏，请检查备份")

    # 2. 修复账号任务计数
    fix_account_task_counts()

    # 3. 恢复卡住的订单
    recovered_order_ids = recover_stuck_orders()

    # 4. 重新提交待处理订单
    await resubmit_pending_orders()

    print("\n" + "="*60)
    print("[RECOVERY] ✓ 启动恢复流程完成")
    print("="*60 + "\n")


if __name__ == "__main__":
    # 测试恢复流程
    asyncio.run(startup_recovery())
