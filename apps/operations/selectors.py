from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.encounters.models import Encounter
from apps.patients.models import Patient
from apps.reporting.charting import chart_json

from .models import (
    ProcurementOrder,
    ProcurementStatusChoices,
    StockItem,
    StockMovement,
    Vendor,
    VendorStatusChoices,
)


def get_operations_dashboard_data():
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Vendors & Suppliers
    total_vendors = Vendor.objects.count()
    active_vendors = Vendor.objects.filter(status=VendorStatusChoices.ACTIVE).count()
    preferred_vendors = Vendor.objects.filter(status=VendorStatusChoices.PREFERRED).count()

    # 2. Inventory & Stock Valuation
    stock_items = StockItem.objects.select_related('preferred_vendor').all()
    total_stock_skus = stock_items.count()
    low_stock_items = [item for item in stock_items if item.is_low_stock]
    total_inventory_valuation = sum(item.total_valuation_kes for item in stock_items) or Decimal('0.00')
    controlled_items = stock_items.filter(is_controlled_substance=True)

    # Inventory Valuation by Category (for Doughnut Chart)
    inv_category_counts = Counter()
    inv_category_valuation = Counter()
    for item in stock_items:
        cat_label = item.get_category_display()
        inv_category_counts[cat_label] += item.quantity_on_hand
        inv_category_valuation[cat_label] += float(item.total_valuation_kes)

    inv_chart_labels = list(inv_category_valuation.keys())
    inv_chart_data = [round(v, 2) for v in inv_category_valuation.values()]

    # 3. Procurement Requisitions & 6-Month Spend Trend
    orders = ProcurementOrder.objects.select_related('vendor', 'requested_by').all()
    total_orders_count = orders.count()
    orders_this_month = orders.filter(order_date__gte=month_start.date())
    spend_this_month = orders_this_month.exclude(status=ProcurementStatusChoices.CANCELLED).aggregate(total=Sum('total_amount_kes'))['total'] or Decimal('0.00')
    total_spend = orders.exclude(status=ProcurementStatusChoices.CANCELLED).aggregate(total=Sum('total_amount_kes'))['total'] or Decimal('0.00')
    pending_approval_orders = orders.filter(status=ProcurementStatusChoices.PENDING_APPROVAL)
    active_deliveries = orders.filter(status__in=[ProcurementStatusChoices.APPROVED, ProcurementStatusChoices.PARTIALLY_DELIVERED])

    # 6-Month Historical Spend Data (real values only; months without
    # procurement activity report zero rather than simulated figures)
    spend_labels = []
    spend_amounts = []
    for i in range(5, -1, -1):
        target_date = now - timedelta(days=i * 30)
        m_label = target_date.strftime('%b %Y')
        m_start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
        if target_date.month == 12:
            m_end = target_date.replace(year=target_date.year + 1, month=1, day=1).date()
        else:
            m_end = target_date.replace(month=target_date.month + 1, day=1).date()

        m_spend = orders.filter(order_date__gte=m_start, order_date__lt=m_end).exclude(status=ProcurementStatusChoices.CANCELLED).aggregate(total=Sum('total_amount_kes'))['total'] or Decimal('0.00')
        spend_labels.append(m_label)
        spend_amounts.append(float(m_spend))

    # 4. Stock Movements (Inflow / Outflow)
    recent_movements = StockMovement.objects.select_related('stock_item', 'recorded_by').order_by('-created_at')[:10]

    # 5. Disease & Epidemiological Patterns (Live Patient Master Data)
    patients = Patient.objects.filter(status='ACTIVE')
    total_patients_count = patients.count()

    diagnosis_counts = Counter()
    for p in patients:
        dx = (p.primary_diagnosis or 'Unspecified Palliative Diagnosis').strip()
        if 'cervix' in dx.lower() or 'cervical' in dx.lower():
            dx_key = 'Cervical Carcinoma'
        elif 'breast' in dx.lower():
            dx_key = 'Breast Carcinoma'
        elif 'prostate' in dx.lower():
            dx_key = 'Prostate Carcinoma'
        elif 'esophag' in dx.lower() or 'oesophag' in dx.lower():
            dx_key = 'Esophageal Carcinoma'
        elif 'colorectal' in dx.lower() or 'colon' in dx.lower() or 'rectal' in dx.lower():
            dx_key = 'Colorectal Carcinoma'
        elif 'kaposi' in dx.lower():
            dx_key = 'Kaposi Sarcoma'
        elif 'liver' in dx.lower() or 'hepat' in dx.lower():
            dx_key = 'Hepatocellular Carcinoma'
        elif 'lung' in dx.lower():
            dx_key = 'Lung Carcinoma'
        elif 'hiv' in dx.lower():
            dx_key = 'Advanced HIV / AIDS'
        elif 'renal' in dx.lower() or 'kidney' in dx.lower():
            dx_key = 'End-Stage Renal Disease'
        else:
            dx_key = dx[:30]
        diagnosis_counts[dx_key] += 1

    top_diseases = diagnosis_counts.most_common(6)
    top_diseases_data = [
        {
            'name': name,
            'count': count,
            'pct': round((count / total_patients_count * 100), 1) if total_patients_count > 0 else 0
        }
        for name, count in top_diseases
    ]

    # 6. Service Modality Encounters (Month to date)
    encounters_month = Encounter.objects.filter(encounter_date__gte=month_start.date())
    total_encounters_month = encounters_month.count()
    home_visits_count = encounters_month.filter(encounter_type='HOME_VISIT').count()
    clinic_visits_count = encounters_month.filter(encounter_type='CLINIC_VISIT').count()
    community_visits_count = encounters_month.filter(encounter_type='COMMUNITY_VISIT').count()
    phone_consults_count = encounters_month.filter(encounter_type='TELEPHONE').count()

    modality_labels = ['Home Visits', 'Clinic Rooms', 'Community / Outreach', 'Teleconsults']
    modality_data = [home_visits_count, clinic_visits_count, community_visits_count, phone_consults_count]

    return {
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'preferred_vendors': preferred_vendors,
        'total_stock_skus': total_stock_skus,
        'low_stock_items': low_stock_items,
        'low_stock_count': len(low_stock_items),
        'total_inventory_valuation': total_inventory_valuation,
        'controlled_items_count': controlled_items.count(),
        'total_orders_count': total_orders_count,
        'spend_this_month': spend_this_month,
        'total_spend': total_spend,
        'pending_approval_count': pending_approval_orders.count(),
        'active_deliveries_count': active_deliveries.count(),
        'recent_orders': orders[:6],
        'recent_movements': recent_movements,
        'top_diseases_data': top_diseases_data,
        'total_patients_count': total_patients_count,
        'total_encounters_month': total_encounters_month,
        'home_visits_count': home_visits_count,
        'clinic_visits_count': clinic_visits_count,
        'community_visits_count': community_visits_count,
        'phone_consults_count': phone_consults_count,
        # JSON serialized payloads for Chart.js
        'spend_labels_json': chart_json(spend_labels),
        'spend_amounts_json': chart_json(spend_amounts),
        'inv_chart_labels_json': chart_json(inv_chart_labels),
        'inv_chart_data_json': chart_json(inv_chart_data),
        'modality_labels_json': chart_json(modality_labels),
        'modality_data_json': chart_json(modality_data),
    }


