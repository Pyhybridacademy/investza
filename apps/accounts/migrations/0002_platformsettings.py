from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform_name', models.CharField(default='InvestZA', max_length=100)),
                ('tagline', models.CharField(blank=True, default='Invest with Confidence', max_length=200)),
                ('support_email', models.EmailField(default='support@investza.co.za', max_length=254)),
                ('support_phone', models.CharField(default='+27 (0) 10 000 0000', max_length=30)),
                ('support_whatsapp', models.CharField(blank=True, help_text='WhatsApp number (international format)', max_length=30)),
                ('website_url', models.URLField(blank=True, default='https://investza.co.za')),
                ('fsp_number', models.CharField(blank=True, help_text='FSP licence number', max_length=30)),
                ('registered_address', models.TextField(blank=True)),
                ('currency_code', models.CharField(default='ZAR', max_length=5)),
                ('currency_symbol', models.CharField(default='R', max_length=5)),
                ('min_deposit', models.DecimalField(decimal_places=2, default=500.0, max_digits=12)),
                ('max_deposit', models.DecimalField(decimal_places=2, default=5000000.0, max_digits=12)),
                ('min_withdrawal', models.DecimalField(decimal_places=2, default=200.0, max_digits=12)),
                ('max_withdrawal', models.DecimalField(decimal_places=2, default=1000000.0, max_digits=12)),
                ('withdrawal_fee_pct', models.DecimalField(decimal_places=2, default=0.0, help_text='Withdrawal fee as a percentage (e.g. 1.5 = 1.5%)', max_digits=5)),
                ('maintenance_mode', models.BooleanField(default=False, help_text='Put platform in maintenance mode — blocks all user logins')),
                ('maintenance_message', models.TextField(blank=True, default='We are performing scheduled maintenance. We will be back shortly.')),
                ('twitter_url', models.URLField(blank=True)),
                ('linkedin_url', models.URLField(blank=True)),
                ('facebook_url', models.URLField(blank=True)),
                ('instagram_url', models.URLField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Platform Settings',
                'verbose_name_plural': 'Platform Settings',
            },
        ),
    ]
