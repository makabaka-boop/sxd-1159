import uuid
import io
import csv
from datetime import datetime
from typing import List, Optional, Tuple, Dict

from .models import (
    User, Material, StorageArea, BorrowRule, BorrowItem,
    BorrowApplication, BorrowStatus, InventoryAdjustment, MaterialType
)
from .database import (
    MaterialDB, StorageAreaDB, BorrowRuleDB, BorrowApplicationDB, InventoryAdjustmentDB
)

def _get_applicable_rule(material_type: Optional[MaterialType]) -> Optional[BorrowRule]:
    rules = BorrowRuleDB.get_all()
    specific_rule = next((r for r in rules if r.material_type == material_type), None)
    if specific_rule:
        return specific_rule
    general_rule = next((r for r in rules if r.material_type is None), None)
    return general_rule
from .schemas import (
    MaterialCreate, MaterialUpdate, StorageAreaCreate, StorageAreaUpdate,
    BorrowRuleCreate, BorrowRuleUpdate, BorrowApplicationCreate,
    BorrowApplicationUpdate, BatchImportRow, BatchImportResult,
    ReturnRequest, ReviewRequest, ExceptionConfirmRequest,
    InventoryAdjustmentCreate, QueryParams
)


def gen_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class MaterialService:
    @staticmethod
    def list_all() -> List[Material]:
        return MaterialDB.get_all()

    @staticmethod
    def get_by_id(material_id: str) -> Optional[Material]:
        return MaterialDB.get_by_id(material_id)

    @staticmethod
    def create(data: MaterialCreate) -> Material:
        if MaterialDB.get_by_id(data.material_id):
            raise ValueError(f"物资编号 {data.material_id} 已存在")
        if not data.storage_area or not data.storage_area.strip():
            raise ValueError("存放区域不能为空")
        areas = StorageAreaDB.get_all()
        area_ids = {a.area_id for a in areas}
        area_names = {a.name for a in areas}
        if data.storage_area not in area_ids and data.storage_area not in area_names:
            raise ValueError(f"存放区域 {data.storage_area} 不存在，请先创建存放区域")
        now = datetime.now().isoformat()
        mat = Material(
            material_id=data.material_id,
            name=data.name,
            material_type=data.material_type,
            storage_area=data.storage_area,
            total_quantity=data.total_quantity,
            available_quantity=data.total_quantity,
            description=data.description,
            created_at=now,
            updated_at=now
        )
        return MaterialDB.add(mat)

    @staticmethod
    def update(material_id: str, data: MaterialUpdate) -> Optional[Material]:
        mat = MaterialDB.get_by_id(material_id)
        if not mat:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(mat, k, v)
        if "total_quantity" in update_data:
            used = mat.total_quantity - mat.available_quantity
            new_available = max(0, mat.total_quantity - used)
            mat.available_quantity = new_available
        mat.updated_at = datetime.now().isoformat()
        return MaterialDB.update(material_id, mat)

    @staticmethod
    def delete(material_id: str) -> bool:
        return MaterialDB.delete(material_id)


class StorageAreaService:
    @staticmethod
    def list_all() -> List[StorageArea]:
        return StorageAreaDB.get_all()

    @staticmethod
    def get_by_id(area_id: str) -> Optional[StorageArea]:
        return StorageAreaDB.get_by_id(area_id)

    @staticmethod
    def create(data: StorageAreaCreate) -> StorageArea:
        if StorageAreaDB.get_by_id(data.area_id):
            raise ValueError(f"存放区域编号 {data.area_id} 已存在")
        area = StorageArea(
            area_id=data.area_id,
            name=data.name,
            description=data.description
        )
        return StorageAreaDB.add(area)

    @staticmethod
    def update(area_id: str, data: StorageAreaUpdate) -> Optional[StorageArea]:
        area = StorageAreaDB.get_by_id(area_id)
        if not area:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(area, k, v)
        return StorageAreaDB.update(area_id, area)

    @staticmethod
    def delete(area_id: str) -> bool:
        return StorageAreaDB.delete(area_id)


