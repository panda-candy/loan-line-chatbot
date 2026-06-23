"""測試專案層級 borrower/lender 角色行為。

這些測試刻意不連接真實 MySQL，而是使用小型記憶體模型，
快速驗證使用者情境；另外也加入靜態檢查，避免未來誤用全域角色權限。
"""

from pathlib import Path
from unittest import TestCase, main

import loan_service


class FakeLoanSystem:
    """用於測試專案角色情境的小型記憶體模型。"""

    def __init__(self):
        self.next_project_id = 1
        self.projects = {}
        self.members = []

    def create_project(self, user_id, role):
        """建立假專案，並把建立者加入專案成員表。"""
        project_id = self.next_project_id
        self.next_project_id += 1
        invite_code = f"CODE{project_id:08d}"
        self.projects[project_id] = {
            "project_id": project_id,
            "invite_code": invite_code,
            "created_by": user_id,
            "creator_role": role,
            "principal_amount": None,
            "annual_interest_rate": None,
            "term_months": None,
            "repayment_method": None,
            "repayment_day": None,
            "status": "waiting_join",
        }
        self.members.append({"project_id": project_id, "user_id": user_id, "role": role})
        return self.get_project_for_user(project_id, user_id)

    def join_project(self, user_id, invite_code):
        """用邀請碼加入專案，並自動指定相對角色。"""
        project = next(
            (p for p in self.projects.values() if p["invite_code"] == invite_code and p["status"] == "waiting_join"),
            None,
        )
        if not project:
            return None
        if project["created_by"] == user_id:
            raise ValueError("creator cannot join own project")

        role = "lender" if project["creator_role"] == "borrower" else "borrower"
        if any(m["project_id"] == project["project_id"] and m["role"] == role for m in self.members):
            raise ValueError("project already has this role")
        self.members.append({"project_id": project["project_id"], "user_id": user_id, "role": role})
        project["status"] = "paired"
        return self.get_project_for_user(project["project_id"], user_id)

    def role_of(self, project_id, user_id):
        """回傳使用者在專案中的角色；非成員則回傳 None。"""
        member = next((m for m in self.members if m["project_id"] == project_id and m["user_id"] == user_id), None)
        return member["role"] if member else None

    def get_project_for_user(self, project_id, user_id):
        """只有使用者是專案成員時才回傳專案資料。"""
        role = self.role_of(project_id, user_id)
        if not role:
            return None
        project = dict(self.projects[project_id])
        project["current_user_role"] = role
        project["borrower_id"] = self._user_for_role(project_id, "borrower")
        project["lender_id"] = self._user_for_role(project_id, "lender")
        return project

    def set_terms(self, user_id, project_id):
        """模擬只有 lender 可以設定借貸條件。"""
        if self.role_of(project_id, user_id) != "lender":
            raise PermissionError("only matched lender can set terms")
        project = self.projects[project_id]
        if project["status"] != "paired":
            raise PermissionError("project is not ready for terms")
        project.update({
            "principal_amount": "10000",
            "annual_interest_rate": "3",
            "term_months": 12,
            "repayment_method": "equal_payment",
            "repayment_day": 5,
            "status": "pending_borrower_confirm",
        })
        return self.get_project_for_user(project_id, user_id)

    def confirm_terms(self, user_id, project_id):
        """模擬只有 borrower 可以確認借貸條件。"""
        project = self.get_project_for_user(project_id, user_id)
        if not project:
            raise PermissionError("not a project member")
        if project["current_user_role"] != "borrower":
            raise PermissionError("only borrower can accept terms")
        if project["status"] != "pending_borrower_confirm":
            raise ValueError("project is not waiting for borrower confirmation")
        self.projects[project_id]["status"] = "active"
        return 1

    def _user_for_role(self, project_id, role):
        member = next((m for m in self.members if m["project_id"] == project_id and m["role"] == role), None)
        return member["user_id"] if member else None


class ProjectRoleScenarioTest(TestCase):
    """測試 borrower/lender 專案角色的完整使用情境。"""

    def setUp(self):
        self.fake = FakeLoanSystem()

    def test_project_role_scenarios(self):
        user_a = 101
        user_b = 202
        user_c = 303

        # 1. User A 建立專案並選擇 borrower。
        project_a = self.fake.create_project(user_a, "borrower")
        self.assertTrue(project_a["invite_code"])
        self.assertEqual(self.fake.role_of(project_a["project_id"], user_a), "borrower")

        # 2. User B 用邀請碼加入，自動成為 lender，專案變成 paired。
        joined = self.fake.join_project(user_b, project_a["invite_code"])
        self.assertEqual(self.fake.role_of(project_a["project_id"], user_b), "lender")
        self.assertEqual(joined["status"], "paired")

        # 3. 同一位使用者可在另一個專案中擔任 lender。
        project_b = self.fake.create_project(user_a, "lender")
        self.assertEqual(self.fake.role_of(project_b["project_id"], user_a), "lender")

        # 4. borrower 不能設定借貸條件。
        with self.assertRaises(PermissionError):
            self.fake.set_terms(user_a, project_a["project_id"])

        # 5. lender 可以設定借貸條件。
        terms_project = self.fake.set_terms(user_b, project_a["project_id"])
        self.assertEqual(terms_project["status"], "pending_borrower_confirm")

        # 6. lender 不能確認借貸條件。
        with self.assertRaises(PermissionError):
            self.fake.confirm_terms(user_b, project_a["project_id"])

        # 7. borrower 可以確認借貸條件。
        contract_id = self.fake.confirm_terms(user_a, project_a["project_id"])
        self.assertEqual(contract_id, 1)
        self.assertEqual(self.fake.projects[project_a["project_id"]]["status"], "active")

        # 8. 非專案成員不能查看專案資料。
        self.assertIsNone(self.fake.get_project_for_user(project_a["project_id"], user_c))


class LoanServiceStaticChecks(TestCase):
    """針對 loan_service.py 關鍵實作細節的靜態檢查。"""

    def test_join_service_sets_project_to_paired(self):
        """避免加入專案後的狀態轉換偏離 paired。"""
        source = Path("loan_service.py").read_text(encoding="utf-8")
        self.assertIn("SET status = 'paired'", source)

    def test_permissions_use_project_member_roles(self):
        """權限判斷不得依賴使用者全域角色欄位。"""
        source = Path("loan_service.py").read_text(encoding="utf-8")
        schema = Path("sql/schema.sql").read_text(encoding="utf-8")

        self.assertNotIn("users.role", source)
        self.assertNotIn("role_flags", schema)
        self.assertNotIn("role_flags", source)
        self.assertIn("FROM loan_project_members", source)
        self.assertIn("JOIN loan_project_members lender", source)
        self.assertIn("JOIN loan_project_members borrower", source)


if __name__ == "__main__":
    main()
