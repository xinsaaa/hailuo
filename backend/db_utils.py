"""
数据库工具模块：提供通用的数据库操作，减少重复代码，优化性能
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, and_, or_
from backend.models import User, VideoOrder, Transaction, AIModel, IPBan, LoginFailure, engine
from datetime import datetime, timedelta


class DatabaseManager:
    """数据库管理器，提供优化的批量操作和查询缓存"""
    
    def __init__(self):
        self._model_cache = {}
        self._cache_timeout = 300  # 5分钟缓存
        
    def get_session(self):
        """获取数据库会话"""
        return Session(engine)
    
    # ============ 用户相关操作 ============
    
    def get_user_by_username(self, session: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return session.exec(select(User).where(User.username == username)).first()
    
    def get_user_by_email(self, session: Session, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return session.exec(select(User).where(User.email == email)).first()
    
    def get_user_by_device(self, session: Session, device_fingerprint: str) -> Optional[User]:
        """根据设备指纹获取用户"""
        return session.exec(
            select(User).where(User.device_fingerprint == device_fingerprint)
        ).first()
    
    def get_user_by_ip(self, session: Session, ip: str) -> Optional[User]:
        """根据注册IP获取用户"""
        return session.exec(select(User).where(User.register_ip == ip)).first()
    
    def check_user_conflicts(self, session: Session, username: str, email: str, 
                           device_fingerprint: str, register_ip: str) -> Dict[str, Any]:
        """批量检查用户冲突，减少查询次数"""
        # 使用单个查询检查所有冲突
        conflicts = session.exec(
            select(User).where(
                or_(
                    User.username == username,
                    User.email == email,
                    User.device_fingerprint == device_fingerprint,
                    User.register_ip == register_ip
                )
            )
        ).all()
        
        result = {
            "username_exists": False,
            "email_exists": False,
            "device_registered": False,
            "ip_registered": False,
            "existing_users": []
        }
        
        for user in conflicts:
            result["existing_users"].append(user)
            if user.username == username:
                result["username_exists"] = True
            if user.email == email:
                result["email_exists"] = True
            if user.device_fingerprint == device_fingerprint:
                result["device_registered"] = True
            if user.register_ip == register_ip:
                result["ip_registered"] = True
                
        return result
    
    # ============ 模型相关操作 ============
    
    def get_models_with_cache(self, session: Session, force_refresh: bool = False) -> List[AIModel]:
        """获取模型列表，带缓存优化"""
        cache_key = "all_models"
        now = datetime.now()
        
        # 检查缓存
        if not force_refresh and cache_key in self._model_cache:
            cached_data = self._model_cache[cache_key]
            if (now - cached_data["timestamp"]).seconds < self._cache_timeout:
                return cached_data["data"]
        
        # 查询数据库
        models = session.exec(
            select(AIModel)
            .where(AIModel.is_enabled == True)
            .order_by(AIModel.sort_order)
        ).all()
        
        # 更新缓存
        self._model_cache[cache_key] = {
            "data": models,
            "timestamp": now
        }
        
        return models
    
    def get_model_by_id(self, session: Session, model_id: str) -> Optional[AIModel]:
        """根据模型ID获取模型"""
        return session.exec(
            select(AIModel).where(AIModel.model_id == model_id)
        ).first()
    
    # ============ 安全相关操作 ============
    
    def get_security_status(self, session: Session, ip: str) -> Dict[str, Any]:
        """批量获取IP安全状态，减少查询次数"""
        # 使用单个查询获取封禁和失败记录
        ban = session.exec(select(IPBan).where(IPBan.ip == ip)).first()
        failure = session.exec(select(LoginFailure).where(LoginFailure.ip == ip)).first()
        
        now = datetime.now()
        is_banned = False
        ban_remaining = 0
        fail_count = 0
        
        if ban and now < ban.expires_at:
            is_banned = True
            ban_remaining = int((ban.expires_at - now).total_seconds())
        elif ban:
            # 封禁已过期，删除记录
            session.delete(ban)
            if failure:
                failure.fail_count = 0
                failure.last_fail_at = None
                session.add(failure)
            session.commit()
        
        if failure:
            fail_count = failure.fail_count
            
        return {
            "is_banned": is_banned,
            "ban_remaining_seconds": ban_remaining,
            "fail_count": fail_count,
            "need_captcha": fail_count >= 3
        }
    
    def record_login_attempt(self, session: Session, ip: str, success: bool) -> bool:
        """记录登录尝试，返回是否触发封禁"""
        failure = session.exec(select(LoginFailure).where(LoginFailure.ip == ip)).first()
        
        if success:
            # 登录成功，清除失败记录
            if failure:
                failure.fail_count = 0
                failure.last_fail_at = None
                session.add(failure)
                session.commit()
            return False
        
        # 登录失败，更新失败次数
        if not failure:
            failure = LoginFailure(ip=ip, fail_count=1, last_fail_at=datetime.now())
            session.add(failure)
        else:
            failure.fail_count += 1
            failure.last_fail_at = datetime.now()
            session.add(failure)
        
        # 检查是否需要封禁
        if failure.fail_count >= 10:  # BAN_THRESHOLD
            existing_ban = session.exec(select(IPBan).where(IPBan.ip == ip)).first()
            if not existing_ban:
                ban = IPBan(
                    ip=ip,
                    expires_at=datetime.now() + timedelta(minutes=30)  # BAN_DURATION_MINUTES
                )
                session.add(ban)
            session.commit()
            return True
        
        session.commit()
        return False
    
    # ============ 订单相关操作 ============
    
    def get_user_orders_paginated(self, session: Session, user_id: int, 
                                 page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """分页获取用户订单"""
        offset = (page - 1) * limit
        
        orders = session.exec(
            select(VideoOrder)
            .where(VideoOrder.user_id == user_id)
            .order_by(VideoOrder.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        
        total = session.exec(
            select(VideoOrder).where(VideoOrder.user_id == user_id)
        ).count()
        
        return {
            "orders": orders,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": offset + limit < total
        }
    
    # ============ 缓存管理 ============
    
    def clear_cache(self, cache_key: str = None):
        """清除缓存"""
        if cache_key:
            self._model_cache.pop(cache_key, None)
        else:
            self._model_cache.clear()


# 全局数据库管理器实例
db_manager = DatabaseManager()
