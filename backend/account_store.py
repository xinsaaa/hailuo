"""
账号存储管理 - 纯HTTP模式，无浏览器依赖
账号元信息存 accounts.json，凭证（cookie/uuid/device_id）存 accounts_credentials.json
"""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

DATA_DIR = Path(__file__).parent
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
CREDS_FILE = DATA_DIR / "accounts_credentials.json"


@dataclass
class AccountConfig:
    account_id: str
    phone_number: str
    display_name: str
    priority: int = 5
    is_active: bool = True
    max_concurrent: int = 3
    current_tasks: int = 0
    series: str = "2.3"


class AccountStore:
    """账号配置管理器（线程安全不需要，asyncio单线程）"""

    def __init__(self):
        self.accounts: Dict[str, AccountConfig] = {}
        self._creds: Dict[str, dict] = {}  # {account_id: {cookie, uuid, device_id}}
        self._load()

    # ---- 持久化 ----

    def _load(self):
        if ACCOUNTS_FILE.exists():
            try:
                data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
                for acc in data.get("accounts", []):
                    cfg = AccountConfig(
                        account_id=acc["account_id"],
                        phone_number=acc.get("phone_number", ""),
                        display_name=acc.get("display_name", acc["account_id"]),
                        priority=acc.get("priority", 5),
                        is_active=acc.get("is_active", True),
                        max_concurrent=acc.get("max_concurrent", 3),
                        current_tasks=0,
                        series=acc.get("series", "2.3"),
                    )
                    self.accounts[cfg.account_id] = cfg
            except Exception as e:
                print(f"[AccountStore] 加载账号失败: {e}")

        if CREDS_FILE.exists():
            try:
                self._creds = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[AccountStore] 加载凭证失败: {e}")

    def save(self):
        accounts_list = [
            {
                "account_id": acc.account_id,
                "phone_number": acc.phone_number,
                "display_name": acc.display_name,
                "priority": acc.priority,
                "is_active": acc.is_active,
                "max_concurrent": acc.max_concurrent,
                "current_tasks": 0,
                "series": acc.series,
            }
            for acc in self.accounts.values()
        ]
        ACCOUNTS_FILE.write_text(
            json.dumps({"accounts": accounts_list, "settings": {}}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        CREDS_FILE.write_text(
            json.dumps(self._creds, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- CRUD ----

    def add_account(self, cfg) -> AccountConfig:
        """添加账号。cfg 可为 AccountConfig 对象或含账号字段的 dict（dict 时可含 cookie/uuid/device_id 凭证）"""
        if isinstance(cfg, AccountConfig):
            acc = cfg
            acc.current_tasks = 0
        else:
            acc = AccountConfig(
                account_id=cfg["account_id"],
                phone_number=cfg.get("phone_number", ""),
                display_name=cfg.get("display_name", cfg["account_id"]),
                priority=cfg.get("priority", 5),
                is_active=cfg.get("is_active", True),
                max_concurrent=cfg.get("max_concurrent", 3),
                current_tasks=0,
                series=cfg.get("series", "2.3"),
            )
            # 保存凭证
            cred = {}
            for k in ("cookie", "uuid", "device_id", "token"):
                if k in cfg:
                    cred[k] = cfg[k]
            if cred:
                self._creds[acc.account_id] = cred
        self.accounts[acc.account_id] = acc
        self.save()
        return acc

    def remove_account(self, account_id: str):
        self.accounts.pop(account_id, None)
        self._creds.pop(account_id, None)
        self.save()

    def update_account(self, account_id: str, **kwargs):
        acc = self.accounts.get(account_id)
        if not acc:
            return
        for k, v in kwargs.items():
            if hasattr(acc, k):
                setattr(acc, k, v)
        # 凭证字段单独处理
        cred_keys = {k for k in kwargs if k in ("cookie", "uuid", "device_id", "token")}
        if cred_keys:
            cred = self._creds.setdefault(account_id, {})
            for k in cred_keys:
                cred[k] = kwargs[k]
        self.save()

    def get_creds(self, account_id: str) -> Optional[dict]:
        return self._creds.get(account_id)

    def set_creds(self, account_id: str, cookie: str, uuid: str, device_id: str):
        self._creds[account_id] = {"cookie": cookie, "uuid": uuid, "device_id": device_id}
        self.save()

    # ---- 调度辅助 ----

    def pick_account_for_series(self, series: str) -> Optional[str]:
        """按优先级选一个可用账号"""
        candidates = [
            acc for acc in self.accounts.values()
            if acc.is_active
            and acc.series == series
            and acc.current_tasks < acc.max_concurrent
            and acc.account_id in self._creds
        ]
        if not candidates:
            # 降级：忽略系列限制
            candidates = [
                acc for acc in self.accounts.values()
                if acc.is_active
                and acc.current_tasks < acc.max_concurrent
                and acc.account_id in self._creds
            ]
        if not candidates:
            return None
        candidates.sort(key=lambda a: (-a.priority, a.current_tasks))
        return candidates[0].account_id

    def has_credentials(self, account_id: str) -> bool:
        return account_id in self._creds

    def get_credentials(self, account_id: str) -> Optional[dict]:
        return self._creds.get(account_id)

    def inc_tasks(self, account_id: str):
        if account_id in self.accounts:
            self.accounts[account_id].current_tasks += 1

    def dec_tasks(self, account_id: str):
        if account_id in self.accounts:
            self.accounts[account_id].current_tasks = max(0, self.accounts[account_id].current_tasks - 1)

    def get_status(self) -> dict:
        accounts_status = {}
        for acc in self.accounts.values():
            has_creds = acc.account_id in self._creds
            accounts_status[acc.account_id] = {
                "account_id": acc.account_id,
                "phone_number": acc.phone_number,
                "display_name": acc.display_name,
                "priority": acc.priority,
                "is_active": acc.is_active,
                "max_concurrent": acc.max_concurrent,
                "current_tasks": acc.current_tasks,
                "series": acc.series,
                "is_logged_in": has_creds,
            }
        return {
            "is_running": True,
            "accounts": accounts_status,
        }


# 全局单例
account_store = AccountStore()
