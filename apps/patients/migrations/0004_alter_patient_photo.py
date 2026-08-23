import apps.patients.storage
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('patients', '0003_patient_photo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='photo',
            field=models.ImageField(
                blank=True,
                help_text='Patient identification photograph',
                null=True,
                storage=apps.patients.storage.private_patient_photo_storage,
                upload_to='%Y/%m/',
            ),
        ),
    ]
