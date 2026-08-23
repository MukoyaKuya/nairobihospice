from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('operations', '0005_integrity_constraints'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='procurementorder',
            constraint=models.CheckConstraint(
                condition=models.Q(total_amount_kes__gte=0),
                name='po_total_amount_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='invoice',
            constraint=models.CheckConstraint(
                condition=models.Q(amount_paid_kes__lte=models.F('total_amount_kes')),
                name='invoice_paid_not_over_total',
            ),
        ),
    ]
