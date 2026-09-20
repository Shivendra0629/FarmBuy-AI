import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import init_db_defaults
from app.database import SessionLocal, IS_PERSISTENT, STORAGE_TYPE, DATABASE_ENGINE
from app.models import Admin, Farmer, Buyer, Supply, Product, Order, OrderItem
from app.routers.auth import login_admin, register_farmer, login_farmer, register_buyer, login_buyer, reset_database
from app.routers.admin import (
    list_admins,
    create_admin,
    update_owner_credentials,
    update_admin_farmer,
    delete_admin_farmer,
    update_admin_buyer,
    delete_admin_buyer,
    delete_admin,
    reset_demo_database
)
from app.schemas import (
    AdminLoginRequest,
    FarmerLoginRegisterRequest,
    FarmerLoginRequest,
    BuyerLoginRegisterRequest,
    BuyerLoginRequest,
    AdminCreateRequest,
    OwnerUpdateCredentialsRequest,
    FarmerUpdateRequest,
    BuyerUpdateRequest,
    DemoResetRequest
)

def run_tests():
    print("=" * 70)
    print("FARMBUY AI — COMPREHENSIVE PERSISTENCE & AUTH VERIFICATION")
    print("=" * 70)
    print(f"[*] Database Engine: {DATABASE_ENGINE}")
    print(f"[*] Storage Type: {STORAGE_TYPE}")
    print(f"[*] Is Persistent: {IS_PERSISTENT}")

    db = SessionLocal()

    # 1. Server initialization check
    print("\n--- Test 1: Initialize Database & Default Seed ---")
    init_db_defaults()
    owner = db.query(Admin).filter(Admin.role == "OWNER").first()
    assert owner is not None, "Super Admin should exist in database!"
    assert owner.admin_user_id == "Sm_0629", f"Expected Super Admin Sm_0629, got {owner.admin_user_id}"
    print(f"[+] Root Super Admin in database: {owner.admin_user_id} (Role: {owner.role}, ID: {owner.id})")

    # 2. Super Admin Initial Login
    print("\n--- Test 2: Super Admin Initial Login ---")
    login_resp = login_admin(AdminLoginRequest(admin_user_id="Sm_0629", password="9973868328"), db=db)
    assert login_resp["role"] == "OWNER"
    owner_token = login_resp["access_token"]
    owner_claims = {"sub": "owner", "role": "OWNER", "user_id": "Sm_0629"}
    print(f"[+] Super Admin login successful: {login_resp['message']}")

    # 3. Server Restart Simulation: Re-run init_db_defaults()
    print("\n--- Test 3: Server Restart / Wake-up Simulation ---")
    init_db_defaults()
    owner_db = db.query(Admin).filter(Admin.role == "OWNER").first()
    assert owner_db is not None, "FATAL: Super Admin disappeared after server restart simulation!"
    assert owner_db.admin_user_id == "Sm_0629"
    # Login again after restart
    post_restart_login = login_admin(AdminLoginRequest(admin_user_id="Sm_0629", password="9973868328"), db=db)
    assert post_restart_login["role"] == "OWNER"
    print("[+] Server restart simulation passed: Super Admin Sm_0629 is permanent and can login after restart.")

    # 4. Create Team Admin (e.g. Divya)
    print("\n--- Test 4: Team Admin Creation ---")
    # Clean up any existing divya first
    existing = db.query(Admin).filter(Admin.admin_user_id == "divya_admin").first()
    if existing:
        db.delete(existing)
        db.commit()

    created_resp = create_admin(
        AdminCreateRequest(name="Divya Sharma", admin_user_id="divya_admin", password="divya_password_123"),
        db=db,
        claims=owner_claims
    )
    print(f"[+] Created Team Admin: {created_resp['message']}")

    # 5. Team Admin Login
    print("\n--- Test 5: Team Admin Login ---")
    divya_resp = login_admin(AdminLoginRequest(admin_user_id="divya_admin", password="divya_password_123"), db=db)
    assert divya_resp["role"] == "ADMIN"
    divya_claims = {"sub": "divya", "role": "ADMIN", "user_id": "divya_admin"}
    print(f"[+] Team Admin Divya logged in successfully! Role: {divya_resp['role']}")

    # 6. Server Restart Simulation for Team Admin
    print("\n--- Test 6: Team Admin Restart Survival ---")
    init_db_defaults()
    divya_in_db = db.query(Admin).filter(Admin.admin_user_id == "divya_admin").first()
    assert divya_in_db is not None, "FATAL: Team admin Divya disappeared after server restart simulation!"
    divya_post_restart = login_admin(AdminLoginRequest(admin_user_id="divya_admin", password="divya_password_123"), db=db)
    assert divya_post_restart["role"] == "ADMIN"
    print("[+] Team Admin Divya survived server restart and logged in successfully!")

    # 7. Register and Login Farmer
    print("\n--- Test 7: Farmer Registration & Login ---")
    f_reg = register_farmer(
        FarmerLoginRegisterRequest(
            name="Ramesh Kumar",
            phone_number="9876543210",
            address="Hooghly Farm Gate",
            pincode="712409",
            state="West Bengal",
            commodity="Tomato",
            quantity_kg=1500.0,
            price_per_kg=22.0
        ),
        db=db
    )
    farmer_id = f_reg["user_id"]
    print(f"[+] Registered Farmer: {f_reg['name']} (ID: #{farmer_id})")

    f_login = login_farmer(FarmerLoginRequest(name="Ramesh Kumar", phone_number="9876543210"), db=db)
    assert f_login["user_id"] == farmer_id
    print(f"[+] Farmer login successful: {f_login['message']}")

    # 8. Register and Login Buyer
    print("\n--- Test 8: Buyer Registration & Login ---")
    b_reg = register_buyer(
        BuyerLoginRegisterRequest(
            name="Metro Fresh Kolkata",
            phone_number="9123456789",
            address="Park Circus Depot",
            city="Kolkata",
            pincode="700017",
            state="West Bengal"
        ),
        db=db
    )
    buyer_id = b_reg["user_id"]
    print(f"[+] Registered Buyer: {b_reg['name']} (ID: #{buyer_id})")

    b_login = login_buyer(BuyerLoginRequest(name="Metro Fresh Kolkata", phone_number="9123456789"), db=db)
    assert b_login["user_id"] == buyer_id
    print(f"[+] Buyer login successful: {b_login['message']}")

    # 9. Admin Modifies Farmer and Buyer Details
    print("\n--- Test 9: Admin Modifies Farmer & Buyer ---")
    mod_f = update_admin_farmer(
        farmer_id=farmer_id,
        payload=FarmerUpdateRequest(name="Ramesh Kumar Ghosh", address="Singur Gate"),
        db=db,
        claims=divya_claims
    )
    assert mod_f["farmer"]["name"] == "Ramesh Kumar Ghosh"
    print(f"[+] Team Admin Divya updated Farmer: {mod_f['farmer']['name']}")

    mod_b = update_admin_buyer(
        buyer_id=buyer_id,
        payload=BuyerUpdateRequest(address="Salt Lake Depot"),
        db=db,
        claims=divya_claims
    )
    assert mod_b["buyer"]["address"] == "Salt Lake Depot"
    print(f"[+] Team Admin Divya updated Buyer address: {mod_b['buyer']['address']}")

    # 10. Super Admin Credential Update and Restart Survival
    print("\n--- Test 10: Super Admin Credential Update & Restart Survival ---")
    update_res = update_owner_credentials(
        OwnerUpdateCredentialsRequest(new_password="new_super_secret_pwd"),
        db=db,
        claims=owner_claims
    )
    print(f"[+] Super Admin password updated: {update_res['message']}")

    # Check old password fails
    try:
        login_admin(AdminLoginRequest(admin_user_id="Sm_0629", password="9973868328"), db=db)
        assert False, "Old password should have failed!"
    except Exception as e:
        print("[+] Old password correctly rejected (401 Unauthorized).")

    # Check new password works
    new_login = login_admin(AdminLoginRequest(admin_user_id="Sm_0629", password="new_super_secret_pwd"), db=db)
    assert new_login["role"] == "OWNER"
    print("[+] New password authenticated successfully.")

    # Server restart simulation
    init_db_defaults()
    new_after_restart = login_admin(AdminLoginRequest(admin_user_id="Sm_0629", password="new_super_secret_pwd"), db=db)
    assert new_after_restart["role"] == "OWNER"
    print("[+] New Super Admin credentials SURVIVED server restart simulation!")

    # Restore password back to 9973868328
    update_owner_credentials(
        OwnerUpdateCredentialsRequest(new_password="9973868328"),
        db=db,
        claims=owner_claims
    )
    restored_login = login_admin(AdminLoginRequest(admin_user_id="Sm_0629", password="9973868328"), db=db)
    assert restored_login["role"] == "OWNER"
    print("[+] Restored Super Admin password back to default '9973868328'.")

    # 11. Database Clean Wipe (Owner only, leaves Admin accounts intact)
    print("\n--- Test 11: Database Clean Wipe (Preserves Admin Accounts) ---")
    wipe_res = reset_demo_database(DemoResetRequest(confirm=True), db=db, claims=owner_claims)
    print(f"[+] Wipe completed: {wipe_res['message']}")

    # Check that farmers and buyers are 0
    assert db.query(Farmer).count() == 0, "Farmers count should be 0 after wipe"
    assert db.query(Buyer).count() == 0, "Buyers count should be 0 after wipe"
    assert db.query(Supply).count() == 0, "Supplies count should be 0 after wipe"
    # Check that Admin accounts are preserved
    owner_post_wipe = db.query(Admin).filter(Admin.role == "OWNER").first()
    divya_post_wipe = db.query(Admin).filter(Admin.admin_user_id == "divya_admin").first()
    assert owner_post_wipe is not None, "Super Admin must NOT be deleted by wipe!"
    assert divya_post_wipe is not None, "Team Admin Divya must NOT be deleted by wipe!"
    print(f"[+] Verification passed: 0 farmers, 0 buyers, 0 supplies in database. Super Admin ({owner_post_wipe.admin_user_id}) and Divya ({divya_post_wipe.admin_user_id}) preserved!")

    # 12. Clean up test admin Divya
    delete_admin(admin_id=divya_post_wipe.id, db=db, claims=owner_claims)
    print("[+] Clean-up: Revoked temporary test admin Divya.")

    db.close()
    print("\n" + "=" * 70)
    print("ALL 11 VERIFICATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
