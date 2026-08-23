import apps.documents.storage
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patientdocument',
            name='file',
            field=models.FileField(
                storage=apps.documents.storage.private_document_storage,
                upload_to='%Y/%m/',
            ),
        ),
    ]
