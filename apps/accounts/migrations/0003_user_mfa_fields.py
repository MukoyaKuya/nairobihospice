from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_staffprofile_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='mfa_enrolled_at',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='mfa_recovery_codes',
            field=models.JSONField(blank=True, default=list, editable=False),
        ),
        migrations.AddField(
            model_name='user',
            name='mfa_secret',
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
    ]
