import requests
import json

BASE = "http://localhost:8113"

def login(u, p):
    r = requests.post(f"{BASE}/api/auth/login", data={"username": u, "password": p})
    r.raise_for_status()
    return r.json()["access_token"]

def h(token):
    return {"Authorization": f"Bearer {token}"}

admin_t = login("admin", "admin123")
op_t = login("operator", "operator123")
aud_t = login("auditor", "auditor123")

print("=" * 70)
print("测试修复项验证")
print("=" * 70)

# 初始化基础数据
print("\n[初始化] 创建存放区域...")
requests.post(f"{BASE}/api/admin/storage-areas", headers=h(admin_t), json={
    "area_id": "AREA01", "name": "活动室A区", "description": "一楼"
})

print("\n=== 修复4测试：新建物资没有校验库区 ===")
print("测试1: 不先创建库区直接创建物资（应该失败）")
r = requests.post(f"{BASE}/api/admin/materials", headers=h(admin_t), json={
    "material_id": "MAT001", "name": "桌牌测试", "material_type": "桌牌",
    "storage_area": "INVALID_AREA", "total_quantity": 50
})
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400, "应该校验库区失败"
print("  ✓ 通过: 正确校验了不存在的库区")

print("\n测试2: 存放区域为空（应该失败）")
r = requests.post(f"{BASE}/api/admin/materials", headers=h(admin_t), json={
    "material_id": "MAT001", "name": "桌牌测试", "material_type": "桌牌",
    "storage_area": "", "total_quantity": 50
})
print(f"  状态: {r.status_code} (预期400)")
assert r.status_code == 400
print("  ✓ 通过: 正确校验了空库区")

print("\n测试3: 用存在的库区ID创建物资（应该成功）")
r = requests.post(f"{BASE}/api/admin/materials", headers=h(admin_t), json={
    "material_id": "MAT001", "name": "桌牌-标准款", "material_type": "桌牌",
    "storage_area": "AREA01", "total_quantity": 50
})
print(f"  状态: {r.status_code} (预期200)")
assert r.status_code == 200
print("  ✓ 通过: 用正确的库区创建成功")

requests.post(f"{BASE}/api/admin/materials", headers=h(admin_t), json={
    "material_id": "MAT002", "name": "扩音器-手持", "material_type": "扩音器",
    "storage_area": "AREA01", "total_quantity": 20
})

print("\n=== 修复2测试：借用规则配置后不生效 ===")
print("创建借用规则：桌牌单次最多借5个")
requests.post(f"{BASE}/api/admin/borrow-rules", headers=h(admin_t), json={
    "rule_id": "RULE01", "material_type": "桌牌", "max_quantity": 5, "max_days": 3
})

print("\n测试: 申请桌牌6个，超过规则限制（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications", headers=h(op_t), json={
    "activity_name": "测试活动", "applicant": "测试人",
    "items": [{"material_id": "MAT001", "requested_quantity": 6}],
    "expected_pickup_date": "2026-06-13", "expected_return_date": "2026-06-20"
})
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "超过规则限制" in r.json().get("detail", "")
print("  ✓ 通过: 借用规则数量限制生效")

print("\n测试: 借用时长超过7天，规则限制3天（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications", headers=h(op_t), json={
    "activity_name": "测试活动2", "applicant": "测试人",
    "items": [{"material_id": "MAT001", "requested_quantity": 3}],
    "expected_pickup_date": "2026-06-13", "expected_return_date": "2026-06-20"
})
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "超过规则限制" in r.json().get("detail", "")
print("  ✓ 通过: 借用规则时长限制生效")

print("\n=== 修复1测试：手动新建申请时，没有校验申请人 ===")
print("测试: 申请人为空（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications", headers=h(op_t), json={
    "activity_name": "测试活动3", "applicant": "",
    "items": [{"material_id": "MAT001", "requested_quantity": 2}]
})
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "申请人不能为空" in r.json().get("detail", "")
print("  ✓ 通过: 申请人校验生效")

print("\n测试: 正常创建申请（应该成功）")
r = requests.post(f"{BASE}/api/operator/applications", headers=h(op_t), json={
    "activity_name": "正常活动", "applicant": "张三",
    "items": [{"material_id": "MAT001", "requested_quantity": 2}, {"material_id": "MAT002", "requested_quantity": 1}]
})
print(f"  状态: {r.status_code} (预期200)")
assert r.status_code == 200
app_id = r.json()["application_id"]
print(f"  申请ID: {app_id}")
print("  ✓ 通过: 正常创建申请成功")

# 审批通过
print("\n[准备] 审核员审批通过...")
requests.post(f"{BASE}/api/auditor/review", headers=h(aud_t), json={
    "application_id": app_id, "approved": True, "comment": "同意"
})

print("\n=== 修复3测试：领用接口没有校验传数据和无效数量 ===")
print("测试1: 领用空数据（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[])
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "请传入领用物品数据" in r.json().get("detail", "")
print("  ✓ 通过: 空数据校验生效")

print("\n测试2: 物资编号不在申请单中（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[
    {"material_id": "INVALID", "quantity": 1}
])
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "不在此申请单中" in r.json().get("detail", "")
print("  ✓ 通过: 物资不在申请单校验生效")

