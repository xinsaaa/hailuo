"""
图片清理任务 - 自动删除7天前的用户上传图片
"""
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
CLEANUP_DAYS = 7  # 保留天数
USER_IMAGES_DIR = "user_images"  # 用户图片目录

def cleanup_old_images():
    """清理7天前的图片文件"""
    try:
        logger.info("🧹 开始清理过期图片...")
        
        # 计算7天前的时间戳
        cutoff_time = time.time() - (CLEANUP_DAYS * 24 * 60 * 60)
        cutoff_datetime = datetime.fromtimestamp(cutoff_time)
        
        logger.info(f"📅 清理 {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')} 之前的图片")
        
        if not os.path.exists(USER_IMAGES_DIR):
            logger.info("📂 用户图片目录不存在，无需清理")
            return
        
        total_deleted = 0
        total_size_freed = 0
        
        # 遍历所有用户目录
        for user_dir in os.listdir(USER_IMAGES_DIR):
            user_path = os.path.join(USER_IMAGES_DIR, user_dir)
            
            if not os.path.isdir(user_path):
                continue
            
            logger.info(f"🔍 检查用户目录: {user_dir}")
            user_deleted = 0
            user_size_freed = 0
            
            # 遍历用户目录下的所有文件
            for filename in os.listdir(user_path):
                file_path = os.path.join(user_path, filename)
                
                if not os.path.isfile(file_path):
                    continue
                
                # 检查文件修改时间
                file_mtime = os.path.getmtime(file_path)
                
                if file_mtime < cutoff_time:
                    try:
                        # 获取文件大小
                        file_size = os.path.getsize(file_path)
                        
                        # 删除文件
                        os.remove(file_path)
                        
                        user_deleted += 1
                        user_size_freed += file_size
                        
                        logger.debug(f"🗑️  删除文件: {filename} ({file_size} bytes)")
                        
                    except Exception as e:
                        logger.error(f"❌ 删除文件失败 {filename}: {str(e)}")
            
            if user_deleted > 0:
                logger.info(f"✅ {user_dir}: 删除 {user_deleted} 个文件，释放 {user_size_freed/1024/1024:.2f} MB")
                total_deleted += user_deleted
                total_size_freed += user_size_freed
                
                # 如果用户目录为空，删除目录
                try:
                    if not os.listdir(user_path):
                        os.rmdir(user_path)
                        logger.info(f"🗂️  删除空目录: {user_dir}")
                except:
                    pass
            else:
                logger.info(f"✨ {user_dir}: 无过期文件")
        
        if total_deleted > 0:
            logger.info(f"🎉 清理完成! 总共删除 {total_deleted} 个文件，释放 {total_size_freed/1024/1024:.2f} MB 存储空间")
        else:
            logger.info("✨ 无过期文件需要清理")
            
    except Exception as e:
        logger.error(f"💥 清理任务执行失败: {str(e)}")

def cleanup_old_orders():
    """清理数据库中对应的过期订单记录（可选）"""
    try:
        from sqlmodel import Session, select
        from backend.models import VideoOrder, engine
        from datetime import datetime, timedelta
        
        logger.info("🗃️  开始清理过期订单记录...")
        
        # 清理30天前的已完成订单记录（保留更长时间）
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        with Session(engine) as session:
            # 查找过期的已完成订单
            old_orders = session.exec(
                select(VideoOrder).where(
                    VideoOrder.created_at < cutoff_date,
                    VideoOrder.status == "completed"
                )
            ).all()
            
            deleted_count = 0
            for order in old_orders:
                # 删除关联的图片文件
                if order.first_frame_image and os.path.exists(order.first_frame_image):
                    try:
                        os.remove(order.first_frame_image)
                    except:
                        pass
                        
                if order.last_frame_image and os.path.exists(order.last_frame_image):
                    try:
                        os.remove(order.last_frame_image)
                    except:
                        pass
                
                # 删除订单记录
                session.delete(order)
                deleted_count += 1
            
            session.commit()
            
            if deleted_count > 0:
                logger.info(f"🗃️  删除 {deleted_count} 个过期订单记录")
            else:
                logger.info("✨ 无过期订单记录需要清理")
                
    except Exception as e:
        logger.error(f"💥 订单清理失败: {str(e)}")

def get_storage_stats():
    """获取存储使用统计"""
    try:
        if not os.path.exists(USER_IMAGES_DIR):
            return {"total_files": 0, "total_size_mb": 0}
        
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(USER_IMAGES_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                    total_files += 1
                except:
                    pass
        
        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / 1024 / 1024, 2)
        }
    except:
        return {"total_files": 0, "total_size_mb": 0}

if __name__ == "__main__":
    # 获取当前存储统计
    before_stats = get_storage_stats()
    logger.info(f"📊 清理前统计: {before_stats['total_files']} 个文件，{before_stats['total_size_mb']} MB")
    
    # 执行清理
    cleanup_old_images()
    cleanup_old_orders()
    
    # 获取清理后统计
    after_stats = get_storage_stats()
    logger.info(f"📊 清理后统计: {after_stats['total_files']} 个文件，{after_stats['total_size_mb']} MB")
    
    freed_mb = before_stats['total_size_mb'] - after_stats['total_size_mb']
    if freed_mb > 0:
        logger.info(f"💾 释放存储空间: {freed_mb} MB")