class BorrowRuleService:
    @staticmethod
    def list_all() -> List[BorrowRule]:
        return BorrowRuleDB.get_all()

    @staticmethod
    def get_by_id(rule_id: str) -> Optional[BorrowRule]:
        return BorrowRuleDB.get_by_id(rule_id)

    @staticmethod
    def create(data: BorrowRuleCreate) -> BorrowRule:
        if BorrowRuleDB.get_by_id(data.rule_id):
            raise ValueError(f"规则编号 {data.rule_id} 已存在")
        rule = BorrowRule(
            rule_id=data.rule_id,
            material_type=data.material_type,
            max_quantity=data.max_quantity,
            max_days=data.max_days,
            description=data.description
        )
        return BorrowRuleDB.add(rule)

    @staticmethod
    def update(rule_id: str, data: BorrowRuleUpdate) -> Optional[BorrowRule]:
        rule = BorrowRuleDB.get_by_id(rule_id)
        if not rule:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(rule, k, v)
        return BorrowRuleDB.update(rule_id, rule)

    @staticmethod
    def delete(rule_id: str) -> bool:
        return BorrowRuleDB.delete(rule_id)


class BorrowApplicationService:
    @staticmethod
    def _build_items(items_data) -> List[BorrowItem]:
        items = []
        for it in items_data:
            mat = MaterialDB.get_by_id(it.material_id)
            if not mat:
                raise ValueError(f"物资编号 {it.material_id} 不存在")
            if it.requested_quantity <= 0:
                raise ValueError(f"物资 {mat.name} 的申请数量必须大于0")
            items.append(BorrowItem(
                material_id=mat.material_id,
                material_name=mat.name,
                material_type=mat.material_type,
                requested_quantity=it.requested_quantity
            ))
        return items

    @staticmethod
    def create(data: BorrowApplicationCreate, creator: User) -> BorrowApplication:
        if not data.activity_name or not data.activity_name.strip():
            raise ValueError("活动名称不能为空")
        if not data.applicant or not data.applicant.strip():
            raise ValueError("申请人不能为空")
        items = BorrowApplicationService._build_items(data.items)

        qty_by_type: Dict[MaterialType, int] = {}
        for it in items:
            qty_by_type[it.material_type] = qty_by_type.get(it.material_type, 0) + it.requested_quantity

        for mt, qty in qty_by_type.items():
            rule = _get_applicable_rule(mt)
            if rule:
                if rule.max_quantity and qty > rule.max_quantity:
                    raise ValueError(f"物资类型 {mt.value} 单次借用数量 {qty} 超过规则限制 {rule.max_quantity}")
                if rule.max_days and data.expected_pickup_date and data.expected_return_date:
                    from datetime import datetime as dt
                    try:
                        d1 = dt.fromisoformat(data.expected_pickup_date)
                        d2 = dt.fromisoformat(data.expected_return_date)
                    except ValueError:
                        pass
                    else:
                        days = (d2 - d1).days
                        if days > rule.max_days:
                            raise ValueError(f"借用时长 {days} 天超过规则限制 {rule.max_days} 天")

        app = BorrowApplication(
            application_id=gen_id("APP"),
            activity_name=data.activity_name.strip(),
            applicant=data.applicant.strip(),
            applicant_phone=data.applicant_phone,
            items=items,
            purpose=data.purpose,
            expected_pickup_date=data.expected_pickup_date,
            expected_return_date=data.expected_return_date,
            status=BorrowStatus.PENDING,
            created_by=creator.username
        )
        return BorrowApplicationDB.add(app)

    @staticmethod
    def batch_import(rows: List[dict], creator: User) -> BatchImportResult:
        success_ids: List[str] = []
        errors: List[dict] = []
        grouped: Dict[str, dict] = {}

        for idx, row in enumerate(rows, start=1):
            row_errors = []
            activity_name = str(row.get("activity_name", "")).strip()
            applicant = str(row.get("applicant", "")).strip()
            material_id = str(row.get("material_id", "")).strip()
            quantity_raw = row.get("quantity", 0)

            if not activity_name:
                row_errors.append("活动名称不能为空")
            try:
                quantity = int(quantity_raw) if quantity_raw is not None else 0
                if quantity <= 0:
                    row_errors.append(f"数量不合法: {quantity_raw}")
            except (ValueError, TypeError):
                row_errors.append(f"数量不合法: {quantity_raw}")
                quantity = 0

            mat = MaterialDB.get_by_id(material_id) if material_id else None
            if not mat:
                row_errors.append(f"物资编号不存在: {material_id}")

            if row_errors:
                errors.append({
                    "row": idx,
                    "data": row,
                    "errors": row_errors
                })
                continue

            key = (activity_name, applicant)
            if key not in grouped:
                grouped[key] = {
                    "activity_name": activity_name,
                    "applicant": applicant,
                    "applicant_phone": row.get("applicant_phone"),
                    "purpose": row.get("purpose"),
                    "expected_pickup_date": row.get("expected_pickup_date"),
                    "expected_return_date": row.get("expected_return_date"),
                    "items": []
                }
            grouped[key]["items"].append({
                "material_id": material_id,
                "requested_quantity": quantity
            })

        for key, gdata in grouped.items():
            try:
                from .schemas import BorrowItemCreate
                items_data = [BorrowItemCreate(**it) for it in gdata["items"]]
                app_data = BorrowApplicationCreate(
                    activity_name=gdata["activity_name"],
                    applicant=gdata["applicant"],
                    applicant_phone=gdata.get("applicant_phone"),
                    items=items_data,
                    purpose=gdata.get("purpose"),
                    expected_pickup_date=gdata.get("expected_pickup_date"),
                    expected_return_date=gdata.get("expected_return_date")
                )
                app = BorrowApplicationService.create(app_data, creator)
                success_ids.append(app.application_id)
            except Exception as e:
                errors.append({
                    "row": f"group:{key}",
                    "data": gdata,
                    "errors": [str(e)]
                })

        return BatchImportResult(
            success_count=len(success_ids),
            error_count=len(errors),
            success_ids=success_ids,
            errors=errors
        )

    @staticmethod
    def list_all() -> List[BorrowApplication]:
        return BorrowApplicationDB.get_all()

    @staticmethod
    def get_by_id(app_id: str) -> Optional[BorrowApplication]:
        return BorrowApplicationDB.get_by_id(app_id)

    @staticmethod
    def update(app_id: str, data: BorrowApplicationUpdate) -> Optional[BorrowApplication]:
        app = BorrowApplicationDB.get_by_id(app_id)
        if not app:
            return None
        if app.status not in (BorrowStatus.PENDING,):
            raise ValueError("仅待审核状态的申请可修改")
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(app, k, v)
        return BorrowApplicationDB.update(app_id, app)

    @staticmethod
    def review(app_id: str, approved: bool, comment: Optional[str], reviewer: User) -> BorrowApplication:
        app = BorrowApplicationDB.get_by_id(app_id)
        if not app:
            raise ValueError("申请不存在")
        if app.status != BorrowStatus.PENDING:
            raise ValueError("仅待审核状态的申请可审批")
        app.status = BorrowStatus.APPROVED if approved else BorrowStatus.CANCELLED
        app.reviewed_by = reviewer.username
        app.reviewed_at = datetime.now().isoformat()
        app.review_comment = comment
        return BorrowApplicationDB.update(app_id, app)

    @staticmethod
    def pickup(app_id: str, operator: User, item_quantities: List[dict]) -> BorrowApplication:
        app = BorrowApplicationDB.get_by_id(app_id)
        if not app:
            raise ValueError("申请不存在")
        if app.status not in (BorrowStatus.APPROVED, BorrowStatus.PARTIAL_RETURN):
            raise ValueError("仅已通过或部分归还状态可领用")
        if not item_quantities or len(item_quantities) == 0:
            raise ValueError("请传入领用物品数据")

        valid_material_ids = {it.material_id for it in app.items}
        qty_map = {}
        for i, iq in enumerate(item_quantities, start=1):
            mid = iq.get("material_id")
            qty_raw = iq.get("quantity")
            if not mid:
                raise ValueError(f"第 {i} 条数据缺少物资编号")
            if mid not in valid_material_ids:
                raise ValueError(f"物资编号 {mid} 不在此申请单中")
            try:
                qty = int(qty_raw) if qty_raw is not None else 0
            except (ValueError, TypeError):
                raise ValueError(f"物资 {mid} 的领用数量不合法: {qty_raw}")
            if qty <= 0:
                raise ValueError(f"物资 {mid} 的领用数量必须大于0")
            if mid in qty_map:
                raise ValueError(f"物资 {mid} 重复传入")
            qty_map[mid] = qty

        for item in app.items:
            pick_qty = qty_map.get(item.material_id, 0)
            if pick_qty <= 0:
                continue
            remain_to_pick = item.requested_quantity - item.picked_quantity
            if pick_qty > remain_to_pick:
                raise ValueError(f"物资 {item.material_name} 领用数量超过申请数量")
            mat = MaterialDB.get_by_id(item.material_id)
            if not mat:
                raise ValueError(f"物资 {item.material_id} 不存在")
            if pick_qty > mat.available_quantity:
                raise ValueError(f"物资 {item.material_name} 库存不足 (剩余 {mat.available_quantity})")
            mat.available_quantity -= pick_qty
            mat.updated_at = datetime.now().isoformat()
            MaterialDB.update(mat.material_id, mat)
            item.picked_quantity += pick_qty

        total_picked = sum(it.picked_quantity for it in app.items)
        total_requested = sum(it.requested_quantity for it in app.items)
        app.picked_up_by = operator.username
        app.picked_up_at = datetime.now().isoformat()
        if total_picked >= total_requested:
            app.status = BorrowStatus.PICKED_UP
        else:
            app.status = BorrowStatus.PARTIAL_RETURN
        return BorrowApplicationDB.update(app_id, app)

    @staticmethod
    def return_materials(app_id: str, data: ReturnRequest, operator: User) -> BorrowApplication:
        app = BorrowApplicationDB.get_by_id(app_id)
        if not app:
            raise ValueError("申请不存在")
        if app.status not in (BorrowStatus.PICKED_UP, BorrowStatus.PARTIAL_RETURN):
            raise ValueError("仅已领用或部分归还状态可归还")

        has_exception = False
        return_map = {ri.material_id: ri for ri in data.items}

        for item in app.items:
            ri = return_map.get(item.material_id)
            if not ri:
                continue
            if ri.returned_quantity + ri.damaged_quantity > (item.picked_quantity - item.returned_quantity - item.damaged_quantity):
                raise ValueError(f"物资 {item.material_name} 归还数量超过已领用未归还数量")

            mat = MaterialDB.get_by_id(item.material_id)
            if mat and ri.returned_quantity > 0:
                mat.available_quantity += ri.returned_quantity
                mat.updated_at = datetime.now().isoformat()
                MaterialDB.update(mat.material_id, mat)

            item.returned_quantity += ri.returned_quantity
            if ri.damaged_quantity > 0:
                item.damaged_quantity += ri.damaged_quantity
                item.damage_note = (item.damage_note + "; " if item.damage_note else "") + (ri.damage_note or "")
                has_exception = True

        app.returned_by = operator.username
        app.returned_at = datetime.now().isoformat()
        app.supplement_note = data.supplement_note

        total_picked = sum(it.picked_quantity for it in app.items)
        total_returned_damaged = sum(it.returned_quantity + it.damaged_quantity for it in app.items)

        if has_exception or any(it.damaged_quantity > 0 for it in app.items):
            app.status = BorrowStatus.EXCEPTION_PENDING
            if not app.exception_note:
                app.exception_note = "存在损坏或异常归还"
        elif total_returned_damaged >= total_picked and total_picked > 0:
            app.status = BorrowStatus.COMPLETED
        else:
            app.status = BorrowStatus.PARTIAL_RETURN

        return BorrowApplicationDB.update(app_id, app)

    @staticmethod
    def confirm_exception(app_id: str, confirmed: bool, comment: Optional[str], auditor: User) -> BorrowApplication:
        app = BorrowApplicationDB.get_by_id(app_id)
        if not app:
            raise ValueError("申请不存在")
        if app.status != BorrowStatus.EXCEPTION_PENDING:
            raise ValueError("仅异常待核状态可确认")

        if confirmed:
            total_picked = sum(it.picked_quantity for it in app.items)
            total_returned_damaged = sum(it.returned_quantity + it.damaged_quantity for it in app.items)
            if total_returned_damaged >= total_picked:
                app.status = BorrowStatus.COMPLETED
            else:
                app.status = BorrowStatus.PARTIAL_RETURN
        if comment:
            app.review_comment = (app.review_comment + "; " if app.review_comment else "") + f"异常审核: {comment}"
        app.reviewed_by = auditor.username
        app.reviewed_at = datetime.now().isoformat()
        return BorrowApplicationDB.update(app_id, app)

    @staticmethod
    def cancel(app_id: str, operator: User) -> BorrowApplication:
        app = BorrowApplicationDB.get_by_id(app_id)
        if not app:
            raise ValueError("申请不存在")
        if app.status not in (BorrowStatus.PENDING, BorrowStatus.APPROVED):
            raise ValueError("仅待审核或已通过状态可取消")
        app.status = BorrowStatus.CANCELLED
        app.review_comment = (app.review_comment + "; " if app.review_comment else "") + f"由 {operator.username} 取消"
        return BorrowApplicationDB.update(app_id, app)

    @staticmethod
    def query(params: QueryParams) -> Tuple[List[BorrowApplication], int]:
        all_apps = BorrowApplicationDB.get_all()
        filtered = []

        for app in all_apps:
            if params.activity_name and params.activity_name not in app.activity_name:
                continue
            if params.applicant and params.applicant not in app.applicant:
                continue
            if params.status and app.status != params.status:
                continue
            if params.material_type:
                if not any(it.material_type == params.material_type for it in app.items):
                    continue
            if params.date_from:
                try:
                    df = datetime.fromisoformat(params.date_from)
                    ca = datetime.fromisoformat(app.created_at)
                    if ca < df:
                        continue
                except ValueError:
                    pass
            if params.date_to:
                try:
                    dt = datetime.fromisoformat(params.date_to)
                    ca = datetime.fromisoformat(app.created_at)
                    if ca > dt:
                        continue
                except ValueError:
                    pass
            filtered.append(app)

        total = len(filtered)
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        return filtered[start:end], total


