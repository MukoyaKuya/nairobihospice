import random
import secrets
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import RoleChoices, StaffProfile, User
from apps.appointments.models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices
from apps.assessments.models import Assessment, AssessmentTypeChoices
from apps.audit.models import AuditAction, AuditEvent
from apps.care.models import (
    CarePlan,
    CarePlanNeed,
    CarePlanStatusChoices,
    CareTeamMember,
    CareTeamRoleChoices,
    EpisodeOfCare,
    EpisodeStatusChoices,
    NeedCategoryChoices,
)
from apps.encounters.models import Encounter, EncounterTypeChoices
from apps.medications.models import MedicationStatement, MedicationStatusChoices, RouteChoices
from apps.notifications.models import Notification, NotificationTypeChoices
from apps.patients.models import Caregiver, NextOfKin, Patient, PatientStatusChoices, SexChoices
from apps.referrals.models import (
    Referral,
    ReferralPriorityChoices,
    ReferralSourceChoices,
    ReferralStatusChoices,
)
from apps.symptoms.models import SymptomAssessmentRecord, SymptomScore, SymptomTypeChoices


class Command(BaseCommand):
    help = 'Seeds realistic Kenyan palliative care demo data for Nairobi Hospice PCMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--allow-outside-debug',
            action='store_true',
            help='Permit seeding in non-DEBUG environments (demo/staging only; never production).',
        )

    def handle(self, *args, **options):
        from django.conf import settings

        if not settings.DEBUG and not options['allow_outside_debug']:
            raise CommandError(
                'Refusing to seed demo data: DEBUG is False. Demo seeding is for '
                'development only. Pass --allow-outside-debug for an explicit '
                'demo/staging environment — never production.'
            )
        self.stdout.write(self.style.NOTICE("Seeding Nairobi Hospice PCMS data..."))

        # 1. Staff & Users
        staff_data = [
            ('doctor@nairobihospice.or.ke', 'dr.mwangi', 'David', 'Mwangi', RoleChoices.DOCTOR, 'MED-KMPDC-8841', 'Palliative Medicine'),
            ('nurse@nairobihospice.or.ke', 'nurse.grace', 'Grace', 'Achieng', RoleChoices.NURSE, 'NCK-RN-55201', 'Palliative Nursing & Home Care'),
            ('co@nairobihospice.or.ke', 'co.wanjiku', 'Faith', 'Wanjiku', RoleChoices.CLINICAL_OFFICER, 'COC-CO-1192', 'Clinical Outpatient Unit'),
            ('social@nairobihospice.or.ke', 'sw.omondi', 'Peter', 'Omondi', RoleChoices.SOCIAL_WORKER, 'SW-K-3349', 'Psychosocial Support Unit'),
            ('counsellor@nairobihospice.or.ke', 'couns.mercy', 'Mercy', 'Chebet', RoleChoices.COUNSELLOR, 'KPA-PSY-7712', 'Psychological & Bereavement'),
            ('pharmacist@nairobihospice.or.ke', 'pharm.mutua', 'James', 'Mutua', RoleChoices.PHARMACIST, 'PPB-PH-4402', 'Hospice Pharmacy'),
            ('reception@nairobihospice.or.ke', 'rec.esther', 'Esther', 'Nyambura', RoleChoices.RECEPTIONIST, '', 'Registration & Front Office'),
            ('manager@nairobihospice.or.ke', 'mgr.kariuki', 'John', 'Kariuki', RoleChoices.MANAGER, '', 'Executive Administration'),
            ('admin@nairobihospice.or.ke', 'admin.sarah', 'Sarah', 'Kimani', RoleChoices.ADMINISTRATOR, '', 'Information Systems'),
        ]

        staff_profiles = {}
        users = {}
        generated_passwords = {}

        for email, uname, fn, ln, role, lic, dept in staff_data:
            u, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': uname,
                    'first_name': fn,
                    'last_name': ln,
                    'phone_number': f"+254 7{random.randint(10000000, 99999999)}",
                    'is_staff': role in [RoleChoices.ADMINISTRATOR, RoleChoices.MANAGER],
                    'is_superuser': role == RoleChoices.ADMINISTRATOR,
                }
            )
            if created:
                # Only set a password for freshly created users. Re-running the
                # seed against an existing database must never silently rotate
                # real staff credentials (or print them).
                pwd = secrets.token_urlsafe(18)
                generated_passwords[email] = pwd
                u.set_password(pwd)
                u.save()
            users[email] = u

            prof, _ = StaffProfile.objects.get_or_create(
                user=u,
                defaults={
                    'role': role,
                    'license_number': lic,
                    'department': dept,
                    'qualifications': 'Palliative Care Certification',
                    'is_active_staff': True,
                    'can_conduct_home_visits': role in [RoleChoices.NURSE, RoleChoices.DOCTOR, RoleChoices.SOCIAL_WORKER],
                }
            )
            staff_profiles[role] = prof

        doctor_user = users['doctor@nairobihospice.or.ke']
        nurse_user = users['nurse@nairobihospice.or.ke']

        # 2. Patients
        patients_spec = [
            {
                'num': 'NH-2026-0001',
                'fn': 'Jane', 'mn': 'Wambui', 'ln': 'Kamau',
                'dob': date(1974, 5, 14), 'sex': SexChoices.FEMALE,
                'phone': '+254 722 345 678', 'alt_phone': '+254 733 987 654',
                'address': 'Kibera, Makina Village, House 42',
                'county': 'Nairobi', 'sub_county': 'Kibra',
                'landmark': 'Near St. Jude Catholic Church, opposite water kiosk',
                'diagnosis': 'Carcinoma of Cervix Stage IV with bilateral hydronephrosis and severe pelvic pain',
                'allergies': 'Tramadol (Severe projectile vomiting)',
                'alerts': 'High pain distress score; bilateral nephrostomy tubes in situ. Needs weekly home nursing review.',
                'nok_name': 'George Kamau', 'nok_rel': 'Spouse', 'nok_phone': '+254 722 345 678',
                'cg_name': 'Mary Wambui', 'cg_rel': 'Daughter', 'cg_phone': '+254 711 002 334',
            },
            {
                'num': 'NH-2026-0002',
                'fn': 'Francis', 'mn': 'Kiprop', 'ln': 'Cheruiyot',
                'dob': date(1962, 11, 20), 'sex': SexChoices.MALE,
                'phone': '+254 715 889 900', 'alt_phone': '',
                'address': 'Kasarani, Clay City Estate, Court 5',
                'county': 'Nairobi', 'sub_county': 'Kasarani',
                'landmark': 'Opposite Clay Works Gate B',
                'diagnosis': 'Carcinoma of Oesophagus Stage IV with severe dysphagia, retrosternal chest pain, and profound cachexia',
                'allergies': 'None known',
                'alerts': 'Aspiration risk. Cannot tolerate solid oral medications. Liquid & sublingual routes only.',
                'nok_name': 'Hellen Cheruiyot', 'nok_rel': 'Spouse', 'nok_phone': '+254 715 889 900',
                'cg_name': 'Peter Cheruiyot', 'cg_rel': 'Son', 'cg_phone': '+254 720 112 233',
            },
            {
                'num': 'NH-2026-0003',
                'fn': 'Mary', 'mn': 'Atieno', 'ln': 'Otieno',
                'dob': date(1982, 3, 8), 'sex': SexChoices.FEMALE,
                'phone': '+254 701 445 566', 'alt_phone': '',
                'address': 'Umoja Innercore, Block C',
                'county': 'Nairobi', 'sub_county': 'Embakasi West',
                'landmark': 'Near Umoja 1 Market',
                'diagnosis': 'Metastatic Breast Carcinoma Stage IV with lytic bone metastases in lumbar spine & ribs',
                'allergies': 'Penicillin (Anaphylactoid rash)',
                'alerts': 'High fall risk and spinal cord compression watch. Patient ambulates with Zimmer frame.',
                'nok_name': 'David Otieno', 'nok_rel': 'Brother', 'nok_phone': '+254 701 445 566',
                'cg_name': 'Eunice Akoth', 'cg_rel': 'Sister', 'cg_phone': '+254 734 556 778',
            },
            {
                'num': 'NH-2026-0004',
                'fn': 'Samuel', 'mn': 'Maina', 'ln': 'Githinji',
                'dob': date(1955, 9, 12), 'sex': SexChoices.MALE,
                'phone': '+254 723 111 222', 'alt_phone': '',
                'address': 'Kikuyu Town, Kidfarmaco',
                'county': 'Kiambu', 'sub_county': 'Kikuyu',
                'landmark': 'Next to PCEA Kikuyu Hospital Junction',
                'diagnosis': 'Castration-Resistant Metastatic Prostate Cancer with pelvis & sacrum bone pain',
                'allergies': 'None',
                'alerts': 'Urinary catheter in situ. Regular drainage care required.',
                'nok_name': 'Margaret Githinji', 'nok_rel': 'Spouse', 'nok_phone': '+254 723 111 222',
                'cg_name': 'Margaret Githinji', 'cg_rel': 'Spouse', 'cg_phone': '+254 723 111 222',
            },
            {
                'num': 'NH-2026-0005',
                'fn': 'Beatrice', 'mn': 'Moraa', 'ln': 'Nyachae',
                'dob': date(1968, 1, 30), 'sex': SexChoices.FEMALE,
                'phone': '+254 712 998 877', 'alt_phone': '',
                'address': 'South B, Hazina Estate',
                'county': 'Nairobi', 'sub_county': 'Starehe',
                'landmark': 'Near Capital Centre',
                'diagnosis': 'End-Stage Renal Disease (ESRD) - Conservative Non-Dialytic Palliative Care',
                'allergies': 'NSAIDs (Avoid all ibuprofen / diclofenac)',
                'alerts': 'Fluid overload risk. Avoid opioid accumulation - dose adjust morphine/gabapentin.',
                'nok_name': 'Dennis Nyachae', 'nok_rel': 'Son', 'nok_phone': '+254 712 998 877',
                'cg_name': 'Dennis Nyachae', 'cg_rel': 'Son', 'cg_phone': '+254 712 998 877',
            },
        ]

        created_patients = []
        for p in patients_spec:
            pt, _ = Patient.objects.get_or_create(
                hospice_number=p['num'],
                defaults={
                    'first_name': p['fn'],
                    'middle_name': p['mn'],
                    'last_name': p['ln'],
                    'date_of_birth': p['dob'],
                    'sex': p['sex'],
                    'phone_number': p['phone'],
                    'alternative_phone': p['alt_phone'],
                    'address': p['address'],
                    'county': p['county'],
                    'sub_county': p['sub_county'],
                    'landmark': p['landmark'],
                    'primary_diagnosis': p['diagnosis'],
                    'allergies': p['allergies'],
                    'clinical_alerts': p['alerts'],
                    'status': PatientStatusChoices.ACTIVE,
                    'registration_date': timezone.now().date() - timedelta(days=60),
                    'created_by': users['reception@nairobihospice.or.ke'],
                }
            )
            created_patients.append(pt)

            NextOfKin.objects.get_or_create(
                patient=pt,
                name=p['nok_name'],
                defaults={'relationship': p['nok_rel'], 'phone_number': p['nok_phone'], 'is_primary': True}
            )

            Caregiver.objects.get_or_create(
                patient=pt,
                name=p['cg_name'],
                defaults={'relationship': p['cg_rel'], 'phone_number': p['cg_phone'], 'is_primary': True, 'availability': 'Full-time caregiver'}
            )

        # 3. Referrals
        ref1, _ = Referral.objects.get_or_create(
            referral_number='REF-2026-0001',
            defaults={
                'patient_name': 'Jane Wambui Kamau',
                'date_of_birth': date(1974, 5, 14),
                'sex': SexChoices.FEMALE,
                'phone_number': '+254 722 345 678',
                'address': 'Kibera, Makina',
                'county': 'Nairobi',
                'referral_source': ReferralSourceChoices.HOSPITAL,
                'referring_facility': 'Kenyatta National Hospital (KNH Oncology Unit)',
                'referring_clinician_name': 'Dr. Angela Oloo (Oncologist)',
                'referral_date': timezone.now().date() - timedelta(days=65),
                'priority': ReferralPriorityChoices.URGENT,
                'status': ReferralStatusChoices.CONVERTED,
                'primary_diagnosis': 'Ca Cervix Stage IV with intractable neuropathic and pelvic pain',
                'reason_for_referral': 'Pain and symptom management, home-based palliative care, caregiver training',
                'clinical_summary': 'Completed palliative RT. Progressive pelvic disease with hydronephrosis. High opioid titration required.',
                'assigned_reviewer': doctor_user,
                'converted_patient': created_patients[0],
                'created_by': users['reception@nairobihospice.or.ke'],
            }
        )

        Referral.objects.get_or_create(
            referral_number='REF-2026-0002',
            defaults={
                'patient_name': 'Emmanuel Kiprotich',
                'date_of_birth': date(1958, 8, 10),
                'sex': SexChoices.MALE,
                'phone_number': '+254 720 334 556',
                'county': 'Nairobi',
                'referral_source': ReferralSourceChoices.HOSPITAL,
                'referring_facility': 'Texas Cancer Centre Nairobi',
                'referring_clinician_name': 'Dr. Kiptoo',
                'referral_date': timezone.now().date() - timedelta(days=2),
                'priority': ReferralPriorityChoices.URGENT,
                'status': ReferralStatusChoices.UNDER_REVIEW,
                'primary_diagnosis': 'Hepatocellular Carcinoma Stage IV with massive ascites',
                'reason_for_referral': 'Symptom management, ascites discomfort, advance care planning',
                'assigned_reviewer': doctor_user,
                'created_by': users['reception@nairobihospice.or.ke'],
            }
        )

        Referral.objects.get_or_create(
            referral_number='REF-2026-0003',
            defaults={
                'patient_name': 'Faith Mwende',
                'date_of_birth': date(1989, 4, 15),
                'sex': SexChoices.FEMALE,
                'phone_number': '+254 733 112 233',
                'county': 'Machakos',
                'referral_source': ReferralSourceChoices.COMMUNITY_WORKER,
                'referring_facility': 'Kaviani Community Health Unit',
                'referring_clinician_name': 'CHP Boniface Mutuku',
                'referral_date': timezone.now().date() - timedelta(days=1),
                'priority': ReferralPriorityChoices.ROUTINE,
                'status': ReferralStatusChoices.RECEIVED,
                'primary_diagnosis': 'Advanced Ovarian Ca with bowel sub-obstruction',
                'reason_for_referral': 'Nausea management, psychological support for young mother',
                'created_by': users['reception@nairobihospice.or.ke'],
            }
        )

        # 4. Episodes & Care Plans for Patient 1 (Jane Kamau)
        jane = created_patients[0]
        ep1, _ = EpisodeOfCare.objects.get_or_create(
            patient=jane,
            defaults={
                'start_date': timezone.now().date() - timedelta(days=60),
                'reason_for_admission': 'Home care palliative support for Cervical Cancer with severe continuous somatic/neuropathic pelvic pain',
                'status': EpisodeStatusChoices.ACTIVE,
                'created_by': doctor_user,
            }
        )

        CareTeamMember.objects.get_or_create(
            episode=ep1,
            staff_member=staff_profiles[RoleChoices.DOCTOR],
            defaults={'role': CareTeamRoleChoices.PRIMARY_DOCTOR, 'is_primary': True, 'start_date': ep1.start_date}
        )
        CareTeamMember.objects.get_or_create(
            episode=ep1,
            staff_member=staff_profiles[RoleChoices.NURSE],
            defaults={'role': CareTeamRoleChoices.PRIMARY_NURSE, 'is_primary': True, 'start_date': ep1.start_date}
        )
        CareTeamMember.objects.get_or_create(
            episode=ep1,
            staff_member=staff_profiles[RoleChoices.SOCIAL_WORKER],
            defaults={'role': CareTeamRoleChoices.SOCIAL_WORKER, 'is_primary': False, 'start_date': ep1.start_date}
        )

        cp1, _ = CarePlan.objects.get_or_create(
            patient=jane,
            title='Holistic Palliative Care Plan - Jane Kamau',
            defaults={
                'episode': ep1,
                'primary_diagnosis': jane.primary_diagnosis,
                'overall_goals': 'Maintain comfort, alleviate severe breakthrough pain, optimize nephrostomy care, train family caregiver on medication timing and positioning, provide emotional bereavement preparedness for family.',
                'resuscitation_preference': 'Allow Natural Death (AND) / Comfort Care Directed Measures',
                'status': CarePlanStatusChoices.ACTIVE,
                'review_date': timezone.now().date() + timedelta(days=5),
                'created_by': doctor_user,
            }
        )

        CarePlanNeed.objects.get_or_create(
            care_plan=cp1,
            problem_description='Continuous somatic and neuropathic pain in lower abdomen radiating to right thigh',
            defaults={
                'category': NeedCategoryChoices.PHYSICAL,
                'goal': 'Reduce pain score to <= 3/10 with minimal drowsiness',
                'interventions': 'Titrate Oral Morphine Solution 10mg q4h around the clock with PRN 5mg breakthrough doses. Amitriptyline 25mg nocte for neuropathic element.',
                'responsible_discipline': 'Medical & Palliative Nursing',
                'target_date': timezone.now().date() + timedelta(days=14),
            }
        )

        CarePlanNeed.objects.get_or_create(
            care_plan=cp1,
            problem_description='Severe constipation risk secondary to scheduled opioid therapy',
            defaults={
                'category': NeedCategoryChoices.PHYSICAL,
                'goal': 'Maintain bowel motion at least once every 2 days without straining',
                'interventions': 'Prescribe prophylactic Lactulose 15ml BD and Bisacodyl 10mg nocte PRN. Hydration encouragement.',
                'responsible_discipline': 'Nursing & Pharmacy',
            }
        )

        CarePlanNeed.objects.get_or_create(
            care_plan=cp1,
            problem_description='Caregiver physical fatigue and emotional distress regarding disease progression',
            defaults={
                'category': NeedCategoryChoices.PSYCHOSOCIAL,
                'goal': 'Daughter Mary receives respite guidance, emotional debriefing, and psychosocial support',
                'interventions': 'Weekly supportive counselling sessions by Social Worker Peter Omondi. Family meeting on care distribution.',
                'responsible_discipline': 'Social Work & Counselling',
            }
        )

        # 5. Encounters for Jane Kamau
        enc1, _ = Encounter.objects.get_or_create(
            patient=jane,
            encounter_date=timezone.now().date() - timedelta(days=45),
            defaults={
                'episode': ep1,
                'encounter_type': EncounterTypeChoices.CLINIC_VISIT,
                'location': 'Nairobi Hospice Outpatient Clinic',
                'reason': 'Initial Palliative Consultation & Opioid Titration',
                'clinical_notes': 'Patient accompanied by daughter Mary. Reports agonizing constant pelvic pain (8/10). Difficulty sleeping. Hydronephrosis well drained via nephrostomies. Initiated on Oral Morphine Solution 5mg q4h + Laxatives.',
                'interventions_performed': 'Prescribed Oral Morphine Solution 5mg q4h. Educated daughter on round-the-clock administration.',
                'next_followup_date': timezone.now().date() - timedelta(days=30),
                'next_followup_plan': 'Home visit in 2 weeks to evaluate response and home environment',
                'recorded_by': doctor_user,
            }
        )

        enc2, _ = Encounter.objects.get_or_create(
            patient=jane,
            encounter_date=timezone.now().date() - timedelta(days=20),
            defaults={
                'episode': ep1,
                'encounter_type': EncounterTypeChoices.HOME_VISIT,
                'location': 'Patient Home - Kibera, Makina',
                'reason': 'Home Care Follow-up & Nephrostomy Dressing',
                'clinical_notes': 'Conducted home visit with Nurse Grace. Patient resting in bed. Pain moderately controlled (5/10). Breakthrough pain occurring at 3am. Nephrostomy site clean, dressing changed. Titrated morphine to 10mg q4h.',
                'interventions_performed': 'Nephrostomy site cleaned and dressed with sterile gauze. Increased morphine dose to 10mg q4h. Assessed food security.',
                'next_followup_date': timezone.now().date() + timedelta(days=7),
                'next_followup_plan': 'Next scheduled home visit for symptom review',
                'recorded_by': nurse_user,
            }
        )

        # 6. Longitudinal ESAS Symptoms for Jane Kamau (showing clear progress 8 -> 5 -> 3)
        # Point 1 (45 days ago)
        rec1, _ = SymptomAssessmentRecord.objects.get_or_create(
            patient=jane,
            recorded_at=timezone.now() - timedelta(days=45),
            defaults={
                'encounter': enc1,
                'total_distress_score': 62,
                'clinical_notes': 'Severe pain and high anxiety upon hospice intake.',
                'recorded_by': doctor_user,
            }
        )
        scores1 = {
            SymptomTypeChoices.PAIN: 8,
            SymptomTypeChoices.TIREDNESS: 7,
            SymptomTypeChoices.DROWSINESS: 3,
            SymptomTypeChoices.NAUSEA: 5,
            SymptomTypeChoices.LACK_OF_APPETITE: 8,
            SymptomTypeChoices.SHORTNESS_OF_BREATH: 2,
            SymptomTypeChoices.DEPRESSION: 7,
            SymptomTypeChoices.ANXIETY: 8,
            SymptomTypeChoices.WELLBEING: 8,
            SymptomTypeChoices.CONSTIPATION: 6,
        }
        for st, sc in scores1.items():
            SymptomScore.objects.get_or_create(record=rec1, symptom_type=st, defaults={'score': sc})

        # Point 2 (20 days ago)
        rec2, _ = SymptomAssessmentRecord.objects.get_or_create(
            patient=jane,
            recorded_at=timezone.now() - timedelta(days=20),
            defaults={
                'encounter': enc2,
                'total_distress_score': 38,
                'clinical_notes': 'Notable improvement in pain and sleep following regular morphine.',
                'recorded_by': nurse_user,
            }
        )
        scores2 = {
            SymptomTypeChoices.PAIN: 5,
            SymptomTypeChoices.TIREDNESS: 5,
            SymptomTypeChoices.DROWSINESS: 4,
            SymptomTypeChoices.NAUSEA: 2,
            SymptomTypeChoices.LACK_OF_APPETITE: 4,
            SymptomTypeChoices.SHORTNESS_OF_BREATH: 1,
            SymptomTypeChoices.DEPRESSION: 4,
            SymptomTypeChoices.ANXIETY: 4,
            SymptomTypeChoices.WELLBEING: 5,
            SymptomTypeChoices.CONSTIPATION: 4,
        }
        for st, sc in scores2.items():
            SymptomScore.objects.get_or_create(record=rec2, symptom_type=st, defaults={'score': sc})

        # Point 3 (3 days ago)
        rec3, _ = SymptomAssessmentRecord.objects.get_or_create(
            patient=jane,
            recorded_at=timezone.now() - timedelta(days=3),
            defaults={
                'total_distress_score': 22,
                'clinical_notes': 'Good pain control 3/10. Patient in good spirits, interacting with grandchildren.',
                'recorded_by': nurse_user,
            }
        )
        scores3 = {
            SymptomTypeChoices.PAIN: 3,
            SymptomTypeChoices.TIREDNESS: 3,
            SymptomTypeChoices.DROWSINESS: 3,
            SymptomTypeChoices.NAUSEA: 1,
            SymptomTypeChoices.LACK_OF_APPETITE: 3,
            SymptomTypeChoices.SHORTNESS_OF_BREATH: 0,
            SymptomTypeChoices.DEPRESSION: 2,
            SymptomTypeChoices.ANXIETY: 2,
            SymptomTypeChoices.WELLBEING: 3,
            SymptomTypeChoices.CONSTIPATION: 2,
        }
        for st, sc in scores3.items():
            SymptomScore.objects.get_or_create(record=rec3, symptom_type=st, defaults={'score': sc})

        # 7. Active Medications for Jane Kamau
        MedicationStatement.objects.get_or_create(
            patient=jane,
            medication_name='Oral Morphine Solution (5mg/5ml)',
            defaults={
                'dosage': '10 mg (10 ml)',
                'route': RouteChoices.ORAL,
                'frequency': 'Every 4 hours (q4h) around the clock',
                'indication': 'Somatic & visceral cancer pelvic pain',
                'start_date': timezone.now().date() - timedelta(days=45),
                'status': MedicationStatusChoices.ACTIVE,
                'prescriber': doctor_user,
                'prescriber_name': doctor_user.display_name,
                'instructions_for_caregiver': 'Give 10ml by mouth every 4 hours. Give extra 5ml dose for breakthrough pain if pain >= 5/10.',
            }
        )

        MedicationStatement.objects.get_or_create(
            patient=jane,
            medication_name='Lactulose Syrup (3.3g/5ml)',
            defaults={
                'dosage': '15 ml',
                'route': RouteChoices.ORAL,
                'frequency': 'Twice daily (BD) with water',
                'indication': 'Opioid-induced constipation prophylaxis',
                'start_date': timezone.now().date() - timedelta(days=45),
                'status': MedicationStatusChoices.ACTIVE,
                'prescriber': doctor_user,
                'prescriber_name': doctor_user.display_name,
                'instructions_for_caregiver': 'Give after morning and evening meals.',
            }
        )

        MedicationStatement.objects.get_or_create(
            patient=jane,
            medication_name='Amitriptyline Tablets',
            defaults={
                'dosage': '25 mg',
                'route': RouteChoices.ORAL,
                'frequency': 'Once daily at bedtime (nocte)',
                'indication': 'Neuropathic lumbosacral pain & insomnia',
                'start_date': timezone.now().date() - timedelta(days=30),
                'status': MedicationStatusChoices.ACTIVE,
                'prescriber': doctor_user,
                'prescriber_name': doctor_user.display_name,
            }
        )

        # 8. Structured Assessments
        Assessment.objects.get_or_create(
            patient=jane,
            assessment_type=AssessmentTypeChoices.INITIAL,
            defaults={
                'assessment_date': timezone.now().date() - timedelta(days=45),
                'pain_score': 8,
                'pps_score': 50,
                'ecog_score': 3,
                'clinical_summary': 'Comprehensive initial holistic palliative assessment conducted. Confirmed severe somatic pelvic pain with neuropathic radiation. Caregiver education completed. Agreed on comfort goals.',
                'assessor': doctor_user,
            }
        )

        # 9. Appointments
        Appointment.objects.get_or_create(
            patient=jane,
            scheduled_date=timezone.now().date(),
            scheduled_time=time(10, 0),
            defaults={
                'staff_member': staff_profiles[RoleChoices.NURSE],
                'appointment_type': AppointmentTypeChoices.HOME_VISIT,
                'duration_minutes': 60,
                'location': jane.address,
                'reason': 'Routine bi-weekly home nursing visit, nephrostomy check, ESAS monitoring',
                'status': AppointmentStatusChoices.SCHEDULED,
                'created_by': nurse_user,
            }
        )

        Appointment.objects.get_or_create(
            patient=created_patients[1],
            scheduled_date=timezone.now().date(),
            scheduled_time=time(11, 30),
            defaults={
                'staff_member': staff_profiles[RoleChoices.DOCTOR],
                'appointment_type': AppointmentTypeChoices.CLINIC_VISIT,
                'duration_minutes': 45,
                'location': 'Nairobi Hospice Outpatient Room 1',
                'reason': 'Dysphagia medication reassessment and family counselling',
                'status': AppointmentStatusChoices.SCHEDULED,
                'created_by': doctor_user,
            }
        )

        Appointment.objects.get_or_create(
            patient=created_patients[2],
            scheduled_date=timezone.now().date() + timedelta(days=2),
            scheduled_time=time(9, 30),
            defaults={
                'staff_member': staff_profiles[RoleChoices.SOCIAL_WORKER],
                'appointment_type': AppointmentTypeChoices.HOME_VISIT,
                'location': created_patients[2].address,
                'reason': 'Psychosocial and family support visit in Umoja',
                'status': AppointmentStatusChoices.SCHEDULED,
                'created_by': doctor_user,
            }
        )

        # 10. Notifications
        Notification.objects.get_or_create(
            recipient=doctor_user,
            title='Care Plan Review Due: Jane Kamau',
            defaults={
                'notification_type': NotificationTypeChoices.CARE_PLAN_DUE,
                'message': 'Jane Kamau (NH-2026-0001) has an active care plan scheduled for MDT review on ' + (timezone.now().date() + timedelta(days=5)).strftime('%d %b %Y'),
                'link_url': f"/care/care-plan/{cp1.pk}/",
                'is_read': False,
            }
        )

        Notification.objects.get_or_create(
            recipient=doctor_user,
            title='High Priority Referral: Emmanuel Kiprotich',
            defaults={
                'notification_type': NotificationTypeChoices.PENDING_REFERRAL,
                'message': 'Urgent incoming referral from Texas Cancer Centre awaiting triage review.',
                'link_url': '/referrals/',
                'is_read': False,
            }
        )

        # 11. Audit Events
        AuditEvent.objects.get_or_create(
            summary="System initialized with Nairobi Hospice clinical dataset",
            defaults={
                'user': users['admin@nairobihospice.or.ke'],
                'user_email': 'admin@nairobihospice.or.ke',
                'user_role': 'ADMINISTRATOR',
                'action': AuditAction.CREATE,
                'resource_type': 'SystemSeed',
                'ip_address': '127.0.0.1',
            }
        )

        # 12. Operations, Vendors, Inventory & Procurement
        from apps.operations.models import (
            MovementTypeChoices,
            ProcurementOrder,
            ProcurementStatusChoices,
            StockCategoryChoices,
            StockItem,
            StockMovement,
            Vendor,
            VendorCategoryChoices,
            VendorStatusChoices,
        )

        mgr_user = users['manager@nairobihospice.or.ke']

        v1, _ = Vendor.objects.get_or_create(
            code='VND-KEMSA-01',
            defaults={
                'name': 'Kenya Medical Supplies Authority (KEMSA)',
                'category': VendorCategoryChoices.PHARMACEUTICAL,
                'contact_person': 'Pauline Ndwiga',
                'phone_number': '+254 20 3922000',
                'email': 'hospice.orders@kemsa.co.ke',
                'kra_pin': 'P051100234K',
                'physical_address': 'Commercial Street, Industrial Area, Nairobi',
                'payment_terms': '30 Days Net',
                'status': VendorStatusChoices.PREFERRED,
                'notes': 'National essential palliative drugs and morphine distributor agreement.',
            }
        )

        v2, _ = Vendor.objects.get_or_create(
            code='VND-HARLEYS-02',
            defaults={
                'name': 'Harleys Pharmaceuticals Limited',
                'category': VendorCategoryChoices.PHARMACEUTICAL,
                'contact_person': 'Suresh Patel',
                'phone_number': '+254 722 202 030',
                'email': 'institutional@harleysltd.com',
                'kra_pin': 'P051288419Z',
                'physical_address': 'Harleys House, Central Business District, Nairobi',
                'payment_terms': '30 Days Net',
                'status': VendorStatusChoices.ACTIVE,
                'notes': 'Antiemetics, adjuvants, and analgesic medications.',
            }
        )

        v3, _ = Vendor.objects.get_or_create(
            code='VND-BOC-03',
            defaults={
                'name': 'BOC Gases Kenya PLC',
                'category': VendorCategoryChoices.OXYGEN_EQUIPMENT,
                'contact_person': 'Kennedy Omwenga',
                'phone_number': '+254 733 600 200',
                'email': 'healthcare@boc.co.ke',
                'kra_pin': 'P051003491M',
                'physical_address': 'Kitui Road, Industrial Area, Nairobi',
                'payment_terms': '15 Days Net',
                'status': VendorStatusChoices.PREFERRED,
                'notes': 'Medical oxygen cylinders for home-based palliative respiratory support.',
            }
        )

        v4, _ = Vendor.objects.get_or_create(
            code='VND-MEGA-04',
            defaults={
                'name': 'Megascope Healthcare Kenya Ltd',
                'category': VendorCategoryChoices.CONSUMABLES,
                'contact_person': 'Christine Mwende',
                'phone_number': '+254 711 400 500',
                'email': 'sales@megascope.co.ke',
                'kra_pin': 'P051399420P',
                'physical_address': 'Kilimani Business Centre, Argwings Kodhek Rd, Nairobi',
                'payment_terms': '30 Days Net',
                'status': VendorStatusChoices.ACTIVE,
                'notes': 'Advanced palliative wound care dressings and silicone suction kits.',
            }
        )

        # Stock Items
        s1, _ = StockItem.objects.get_or_create(
            item_code='STK-MED-01',
            defaults={
                'name': 'Oral Morphine Solution 10mg/5ml (500ml)',
                'category': StockCategoryChoices.CONTROLLED_OPIOID,
                'unit_of_measure': 'Bottles',
                'quantity_on_hand': 45,
                'minimum_reorder_level': 15,
                'unit_cost_kes': 1200.00,
                'preferred_vendor': v1,
                'location_bin': 'Pharmacy Controlled Safe 1',
                'is_controlled_substance': True,
            }
        )

        s2, _ = StockItem.objects.get_or_create(
            item_code='STK-MED-02',
            defaults={
                'name': 'Fentanyl Transdermal Patches 25mcg/hr',
                'category': StockCategoryChoices.CONTROLLED_OPIOID,
                'unit_of_measure': 'Boxes (5 Patches)',
                'quantity_on_hand': 12,
                'minimum_reorder_level': 10,
                'unit_cost_kes': 4800.00,
                'preferred_vendor': v2,
                'location_bin': 'Pharmacy Controlled Safe 1',
                'is_controlled_substance': True,
            }
        )

        s3, _ = StockItem.objects.get_or_create(
            item_code='STK-WND-01',
            defaults={
                'name': 'Aquacel Ag Silver Hydrofiber Dressing 10x10cm',
                'category': StockCategoryChoices.WOUND_CARE,
                'unit_of_measure': 'Boxes (10 Dressings)',
                'quantity_on_hand': 8,
                'minimum_reorder_level': 15,
                'unit_cost_kes': 3500.00,
                'preferred_vendor': v4,
                'location_bin': 'Stores Rack B2',
                'is_controlled_substance': False,
            }
        )

        s4, _ = StockItem.objects.get_or_create(
            item_code='STK-OXY-01',
            defaults={
                'name': 'Medical Oxygen Cylinder (Size F / 1.36m3)',
                'category': StockCategoryChoices.OXYGEN_EQUIPMENT,
                'unit_of_measure': 'Cylinders',
                'quantity_on_hand': 6,
                'minimum_reorder_level': 4,
                'unit_cost_kes': 2800.00,
                'preferred_vendor': v3,
                'location_bin': 'Oxygen Bay / Cylinder Bay',
                'is_controlled_substance': False,
            }
        )

        s5, _ = StockItem.objects.get_or_create(
            item_code='STK-PPE-01',
            defaults={
                'name': 'Nitrile Examination Gloves Medium (Box of 100)',
                'category': StockCategoryChoices.PPE_SANITATION,
                'unit_of_measure': 'Boxes',
                'quantity_on_hand': 55,
                'minimum_reorder_level': 20,
                'unit_cost_kes': 750.00,
                'preferred_vendor': v4,
                'location_bin': 'Stores Rack A1',
                'is_controlled_substance': False,
            }
        )

        # Procurement Orders
        po1, _ = ProcurementOrder.objects.get_or_create(
            po_number='PO-2026-0041',
            defaults={
                'vendor': v1,
                'order_date': timezone.now().date() - timedelta(days=14),
                'expected_delivery_date': timezone.now().date() - timedelta(days=7),
                'actual_delivery_date': timezone.now().date() - timedelta(days=6),
                'status': ProcurementStatusChoices.COMPLETED,
                'total_amount_kes': 145000.00,
                'invoice_number': 'INV-KEMSA-8819',
                'notes': 'Quarterly essential palliative morphine solution batch.',
                'requested_by': mgr_user,
                'approved_by': users['admin@nairobihospice.or.ke'],
            }
        )

        po2, _ = ProcurementOrder.objects.get_or_create(
            po_number='PO-2026-0042',
            defaults={
                'vendor': v4,
                'order_date': timezone.now().date() - timedelta(days=4),
                'expected_delivery_date': timezone.now().date() + timedelta(days=3),
                'status': ProcurementStatusChoices.APPROVED,
                'total_amount_kes': 68500.00,
                'invoice_number': '',
                'notes': 'Urgent silver dressings replenishment for fungating cancer wounds.',
                'requested_by': mgr_user,
                'approved_by': users['admin@nairobihospice.or.ke'],
            }
        )

        po3, _ = ProcurementOrder.objects.get_or_create(
            po_number='PO-2026-0043',
            defaults={
                'vendor': v3,
                'order_date': timezone.now().date() - timedelta(days=1),
                'expected_delivery_date': timezone.now().date() + timedelta(days=5),
                'status': ProcurementStatusChoices.PENDING_APPROVAL,
                'total_amount_kes': 34000.00,
                'invoice_number': '',
                'notes': 'Cylinder refills for outpatient oxygen bank.',
                'requested_by': mgr_user,
            }
        )

        # Stock Movements
        StockMovement.objects.get_or_create(
            stock_item=s1,
            reference_document='PO-2026-0041',
            defaults={
                'movement_type': MovementTypeChoices.RECEIVE,
                'quantity': 50,
                'balance_after': 50,
                'notes': 'Received batch from KEMSA order PO-2026-0041',
                'recorded_by': mgr_user,
            }
        )

        StockMovement.objects.get_or_create(
            stock_item=s1,
            reference_document='RX-Jane-Wambui',
            defaults={
                'movement_type': MovementTypeChoices.DISPENSE,
                'quantity': -5,
                'balance_after': 45,
                'notes': 'Dispensed oral morphine solution courses to clinic patients',
                'recorded_by': users['pharmacist@nairobihospice.or.ke'],
            }
        )

        StockMovement.objects.get_or_create(
            stock_item=s3,
            reference_document='ROUTE-KIBERA',
            defaults={
                'movement_type': MovementTypeChoices.TRANSFER,
                'quantity': -7,
                'balance_after': 8,
                'notes': 'Transferred silver dressings to Home Care Nursing Route Bags',
                'recorded_by': users['nurse@nairobihospice.or.ke'],
            }
        )

        # Invoices
        from apps.operations.models import Invoice, InvoiceLineItem, InvoiceTypeChoices, PaymentStatusChoices

        inv1, _ = Invoice.objects.get_or_create(
            invoice_number='INV-2026-0091',
            defaults={
                'invoice_type': InvoiceTypeChoices.SUPPLIER_PURCHASE,
                'vendor': v1,
                'procurement_order': po1,
                'issue_date': timezone.now().date() - timedelta(days=14),
                'due_date': timezone.now().date() + timedelta(days=16),
                'status': PaymentStatusChoices.PAID,
                'subtotal_amount_kes': 145000.00,
                'tax_amount_kes': 0.00,
                'discount_amount_kes': 0.00,
                'total_amount_kes': 145000.00,
                'amount_paid_kes': 145000.00,
                'payment_method': 'Bank EFT (Standard Chartered)',
                'payment_reference': 'EFT-SCB-881920',
                'notes': 'KEMSA quarterly essential morphine and palliative medicines supply.',
                'created_by': mgr_user,
            }
        )
        InvoiceLineItem.objects.get_or_create(
            invoice=inv1,
            description='Oral Morphine Solution 10mg/5ml (500ml Bottles) x 50',
            defaults={
                'stock_item': s1,
                'quantity': 50,
                'unit_price_kes': 900.00,
                'total_price_kes': 45000.00,
            }
        )
        InvoiceLineItem.objects.get_or_create(
            invoice=inv1,
            description='Fentanyl Transdermal Matrix Patches 25mcg/hr (Boxes of 5) x 25',
            defaults={
                'stock_item': s2,
                'quantity': 25,
                'unit_price_kes': 4000.00,
                'total_price_kes': 100000.00,
            }
        )

        inv2, _ = Invoice.objects.get_or_create(
            invoice_number='INV-2026-0092',
            defaults={
                'invoice_type': InvoiceTypeChoices.SUPPLIER_PURCHASE,
                'vendor': v4,
                'procurement_order': po2,
                'issue_date': timezone.now().date() - timedelta(days=4),
                'due_date': timezone.now().date() + timedelta(days=26),
                'status': PaymentStatusChoices.ISSUED,
                'subtotal_amount_kes': 68500.00,
                'tax_amount_kes': 0.00,
                'discount_amount_kes': 0.00,
                'total_amount_kes': 68500.00,
                'amount_paid_kes': 0.00,
                'payment_method': 'Bank Transfer (EFT)',
                'payment_reference': '',
                'notes': 'Aquacel Ag silver wound dressings for palliative wound care.',
                'created_by': mgr_user,
            }
        )
        InvoiceLineItem.objects.get_or_create(
            invoice=inv2,
            description='Aquacel Ag Extra Hydrofiber Silver Dressings 10x10cm (Box of 10) x 15',
            defaults={
                'stock_item': s3,
                'quantity': 15,
                'unit_price_kes': 4566.67,
                'total_price_kes': 68500.00,
            }
        )

        inv3, _ = Invoice.objects.get_or_create(
            invoice_number='INV-2026-0093',
            defaults={
                'invoice_type': InvoiceTypeChoices.PATIENT_SERVICE,
                'patient': created_patients[0],
                'issue_date': timezone.now().date() - timedelta(days=2),
                'due_date': timezone.now().date() + timedelta(days=28),
                'status': PaymentStatusChoices.PAID,
                'subtotal_amount_kes': 4500.00,
                'tax_amount_kes': 0.00,
                'discount_amount_kes': 1000.00,
                'total_amount_kes': 3500.00,
                'amount_paid_kes': 3500.00,
                'payment_method': 'M-PESA Paybill 981234',
                'payment_reference': 'QKN8892109',
                'notes': 'Subsidized clinical assessment, oral morphine solution refill, and home nursing package.',
                'created_by': mgr_user,
            }
        )
        InvoiceLineItem.objects.get_or_create(
            invoice=inv3,
            description='Comprehensive MDT Palliative Care Consultation & Review',
            defaults={
                'quantity': 1,
                'unit_price_kes': 2000.00,
                'total_price_kes': 2000.00,
            }
        )
        InvoiceLineItem.objects.get_or_create(
            invoice=inv3,
            description='Oral Morphine Solution 10mg/5ml (500ml Course)',
            defaults={
                'stock_item': s1,
                'quantity': 1,
                'unit_price_kes': 1500.00,
                'total_price_kes': 1500.00,
            }
        )
        InvoiceLineItem.objects.get_or_create(
            invoice=inv3,
            description='Home Care Nursing Kit & Dressing Consumables',
            defaults={
                'quantity': 1,
                'unit_price_kes': 1000.00,
                'total_price_kes': 1000.00,
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Nairobi Hospice PCMS demo dataset including Operations and Invoicing suite!"))
        self.stdout.write(self.style.WARNING('Generated development passwords (store securely; they will not be shown again):'))
        for email, password in generated_passwords.items():
            self.stdout.write(f'{email}: {password}')
