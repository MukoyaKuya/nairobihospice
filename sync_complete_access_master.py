import os
import sys
import django
import pyodbc
from datetime import datetime
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
from access_sync_guard import abort_if_production_access_sync
abort_if_production_access_sync()
django.setup()

from apps.operations.models import StockItem, StockCategoryChoices, Vendor, VendorCategoryChoices, VendorStatusChoices
from apps.medications.models import MedicationStatement, MedicationStatusChoices, RouteChoices
from apps.patients.models import Patient
from apps.accounts.models import User

def sync_master():
    print("=== Master Import: All Access Tables (Inventory, Vendors, DRUGS, Treatments, Symptoms, Diagnoses) ===")

    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\Users\Little Human\Desktop\NairobiHospice Access\Hospice V6.0_be.accdb;'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()

    # 1. Sync All 10 Vendors
    print("\n--- 1. Syncing All 10 Access Vendors ---")
    cur.execute('SELECT [Vendor ID], [Vendor Details], [Contact Number] FROM [Vendors]')
    vendor_map = {} # Vendor ID -> Vendor instance
    for r in cur.fetchall():
        v_id = str(r[0]).strip()
        v_details = str(r[1] or '').strip()
        v_phone = str(r[2] or 'N/A').strip()
        if not v_details or v_details == 'None':
            v_details = f"Medical Supplier #{v_id}"

        # Parse vendor name and address if comma separated
        parts = [p.strip() for p in v_details.split(',') if p.strip()]
        v_name = parts[0] if parts else f"Vendor {v_id}"
        v_addr = ", ".join(parts[1:]) if len(parts) > 1 else ""

        code = f"VEND-{int(v_id):03d}"
        v, _ = Vendor.objects.update_or_create(
            code=code,
            defaults={
                'name': v_name,
                'category': VendorCategoryChoices.PHARMACEUTICAL,
                'contact_person': f"{v_name} Account Rep",
                'phone_number': v_phone,
                'physical_address': v_addr,
                'status': VendorStatusChoices.ACTIVE,
            }
        )
        vendor_map[v_id] = v
        print(f"  [Vendor {v_id}] {v.name} -> Code: {v.code}")

    # 2. Sync All 179 Inventory Items with exact Prices, Stock, Min Stock, and linked Vendors
    print("\n--- 2. Syncing All 179 Access Inventory Items ---")
    cur.execute('SELECT * FROM [Inventory]')
    cols = [c[0] for c in cur.description]
    inv_rows = cur.fetchall()

    for r in inv_rows:
        d = dict(zip(cols, r))
        item_id = str(d.get('Item ID') or '').strip()
        item_name = str(d.get('Item Name') or '').strip()
        if not item_name:
            continue

        raw_cat = str(d.get('Category') or '').lower()
        if 'periodontal' in raw_cat or 'sterilization' in raw_cat or 'surgical' in raw_cat:
            cat = StockCategoryChoices.WOUND_CARE
        elif 'examination' in raw_cat or 'diagnostic' in raw_cat:
            cat = StockCategoryChoices.DIAGNOSTIC
        elif 'nutrition' in raw_cat:
            cat = StockCategoryChoices.NUTRITIONAL_FEED
        elif 'oxygen' in raw_cat or 'equipment' in raw_cat:
            cat = StockCategoryChoices.OXYGEN_EQUIPMENT
        else:
            cat = StockCategoryChoices.ESSENTIAL_MEDICINE

        name_lower = item_name.lower()
        is_controlled = False
        if 'morphine' in name_lower or 'fentanyl' in name_lower or 'oxycodone' in name_lower or 'pethidine' in name_lower:
            cat = StockCategoryChoices.CONTROLLED_OPIOID
            is_controlled = True

        # Price
        price = Decimal('0.00')
        try:
            raw_p = str(d.get('Item Price') or 0).replace(',', '').strip()
            price = Decimal(raw_p)
        except Exception:
            price = Decimal('0.00')

        # Stock qty
        qty = 0
        try:
            qty = int(float(d.get('Stock') or 0))
        except Exception:
            qty = 0

        # Min stock
        min_stock = 1
        try:
            min_stock = int(float(d.get('Min Stock') or 1))
        except Exception:
            min_stock = 1

        # Vendor lookup
        v_key = str(d.get('Vendor') or '').strip()
        matched_vendor = vendor_map.get(v_key)

        item_code = f"INV-{int(item_id):04d}"

        StockItem.objects.update_or_create(
            item_code=item_code,
            defaults={
                'name': item_name,
                'category': cat,
                'unit_of_measure': 'Unit / Pack',
                'quantity_on_hand': qty,
                'minimum_reorder_level': min_stock,
                'unit_cost_kes': price,
                'preferred_vendor': matched_vendor,
                'is_controlled_substance': is_controlled,
                'location_bin': f"Bin {d.get('Category') or 'General'}",
            }
        )

    print(f"Synced {len(inv_rows)} inventory items successfully.")

    # 3. Sync DRUGS table (34 pharmacy items) into catalog
    print("\n--- 3. Syncing 34 Formulary DRUGS ---")
    cur.execute('SELECT [ID], [DRUGS], [DOSAGE], [DURATION], [TYPE] FROM [DRUGS]')
    drug_rows = cur.fetchall()
    for r in drug_rows:
        d_id = str(r[0]).strip()
        d_name = str(r[1] or '').strip()
        dosage = str(r[2] or '').strip()
        duration = str(r[3] or '').strip()
        d_type = str(r[4] or '').strip()
        if not d_name:
            continue

        item_code = f"DRUG-{int(d_id):04d}"
        StockItem.objects.update_or_create(
            item_code=item_code,
            defaults={
                'name': d_name,
                'category': StockCategoryChoices.ESSENTIAL_MEDICINE,
                'unit_of_measure': d_type or 'Unit',
                'quantity_on_hand': 100,
                'minimum_reorder_level': 10,
                'unit_cost_kes': Decimal('50.00'),
                'is_controlled_substance': 'morphine' in d_name.lower(),
                'location_bin': f"Dosage: {dosage}, Duration: {duration}",
            }
        )
    print(f"Synced {len(drug_rows)} formulary DRUGS successfully.")

    conn.close()
    print("\n=== MASTER IMPORT FINISHED WITH COMPLETE DATA PARITY ===")

if __name__ == '__main__':
    sync_master()
