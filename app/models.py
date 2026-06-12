from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"


class MaterialType(str, Enum):
    TABLE_CARD = "桌牌"
    MEGAPHONE = "扩音器"
    FOLDING_TABLE = "折叠桌"
    SIGN_STAND = "指示架"
    CHECKIN_DEVICE = "签到器"


class BorrowStatus(str, Enum):
    PENDING = "待审核"
    APPROVED = "已通过"
    PICKED_UP = "已领用"
    PARTIAL_RETURN = "部分归还"
    EXCEPTION_PENDING = "异常待核"
    COMPLETED = "已完成"
    CANCELLED = "已取消"


class User(BaseModel):
    username: str
    password_hash: str
    role: UserRole
    full_name: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Material(BaseModel):
    material_id: str
    name: str
    material_type: MaterialType
    storage_area: str
    total_quantity: int
    available_quantity: int
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class StorageArea(BaseModel):
    area_id: str
    name: str
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class BorrowRule(BaseModel):
    rule_id: str
    material_type: Optional[MaterialType] = None
    max_quantity: Optional[int] = None
    max_days: Optional[int] = None
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class BorrowItem(BaseModel):
    material_id: str
    material_name: str
    material_type: MaterialType
    requested_quantity: int
    picked_quantity: int = 0
    returned_quantity: int = 0
    damaged_quantity: int = 0
    damage_note: Optional[str] = None


class BorrowApplication(BaseModel):
    application_id: str
    activity_name: str
    applicant: str
    applicant_phone: Optional[str] = None
    items: List[BorrowItem]
    purpose: Optional[str] = None
    expected_pickup_date: Optional[str] = None
    expected_return_date: Optional[str] = None
    status: BorrowStatus = BorrowStatus.PENDING
    created_by: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_comment: Optional[str] = None
    picked_up_by: Optional[str] = None
    picked_up_at: Optional[str] = None
    returned_by: Optional[str] = None
    returned_at: Optional[str] = None
    exception_note: Optional[str] = None
    supplement_note: Optional[str] = None


class InventoryAdjustment(BaseModel):
    adjustment_id: str
    material_id: str
    material_name: str
    before_quantity: int
    after_quantity: int
    reason: str
    handled_by: str
    handled_at: str = Field(default_factory=lambda: datetime.now().isoformat())
