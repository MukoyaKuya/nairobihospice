from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [('notifications', '0002_alter_notification_notification_type')]

    operations = [
        migrations.CreateModel(
            name='WebhookDelivery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_name', models.CharField(max_length=100)),
                ('url', models.URLField(max_length=2048)),
                ('payload', models.JSONField()),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='webhookdelivery',
            index=models.Index(fields=['delivered_at', 'created_at'], name='webhook_delivered_created_idx'),
        ),
    ]
