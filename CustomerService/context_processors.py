from csdata.models import AdminSetting

def global_settings(request):
    """Context processor to make global admin settings available in all templates."""
    context = {
        'global_email_active': True,
        'global_customer_email_active': True,
        'global_provider_email_active': True,
        'global_admin_email_active': True,
    }
    try:
        # Master Switch
        setting, _ = AdminSetting.objects.get_or_create(
            key='global_email_active',
            defaults={'value': True, 'description': 'Master switch for email notification service'}
        )
        context['global_email_active'] = setting.value

        # Customer Emails
        setting_cust, _ = AdminSetting.objects.get_or_create(
            key='global_customer_email_active',
            defaults={'value': True, 'description': 'Enable/Disable customer emails globally'}
        )
        context['global_customer_email_active'] = setting_cust.value

        # Provider Emails
        setting_prov, _ = AdminSetting.objects.get_or_create(
            key='global_provider_email_active',
            defaults={'value': True, 'description': 'Enable/Disable provider emails globally'}
        )
        context['global_provider_email_active'] = setting_prov.value

        # Admin Emails
        setting_adm, _ = AdminSetting.objects.get_or_create(
            key='global_admin_email_active',
            defaults={'value': True, 'description': 'Enable/Disable admin emails globally'}
        )
        context['global_admin_email_active'] = setting_adm.value

        # Pending refunds badge count
        from csdata.models import Bookings
        context['pending_refunds_count'] = Bookings.objects.filter(
            refund_status__in=['Requested', 'Under Investigation', 'Provider Disputed']
        ).count()

    except Exception:
        pass
    return context
