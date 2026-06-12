from datetime import timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import (
    authenticate_user, create_access_token, get_current_user,
    require_roles, init_default_users, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.models import UserRole, MaterialType, BorrowStatus, DueReminderStatus
from app.schemas import (
    Token, UserInfo, MaterialCreate, MaterialUpdate,
    StorageAreaCreate, StorageAreaUpdate,
    BorrowRuleCreate, BorrowRuleUpdate,
    BorrowApplicationCreate, BorrowApplicationUpdate,
    BatchImportResult, ReturnRequest, ReviewRequest,
    ExceptionConfirmRequest, InventoryAdjustmentCreate,
    QueryParams
)
from app.services import (
    MaterialService, StorageAreaService, BorrowRuleService,
    BorrowApplicationService, InventoryService,
    StatisticsService, ExportService, compute_due_reminder
)
import csv
import io

app = FastAPI(
    title="社团物资借用管理系统",
    description="校内社团活动桌牌、扩音器、折叠桌、指示架和签到器借用流程管理接口",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_default_users()


@app.get("/")
def root():
    return {"message": "社团物资借用管理系统 API", "version": "1.0.0"}


@app.post("/api/auth/login", response_model=Token, tags=["认证"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value},
        expires_delta=access_token_expires
    )
    return Token(
        access_token=access_token,
        username=user.username,
        role=user.role,
        full_name=user.full_name
    )


@app.get("/api/auth/me", response_model=UserInfo, tags=["认证"])
def get_me(current_user=Depends(get_current_user)):
    return UserInfo(
        username=current_user.username,
        role=current_user.role,
        full_name=current_user.full_name
    )


# ============ 管理员接口 ============

@app.get("/api/admin/materials", tags=["管理员-物资管理"])
def list_materials(current_user=Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.AUDITOR))):
    return MaterialService.list_all()


@app.get("/api/admin/materials/{material_id}", tags=["管理员-物资管理"])
def get_material(material_id: str, current_user=Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.AUDITOR))):
    mat = MaterialService.get_by_id(material_id)
    if not mat:
        raise HTTPException(status_code=404, detail="物资不存在")
    return mat


@app.post("/api/admin/materials", tags=["管理员-物资管理"])
def create_material(data: MaterialCreate, current_user=Depends(require_roles(UserRole.ADMIN))):
    try:
        return MaterialService.create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/materials/{material_id}", tags=["管理员-物资管理"])
def update_material(material_id: str, data: MaterialUpdate, current_user=Depends(require_roles(UserRole.ADMIN))):
    result = MaterialService.update(material_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="物资不存在")
    return result


@app.delete("/api/admin/materials/{material_id}", tags=["管理员-物资管理"])
def delete_material(material_id: str, current_user=Depends(require_roles(UserRole.ADMIN))):
    if not MaterialService.delete(material_id):
        raise HTTPException(status_code=404, detail="物资不存在")
    return {"success": True}


@app.get("/api/admin/storage-areas", tags=["管理员-存放区域"])
def list_storage_areas(current_user=Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.AUDITOR))):
    return StorageAreaService.list_all()


@app.post("/api/admin/storage-areas", tags=["管理员-存放区域"])
def create_storage_area(data: StorageAreaCreate, current_user=Depends(require_roles(UserRole.ADMIN))):
    try:
        return StorageAreaService.create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/storage-areas/{area_id}", tags=["管理员-存放区域"])
def update_storage_area(area_id: str, data: StorageAreaUpdate, current_user=Depends(require_roles(UserRole.ADMIN))):
    result = StorageAreaService.update(area_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="存放区域不存在")
    return result


@app.delete("/api/admin/storage-areas/{area_id}", tags=["管理员-存放区域"])
def delete_storage_area(area_id: str, current_user=Depends(require_roles(UserRole.ADMIN))):
    if not StorageAreaService.delete(area_id):
        raise HTTPException(status_code=404, detail="存放区域不存在")
    return {"success": True}


@app.get("/api/admin/borrow-rules", tags=["管理员-借用规则"])
def list_borrow_rules(current_user=Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.AUDITOR))):
    return BorrowRuleService.list_all()


@app.post("/api/admin/borrow-rules", tags=["管理员-借用规则"])
def create_borrow_rule(data: BorrowRuleCreate, current_user=Depends(require_roles(UserRole.ADMIN))):
    try:
        return BorrowRuleService.create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/borrow-rules/{rule_id}", tags=["管理员-借用规则"])
def update_borrow_rule(rule_id: str, data: BorrowRuleUpdate, current_user=Depends(require_roles(UserRole.ADMIN))):
    result = BorrowRuleService.update(rule_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="规则不存在")
    return result


@app.delete("/api/admin/borrow-rules/{rule_id}", tags=["管理员-借用规则"])
def delete_borrow_rule(rule_id: str, current_user=Depends(require_roles(UserRole.ADMIN))):
    if not BorrowRuleService.delete(rule_id):
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"success": True}


# ============ 操作员接口 ============

