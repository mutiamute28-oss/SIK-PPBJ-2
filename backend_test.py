#!/usr/bin/env python3
"""
Backend API Tests for Super Admin Role & RBAC
Tests the SIK-PPBJ finance app backend (FastAPI)
"""

import requests
import sys
from typing import Optional, Dict

# Configuration
BASE_URL = "https://ppbj-dependencies.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
CREDENTIALS = {
    "superadmin": {"email": "mutiamute28@gmail.com", "password": "Banjarmasin1"},
    "admin": {"email": "admin@sbb.co.id", "password": "admin123"},
    "keuangan": {"email": "keuangan@sbb.co.id", "password": "keuangan123"},
    "approver": {"email": "approver@sbb.co.id", "password": "approver123"},
    "pemohon": {"email": "pemohon@sbb.co.id", "password": "pemohon123"},
}

# Test results tracking
test_results = []
failed_tests = []


class TestSession:
    """Manages authenticated session with cookies"""
    def __init__(self):
        self.session = requests.Session()
        self.user_info = None
        
    def login(self, email: str, password: str) -> bool:
        """Login and store cookies"""
        try:
            resp = self.session.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=30
            )
            if resp.status_code == 200:
                self.user_info = resp.json()
                return True
            else:
                print(f"  ❌ Login failed: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  ❌ Login error: {e}")
            return False
    
    def get(self, path: str, **kwargs):
        """GET request with session cookies"""
        return self.session.get(f"{BASE_URL}{path}", timeout=30, **kwargs)
    
    def post(self, path: str, **kwargs):
        """POST request with session cookies"""
        return self.session.post(f"{BASE_URL}{path}", timeout=30, **kwargs)
    
    def put(self, path: str, **kwargs):
        """PUT request with session cookies"""
        return self.session.put(f"{BASE_URL}{path}", timeout=30, **kwargs)
    
    def delete(self, path: str, **kwargs):
        """DELETE request with session cookies"""
        return self.session.delete(f"{BASE_URL}{path}", timeout=30, **kwargs)


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  Details: {details}")
    test_results.append({"name": name, "passed": passed, "details": details})
    if not passed:
        failed_tests.append({"name": name, "details": details})


def test_all_accounts_login():
    """Test 1: Verify all 5 seeded accounts can login"""
    print("\n=== TEST 1: All Seeded Accounts Login ===")
    all_passed = True
    
    for role, creds in CREDENTIALS.items():
        session = TestSession()
        success = session.login(creds["email"], creds["password"])
        
        if success and session.user_info:
            expected_role = "user" if role == "pemohon" else role
            actual_role = session.user_info.get("role")
            role_match = actual_role == expected_role
            
            if role_match:
                log_test(f"Login {role} ({creds['email']})", True, f"Role: {actual_role}")
            else:
                log_test(f"Login {role} ({creds['email']})", False, 
                        f"Expected role '{expected_role}', got '{actual_role}'")
                all_passed = False
        else:
            log_test(f"Login {role} ({creds['email']})", False, "Login failed")
            all_passed = False
    
    return all_passed


def test_superadmin_access():
    """Test 2: Superadmin can access admin-only and keuangan-only endpoints"""
    print("\n=== TEST 2: Superadmin Access to Protected Endpoints ===")
    
    session = TestSession()
    if not session.login(CREDENTIALS["superadmin"]["email"], CREDENTIALS["superadmin"]["password"]):
        log_test("Superadmin login", False, "Could not login as superadmin")
        return False
    
    # Check role is superadmin
    if session.user_info.get("role") != "superadmin":
        log_test("Superadmin role verification", False, 
                f"Expected role 'superadmin', got '{session.user_info.get('role')}'")
        return False
    
    log_test("Superadmin login", True, f"Logged in as {session.user_info.get('email')}")
    
    # Test admin-only endpoint: GET /api/users
    resp = session.get("/users")
    if resp.status_code == 200:
        users = resp.json()
        log_test("Superadmin access GET /api/users (admin-only)", True, 
                f"Retrieved {len(users)} users")
    else:
        log_test("Superadmin access GET /api/users (admin-only)", False, 
                f"Status {resp.status_code}: {resp.text}")
        return False
    
    # Test keuangan-only endpoint: PUT /api/accounts (create/update account)
    # First, get existing accounts
    resp = session.get("/accounts")
    if resp.status_code == 200:
        log_test("Superadmin access GET /api/accounts", True, "Can view accounts")
    else:
        log_test("Superadmin access GET /api/accounts", False, 
                f"Status {resp.status_code}: {resp.text}")
    
    # Try to create a test account (keuangan-only endpoint)
    test_account = {
        "code": "9-99999",
        "name": "Test Account for Superadmin",
        "category": "Beban",
        "type": "Test",
        "normal": "debit"
    }
    resp = session.post("/accounts", json=test_account)
    if resp.status_code in [200, 201, 400]:  # 400 if already exists is OK
        if resp.status_code == 400 and "sudah ada" in resp.text:
            log_test("Superadmin access POST /api/accounts (keuangan-only)", True, 
                    "Endpoint accessible (account already exists)")
        else:
            log_test("Superadmin access POST /api/accounts (keuangan-only)", True, 
                    "Can create account")
            # Clean up - delete the test account
            accounts = session.get("/accounts").json()
            test_acc = next((a for a in accounts if a.get("code") == "9-99999"), None)
            if test_acc:
                session.delete(f"/accounts/{test_acc.get('id')}")
    else:
        log_test("Superadmin access POST /api/accounts (keuangan-only)", False, 
                f"Status {resp.status_code}: {resp.text}")
        return False
    
    return True


