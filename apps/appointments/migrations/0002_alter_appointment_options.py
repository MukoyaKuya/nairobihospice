from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('appointments', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='appointment',
            options={
                'ordering': ['-scheduled_date', '-scheduled_time'],
                'verbose_name': 'Appointment',
                'verbose_name_plural': 'Appointments',
            },
        ),
    ]
