from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from .models import MaterialType, BorrowStatus, UserRole, DueReminderStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: UserRole
    full_name: str


class UserInfo(BaseModel):
    username: str
    role: UserRole
    full_name: str


class MaterialCreate(BaseModel):
    material_id: str
    name: str
    material_type: MaterialType
    storage_area: str
    total_quantity: int = Field(ge=0)
    description: Optional[str] = None


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    material_type: Optional[MaterialType] = None
    storage_area: Optional[str] = None
    total_quantity: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None


class StorageAreaCreate(BaseModel):
    area_id: str
    name: str
    description: Optional[str] = None


class StorageAreaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class BorrowRuleCreate(BaseModel):
    rule_id: str
    material_type: Optional[MaterialType] = None
    max_quantity: Optional[int] = Field(None, ge=1)
    max_days: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None


class BorrowRuleUpdate(BaseModel):
    material_type: Optional[MaterialType] = None
    max_quantity: Optional[int] = Field(None, ge=1)
    max_days: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None


class BorrowItemCreate(BaseModel):
    material_id: str
    requested_quantity: int = Field(ge=1)


class BorrowItemInfo(BaseModel):
    material_id: str
    material_name: str
    material_type: MaterialType
    requested_quantity: int
    picked_quantity: int = 0
    returned_quantity: int = 0
    damaged_quantity: int = 0
    damage_note: Optional[str] = None


class BorrowApplicationCreate(BaseModel):
    activity_name: str
    applicant: str
    applicant_phone: Optional[str] = None
    items: List[BorrowItemCreate]
    purpose: Optional[str] = None
    expected_pickup_date: Optional[str] = None
    expected_return_date: Optional[str] = None


class BorrowApplicationUpdate(BaseModel):
    activity_name: Optional[str] = None
    applicant: Optional[str] = None
    applicant_phone: Optional[str] = None
    purpose: Optional[str] = None
    expected_pickup_date: Optional[str] = None
    expected_return_date: Optional[str] = None


class BatchImportRow(BaseModel):
    activity_name: str
    applicant: str
    applicant_phone: Optional[str] = None
    material_id: str
    quantity: int
    purpose: Optional[str] = None
    expected_pickup_date: Optional[str] = None
    expected_return_date: Optional[str] = None


class BatchImportResult(BaseModel):
    success_count: int
    error_count: int
    success_ids: List[str]
    errors: List[dict]


class PickupRequest(BaseModel):
    application_id: str
    items: List[dict]


class ReturnItem(BaseModel):
    material_id: str
    returned_quantity: int = Field(ge=0)
    damaged_quantity: int = Field(0, ge=0)
    damage_note: Optional[str] = None


class ReturnRequest(BaseModel):
    application_id: str
    items: List[ReturnItem]
    supplement_note: Optional[str] = None


class ReviewRequest(BaseModel):
    application_id: str
    approved: bool
    comment: Optional[str] = None


class ExceptionConfirmRequest(BaseModel):
    application_id: str
    confirmed: bool
    comment: Optional[str] = None


class InventoryAdjustmentCreate(BaseModel):
    material_id: str
    after_quantity: int = Field(ge=0)
    reason: str


class QueryParams(BaseModel):
    activity_name: Optional[str] = None
    applicant: Optional[str] = None
    material_type: Optional[MaterialType] = None
    status: Optional[BorrowStatus] = None
    due_reminder_status: Optional[DueReminderStatus] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100000)


class DueReminderInfo(BaseModel):
    due_reminder_status: DueReminderStatus
    approaching_due: bool
    overdue: bool
    overdue_days: Optional[int] = None
