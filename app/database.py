import json
import os
import threading
from typing import Dict, List, Optional, TypeVar, Type
from datetime import datetime

from .models import (
    User, Material, StorageArea, BorrowRule,
    BorrowApplication, InventoryAdjustment
)

T = TypeVar('T')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

_lock = threading.RLock()


def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)


def _get_file_path(collection: str) -> str:
    _ensure_data_dir()
    return os.path.join(DATA_DIR, f'{collection}.json')


def _read_collection(collection: str) -> List[Dict]:
    path = _get_file_path(collection)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        if not content.strip():
            return []
        return json.loads(content)


def _write_collection(collection: str, data: List[Dict]):
    path = _get_file_path(collection)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _to_dict_list(items: List) -> List[Dict]:
    return [item.model_dump() if hasattr(item, 'model_dump') else dict(item) for item in items]


def _from_dict_list(data: List[Dict], model: Type[T]) -> List[T]:
    return [model(**d) for d in data]


class DB:
    @staticmethod
    def _get_all(collection: str, model: Type[T]) -> List[T]:
        with _lock:
            data = _read_collection(collection)
            return _from_dict_list(data, model)

    @staticmethod
    def _save_all(collection: str, items: List):
        with _lock:
            _write_collection(collection, _to_dict_list(items))

    @staticmethod
    def _add(collection: str, item, model: Type[T]) -> T:
        with _lock:
            items = DB._get_all(collection, model)
            items.append(item)
            DB._save_all(collection, items)
            return item

    @staticmethod
    def _update(collection: str, item_id: str, updated_item, id_field: str, model: Type[T]) -> Optional[T]:
        with _lock:
            items = DB._get_all(collection, model)
            for i, it in enumerate(items):
                if getattr(it, id_field) == item_id:
                    items[i] = updated_item
                    DB._save_all(collection, items)
                    return updated_item
            return None

    @staticmethod
    def _delete(collection: str, item_id: str, id_field: str, model: Type[T]) -> bool:
        with _lock:
            items = DB._get_all(collection, model)
            original_len = len(items)
            items = [it for it in items if getattr(it, id_field) != item_id]
            if len(items) < original_len:
                DB._save_all(collection, items)
                return True
            return False

    @staticmethod
    def _get_by_id(collection: str, item_id: str, id_field: str, model: Type[T]) -> Optional[T]:
        with _lock:
            items = DB._get_all(collection, model)
            for it in items:
                if getattr(it, id_field) == item_id:
                    return it
            return None


class UserDB(DB):
    COLLECTION = 'users'

    @staticmethod
    def get_all() -> List[User]:
        return UserDB._get_all(UserDB.COLLECTION, User)

    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        return UserDB._get_by_id(UserDB.COLLECTION, username, 'username', User)

    @staticmethod
    def add(user: User) -> User:
        return UserDB._add(UserDB.COLLECTION, user, User)

    @staticmethod
    def update(username: str, user: User) -> Optional[User]:
        return UserDB._update(UserDB.COLLECTION, username, user, 'username', User)

    @staticmethod
    def delete(username: str) -> bool:
        return UserDB._delete(UserDB.COLLECTION, username, 'username', User)


class MaterialDB(DB):
    COLLECTION = 'materials'

    @staticmethod
    def get_all() -> List[Material]:
        return MaterialDB._get_all(MaterialDB.COLLECTION, Material)

    @staticmethod
    def get_by_id(material_id: str) -> Optional[Material]:
        return MaterialDB._get_by_id(MaterialDB.COLLECTION, material_id, 'material_id', Material)

    @staticmethod
    def add(material: Material) -> Material:
        return MaterialDB._add(MaterialDB.COLLECTION, material, Material)

    @staticmethod
    def update(material_id: str, material: Material) -> Optional[Material]:
        return MaterialDB._update(MaterialDB.COLLECTION, material_id, material, 'material_id', Material)

    @staticmethod
    def delete(material_id: str) -> bool:
        return MaterialDB._delete(MaterialDB.COLLECTION, material_id, 'material_id', Material)


