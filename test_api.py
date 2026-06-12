import requests
import json

BASE = "http://localhost:8113"

def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}

def pp(name, r):
    print(f"\n=== {name} ===")
    print(f"Status: {r.status_code}")
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except:
        print(r.text)

print("=" * 60)
print("社团物资借用管理系统 - API 测试")
print("=" * 60)

admin_token = login("admin", "admin123")
operator_token = login("operator", "operator123")
auditor_token = login("auditor", "auditor123")
print("\n✓ 三种角色登录成功")

pp("获取当前用户信息", requests.get(f"{BASE}/api/auth/me", headers=auth_header(admin_token)))

pp("创建存放区域", requests.post(f"{BASE}/api/admin/storage-areas", headers=auth_header(admin_token), json={
    "area_id": "AREA01",
    "name": "活动室A区",
    "description": "一楼大厅东侧"
}))

pp("列出存放区域", requests.get(f"{BASE}/api/admin/storage-areas", headers=auth_header(admin_token)))

materials = [
    {"material_id": "MAT001", "name": "桌牌-标准款", "material_type": "桌牌", "storage_area": "AREA01", "total_quantity": 50, "description": "A4亚克力桌牌"},
    {"material_id": "MAT002", "name": "扩音器-手持", "material_type": "扩音器", "storage_area": "AREA01", "total_quantity": 20, "description": "带麦扩音器"},
    {"material_id": "MAT003", "name": "折叠桌-长方形", "material_type": "折叠桌", "storage_area": "AREA01", "total_quantity": 30, "description": "1.2m折叠桌"},
    {"material_id": "MAT004", "name": "指示架-L型", "material_type": "指示架", "storage_area": "AREA01", "total_quantity": 25},
    {"material_id": "MAT005", "name": "签到器-电子", "material_type": "签到器", "storage_area": "AREA01", "total_quantity": 10},
]
for m in materials:
    r = requests.post(f"{BASE}/api/admin/materials", headers=auth_header(admin_token), json=m)
    print(f"创建物资 {m['material_id']}: {r.status_code}")

pp("列出所有物资", requests.get(f"{BASE}/api/admin/materials", headers=auth_header(admin_token)))

pp("创建借用规则", requests.post(f"{BASE}/api/admin/borrow-rules", headers=auth_header(admin_token), json={
    "rule_id": "RULE01",
    "max_quantity": 20,
    "max_days": 7,
    "description": "通用借用规则"
}))

pp("操作员创建借用申请", requests.post(f"{BASE}/api/operator/applications", headers=auth_header(operator_token), json={
    "activity_name": "社团招新活动",
    "applicant": "张三",
    "applicant_phone": "13800138000",
    "items": [
        {"material_id": "MAT001", "requested_quantity": 10},
        {"material_id": "MAT002", "requested_quantity": 3}
    ],
    "purpose": "招新现场使用",
    "expected_pickup_date": "2026-06-13",
    "expected_return_date": "2026-06-15"
}))

pp("批量导入申请（包含错误行）", requests.post(f"{BASE}/api/operator/applications/batch-import", headers=auth_header(operator_token), json=[
    {"activity_name": "学术讲座", "applicant": "李四", "material_id": "MAT003", "quantity": 5, "purpose": "讲座场地布置"},
    {"activity_name": "", "applicant": "王五", "material_id": "MAT004", "quantity": 2},
    {"activity_name": "文艺晚会", "applicant": "赵六", "material_id": "INVALID", "quantity": 3},
    {"activity_name": "运动会", "applicant": "孙七", "material_id": "MAT005", "quantity": -1},
    {"activity_name": "学术讲座", "applicant": "李四", "material_id": "MAT004", "quantity": 8},
]))

apps = requests.get(f"{BASE}/api/applications", headers=auth_header(admin_token)).json()
print(f"\n当前申请总数: {apps['total']}")
first_app_id = apps["items"][0]["application_id"]
print(f"第一个申请ID: {first_app_id}")

pp("审核员审批申请-通过", requests.post(f"{BASE}/api/auditor/review", headers=auth_header(auditor_token), json={
    "application_id": first_app_id,
    "approved": True,
    "comment": "同意借用，请注意爱护物资"
}))

pp("操作员领用物资", requests.post(f"{BASE}/api/operator/applications/{first_app_id}/pickup", headers=auth_header(operator_token), json=[
    {"material_id": "MAT001", "quantity": 10},
    {"material_id": "MAT002", "quantity": 2}
]))

pp("操作员归还物资（含损坏）", requests.post(f"{BASE}/api/operator/applications/return", headers=auth_header(operator_token), json={
    "application_id": first_app_id,
    "items": [
        {"material_id": "MAT001", "returned_quantity": 9, "damaged_quantity": 1, "damage_note": "边缘有裂纹"},
        {"material_id": "MAT002", "returned_quantity": 2, "damaged_quantity": 0}
    ],
    "supplement_note": "活动已顺利结束"
}))

pp("审核员确认异常", requests.post(f"{BASE}/api/auditor/confirm-exception", headers=auth_header(auditor_token), json={
    "application_id": first_app_id,
    "confirmed": True,
    "comment": "损坏情况已确认，记录在案"
}))

pp("库存占用统计", requests.get(f"{BASE}/api/statistics/inventory-occupation", headers=auth_header(admin_token)))

pp("异常归还统计", requests.get(f"{BASE}/api/statistics/exception-returns", headers=auth_header(admin_token)))

pp("审核积压统计", requests.get(f"{BASE}/api/statistics/review-backlog", headers=auth_header(admin_token)))

pp("查询申请（按状态筛选）", requests.get(f"{BASE}/api/applications", headers=auth_header(admin_token), params={"status": "待审核"}))

pp("导出CSV", requests.get(f"{BASE}/api/export/applications", headers=auth_header(admin_token)))

pp("审核员修正库存", requests.post(f"{BASE}/api/auditor/inventory-adjustment", headers=auth_header(auditor_token), json={
    "material_id": "MAT001",
    "after_quantity": 48,
    "reason": "盘点时发现实物与账面不符，修正"
}))

pp("物资类型元数据", requests.get(f"{BASE}/api/meta/material-types"))
pp("借用状态元数据", requests.get(f"{BASE}/api/meta/borrow-statuses"))

print("\n" + "=" * 60)
print("✓ 所有核心 API 测试完成")
print("=" * 60)