print("\n测试3: 领用数量为0或负数（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[
    {"material_id": "MAT001", "quantity": -1}
])
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "必须大于0" in r.json().get("detail", "")
print("  ✓ 通过: 无效数量校验生效")

print("\n测试4: 缺少物资编号（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[
    {"quantity": 1}
])
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "缺少物资编号" in r.json().get("detail", "")
print("  ✓ 通过: 缺少物资编号校验生效")

print("\n测试5: 数量为非法字符串（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[
    {"material_id": "MAT001", "quantity": "abc"}
])
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "数量不合法" in r.json().get("detail", "")
print("  ✓ 通过: 数量不合法校验生效")

print("\n测试6: 重复传入同一物资（应该失败）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[
    {"material_id": "MAT001", "quantity": 1},
    {"material_id": "MAT001", "quantity": 1}
])
print(f"  状态: {r.status_code} (预期400)")
print(f"  错误: {r.json().get('detail', '')}")
assert r.status_code == 400 and "重复传入" in r.json().get("detail", "")
print("  ✓ 通过: 重复物资校验生效")

print("\n测试7: 正常领用（应该成功）")
r = requests.post(f"{BASE}/api/operator/applications/{app_id}/pickup", headers=h(op_t), json=[
    {"material_id": "MAT001", "quantity": 2},
    {"material_id": "MAT002", "quantity": 1}
])
print(f"  状态: {r.status_code} (预期200)")
assert r.status_code == 200
print("  ✓ 通过: 正常领用成功")

print("\n=== 修复5测试：取消申请接口当前审核员也能操作 ===")
print("测试: 审核员尝试取消申请（应该失败，403）")
# 创建一个新申请用于测试
r2 = requests.post(f"{BASE}/api/operator/applications", headers=h(op_t), json={
    "activity_name": "待取消活动", "applicant": "李四",
    "items": [{"material_id": "MAT001", "requested_quantity": 1}]
})
app2_id = r2.json()["application_id"]
r = requests.post(f"{BASE}/api/operator/applications/{app2_id}/cancel", headers=h(aud_t))
print(f"  状态: {r.status_code} (预期403)")
assert r.status_code == 403
print("  ✓ 通过: 审核员无法取消申请")

print("\n测试: 操作员取消申请（应该成功）")
r = requests.post(f"{BASE}/api/operator/applications/{app2_id}/cancel", headers=h(op_t))
print(f"  状态: {r.status_code} (预期200)")
assert r.status_code == 200
assert r.json()["status"] == "已取消"
print("  ✓ 通过: 操作员可以取消申请")

print("\n=== 修复6测试：统计接口不能看筛选后的统计 ===")
print("创建一些测试数据以便统计...")
for i in range(3):
    requests.post(f"{BASE}/api/operator/applications", headers=h(op_t), json={
        "activity_name": f"筛选测试活动{i}", "applicant": f"申请人{i}",
        "items": [{"material_id": "MAT001", "requested_quantity": 1}]
    })

print("\n测试1: 库存占用统计 - 按物资类型筛选")
r = requests.get(f"{BASE}/api/statistics/inventory-occupation", headers=h(admin_t), params={"material_type": "桌牌"})
print(f"  状态: {r.status_code}")
data = r.json()
print(f"  筛选条件: {data.get('filter')}")
print(f"  结果中只有桌牌类型: {'桌牌' in data['by_type'] and len(data['by_type']) == 1}")
assert data.get("filter", {}).get("material_type") == "桌牌"
assert "桌牌" in data["by_type"] and len(data["by_type"]) == 1
print("  ✓ 通过: 库存占用按物资类型筛选生效")

print("\n测试2: 审核积压统计 - 按申请人筛选")
r = requests.get(f"{BASE}/api/statistics/review-backlog", headers=h(admin_t), params={"applicant": "申请人1"})
print(f"  状态: {r.status_code}")
data = r.json()
print(f"  筛选条件: {data.get('filter')}")
print(f"  待审核数量: {data['pending_review']['count']}")
assert data.get("filter", {}).get("applicant") == "申请人1"
print("  ✓ 通过: 审核积压按申请人筛选生效")

print("\n测试3: 异常归还统计 - 按活动名称筛选")
# 先归还之前的申请制造异常
requests.post(f"{BASE}/api/operator/applications/return", headers=h(op_t), json={
    "application_id": app_id,
    "items": [
        {"material_id": "MAT001", "returned_quantity": 1, "damaged_quantity": 1, "damage_note": "测试损坏"},
        {"material_id": "MAT002", "returned_quantity": 1}
    ]
})
r = requests.get(f"{BASE}/api/statistics/exception-returns", headers=h(admin_t), params={"activity_name": "正常活动"})
print(f"  状态: {r.status_code}")
data = r.json()
print(f"  筛选条件: {data.get('filter')}")
print(f"  异常数量: {data['total']}")
assert data.get("filter", {}).get("activity_name") == "正常活动"
assert data["total"] >= 1
print("  ✓ 通过: 异常归还按活动名称筛选生效")

print("\n" + "=" * 70)
print("✓ 所有 6 项修复验证通过！")
print("=" * 70)