class InventoryService:
    @staticmethod
    def adjust(data: InventoryAdjustmentCreate, handler: User) -> InventoryAdjustment:
        mat = MaterialDB.get_by_id(data.material_id)
        if not mat:
            raise ValueError(f"物资编号 {data.material_id} 不存在")
        before = mat.total_quantity
        diff = data.after_quantity - before
        mat.total_quantity = data.after_quantity
        mat.available_quantity = max(0, mat.available_quantity + diff)
        mat.updated_at = datetime.now().isoformat()
        MaterialDB.update(mat.material_id, mat)

        adj = InventoryAdjustment(
            adjustment_id=gen_id("ADJ"),
            material_id=mat.material_id,
            material_name=mat.name,
            before_quantity=before,
            after_quantity=data.after_quantity,
            reason=data.reason,
            handled_by=handler.username
        )
        return InventoryAdjustmentDB.add(adj)

    @staticmethod
    def list_adjustments() -> List[InventoryAdjustment]:
        return InventoryAdjustmentDB.get_all()


def _filter_apps(
    apps: List[BorrowApplication],
    activity_name: Optional[str] = None,
    applicant: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[BorrowApplication]:
    filtered = []
    for app in apps:
        if activity_name and activity_name not in app.activity_name:
            continue
        if applicant and applicant not in app.applicant:
            continue
        if material_type:
            if not any(it.material_type == material_type for it in app.items):
                continue
        if date_from:
            try:
                df = datetime.fromisoformat(date_from)
                ca = datetime.fromisoformat(app.created_at)
                if ca < df:
                    continue
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.fromisoformat(date_to)
                ca = datetime.fromisoformat(app.created_at)
                if ca > dt:
                    continue
            except ValueError:
                pass
        filtered.append(app)
    return filtered


class StatisticsService:
    @staticmethod
    def inventory_occupation(
        material_type: Optional[MaterialType] = None
    ) -> dict:
        materials = MaterialDB.get_all()
        by_type: Dict[str, dict] = {}
        for m in materials:
            if material_type and m.material_type != material_type:
                continue
            t = m.material_type.value
            if t not in by_type:
                by_type[t] = {"total": 0, "occupied": 0, "available": 0}
            by_type[t]["total"] += m.total_quantity
            occupied = m.total_quantity - m.available_quantity
            by_type[t]["occupied"] += occupied
            by_type[t]["available"] += m.available_quantity
        return {
            "filter": {"material_type": material_type.value if material_type else None},
            "by_type": by_type,
            "total_all": sum(v["total"] for v in by_type.values()),
            "occupied_all": sum(v["occupied"] for v in by_type.values()),
            "available_all": sum(v["available"] for v in by_type.values())
        }

    @staticmethod
    def exception_returns(
        activity_name: Optional[str] = None,
        applicant: Optional[str] = None,
        material_type: Optional[MaterialType] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> dict:
        apps = BorrowApplicationDB.get_all()
        apps = _filter_apps(apps, activity_name, applicant, material_type, date_from, date_to)
        exception_list = []
        for app in apps:
            damaged_items = [it for it in app.items if it.damaged_quantity > 0]
            if damaged_items or app.status == BorrowStatus.EXCEPTION_PENDING:
                exception_list.append({
                    "application_id": app.application_id,
                    "activity_name": app.activity_name,
                    "applicant": app.applicant,
                    "status": app.status.value,
                    "damaged_items": [
                        {
                            "material_id": it.material_id,
                            "material_name": it.material_name,
                            "damaged_quantity": it.damaged_quantity,
                            "damage_note": it.damage_note
                        } for it in damaged_items
                    ],
                    "exception_note": app.exception_note,
                    "returned_at": app.returned_at
                })
        return {
            "filter": {
                "activity_name": activity_name,
                "applicant": applicant,
                "material_type": material_type.value if material_type else None,
                "date_from": date_from,
                "date_to": date_to
            },
            "total": len(exception_list),
            "items": exception_list
        }

    @staticmethod
    def review_backlog(
        activity_name: Optional[str] = None,
        applicant: Optional[str] = None,
        material_type: Optional[MaterialType] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> dict:
        apps = BorrowApplicationDB.get_all()
        apps = _filter_apps(apps, activity_name, applicant, material_type, date_from, date_to)
        pending = [a for a in apps if a.status == BorrowStatus.PENDING]
        exception_pending = [a for a in apps if a.status == BorrowStatus.EXCEPTION_PENDING]
        return {
            "filter": {
                "activity_name": activity_name,
                "applicant": applicant,
                "material_type": material_type.value if material_type else None,
                "date_from": date_from,
                "date_to": date_to
            },
            "pending_review": {
                "count": len(pending),
                "items": [
                    {
                        "application_id": a.application_id,
                        "activity_name": a.activity_name,
                        "applicant": a.applicant,
                        "created_at": a.created_at,
                        "items_count": len(a.items)
                    } for a in pending
                ]
            },
            "exception_pending": {
                "count": len(exception_pending),
                "items": [
                    {
                        "application_id": a.application_id,
                        "activity_name": a.activity_name,
                        "applicant": a.applicant,
                        "returned_at": a.returned_at
                    } for a in exception_pending
                ]
            },
            "total_backlog": len(pending) + len(exception_pending)
        }


class ExportService:
    @staticmethod
    def export_apps(apps: List[BorrowApplication], fmt: str = "csv") -> Tuple[bytes, str, str]:
        if fmt == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "申请编号", "活动名称", "申请人", "联系电话", "状态",
                "申请时间", "审核人", "审核时间", "审核备注",
                "领用人", "领用时间", "归还人", "归还时间",
                "物资编号", "物资名称", "物资类型",
                "申请数量", "已领数量", "已还数量", "损坏数量", "损坏说明",
                "活动用途", "预计领用日期", "预计归还日期", "补充说明", "异常说明"
            ])
            for a in apps:
                for it in a.items:
                    writer.writerow([
                        a.application_id, a.activity_name, a.applicant, a.applicant_phone or "",
                        a.status.value, a.created_at, a.reviewed_by or "", a.reviewed_at or "",
                        a.review_comment or "", a.picked_up_by or "", a.picked_up_at or "",
                        a.returned_by or "", a.returned_at or "",
                        it.material_id, it.material_name, it.material_type.value,
                        it.requested_quantity, it.picked_quantity, it.returned_quantity,
                        it.damaged_quantity, it.damage_note or "",
                        a.purpose or "", a.expected_pickup_date or "", a.expected_return_date or "",
                        a.supplement_note or "", a.exception_note or ""
                    ])
            content = output.getvalue().encode("utf-8-sig")
            filename = f"borrow_applications_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
            return content, "text/csv", filename
        else:
            raise ValueError("不支持的导出格式")
