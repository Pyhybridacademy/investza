from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_platformsettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('endpoint', models.TextField(unique=True)),
                ('p256dh', models.TextField()),
                ('auth', models.TextField()),
                ('user_agent', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='push_subscriptions',
                    to='accounts.user',
                )),
            ],
            options={'ordering': ['-created_at'], 'verbose_name': 'Push Subscription', 'verbose_name_plural': 'Push Subscriptions'},
        ),
        migrations.CreateModel(
            name='ProvisionalNotification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=100)),
                ('body', models.TextField(max_length=500)),
                ('url', models.CharField(blank=True, default='/', max_length=255)),
                ('icon', models.CharField(blank=True, default='/static/icons/icon-192.svg', max_length=255)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('SENT', 'Sent'), ('FAILED', 'Failed')], default='DRAFT', max_length=10)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('total_sent', models.PositiveIntegerField(default=0)),
                ('total_failed', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_notifications',
                    to='accounts.user',
                )),
            ],
            options={'ordering': ['-created_at'], 'verbose_name': 'Provisional Notification', 'verbose_name_plural': 'Provisional Notifications'},
        ),
    ]