def test_admin_restrictions():
    """Test 3: Admin cannot create/modify/delete superadmin accounts"""
    print("\n=== TEST 3: Admin Restrictions on Superadmin Management ===")
    
    # Login as admin
    admin_session = TestSession()
    if not admin_session.login(CREDENTIALS["admin"]["email"], CREDENTIALS["admin"]["password"]):
        log_test("Admin login", False, "Could not login as admin")
        return False
    
    log_test("Admin login", True, f"Logged in as {admin_session.user_info.get('email')}")
    
    # Get list of users to find superadmin ID
    resp = admin_session.get("/users")
    if resp.status_code != 200:
        log_test("Admin can GET /api/users", False, f"Status {resp.status_code}")
        return False
    
    users = resp.json()
    log_test("Admin can GET /api/users", True, f"Retrieved {len(users)} users")
    
    superadmin_user = next((u for u in users if u.get("role") == "superadmin"), None)
    if not superadmin_user:
        log_test("Find superadmin user", False, "No superadmin found in users list")
        return False
    
    superadmin_id = superadmin_user.get("id")
    log_test("Find superadmin user", True, f"Found superadmin ID: {superadmin_id}")
    
    # Test 3a: Admin CANNOT create superadmin account
    resp = admin_session.post("/auth/register", json={
        "email": "test-superadmin@test.com",
        "password": "TestPass123",
        "name": "Test Superadmin",
        "role": "superadmin"
    })
    
    if resp.status_code == 403:
        log_test("Admin CANNOT create superadmin (POST /api/auth/register)", True, 
                "Correctly blocked with 403")
    else:
        log_test("Admin CANNOT create superadmin (POST /api/auth/register)", False, 
                f"Expected 403, got {resp.status_code}: {resp.text}")
    
    # Test 3b: Admin CANNOT modify superadmin account
    resp = admin_session.put(f"/users/{superadmin_id}", json={
        "name": "Modified Superadmin Name"
    })
    
    if resp.status_code == 403:
        log_test("Admin CANNOT modify superadmin (PUT /api/users/{id})", True, 
                "Correctly blocked with 403")
    else:
        log_test("Admin CANNOT modify superadmin (PUT /api/users/{id})", False, 
                f"Expected 403, got {resp.status_code}: {resp.text}")
    
    # Test 3c: Admin CANNOT delete superadmin account
    resp = admin_session.delete(f"/users/{superadmin_id}")
    
    if resp.status_code == 403:
        log_test("Admin CANNOT delete superadmin (DELETE /api/users/{id})", True, 
                "Correctly blocked with 403")
    else:
        log_test("Admin CANNOT delete superadmin (DELETE /api/users/{id})", False, 
                f"Expected 403, got {resp.status_code}: {resp.text}")
    
    # Test 3d: Admin CAN create normal user
    resp = admin_session.post("/auth/register", json={
        "email": "test-normal-user@test.com",
        "password": "TestPass123",
        "name": "Test Normal User",
        "role": "user"
    })
    
    if resp.status_code in [200, 201]:
        created_user = resp.json()
        user_id = created_user.get("id")
        log_test("Admin CAN create normal user (role=user)", True, 
                f"Created user ID: {user_id}")
        
        # Clean up - delete the test user
        delete_resp = admin_session.delete(f"/users/{user_id}")
        if delete_resp.status_code == 200:
            log_test("Clean up test user", True, "Deleted test user")
        else:
            log_test("Clean up test user", False, 
                    f"Could not delete: {delete_resp.status_code}")
    elif resp.status_code == 400 and "sudah terdaftar" in resp.text:
        log_test("Admin CAN create normal user (role=user)", True, 
                "Endpoint accessible (email already exists)")
        # Try to find and delete existing test user
        users = admin_session.get("/users").json()
        test_user = next((u for u in users if u.get("email") == "test-normal-user@test.com"), None)
        if test_user:
            admin_session.delete(f"/users/{test_user.get('id')}")
    else:
        log_test("Admin CAN create normal user (role=user)", False, 
                f"Status {resp.status_code}: {resp.text}")
    
    return True