@app.post("/api/operator/applications", tags=["操作员-借用申请"])
def create_application(data: BorrowApplicationCreate, current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    try:
        return BorrowApplicationService.create(data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/operator/applications/batch-import", response_model=BatchImportResult, tags=["操作员-借用申请"])
def batch_import_applications(rows: List[dict], current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    return BorrowApplicationService.batch_import(rows, current_user)


@app.post("/api/operator/applications/batch-import-csv", response_model=BatchImportResult, tags=["操作员-借用申请"])
async def batch_import_csv(file: UploadFile = File(...), current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    return BorrowApplicationService.batch_import(rows, current_user)


@app.put("/api/operator/applications/{app_id}", tags=["操作员-借用申请"])
def update_application(app_id: str, data: BorrowApplicationUpdate, current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    try:
        result = BorrowApplicationService.update(app_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="申请不存在")
    return result


@app.post("/api/operator/applications/{app_id}/pickup", tags=["操作员-借用申请"])
def pickup_materials(app_id: str, items: List[dict], current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    try:
        return BorrowApplicationService.pickup(app_id, current_user, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/operator/applications/return", tags=["操作员-借用申请"])
def return_materials(data: ReturnRequest, current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    try:
        return BorrowApplicationService.return_materials(data.application_id, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/operator/applications/{app_id}/cancel", tags=["操作员-借用申请"])
def cancel_application(app_id: str, current_user=Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))):
    try:
        return BorrowApplicationService.cancel(app_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ 审核员接口 ============

@app.post("/api/auditor/review", tags=["审核员-审批"])
def review_application(data: ReviewRequest, current_user=Depends(require_roles(UserRole.AUDITOR, UserRole.ADMIN))):
    try:
        return BorrowApplicationService.review(data.application_id, data.approved, data.comment, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auditor/confirm-exception", tags=["审核员-审批"])
def confirm_exception(data: ExceptionConfirmRequest, current_user=Depends(require_roles(UserRole.AUDITOR, UserRole.ADMIN))):
    try:
        return BorrowApplicationService.confirm_exception(data.application_id, data.confirmed, data.comment, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auditor/inventory-adjustment", tags=["审核员-库存修正"])
def adjust_inventory(data: InventoryAdjustmentCreate, current_user=Depends(require_roles(UserRole.AUDITOR, UserRole.ADMIN))):
    try:
        return InventoryService.adjust(data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/auditor/inventory-adjustments", tags=["审核员-库存修正"])
def list_inventory_adjustments(current_user=Depends(require_roles(UserRole.AUDITOR, UserRole.ADMIN))):
    return InventoryService.list_adjustments()


# ============ 查询、统计、导出接口 ============

@app.get("/api/applications", tags=["查询与统计"])
def query_applications(
    activity_name: Optional[str] = None,
    applicant: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    status: Optional[BorrowStatus] = None,
    due_reminder_status: Optional[DueReminderStatus] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user)
):
    params = QueryParams(
        activity_name=activity_name,
        applicant=applicant,
        material_type=material_type,
        status=status,
        due_reminder_status=due_reminder_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size
    )
    items, total = BorrowApplicationService.query(params)
    enriched_items = []
    for item in items:
        app_dict = item.model_dump()
        reminder = compute_due_reminder(item)
        app_dict["due_reminder"] = reminder.model_dump()
        enriched_items.append(app_dict)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": enriched_items
    }


@app.get("/api/applications/{app_id}", tags=["查询与统计"])
def get_application(app_id: str, current_user=Depends(get_current_user)):
    app = BorrowApplicationService.get_by_id(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请不存在")
    app_dict = app.model_dump()
    reminder = compute_due_reminder(app)
    app_dict["due_reminder"] = reminder.model_dump()
    return app_dict


@app.get("/api/statistics/inventory-occupation", tags=["查询与统计"])
def stat_inventory_occupation(
    material_type: Optional[MaterialType] = None,
    current_user=Depends(get_current_user)
):
    return StatisticsService.inventory_occupation(material_type=material_type)


@app.get("/api/statistics/exception-returns", tags=["查询与统计"])
def stat_exception_returns(
    activity_name: Optional[str] = None,
    applicant: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    return StatisticsService.exception_returns(
        activity_name=activity_name,
        applicant=applicant,
        material_type=material_type,
        date_from=date_from,
        date_to=date_to
    )


@app.get("/api/statistics/review-backlog", tags=["查询与统计"])
def stat_review_backlog(
    activity_name: Optional[str] = None,
    applicant: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    return StatisticsService.review_backlog(
        activity_name=activity_name,
        applicant=applicant,
        material_type=material_type,
        date_from=date_from,
        date_to=date_to
    )


@app.get("/api/statistics/return-reminder", tags=["查询与统计"])
def stat_return_reminder(
    activity_name: Optional[str] = None,
    applicant: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    return StatisticsService.return_reminder(
        activity_name=activity_name,
        applicant=applicant,
        material_type=material_type,
        date_from=date_from,
        date_to=date_to
    )


@app.get("/api/export/applications", tags=["导出"])
def export_applications(
    activity_name: Optional[str] = None,
    applicant: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    status: Optional[BorrowStatus] = None,
    due_reminder_status: Optional[DueReminderStatus] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    fmt: str = Query("csv", pattern="^csv$"),
    current_user=Depends(get_current_user)
):
    params = QueryParams(
        activity_name=activity_name,
        applicant=applicant,
        material_type=material_type,
        status=status,
        due_reminder_status=due_reminder_status,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=100000
    )
    items, _ = BorrowApplicationService.query(params)
    content, media_type, filename = ExportService.export_apps(items, fmt)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/meta/material-types", tags=["元数据"])
def list_material_types():
    return [{"key": m.name, "value": m.value} for m in MaterialType]


@app.get("/api/meta/borrow-statuses", tags=["元数据"])
def list_borrow_statuses():
    return [{"key": s.name, "value": s.value} for s in BorrowStatus]


@app.get("/api/meta/user-roles", tags=["元数据"])
def list_user_roles():
    return [{"key": r.name, "value": r.value} for r in UserRole]


@app.get("/api/meta/due-reminder-statuses", tags=["元数据"])
def list_due_reminder_statuses():
    return [{"key": s.name, "value": s.value} for s in DueReminderStatus]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8113)