class StorageAreaDB(DB):
    COLLECTION = 'storage_areas'

    @staticmethod
    def get_all() -> List[StorageArea]:
        return StorageAreaDB._get_all(StorageAreaDB.COLLECTION, StorageArea)

    @staticmethod
    def get_by_id(area_id: str) -> Optional[StorageArea]:
        return StorageAreaDB._get_by_id(StorageAreaDB.COLLECTION, area_id, 'area_id', StorageArea)

    @staticmethod
    def add(area: StorageArea) -> StorageArea:
        return StorageAreaDB._add(StorageAreaDB.COLLECTION, area, StorageArea)

    @staticmethod
    def update(area_id: str, area: StorageArea) -> Optional[StorageArea]:
        return StorageAreaDB._update(StorageAreaDB.COLLECTION, area_id, area, 'area_id', StorageArea)

    @staticmethod
    def delete(area_id: str) -> bool:
        return StorageAreaDB._delete(StorageAreaDB.COLLECTION, area_id, 'area_id', StorageArea)


class BorrowRuleDB(DB):
    COLLECTION = 'borrow_rules'

    @staticmethod
    def get_all() -> List[BorrowRule]:
        return BorrowRuleDB._get_all(BorrowRuleDB.COLLECTION, BorrowRule)

    @staticmethod
    def get_by_id(rule_id: str) -> Optional[BorrowRule]:
        return BorrowRuleDB._get_by_id(BorrowRuleDB.COLLECTION, rule_id, 'rule_id', BorrowRule)

    @staticmethod
    def add(rule: BorrowRule) -> BorrowRule:
        return BorrowRuleDB._add(BorrowRuleDB.COLLECTION, rule, BorrowRule)

    @staticmethod
    def update(rule_id: str, rule: BorrowRule) -> Optional[BorrowRule]:
        return BorrowRuleDB._update(BorrowRuleDB.COLLECTION, rule_id, rule, 'rule_id', BorrowRule)

    @staticmethod
    def delete(rule_id: str) -> bool:
        return BorrowRuleDB._delete(BorrowRuleDB.COLLECTION, rule_id, 'rule_id', BorrowRule)


class BorrowApplicationDB(DB):
    COLLECTION = 'borrow_applications'

    @staticmethod
    def get_all() -> List[BorrowApplication]:
        return BorrowApplicationDB._get_all(BorrowApplicationDB.COLLECTION, BorrowApplication)

    @staticmethod
    def get_by_id(app_id: str) -> Optional[BorrowApplication]:
        return BorrowApplicationDB._get_by_id(BorrowApplicationDB.COLLECTION, app_id, 'application_id', BorrowApplication)

    @staticmethod
    def add(app: BorrowApplication) -> BorrowApplication:
        return BorrowApplicationDB._add(BorrowApplicationDB.COLLECTION, app, BorrowApplication)

    @staticmethod
    def update(app_id: str, app: BorrowApplication) -> Optional[BorrowApplication]:
        return BorrowApplicationDB._update(BorrowApplicationDB.COLLECTION, app_id, app, 'application_id', BorrowApplication)

    @staticmethod
    def delete(app_id: str) -> bool:
        return BorrowApplicationDB._delete(BorrowApplicationDB.COLLECTION, app_id, 'application_id', BorrowApplication)


class InventoryAdjustmentDB(DB):
    COLLECTION = 'inventory_adjustments'

    @staticmethod
    def get_all() -> List[InventoryAdjustment]:
        return InventoryAdjustmentDB._get_all(InventoryAdjustmentDB.COLLECTION, InventoryAdjustment)

    @staticmethod
    def add(adj: InventoryAdjustment) -> InventoryAdjustment:
        return InventoryAdjustmentDB._add(InventoryAdjustmentDB.COLLECTION, adj, InventoryAdjustment)