def test_superadmin_management_powers():
    """Test 4: Superadmin can create/delete users with any role including superadmin"""
    print("\n=== TEST 4: Superadmin Management Powers ===")
    
    # Login as superadmin
    session = TestSession()
    if not session.login(CREDENTIALS["superadmin"]["email"], CREDENTIALS["superadmin"]["password"]):
        log_test("Superadmin login for management test", False, "Could not login")
        return False
    
    # Test 4a: Superadmin CAN create a temporary superadmin account
    resp = session.post("/auth/register", json={
        "email": "temp-superadmin@test.com",
        "password": "TempSuper123",
        "name": "Temporary Superadmin",
        "role": "superadmin"
    })
    
    temp_superadmin_id = None
    if resp.status_code in [200, 201]:
        created_user = resp.json()
        temp_superadmin_id = created_user.get("id")
        log_test("Superadmin CAN create superadmin account", True, 
                f"Created temp superadmin ID: {temp_superadmin_id}")
    elif resp.status_code == 400 and "sudah terdaftar" in resp.text:
        log_test("Superadmin CAN create superadmin account", True, 
                "Endpoint accessible (email already exists)")
        # Find existing temp superadmin
        users = session.get("/users").json()
        temp_user = next((u for u in users if u.get("email") == "temp-superadmin@test.com"), None)
        if temp_user:
            temp_superadmin_id = temp_user.get("id")
    else:
        log_test("Superadmin CAN create superadmin account", False, 
                f"Status {resp.status_code}: {resp.text}")
        return False
    
    # Test 4b: Superadmin CAN create admin account
    resp = session.post("/auth/register", json={
        "email": "temp-admin@test.com",
        "password": "TempAdmin123",
        "name": "Temporary Admin",
        "role": "admin"
    })
    
    temp_admin_id = None
    if resp.status_code in [200, 201]:
        created_user = resp.json()
        temp_admin_id = created_user.get("id")
        log_test("Superadmin CAN create admin account", True, 
                f"Created temp admin ID: {temp_admin_id}")
    elif resp.status_code == 400 and "sudah terdaftar" in resp.text:
        log_test("Superadmin CAN create admin account", True, 
                "Endpoint accessible (email already exists)")
        users = session.get("/users").json()
        temp_user = next((u for u in users if u.get("email") == "temp-admin@test.com"), None)
        if temp_user:
            temp_admin_id = temp_user.get("id")
    else:
        log_test("Superadmin CAN create admin account", False, 
                f"Status {resp.status_code}: {resp.text}")
    
    # Test 4c: Superadmin CANNOT delete own account
    own_id = session.user_info.get("id")
    resp = session.delete(f"/users/{own_id}")
    
    if resp.status_code == 400:
        log_test("Superadmin CANNOT delete own account", True, 
                "Correctly blocked with 400")
    else:
        log_test("Superadmin CANNOT delete own account", False, 
                f"Expected 400, got {resp.status_code}: {resp.text}")
    
    # Test 4d: Delete temp superadmin (should succeed since there are 2 superadmins now)
    if temp_superadmin_id:
        resp = session.delete(f"/users/{temp_superadmin_id}")
        
        if resp.status_code == 200:
            log_test("Superadmin CAN delete temp superadmin (not last one)", True, 
                    "Successfully deleted temp superadmin")
        else:
            log_test("Superadmin CAN delete temp superadmin (not last one)", False, 
                    f"Status {resp.status_code}: {resp.text}")
    
    # Test 4e: Verify cannot delete last superadmin
    # Count remaining superadmins
    users = session.get("/users").json()
    superadmins = [u for u in users if u.get("role") == "superadmin"]
    
    if len(superadmins) == 1:
        # Try to delete the last superadmin (should fail)
        last_superadmin_id = superadmins[0].get("id")
        resp = session.delete(f"/users/{last_superadmin_id}")
        
        if resp.status_code == 400:
            log_test("Guard: Cannot delete last superadmin", True, 
                    "Correctly blocked with 400")
        else:
            log_test("Guard: Cannot delete last superadmin", False, 
                    f"Expected 400, got {resp.status_code}: {resp.text}")
    else:
        log_test("Guard: Cannot delete last superadmin", True, 
                f"Skipped (multiple superadmins exist: {len(superadmins)})")
    
    # Clean up temp admin if created
    if temp_admin_id:
        resp = session.delete(f"/users/{temp_admin_id}")
        if resp.status_code == 200:
            log_test("Clean up temp admin", True, "Deleted temp admin")
        else:
            log_test("Clean up temp admin", False, 
                    f"Could not delete: {resp.status_code}")
    
    return True


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    total = len(test_results)
    passed = sum(1 for t in test_results if t["passed"])
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed_tests:
        print("\n" + "="*70)
        print("FAILED TESTS DETAILS")
        print("="*70)
        for test in failed_tests:
            print(f"\n❌ {test['name']}")
            if test['details']:
                print(f"   {test['details']}")
    
    print("\n" + "="*70)
    
    return failed == 0


def main():
    """Run all tests"""
    print("="*70)
    print("BACKEND API TESTS: Super Admin Role & RBAC")
    print("="*70)
    print(f"Backend URL: {BASE_URL}")
    print("="*70)
    
    try:
        # Run all test suites
        test_all_accounts_login()
        test_superadmin_access()
        test_admin_restrictions()
        test_superadmin_management_powers()
        
        # Print summary
        all_passed = print_summary()
        
        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
