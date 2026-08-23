"""Run bounded ORM smoke queries against a populated database.

Usage: python manage.py shell < scripts/load_smoke.py
For representative results, run this against a staging-sized dataset and inspect
the query plan with PostgreSQL EXPLAIN or MySQL EXPLAIN.
"""
from django.db import connection, reset_queries

from apps.patients.models import Patient

reset_queries()
patient = Patient.objects.order_by('-registration_date', '-created_at').first()
if patient:
    list(patient.encounters.select_related('recorded_by').order_by('-encounter_date', '-created_at')[:100])
    list(patient.assessments.select_related('assessor').order_by('-assessment_date', '-created_at')[:100])
    list(patient.medications.select_related('prescriber').order_by('-status', '-start_date')[:100])
    list(patient.symptom_records.prefetch_related('scores').order_by('-recorded_at')[:100])
print(f'patient_history_queries={len(connection.queries)}')
