from django.db import migrations


SQLITE_INSERT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS check_dispense_patient_rx_match_insert
BEFORE INSERT ON operations_stockmovement
FOR EACH ROW
WHEN NEW.movement_type = 'DISPENSE' AND NEW.medication_statement_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Medication statement does not belong to the dispensed patient')
    WHERE NOT EXISTS (
        SELECT 1 FROM medications_medicationstatement
        WHERE id = NEW.medication_statement_id AND patient_id = NEW.patient_id
    );
END;
"""

SQLITE_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS check_dispense_patient_rx_match_update
BEFORE UPDATE ON operations_stockmovement
FOR EACH ROW
WHEN NEW.movement_type = 'DISPENSE' AND NEW.medication_statement_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'Medication statement does not belong to the dispensed patient')
    WHERE NOT EXISTS (
        SELECT 1 FROM medications_medicationstatement
        WHERE id = NEW.medication_statement_id AND patient_id = NEW.patient_id
    );
END;
"""

SQLITE_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS check_dispense_patient_rx_match_insert;
DROP TRIGGER IF EXISTS check_dispense_patient_rx_match_update;
"""


def create_triggers(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    with connection.cursor() as cursor:
        if vendor == 'sqlite':
            cursor.execute(SQLITE_INSERT_TRIGGER)
            cursor.execute(SQLITE_UPDATE_TRIGGER)
        elif vendor == 'postgresql':
            cursor.execute("""
            CREATE OR REPLACE FUNCTION check_dispense_patient_rx_match_func()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.movement_type = 'DISPENSE' AND NEW.medication_statement_id IS NOT NULL THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM medications_medicationstatement
                        WHERE id = NEW.medication_statement_id AND patient_id = NEW.patient_id
                    ) THEN
                        RAISE EXCEPTION 'Medication statement does not belong to the dispensed patient';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS check_dispense_patient_rx_match_trg ON operations_stockmovement;
            CREATE TRIGGER check_dispense_patient_rx_match_trg
            BEFORE INSERT OR UPDATE ON operations_stockmovement
            FOR EACH ROW
            EXECUTE FUNCTION check_dispense_patient_rx_match_func();
            """)
        elif vendor == 'mysql':
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS check_dispense_patient_rx_match_insert
            BEFORE INSERT ON operations_stockmovement
            FOR EACH ROW
            BEGIN
                IF NEW.movement_type = 'DISPENSE' AND NEW.medication_statement_id IS NOT NULL THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM medications_medicationstatement
                        WHERE id = NEW.medication_statement_id AND patient_id = NEW.patient_id
                    ) THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Medication statement does not belong to the dispensed patient';
                    END IF;
                END IF;
            END;
            """)
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS check_dispense_patient_rx_match_update
            BEFORE UPDATE ON operations_stockmovement
            FOR EACH ROW
            BEGIN
                IF NEW.movement_type = 'DISPENSE' AND NEW.medication_statement_id IS NOT NULL THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM medications_medicationstatement
                        WHERE id = NEW.medication_statement_id AND patient_id = NEW.patient_id
                    ) THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Medication statement does not belong to the dispensed patient';
                    END IF;
                END IF;
            END;
            """)


def drop_triggers(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    with connection.cursor() as cursor:
        if vendor == 'sqlite':
            cursor.execute(SQLITE_DROP_TRIGGERS)
        elif vendor == 'postgresql':
            cursor.execute("DROP TRIGGER IF EXISTS check_dispense_patient_rx_match_trg ON operations_stockmovement;")
            cursor.execute("DROP FUNCTION IF EXISTS check_dispense_patient_rx_match_func();")
        elif vendor == 'mysql':
            cursor.execute("DROP TRIGGER IF EXISTS check_dispense_patient_rx_match_insert;")
            cursor.execute("DROP TRIGGER IF EXISTS check_dispense_patient_rx_match_update;")


class Migration(migrations.Migration):
    dependencies = [
        ('operations', '0012_alter_appointmentdeletionrequest_status_and_more'),
        ('medications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_triggers, reverse_code=drop_triggers),
    ]