def get_disease_analytics_data():
    patients = Patient.objects.all()
    total_patients = patients.count()
    active_patients = patients.filter(status='ACTIVE').count()

    # Diagnosis Frequency
    diagnosis_counts = Counter()
    county_counts = Counter()
    gender_counts = Counter()
    age_groups = {'0 - 18 yrs': 0, '19 - 35 yrs': 0, '36 - 50 yrs': 0, '51 - 65 yrs': 0, '66+ yrs': 0, 'Unknown': 0}
    category_counts = {'Solid Oncology (Carcinomas)': 0, 'Hematologic / Other Malignancy': 0, 'Non-Malignant Palliative': 0}

    for p in patients:
        dx = (p.primary_diagnosis or 'Unspecified').strip()
        diagnosis_counts[dx] += 1

        # Classify disease domain
        dx_lower = dx.lower()
        if any(c in dx_lower for c in ['cancer', 'carcinoma', 'sarcoma', 'melanoma', 'tumor', 'tumour', 'breast', 'cervix', 'cervical', 'prostate', 'colon', 'rectal', 'esophag', 'oesophag', 'liver', 'hepat', 'lung']):
            if 'sarcoma' in dx_lower or 'leukemia' in dx_lower or 'lymphoma' in dx_lower:
                category_counts['Hematologic / Other Malignancy'] += 1
            else:
                category_counts['Solid Oncology (Carcinomas)'] += 1
        else:
            category_counts['Non-Malignant Palliative'] += 1

        county = (p.county or 'Nairobi').strip()
        county_counts[county] += 1

        gender_counts[p.get_sex_display()] += 1

        age = p.age
        if age is None:
            age_groups['Unknown'] += 1
        elif age <= 18:
            age_groups['0 - 18 yrs'] += 1
        elif age <= 35:
            age_groups['19 - 35 yrs'] += 1
        elif age <= 50:
            age_groups['36 - 50 yrs'] += 1
        elif age <= 65:
            age_groups['51 - 65 yrs'] += 1
        else:
            age_groups['66+ yrs'] += 1

    top_diagnoses_raw = diagnosis_counts.most_common(10)
    top_diagnoses = [
        {'diagnosis': name, 'count': count, 'percentage': round((count / total_patients * 100), 1) if total_patients else 0}
        for name, count in top_diagnoses_raw
    ]

    top_counties_raw = county_counts.most_common(6)
    top_counties = [
        {'county': name, 'count': count, 'percentage': round((count / total_patients * 100), 1) if total_patients else 0}
        for name, count in top_counties_raw
    ]

    age_groups_list = [
        {'label': k, 'count': v} for k, v in age_groups.items()
    ]

    # Chart datasets
    chart_dx_labels = [name[:25] for name, _ in top_diagnoses_raw]
    chart_dx_counts = [count for _, count in top_diagnoses_raw]

    chart_age_labels = list(age_groups.keys())
    chart_age_counts = list(age_groups.values())

    chart_gender_labels = list(gender_counts.keys())
    chart_gender_counts = list(gender_counts.values())

    chart_county_labels = [f"{name} County" for name, _ in top_counties_raw]
    chart_county_counts = [count for _, count in top_counties_raw]

    chart_category_labels = list(category_counts.keys())
    chart_category_counts = list(category_counts.values())

    return {
        'total_patients': total_patients,
        'active_patients': active_patients,
        'top_diagnoses': top_diagnoses,
        'top_counties': top_counties,
        'gender_counts': dict(gender_counts),
        'age_groups_list': age_groups_list,
        # JSON serialized chart data
        'chart_dx_labels_json': chart_json(chart_dx_labels),
        'chart_dx_counts_json': chart_json(chart_dx_counts),
        'chart_age_labels_json': chart_json(chart_age_labels),
        'chart_age_counts_json': chart_json(chart_age_counts),
        'chart_gender_labels_json': chart_json(chart_gender_labels),
        'chart_gender_counts_json': chart_json(chart_gender_counts),
        'chart_county_labels_json': chart_json(chart_county_labels),
        'chart_county_counts_json': chart_json(chart_county_counts),
        'chart_category_labels_json': chart_json(chart_category_labels),
        'chart_category_counts_json': chart_json(chart_category_counts),
    }
