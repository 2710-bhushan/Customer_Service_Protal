import math
import random
import string
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Case, When, BooleanField, Value, Q
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from csdata.models import (
    Cdetail, OTPVerification, ProviderRegistration,
    Ticket, Employee, Bookings, Offer, Advertisement, WalletTransaction
)

# Fallback password verifier supporting plaintext and pbkdf2/bcrypt hashing
def verify_password(input_password, stored_password):
    if stored_password.startswith('pbkdf2_') or stored_password.startswith('bcrypt'):
        return check_password(input_password, stored_password)
    return input_password == stored_password


# ─────────────────────────────────────────────
# DATA MASKING HELPERS
# ─────────────────────────────────────────────

def mask_bank_account(account_num):
    if not account_num:
        return 'Not Provided'
    if len(account_num) <= 4:
        return 'XXXX'
    return 'XXXX XXXX XXXX ' + account_num[-4:]


def mask_upi_id(upi_id):
    if not upi_id:
        return 'Not Provided'
    if '@' not in upi_id:
        return '******'
    try:
        username, domain = upi_id.split('@', 1)
        masked = username[:4] + '****' if len(username) > 4 else '****'
        return f'{masked}@{domain}'
    except Exception:
        return '******'


# ─────────────────────────────────────────────
# EMAIL TEMPLATES AND UTILITIES
# ─────────────────────────────────────────────

def send_graphical_email(subject, html_body, recipient, is_operational=True):
    """Send HTML email via Gmail SMTP with console fallback, respecting preferences."""
    # Check global admin preferences
    try:
        from csdata.models import AdminSetting
        
        # 1. Master Switch check
        master_setting, _ = AdminSetting.objects.get_or_create(key='global_email_active', defaults={'value': True, 'description': 'Master switch for email notification service'})
        if not master_setting.value:
            print(f"[GLOBAL EMAIL SERVICE INACTIVE] Email blocked to {recipient}: {subject}")
            return

        # 2. Categorized global switches
        is_admin_recipient = recipient in ['bhushan.272006@gmail.com', 'bh.ja.ingale@gmail.com']
        
        if is_admin_recipient:
            cat_setting, _ = AdminSetting.objects.get_or_create(key='global_admin_email_active', defaults={'value': True, 'description': 'Enable/Disable admin emails globally'})
            if not cat_setting.value:
                print(f"[GLOBAL ADMIN EMAIL SERVICE INACTIVE] Admin email blocked: {subject}")
                return
        else:
            # Check if provider
            from csdata.models import Employee, ProviderRegistration, Cdetail
            is_provider = Employee.objects.filter(email__iexact=recipient).exists() or ProviderRegistration.objects.filter(email__iexact=recipient).exists()
            
            if is_provider:
                cat_setting, _ = AdminSetting.objects.get_or_create(key='global_provider_email_active', defaults={'value': True, 'description': 'Enable/Disable provider emails globally'})
                if not cat_setting.value:
                    print(f"[GLOBAL PROVIDER EMAIL SERVICE INACTIVE] Provider email blocked to {recipient}: {subject}")
                    return
            else:
                # Check if customer
                is_customer = Cdetail.objects.filter(mail__iexact=recipient).exists()
                if is_customer:
                    cat_setting, _ = AdminSetting.objects.get_or_create(key='global_customer_email_active', defaults={'value': True, 'description': 'Enable/Disable customer emails globally'})
                    if not cat_setting.value:
                        print(f"[GLOBAL CUSTOMER EMAIL SERVICE INACTIVE] Customer email blocked to {recipient}: {subject}")
                        return
    except Exception as e:
        print(f"[GLOBAL EMAIL SERVICE CHECK ERROR]: {e}")

    if is_operational:
        # Check customer preferences
        try:
            cust = Cdetail.objects.filter(mail__iexact=recipient).first()
            if cust and not cust.allow_email_notifications:
                print(f"[EMAIL NOTIFICATION MUTED] Operational email to customer {recipient} blocked: {subject}")
                return
        except Exception as e:
            print(f"[PREFERENCE CHECK ERROR] Customer: {e}")

        # Check employee preferences
        try:
            emp = Employee.objects.filter(email__iexact=recipient).first()
            if emp and not emp.allow_email_notifications:
                print(f"[EMAIL NOTIFICATION MUTED] Operational email to provider {recipient} blocked: {subject}")
                return
        except Exception as e:
            print(f"[PREFERENCE CHECK ERROR] Provider: {e}")

        # Check pending provider registration preferences
        try:
            reg = ProviderRegistration.objects.filter(email__iexact=recipient).first()
            if reg and not reg.allow_email_notifications:
                print(f"[EMAIL NOTIFICATION MUTED] Operational email to pending provider {recipient} blocked: {subject}")
                return
        except Exception as e:
            print(f"[PREFERENCE CHECK ERROR] Provider Registration: {e}")

    try:
        send_mail(
            subject=subject,
            message='Please enable HTML to view this email.',
            from_email='ServiceHub <bhushan.272006@gmail.com>',
            recipient_list=[recipient],
            html_message=html_body,
            fail_silently=False,
        )
        print(f"[EMAIL] Sent to {recipient}: {subject}")
    except Exception as e:
        print(f"\n=== EMAIL FALLBACK (SMTP ERROR: {e}) ===")
        print(f"To: {recipient}\nSubject: {subject}")
        print(html_body[:800])
        print("=" * 60)



def get_base_email_template(title, header_bg, content_html):
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:20px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);border:1px solid #e2e8f0;">
      <div style="background:{header_bg};padding:35px 40px;text-align:center;">
        <div style="margin-bottom:10px;"><strong style="font-size:32px;color:#ffffff;letter-spacing:1.5px;text-shadow:0 1px 3px rgba(0,0,0,0.15);">⚡ ServiceHub</strong></div>
        <h1 style="color:#ffffff;margin:0;font-size:24px;font-weight:700;text-shadow:0 1px 2px rgba(0,0,0,0.1);">{title}</h1>
      </div>
      <div style="padding:40px;color:#334155;background:#ffffff;line-height:1.6;font-size:15px;">
        {content_html}
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:30px 0;">
        <p style="color:#64748b;font-size:12px;text-align:center;line-height:1.5;margin:0;">
          Need help? Contact support at <a href="mailto:support@servicehub.com" style="color:#4f46e5;text-decoration:none;font-weight:600;">support@servicehub.com</a> or raise a ticket on your dashboard.
        </p>
      </div>
      <div style="background:#f8fafc;padding:20px;text-align:center;border-top:1px solid #f1f5f9;">
        <p style="color:#94a3b8;font-size:12px;margin:0;">© 2026 ServiceHub Marketplace. All rights reserved.</p>
      </div>
    </div>
    """


def get_otp_email_html(otp, email):
    content = f"""
    <h2 style="color:#4f46e5;margin:0 0 16px;font-size:20px;font-weight:700;">Your One-Time Password</h2>
    <p style="color:#475569;margin:0 0 24px;line-height:1.6;">Enter this code to verify your identity and access your account:</p>
    <div style="background:#f5f3ff;border:2px solid #6c63ff;border-radius:12px;padding:24px;text-align:center;margin:0 0 24px;">
      <span style="font-size:48px;font-weight:800;letter-spacing:12px;color:#4f46e5;">{otp}</span>
    </div>
    <p style="color:#64748b;font-size:13px;line-height:1.4;">This OTP is valid for 10 minutes. Please do not share it with anyone for security reasons.</p>
    """
    return get_base_email_template("Email Verification", "linear-gradient(135deg,#6c63ff,#3b82f6)", content)


def get_provider_approval_html(provider_name, email, password):
    content = f"""
    <p>Hello <strong style="color:#059669;">{provider_name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">Congratulations! Your application to join ServiceHub as a partner has been <strong>approved</strong>. Your profile is now live.</p>
    <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;padding:24px;margin:24px 0;">
      <h3 style="color:#059669;margin:0 0 16px;font-size:16px;">Your Login Credentials</h3>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="color:#4b5563;padding:6px 0;">Email:</td><td style="color:#1f2937;font-weight:600;">{email}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Password:</td><td style="color:#1f2937;font-weight:600;font-family:monospace;">{password}</td></tr>
      </table>
    </div>
    <p style="color:#475569;line-height:1.6;">Please change your password immediately upon first login.</p>
    """
    return get_base_email_template("🎉 Application Approved!", "linear-gradient(135deg,#10b981,#059669)", content)


def get_booking_confirmation_html(booking, employee, customer):
    tracking_url = f"http://127.0.0.1:8000/track/{booking.unique}/"
    content = f"""
    <p>Hello <strong>{customer.name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">Your service booking has been created and is currently awaiting acceptance from the provider.</p>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:24px 0;">
      <h3 style="color:#4f46e5;margin:0 0 16px;font-size:16px;">Booking Summary</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="color:#4b5563;padding:6px 0;">Booking ID:</td><td style="color:#1f2937;font-weight:bold;">#{booking.unique}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Service Category:</td><td style="color:#1f2937;">{employee.service_provided}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Service Provider:</td><td style="color:#1f2937;">{employee.name}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Date & Time:</td><td style="color:#1f2937;">{booking.service_date} at {booking.service_time}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Amount:</td><td style="color:#059669;font-weight:700;">₹{booking.price - booking.discount_applied:.2f}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Payment Method:</td><td style="color:#1f2937;">{booking.payment_method}</td></tr>
      </table>
    </div>
    <div style="text-align:center;margin:30px 0;">
      <a href="{tracking_url}" style="background:linear-gradient(135deg,#6c63ff,#3b82f6);color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:bold;display:inline-block;box-shadow:0 4px 12px rgba(108,99,255,0.2);">Track Booking Status</a>
    </div>
    """
    return get_base_email_template("Booking Confirmation", "linear-gradient(135deg,#6c63ff,#3b82f6)", content)


def get_payment_success_html(booking, customer, tx_id):
    content = f"""
    <p>Hello <strong>{customer.name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">We have successfully received your payment for Booking <strong>#{booking.unique}</strong>.</p>
    <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;padding:24px;margin:24px 0;">
      <h3 style="color:#059669;margin:0 0 16px;font-size:16px;">Payment Receipt</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="color:#4b5563;padding:6px 0;">Transaction ID:</td><td style="color:#1f2937;font-family:monospace;">{tx_id}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Amount Paid:</td><td style="color:#059669;font-weight:700;">₹{booking.price - booking.discount_applied:.2f}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Status:</td><td style="color:#059669;font-weight:bold;">Success / Completed</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Payment Method:</td><td style="color:#1f2937;">{booking.payment_method}</td></tr>
      </table>
    </div>
    """
    return get_base_email_template("💳 Payment Successful!", "linear-gradient(135deg,#10b981,#059669)", content)


def get_booking_accepted_html(booking, employee, customer):
    tracking_url = f"http://127.0.0.1:8000/track/{booking.unique}/"
    content = f"""
    <p>Hello <strong>{customer.name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;"><strong style="color:#059669;">{employee.name}</strong> has accepted your booking request and is preparing for service.</p>
    <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;padding:20px;margin:24px 0;">
      <p style="margin:0;color:#0f5132;font-size:14px;">Status: <strong>Provider Heading to Location</strong></p>
    </div>
    <div style="text-align:center;margin:30px 0;">
      <a href="{tracking_url}" style="background:linear-gradient(135deg,#10b981,#059669);color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:bold;display:inline-block;box-shadow:0 4px 12px rgba(16,185,129,0.2);">Track Live Location</a>
    </div>
    """
    return get_base_email_template("🚀 Booking Accepted!", "linear-gradient(135deg,#10b981,#059669)", content)


def get_booking_rejected_html(booking, employee, customer):
    content = f"""
    <p>Hello <strong>{customer.name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">Unfortunately, <strong>{employee.name}</strong> has declined your booking request #<strong>{booking.unique}</strong> due to scheduling conflict or unavailability.</p>
    <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;padding:20px;margin:24px 0;color:#991b1b;font-size:14px;">
      Your refund will be automatically processed back to your original source of payment within 3-5 business days if paid online.
    </div>
    """
    return get_base_email_template("❌ Booking Declined", "linear-gradient(135deg,#ef4444,#dc2626)", content)


def get_complaint_submission_html(ticket, customer_name):
    content = f"""
    <p>Hello <strong>{customer_name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">We have received your support ticket successfully. Our team will review the issue details and contact you within 24 hours.</p>
    <div style="background:#fffbeb;border:1px solid #fef08a;border-radius:12px;padding:20px;margin:20px 0;">
      <p style="color:#b45309;margin:0 0 8px;font-weight:600;">Complaint Ticket details:</p>
      <p style="color:#451a03;margin:0;font-size:14px;line-height:1.5;">{ticket.ticketdetail}</p>
    </div>
    """
    return get_base_email_template("🎫 Support Ticket Created", "linear-gradient(135deg,#f59e0b,#d97706)", content)


def get_complaint_resolution_html(ticket, customer_name):
    content = f"""
    <p>Hello <strong>{customer_name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">Your complaint ticket <strong>#{ticket.unique}</strong> has been resolved by our support administrators.</p>
    <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;padding:20px;margin:20px 0;">
      <p style="color:#059669;margin:0 0 8px;font-weight:600;">Admin Response Details:</p>
      <p style="color:#064e3b;margin:0;font-size:14px;line-height:1.5;">{ticket.admin_response}</p>
    </div>
    """
    return get_base_email_template("✅ Ticket Resolved", "linear-gradient(135deg,#10b981,#059669)", content)


def get_bank_verification_update_html(employee, status, reason=""):
    status_text = "Approved" if status == 'Approved' else "Correction Requested" if status == 'Correction Requested' else "Rejected"
    banner_bg = "linear-gradient(135deg,#10b981,#059669)" if status == 'Approved' else "linear-gradient(135deg,#f59e0b,#d97706)" if status == 'Correction Requested' else "linear-gradient(135deg,#ef4444,#dc2626)"
    
    reason_section = ""
    if reason:
      reason_section = f"""
      <div style="background:#fffbeb;border:1px solid #fef08a;border-radius:12px;padding:20px;margin:20px 0;">
        <p style="color:#b45309;margin:0 0 8px;font-weight:600;">Note / Reason:</p>
        <p style="color:#451a03;margin:0;font-size:14px;">{reason}</p>
      </div>
      """
      
    content = f"""
    <p>Hello <strong>{employee.name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">Your payout bank account details verification status has been updated to: <strong>{status_text}</strong>.</p>
    {reason_section}
    <p style="color:#475569;line-height:1.6;">Please check your provider dashboard for details and lock status.</p>
    """
    return get_base_email_template("🏦 Bank Verification Status Update", banner_bg, content)


def get_withdrawal_update_html(employee, tx, status):
    status_text = "Approved" if status == 'Completed' else "Rejected"
    banner_bg = "linear-gradient(135deg,#10b981,#059669)" if status == 'Completed' else "linear-gradient(135deg,#ef4444,#dc2626)"
    
    content = f"""
    <p>Hello <strong>{employee.name}</strong>,</p>
    <p style="color:#475569;line-height:1.6;">Your payout withdrawal request for <strong>₹{tx.amount:.2f}</strong> has been <strong>{status_text.lower()}</strong> by the admin.</p>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:24px 0;">
      <h3 style="color:#4f46e5;margin:0 0 16px;font-size:16px;">Withdrawal Details</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="color:#4b5563;padding:6px 0;">Amount:</td><td style="color:#059669;font-weight:700;">₹{tx.amount:.2f}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Transaction ID:</td><td style="color:#1f2937;font-family:monospace;">{tx.dummy_txn_id or 'N/A'}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Target Bank:</td><td style="color:#1f2937;">{employee.bank_name}</td></tr>
        <tr><td style="color:#4b5563;padding:6px 0;">Account number:</td><td style="color:#1f2937;font-family:monospace;">{mask_bank_account(employee.bank_account_num)}</td></tr>
      </table>
    </div>
    """
    return get_base_email_template("💰 Withdrawal Request Update", banner_bg, content)



# ─────────────────────────────────────────────
# AUTHENTICATION - OTP SYSTEM
# ─────────────────────────────────────────────

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def logout_view(request):
    request.session.flush()
    response = redirect('/signin/')
    for cookie in ['user_name', 'user_email', 'user_image', 'user_type', 'user_phone']:
        response.delete_cookie(cookie)
    return response


def signup(request):
    if request.method == 'POST':
        mail = request.POST.get('mail', '').strip().lower()
        passw = request.POST.get('passw', '')
        rpass = request.POST.get('rpass', '')
        account_type = request.POST.get('account_type', 'customer')

        if not mail or not passw:
            return render(request, 'home/signup.html', {'error': 'All fields are required.'})
        if passw != rpass:
            return render(request, 'home/signup.html', {'error': 'Passwords do not match.'})
        if len(passw) < 6:
            return render(request, 'home/signup.html', {'error': 'Password must be at least 6 characters.'})

        if Cdetail.objects.filter(mail=mail).exists():
            return render(request, 'home/signup.html', {'error': 'Email already registered. Please sign in.'})
        if account_type == 'provider' and ProviderRegistration.objects.filter(email=mail).exists():
            return render(request, 'home/signup.html', {'error': 'Email already submitted for provider registration.'})

        otp = generate_otp()
        OTPVerification.objects.filter(email=mail, purpose='registration', is_used=False).update(is_used=True)
        OTPVerification.objects.create(email=mail, otp=otp, purpose='registration')

        request.session['reg_mail'] = mail
        request.session['reg_passw'] = passw
        request.session['reg_account_type'] = account_type

        send_graphical_email(
            'Your ServiceHub Verification OTP',
            get_otp_email_html(otp, mail),
            mail,
            is_operational=False
        )
        return redirect('/verify-otp/')
    return render(request, 'home/signup.html')


def verify_otp(request):
    mail = request.session.get('reg_mail')
    if not mail:
        return redirect('/signup/')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        account_type = request.session.get('reg_account_type', 'customer')

        try:
            otp_obj = OTPVerification.objects.filter(
                email=mail,
                purpose='registration',
                is_used=False
            ).latest('created_at')

            if (timezone.now() - otp_obj.created_at).seconds > 600:
                return render(request, 'home/verify_otp.html', {
                    'email': mail, 'error': 'OTP expired. Please register again.'
                })

            if otp_obj.otp != entered_otp:
                return render(request, 'home/verify_otp.html', {
                    'email': mail, 'error': 'Invalid OTP. Please try again.'
                })

            otp_obj.is_used = True
            otp_obj.save()

            if account_type == 'provider':
                return redirect('/register-provider/')
            else:
                passw = request.session.get('reg_passw', '')
                Cdetail.objects.create(
                    mail=mail,
                    passw=passw,
                    is_verified=True,
                )
                request.session['user_email'] = mail
                request.session['user_type'] = 'user'
                for k in ['reg_mail', 'reg_passw', 'reg_account_type']:
                    request.session.pop(k, None)
                return redirect('/bookservice/')

        except OTPVerification.DoesNotExist:
            return render(request, 'home/verify_otp.html', {
                'email': mail, 'error': 'No OTP found. Please register again.'
            })

    return render(request, 'home/verify_otp.html', {'email': mail})


def resend_otp(request):
    mail = request.session.get('reg_mail')
    if not mail:
        return redirect('/signup/')
    otp = generate_otp()
    OTPVerification.objects.filter(email=mail, purpose='registration', is_used=False).update(is_used=True)
    OTPVerification.objects.create(email=mail, otp=otp, purpose='registration')
    send_graphical_email(
        'Your ServiceHub Verification OTP (Resent)',
        get_otp_email_html(otp, mail),
        mail,
        is_operational=False
    )
    return redirect('/verify-otp/?resent=true')


def register_provider(request):
    mail = request.session.get('reg_mail')
    passw = request.session.get('reg_passw', '')
    if not mail or request.session.get('reg_account_type') != 'provider':
        return redirect('/signup/')

    SERVICE_CATEGORIES = [
        'Electrician', 'Plumber', 'Carpenter', 'AC Repair',
        'Cleaning', 'Painter', 'Technician', 'Others'
    ]

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        service_category = request.POST.get('service_category', '')
        has_business = request.POST.get('has_business_registration') == 'yes'
        terms = request.POST.get('terms_accepted') == 'on'
        allow_email = request.POST.get('allow_email_notifications') == 'yes'

        address_line1 = request.POST.get('address_line1', '')
        address_line2 = request.POST.get('address_line2', '')
        area = request.POST.get('area', '')
        city = request.POST.get('city', '')
        district = request.POST.get('district', '')
        state = request.POST.get('state', '')
        pincode = request.POST.get('pincode', '')
        gps_lat = float(request.POST.get('gps_lat', 0) or 0)
        gps_lng = float(request.POST.get('gps_lng', 0) or 0)
        gps_address = request.POST.get('gps_address', '')

        profile_photo = request.FILES.get('profile_photo')
        aadhaar_card = request.FILES.get('aadhaar_card')
        pan_card = request.FILES.get('pan_card')
        business_cert = request.FILES.get('business_registration_cert') if has_business else None

        if not full_name or not phone or not service_category:
            return render(request, 'home/register_provider.html', {
                'email': mail, 'categories': SERVICE_CATEGORIES,
                'error': 'Please fill all required fields.'
            })

        reg = ProviderRegistration.objects.create(
            full_name=full_name,
            email=mail,
            phone=phone,
            service_category=service_category,
            profile_photo=profile_photo,
            aadhaar_card=aadhaar_card,
            pan_card=pan_card,
            has_business_registration=has_business,
            business_registration_cert=business_cert,
            address_line1=address_line1,
            address_line2=address_line2,
            area=area,
            city=city,
            district=district,
            state=state,
            pincode=pincode,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            gps_address=gps_address,
            terms_accepted=terms,
            allow_email_notifications=allow_email,
            status='pending',
        )

        # Notify Admin about new registration
        admin_subject = "New Service Provider Registered"
        admin_html = get_base_email_template(
            "👷 New Provider Registration",
            "linear-gradient(135deg,#6c63ff,#3b82f6)",
            f"""
            <p style="color:#334155;line-height:1.6;">A new service provider has registered on the platform:</p>
            <p style="color:#334155;line-height:1.6;"><strong>Name:</strong> {full_name}</p>
            <p style="color:#334155;line-height:1.6;"><strong>Email:</strong> {mail}</p>
            <p style="color:#334155;line-height:1.6;"><strong>Category:</strong> {service_category}</p>
            <p style="color:#334155;line-height:1.6;">Please review and verify their details in the admin portal.</p>
            """
        )
        send_graphical_email(admin_subject, admin_html, 'bhushan.272006@gmail.com')

        for k in ['reg_mail', 'reg_passw', 'reg_account_type']:
            request.session.pop(k, None)

        return render(request, 'home/provider_submitted.html', {'name': full_name})

    return render(request, 'home/register_provider.html', {
        'email': mail, 'categories': SERVICE_CATEGORIES
    })


def send_login_otp(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            email = data.get('mail', '').strip().lower()
        except Exception:
            email = request.POST.get('mail', '').strip().lower()

        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required.'})

        if not Cdetail.objects.filter(mail=email).exists():
            return JsonResponse({'success': False, 'message': 'Email not registered as customer.'})

        otp = generate_otp()
        OTPVerification.objects.filter(email=email, purpose='login', is_used=False).update(is_used=True)
        OTPVerification.objects.create(email=email, otp=otp, purpose='login')

        send_graphical_email(
            'Your ServiceHub Login OTP',
            get_otp_email_html(otp, email),
            email,
            is_operational=False
        )
        return JsonResponse({'success': True, 'message': 'OTP sent successfully.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


def signin(request):
    if request.method == 'POST':
        mail = request.POST.get('mail', '').strip().lower()
        login_type = request.POST.get('login_type', 'customer')
        is_otp_login = request.POST.get('is_otp_login') == 'true'

        if not mail:
            return render(request, 'home/signin.html', {'error': 'Please enter email address.', 'tab': login_type})

        # ── ADMIN LOGIN ──
        if login_type == 'admin':
            password = request.POST.get('pass', '')
            if mail == 'admin@gmail.com' and password == 'admin123':
                request.session['user_email'] = mail
                request.session['user_type'] = 'admin'
                request.session['user_name'] = 'System Admin'
                return redirect('/aadmin/')
            return render(request, 'home/signin.html', {
                'error': 'Invalid admin credentials.', 'tab': 'admin'
            })

        # ── PROVIDER LOGIN ──
        if login_type == 'provider':
            password = request.POST.get('pass', '')
            try:
                employee = Employee.objects.get(email=mail, is_active=True)
                if verify_password(password, employee.passw):
                    request.session['user_email'] = employee.email
                    request.session['user_type'] = 'employee'
                    request.session['user_name'] = employee.name
                    request.session['user_phone'] = employee.phone
                    request.session['user_image'] = employee.profile_image or ''
                    return redirect('/employeeservicebooked/')
                else:
                    raise Employee.DoesNotExist
            except Employee.DoesNotExist:
                return render(request, 'home/signin.html', {
                    'error': 'Invalid provider credentials.', 'tab': 'provider'
                })

        # ── CUSTOMER LOGIN ──
        if login_type == 'customer':
            if is_otp_login:
                entered_otp = request.POST.get('otp_code', '').strip()
                if not entered_otp:
                    return render(request, 'home/signin.html', {
                        'error': 'Please enter the OTP.', 'tab': 'customer', 'is_otp': True, 'email_val': mail
                    })
                try:
                    otp_obj = OTPVerification.objects.filter(
                        email=mail,
                        purpose='login',
                        is_used=False
                    ).latest('created_at')

                    if (timezone.now() - otp_obj.created_at).seconds > 600:
                        return render(request, 'home/signin.html', {
                            'error': 'OTP expired. Please try again.', 'tab': 'customer'
                        })

                    if otp_obj.otp != entered_otp:
                        return render(request, 'home/signin.html', {
                            'error': 'Invalid OTP.', 'tab': 'customer', 'is_otp': True, 'email_val': mail
                        })

                    otp_obj.is_used = True
                    otp_obj.save()

                    user = Cdetail.objects.get(mail=mail)
                    if user.is_suspended:
                        return render(request, 'home/signin.html', {
                            'error': 'Your account has been suspended. Contact support.', 'tab': 'customer'
                        })

                    request.session['user_email'] = user.mail
                    request.session['user_type'] = 'user'
                    request.session['user_name'] = user.name or mail.split('@')[0]
                    request.session['user_phone'] = user.phone or ''
                    request.session['user_image'] = user.profile_image or ''
                    return redirect('/bookservice/')

                except (OTPVerification.DoesNotExist, Cdetail.DoesNotExist):
                    return render(request, 'home/signin.html', {
                        'error': 'Account or verification session not found.', 'tab': 'customer'
                    })
            else:
                password = request.POST.get('pass', '')
                if not password:
                    return render(request, 'home/signin.html', {
                        'error': 'Please enter your password.', 'tab': 'customer'
                    })
                try:
                    user = Cdetail.objects.get(mail=mail)
                    if verify_password(password, user.passw):
                        if user.is_suspended:
                            return render(request, 'home/signin.html', {
                                'error': 'Your account has been suspended. Contact support.', 'tab': 'customer'
                            })
                        request.session['user_email'] = user.mail
                        request.session['user_type'] = 'user'
                        request.session['user_name'] = user.name or mail.split('@')[0]
                        request.session['user_phone'] = user.phone or ''
                        request.session['user_image'] = user.profile_image or ''
                        return redirect('/bookservice/')
                    else:
                        raise Cdetail.DoesNotExist
                except Cdetail.DoesNotExist:
                    return render(request, 'home/signin.html', {
                        'error': 'Invalid email or password.', 'tab': 'customer'
                    })

    return render(request, 'home/signin.html')



# ─────────────────────────────────────────────
# PUBLIC PAGES
# ─────────────────────────────────────────────

def home(request):
    search_query = request.GET.get('q', '')
    category = request.GET.get('category', '')

    employees = Employee.objects.filter(is_active=True)

    if search_query:
        employees = employees.filter(
            Q(name__icontains=search_query) |
            Q(service_provided__icontains=search_query) |
            Q(specialization__icontains=search_query) |
            Q(service_area__icontains=search_query)
        )
    if category:
        employees = employees.filter(service_provided__icontains=category)

    ads = Advertisement.objects.filter(is_active=True)
    categories = [
        {'name': 'Electrician', 'icon': '⚡'},
        {'name': 'Plumber', 'icon': '🔧'},
        {'name': 'Carpenter', 'icon': '🪚'},
        {'name': 'Painter', 'icon': '🖌️'},
        {'name': 'Cleaning', 'icon': '🧹'},
        {'name': 'AC Repair', 'icon': '❄️'},
        {'name': 'Appliance Repair', 'icon': '🔌'},
        {'name': 'Others', 'icon': '🛠️'},
    ]

    return render(request, 'home/index.html', {
        'employees': employees,
        'ads': ads,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category,
    })


def about(request):
    return render(request, 'home/about.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if not name or not email or not message:
            return render(request, 'home/contact.html', {'error': 'All fields are required.'})

        # Generate a mock Reference number
        ref_num = 'REF' + ''.join(random.choices(string.digits, k=7))

        # Admin Email
        admin_subject = f"📬 Contact Form Inquiry: {subject}"
        admin_html = get_base_email_template(
            "📬 New Support Message",
            "linear-gradient(135deg,#6c63ff,#3b82f6)",
            f"""
            <p style="color:#334155;line-height:1.6;"><strong>Customer Name:</strong> {name}</p>
            <p style="color:#334155;line-height:1.6;"><strong>Customer Email:</strong> {email}</p>
            <p style="color:#334155;line-height:1.6;"><strong>Customer Phone:</strong> {phone or 'Not provided'}</p>
            <p style="color:#334155;line-height:1.6;"><strong>Subject:</strong> {subject}</p>
            <p style="color:#334155;line-height:1.6;"><strong>Message:</strong></p>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;padding:15px;border-radius:8px;white-space:pre-wrap;color:#334155;">{message}</div>
            """
        )
        send_graphical_email(admin_subject, admin_html, 'bhushan.272006@gmail.com')

        # Customer Confirmation Email
        cust_subject = "We have received your request - ServiceHub Support"
        cust_html = get_base_email_template(
            "✉️ Request Received!",
            "linear-gradient(135deg,#10b981,#059669)",
            f"""
            <p>Hello <strong>{name}</strong>,</p>
            <p style="color:#475569;line-height:1.6;">Thank you for contacting us.</p>
            <p style="color:#475569;line-height:1.6;">We have received your request successfully.</p>
            <p style="color:#475569;line-height:1.6;">Our team will contact you within 24 hours.</p>
            <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:15px;text-align:center;margin:20px 0;">
              <span style="font-size:12px;color:#064e3b;display:block;">Reference Number:</span>
              <span style="font-size:24px;font-weight:bold;color:#059669;letter-spacing:1px;">{ref_num}</span>
            </div>
            <p style="font-size:13px;color:#64748b;">Please keep this reference number handy for future communication.</p>
            """
        )
        send_graphical_email(cust_subject, cust_html, email)

        return render(request, 'home/contact.html', {'success': True, 'ref_num': ref_num})

    return render(request, 'home/contact.html')


def provider_profile_public(request, unique):
    employee = get_object_or_404(Employee, unique=unique, is_active=True)
    return render(request, 'home/provider_profile.html', {'employee': employee})


# ─────────────────────────────────────────────
# CUSTOMER PROFILE
# ─────────────────────────────────────────────

def customer_profile(request):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    user = get_object_or_404(Cdetail, mail=user_email)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_profile':
            user.name = request.POST.get('name', user.name)
            user.phone = request.POST.get('phone', user.phone)
            user.gender = request.POST.get('gender', user.gender)
            profile_photo = request.FILES.get('profile_photo')
            if profile_photo:
                from django.core.files.storage import default_storage
                file_name = default_storage.save('user_profiles/' + profile_photo.name, profile_photo)
                user.profile_image = '/media/' + file_name
            user.save()
            request.session['user_name'] = user.name
            return redirect('/profile/?updated=true')

        elif action == 'add_address':
            label = request.POST.get('label', 'Home')
            addr = {
                'label': label,
                'address_line1': request.POST.get('address_line1', ''),
                'address_line2': request.POST.get('address_line2', ''),
                'area': request.POST.get('area', ''),
                'city': request.POST.get('city', ''),
                'district': request.POST.get('district', ''),
                'state': request.POST.get('state', ''),
                'pincode': request.POST.get('pincode', ''),
                'is_default': len(user.addresses) == 0,
            }
            if not user.addresses:
                user.addresses = []
            user.addresses.append(addr)
            user.save()
            return redirect('/profile/?addr=added')

        elif action == 'delete_address':
            idx = int(request.POST.get('index', -1))
            if 0 <= idx < len(user.addresses):
                user.addresses.pop(idx)
                user.save()
            return redirect('/profile/')

        elif action == 'update_bank':
            user.bank_account_num = request.POST.get('bank_account_num', '')
            user.bank_ifsc = request.POST.get('bank_ifsc', '')
            user.upi_id = request.POST.get('upi_id', '')
            user.save()
            return redirect('/profile/?bank=updated')

    # Wallet transactions generator
    wallet_history = []
    user_bookings = Bookings.objects.filter(uniqueuser=user.unique).order_by('created_at')
    
    # Chronological history tracking
    for b in user_bookings:
        # 1. Credits from successful refunds
        if b.refund_status == 'Processed':
            wallet_history.append({
                'date': b.created_at,
                'booking_id': b.unique,
                'type': 'Credit (Refund Approved)',
                'amount': f"+₹{b.price:.2f}",
                'style': 'color: var(--success); font-weight: 700;',
                'desc': f"Refund approved for booking #{b.unique}"
            })
        # 2. Debits from booking payments using wallet
        if 'Wallet' in (b.payment_method or ''):
            wallet_history.append({
                'date': b.created_at,
                'booking_id': b.unique,
                'type': 'Debit (Service Booking)',
                'amount': f"-₹{b.price - b.discount_applied:.2f}",
                'style': 'color: var(--danger); font-weight: 700;',
                'desc': f"Paid for service booking #{b.unique}"
            })
            
    # Sort history descending (most recent first)
    wallet_history.reverse()

    return render(request, 'user/profile.html', {
        'user': user,
        'masked_bank': mask_bank_account(user.bank_account_num),
        'masked_upi': mask_upi_id(user.upi_id),
        'wallet_history': wallet_history,
    })


# ─────────────────────────────────────────────
# CUSTOMER PANEL & BOOKINGS
# ─────────────────────────────────────────────

def bookservice(request):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')

    if not user_email or user_type != 'user':
        return redirect('/signin/')

    search_query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    user = get_object_or_404(Cdetail, mail=user_email)
    favorite_ids = user.service or []

    employees = Employee.objects.filter(is_active=True)
    if search_query:
        employees = employees.filter(
            Q(name__icontains=search_query) |
            Q(service_provided__icontains=search_query) |
            Q(specialization__icontains=search_query) |
            Q(service_area__icontains=search_query)
        )
    if category:
        employees = employees.filter(service_provided__icontains=category)

    employees = employees.annotate(
        is_favorite=Case(
            When(unique__in=favorite_ids, then=True),
            default=False,
            output_field=BooleanField()
        )
    )

    offers = Offer.objects.filter(is_active=True)
    categories = [
        {'name': 'Electrician', 'icon': '⚡'},
        {'name': 'Plumber', 'icon': '🔧'},
        {'name': 'Carpenter', 'icon': '🪚'},
        {'name': 'Painter', 'icon': '🖌️'},
        {'name': 'Cleaning', 'icon': '🧹'},
        {'name': 'AC Repair', 'icon': '❄️'},
        {'name': 'Appliance Repair', 'icon': '🔌'},
        {'name': 'Others', 'icon': '🛠️'},
    ]

    return render(request, 'user/bookservice.html', {
        'data': employees,
        'offers': offers,
        'search_query': search_query,
        'selected_category': category,
        'categories': categories,
        'user': user,
    })


def usercommon(request, unique):
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('/signin/')

    employee = get_object_or_404(Employee, unique=unique)
    user = get_object_or_404(Cdetail, mail=user_email)

    is_favorite = unique in (user.service or [])
    employee.is_favorite = is_favorite
    return render(request, 'user/usercommon.html', {'usercommon': employee, 'user': user})


def payment_page(request, unique):
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('/signin/')

    service = get_object_or_404(Employee, unique=unique)
    user = get_object_or_404(Cdetail, mail=user_email)

    return render(request, 'user/payment.html', {
        'service': service,
        'user': user,
        'masked_bank': mask_bank_account(user.bank_account_num),
        'masked_upi': mask_upi_id(user.upi_id),
    })


@csrf_exempt
def validate_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip()
        try:
            offer = Offer.objects.get(code__iexact=code, is_active=True)
            return JsonResponse({'success': True, 'discount_percent': offer.discount_percent, 'desc': offer.description})
        except Offer.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid or expired promo code'})
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@require_POST
def process_payment(request):
    try:
        service_id = request.POST.get('service_id')
        payment_method = request.POST.get('payment_method', 'UPI')
        coupon_code = request.POST.get('coupon_code', '')
        user_lat = float(request.POST.get('user_lat', 0) or 0)
        user_lng = float(request.POST.get('user_lng', 0) or 0)
        live_address = request.POST.get('live_address', '')
        selected_address_idx = request.POST.get('selected_address_idx', '')
        service_date = request.POST.get('service_date', '')
        service_time_val = request.POST.get('service_time', '')

        # Dummy simulated fields
        txn_id = request.POST.get('txn_id', '')

        user_email = request.session.get('user_email')
        user_type = request.session.get('user_type')
        if not user_email or user_type != 'user':
            return redirect('/signin/')

        customer = Cdetail.objects.get(mail=user_email)
        service_provider = Employee.objects.get(unique=service_id)

        if user_lat == 0.0 and user_lng == 0.0:
            user_lat = service_provider.live_lat + 0.009 + (random.random() * 0.004)
            user_lng = service_provider.live_lng + 0.009 + (random.random() * 0.004)

        if live_address:
            customer.live_address = live_address
        customer.live_lat = user_lat
        customer.live_lng = user_lng

        # Determine booking address
        booking_addr = live_address
        if selected_address_idx and customer.addresses:
            try:
                addr = customer.addresses[int(selected_address_idx)]
                booking_addr = f"{addr.get('address_line1', '')}, {addr.get('area', '')}, {addr.get('city', '')}, {addr.get('state', '')} - {addr.get('pincode', '')}"
            except (IndexError, ValueError):
                pass
        
        if not booking_addr and customer.addresses:
            for addr in customer.addresses:
                if addr.get('is_default'):
                    booking_addr = f"{addr.get('address_line1', '')}, {addr.get('area', '')}, {addr.get('city', '')}, {addr.get('state', '')} - {addr.get('pincode', '')}"
                    break

        customer.save()

        # Calculate price
        base_price = service_provider.starting_price or 299.00
        discount = 0.0
        if coupon_code:
            try:
                offer = Offer.objects.get(code__iexact=coupon_code, is_active=True)
                discount = base_price * (offer.discount_percent / 100.0)
            except Offer.DoesNotExist:
                pass

        final_total = max(0.0, base_price - discount)

        # Wallet Deduction Logic
        use_wallet = request.POST.get('use_wallet') == 'true'
        wallet_deduction = 0.0
        if use_wallet and customer.wallet_balance > 0:
            wallet_deduction = min(customer.wallet_balance, final_total)
            customer.wallet_balance = max(0.0, customer.wallet_balance - wallet_deduction)
            customer.save()
            
            # Adjust payment method name
            if wallet_deduction >= final_total:
                payment_method = 'Wallet'
            else:
                payment_method = f"Wallet + {payment_method}"

        svc_date = None
        svc_time = None
        if service_date:
            try:
                from datetime import datetime
                svc_date = datetime.strptime(service_date, '%Y-%m-%d').date()
            except Exception:
                pass
        if service_time_val:
            try:
                from datetime import datetime
                svc_time = datetime.strptime(service_time_val, '%H:%M').time()
            except Exception:
                pass

        # Determine booking status based on payment method
        # COD and Pay After Service directly bypass sandbox gateway with Pending Service Provider Acceptance status
        if payment_method in ['Cash On Delivery', 'Pay After Service', 'Cash', 'Cash on Service', 'Pay on Delivery']:
            booking_status = 'Pending Service Provider Acceptance'
        else:
            booking_status = 'Pending Service Provider Acceptance'

        booking = Bookings.objects.create(
            uniqueuser=customer.unique,
            uniqueservice=service_provider.unique,
            advance=True,
            email=customer.mail,
            status=booking_status,
            booking_address=booking_addr,
            user_lat=user_lat,
            user_lng=user_lng,
            emp_lat=service_provider.live_lat,
            emp_lng=service_provider.live_lng,
            price=base_price,
            discount_applied=discount,
            promo_code=coupon_code,
            payment_method=payment_method,
            service_date=svc_date,
            service_time=svc_time,
        )

        if not customer.servicehistory:
            customer.servicehistory = []
        customer.servicehistory.append(service_provider.unique)
        customer.save()

        # Email notifications
        # 1. Booking Confirmation to Customer
        confirm_body = get_booking_confirmation_html(booking, service_provider, customer)
        send_graphical_email('Service Booking Confirmed! 🎉', confirm_body, customer.mail)

        # 2. Payment Success to Customer (if online payment)
        if payment_method not in ['Cash On Delivery', 'Pay After Service']:
            pay_success_body = get_payment_success_html(booking, customer, txn_id or booking.dummy_txn_id)
            send_graphical_email('💳 Payment Receipt - ServiceHub', pay_success_body, customer.mail)

        # 3. New Booking Request to Provider
        provider_subject = "🔔 New Service Booking Request"
        provider_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#4f46e5,#3b82f6);padding:30px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">🔔 New Booking Assigned</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{service_provider.name}</strong>,</p>
            <p>You have received a new service booking request:</p>
            <div style="background:rgba(255,255,255,0.05);padding:15px;border-radius:8px;">
              <p style="margin:0 0 6px;"><strong>Booking Ref:</strong> #{booking.unique}</p>
              <p style="margin:0 0 6px;"><strong>Customer:</strong> {customer.name}</p>
              <p style="margin:0 0 6px;"><strong>Schedule:</strong> {booking.service_date} at {booking.service_time}</p>
              <p style="margin:0;"><strong>Payout Price:</strong> ₹{booking.price - booking.discount_applied:.2f}</p>
            </div>
            <p>Please log in to your dashboard to Accept or Decline this request.</p>
          </div>
        </div>
        """
        send_graphical_email(provider_subject, provider_html, service_provider.email)

        return redirect('/servicehistory/?payment=success')

    except Exception as e:
        print(f'Checkout error: {e}')
        return redirect('/bookservice/?error=payment_failed')


def servicehistory(request):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    user = get_object_or_404(Cdetail, mail=user_email)
    bookings = Bookings.objects.filter(uniqueuser=user.unique).order_by('-unique')
    services_dict = {s.unique: s for s in Employee.objects.all()}

    for b in bookings:
        b.employee = services_dict.get(b.uniqueservice)

    completed_bookings = Bookings.objects.filter(uniqueuser=user.unique, status='Service Completed').order_by('-unique')
    for cb in completed_bookings:
        cb.employee = services_dict.get(cb.uniqueservice)

    return render(request, 'user/servicehistory.html', {
        'bookings': bookings,
        'user': user,
        'completed_bookings': completed_bookings,
        'masked_bank': mask_bank_account(user.bank_account_num),
        'masked_upi': mask_upi_id(user.upi_id),
    })


@require_POST
def request_refund(request, booking_id):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    booking = get_object_or_404(Bookings, unique=booking_id)
    user = get_object_or_404(Cdetail, mail=user_email)

    bank_acc = request.POST.get('bank_account_num', '').strip()
    bank_ifsc = request.POST.get('bank_ifsc', '').strip()
    upi_id = request.POST.get('upi_id', '').strip()
    refund_reason = request.POST.get('refund_reason', '').strip()

    if bank_acc:
        user.bank_account_num = bank_acc
    if bank_ifsc:
        user.bank_ifsc = bank_ifsc
    if upi_id:
        user.upi_id = upi_id
    user.save()

    booking.refund_status = 'Requested'
    booking.refund_reason = refund_reason
    booking.status = 'Refund Requested'
    
    refund_proof_pic = request.FILES.get('refund_proof_pic')
    if refund_proof_pic:
        booking.refund_proof_pic = refund_proof_pic
        
    booking.save()

    return redirect('/servicehistory/?refund=requested')


def raiseticket(request):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    user = get_object_or_404(Cdetail, mail=user_email)

    if request.method == 'POST':
        phone = request.POST.get('phone', '')
        mail = request.POST.get('mail', user_email)
        ticketdetail = request.POST.get('ticketdetail', '')
        attachment = request.FILES.get('attachment')

        ticket = Ticket.objects.create(
            mail=mail, phone=phone,
            ticketdetail=ticketdetail,
            attachment=attachment,
            status='Pending'
        )

        email_body = get_complaint_submission_html(ticket, user.name or mail)
        send_graphical_email('Support Ticket Created - ServiceHub', email_body, mail)
        return redirect('/servicehistory/?complaint=submitted')

    return render(request, 'user/raiseticket.html', {'user': user})


def toggle_favorite(request, employee_id):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
    try:
        user = Cdetail.objects.get(mail=user_email)
        employee = Employee.objects.get(unique=employee_id)
        if not user.service:
            user.service = []
        if employee.unique in user.service:
            user.service.remove(employee.unique)
            action = 'removed'
        else:
            user.service.append(employee.unique)
            action = 'added'
        user.save()
        return JsonResponse({'status': 'success', 'action': action})
    except (Cdetail.DoesNotExist, Employee.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)


def favorites(request):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    user = get_object_or_404(Cdetail, mail=user_email)
    favorite_ids = user.service or []
    services = Employee.objects.filter(unique__in=favorite_ids)

    search_query = request.GET.get('q', '')
    if search_query:
        services = services.filter(
            Q(name__icontains=search_query) |
            Q(service_provided__icontains=search_query)
        )

    services = services.annotate(is_favorite=Value(True, output_field=BooleanField()))
    return render(request, 'user/favorites.html', {
        'data': services, 'search_query': search_query, 'user': user
    })


# ─────────────────────────────────────────────
# CUSTOMER COMPLETION & CANCEL FLOWS
# ─────────────────────────────────────────────

@csrf_exempt
def customer_confirm_booking(request, booking_id):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    booking = get_object_or_404(Bookings, unique=booking_id)
    if booking.status == 'Service Completed':
        complete_booking_helper(booking)
        return redirect(f'/track/{booking.unique}/')
    return redirect('/servicehistory/?confirm=error')


@csrf_exempt
def customer_raise_issue(request, booking_id):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    booking = get_object_or_404(Bookings, unique=booking_id)
    booking.status = 'Issue Raised'
    booking.save()

    # Create dispute ticket in database
    Ticket.objects.create(
        mail=booking.email,
        phone=request.session.get('user_phone', ''),
        ticketdetail=f"Dispute raised for Booking #{booking.unique} against Provider ID #{booking.uniqueservice}. Service amount: {booking.price}. Status: Issue Raised.",
        status='Pending'
    )

    # Notify admin about the complaint issue
    admin_subject = f"🚨 Alert: Booking #{booking.unique} marked as Issue Raised"
    admin_html = get_base_email_template(
        "🚨 Job Dispute Raised",
        "linear-gradient(135deg,#ef4444,#dc2626)",
        f"""
        <p style="color:#334155;line-height:1.6;">A customer has raised an issue for Booking <strong>#{booking.unique}</strong>.</p>
        <p style="color:#334155;line-height:1.6;"><strong>Customer Email:</strong> {booking.email}</p>
        <p style="color:#334155;line-height:1.6;"><strong>Provider ID:</strong> {booking.uniqueservice}</p>
        <p style="color:#334155;line-height:1.6;">Please review the details immediately and resolve any customer concerns.</p>
        """
    )
    send_graphical_email(admin_subject, admin_html, 'bhushan.272006@gmail.com')

    # Notify Service Provider
    try:
        provider = Employee.objects.get(unique=booking.uniqueservice)
        provider_email = provider.email
    except Employee.DoesNotExist:
        provider = None
        provider_email = None

    if provider_email:
        provider_subject = f"🚨 Alert: Dispute Raised for Booking #{booking.unique}"
        provider_html = get_base_email_template(
            "🚨 Dispute Raised",
            "linear-gradient(135deg,#ef4444,#dc2626)",
            f"""
            <p>Hello <strong>{provider.name}</strong>,</p>
            <p style="color:#475569;line-height:1.6;">A customer has raised a dispute/issue for Booking <strong>#{booking.unique}</strong>.</p>
            <p style="color:#475569;line-height:1.6;">The payment for this booking has been temporarily frozen. Admin will review this case and get in touch with you shortly.</p>
            """
        )
        send_graphical_email(provider_subject, provider_html, provider_email)

    return redirect('/raiseticket/')



@csrf_exempt
def customer_cancel_booking(request, booking_id):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type != 'user':
        return redirect('/signin/')

    booking = get_object_or_404(Bookings, unique=booking_id)
    employee = get_object_or_404(Employee, unique=booking.uniqueservice)

    if booking.status in ['Pending', 'Pending Service Provider Acceptance']:
        booking.status = 'Cancelled'
        booking.save()

        # Send cancellation email to service provider
        provider_subject = f"❌ Booking Request #{booking.unique} Cancelled by Customer"
        provider_html = get_base_email_template(
            "❌ Booking Cancelled",
            "linear-gradient(135deg,#ef4444,#dc2626)",
            f"""
            <p>Hello <strong>{employee.name}</strong>,</p>
            <p style="color:#475569;line-height:1.6;">Booking request <strong>#{booking.unique}</strong> has been cancelled by the customer.</p>
            <p style="color:#475569;line-height:1.6;">This slot is now available for other bookings.</p>
            """
        )
        send_graphical_email(provider_subject, provider_html, employee.email)
        return redirect('/servicehistory/?cancel=success')
        
    return redirect('/servicehistory/?cancel=error')


# ─────────────────────────────────────────────
# SERVICE PROVIDER (EMPLOYEE) DASHBOARD
# ─────────────────────────────────────────────

def employeeservicebooked(request):
    employee_email = request.session.get('user_email')
    user_type = request.session.get('user_type')

    if not employee_email or user_type != 'employee':
        return redirect('/signin/')

    try:
        employee = Employee.objects.get(email=employee_email)
    except Employee.DoesNotExist:
        return redirect('/signin/')

    bookings = Bookings.objects.filter(uniqueservice=employee.unique).order_by('-unique')
    user_dict = {u.unique: u for u in Cdetail.objects.all()}

    combined = []
    for booking in bookings:
        user = user_dict.get(booking.uniqueuser)
        if user:
            combined.append({'booking': booking, 'user': user})

    pending_count = sum(1 for item in combined if item['booking'].status in ['Pending', 'Pending Service Provider Acceptance'])
    agent_offers = Offer.objects.filter(created_by=employee.email)

    # Wallet metrics
    wallet_transactions = WalletTransaction.objects.filter(employee=employee).order_by('-created_at')
    
    # Total earnings: completed Collection credits
    total_earnings = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Collection' and tx.status == 'Completed')
    
    # Total withdrawn amount: completed Payouts
    withdrawn_amount = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Withdrawal' and tx.status == 'Completed')
    
    # Pending Payout withdrawals
    pending_withdrawal_amount = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Withdrawal' and tx.status == 'Pending')
    
    # Wallet Balance
    wallet_balance = total_earnings - withdrawn_amount - pending_withdrawal_amount

    # Time-based earnings calculations
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timezone.timedelta(days=7)
    month_start = today_start - timezone.timedelta(days=30)

    today_earnings = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Collection' and tx.status == 'Completed' and tx.created_at >= today_start)
    weekly_earnings = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Collection' and tx.status == 'Completed' and tx.created_at >= week_start)
    monthly_earnings = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Collection' and tx.status == 'Completed' and tx.created_at >= month_start)

    # Count of refund complaints under investigation
    under_investigation_count = Bookings.objects.filter(
        uniqueservice=employee.unique,
        refund_status='Under Investigation'
    ).count()

    return render(request, 'employee/employeeservicebooked.html', {
        'combined_list': combined,
        'employee': employee,
        'agent_offers': agent_offers,
        'pending_count': pending_count,
        'wallet_transactions': wallet_transactions,
        'total_earnings': total_earnings,
        'withdrawn_amount': withdrawn_amount,
        'pending_withdrawal_amount': pending_withdrawal_amount,
        'wallet_balance': wallet_balance,
        'today_earnings': today_earnings,
        'weekly_earnings': weekly_earnings,
        'monthly_earnings': monthly_earnings,
        'under_investigation_count': under_investigation_count,
    })


@csrf_exempt
def agent_add_offer(request):
    employee_email = request.session.get('user_email')
    if not employee_email:
        return redirect('/signin/')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        discount = int(request.POST.get('discount', 10))
        desc = request.POST.get('description', '')
        if code:
            Offer.objects.create(
                code=code, discount_percent=discount,
                created_by=employee_email, description=desc, is_active=True
            )
    return redirect('/employeeservicebooked/?offer=added')


@csrf_exempt
def agent_toggle_booking(request, booking_id, action):
    employee_email = request.session.get('user_email')
    if not employee_email:
        return redirect('/signin/')

    booking = get_object_or_404(Bookings, unique=booking_id)
    employee = get_object_or_404(Employee, email=employee_email)
    customer = get_object_or_404(Cdetail, unique=booking.uniqueuser)

    if action == 'accept':
        booking.status = 'Heading to Location'
        booking.emp_lat = employee.live_lat
        booking.emp_lng = employee.live_lng
        booking.save()
        send_graphical_email(
            '🚀 Booking Accepted by Provider',
            get_booking_accepted_html(booking, employee, customer),
            customer.mail
        )
    elif action == 'decline':
        booking.status = 'Declined'
        booking.save()
        send_graphical_email(
            '❌ Booking Declined by Provider',
            get_booking_rejected_html(booking, employee, customer),
            customer.mail
        )
    elif action == 'reached':
        booking.status = 'Reached Location'
        booking.save()
        
        # Email customer that provider reached
        cust_subject = "👷 Service Provider Reached Your Location!"
        cust_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#10b981,#059669);padding:30px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">📍 Provider Arrived!</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{customer.name}</strong>,</p>
            <p>Your service provider <strong>{employee.name}</strong> has arrived at your designated service location.</p>
            <p>Please facilitate their access to start the work.</p>
          </div>
        </div>
        """
        send_graphical_email(cust_subject, cust_html, customer.mail)
        
    elif action == 'start':
        booking.status = 'In Progress'
        booking.save()
        
    elif action == 'complete':
        booking.status = 'Service Completed'
        booking.save()

        # Email customer: Confirm Completion request
        confirm_url = f"http://127.0.0.1:8000/track/{booking.unique}/"
        cust_subject = "🔔 Confirm Service Completion request"
        cust_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#f59e0b,#d97706);padding:30px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">🔔 Confirm Job Completion</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{customer.name}</strong>,</p>
            <p>Your service provider <strong>{employee.name}</strong> has marked the booking #<strong>{booking.unique}</strong> as completed.</p>
            <p>Please confirm completion on your dashboard to release the payment, or raise a support ticket if there is any issue.</p>
            <div style="text-align:center;margin:30px 0;">
              <a href="{confirm_url}" style="background:linear-gradient(135deg,#f59e0b,#d97706);color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:bold;display:inline-block;">Review & Confirm Now</a>
            </div>
          </div>
        </div>
        """
        send_graphical_email(cust_subject, cust_html, customer.mail)

    referer = request.META.get('HTTP_REFERER', '')
    if 'track' in referer:
        return redirect(referer)
    return redirect('/employeeservicebooked/?status=updated')



@csrf_exempt
def provider_update_location(request, booking_id):
    employee_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not employee_email or user_type != 'employee':
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)

    if request.method == 'POST':
        booking = get_object_or_404(Bookings, unique=booking_id)
        employee = get_object_or_404(Employee, email=employee_email)

        import json
        try:
            data = json.loads(request.body)
            lat = float(data.get('lat', 0))
            lng = float(data.get('lng', 0))
        except Exception:
            lat = float(request.POST.get('lat', 0) or 0)
            lng = float(request.POST.get('lng', 0) or 0)

        if lat and lng:
            employee.live_lat = lat
            employee.live_lng = lng
            employee.save()

            booking.emp_lat = lat
            booking.emp_lng = lng
            booking.save()
            return JsonResponse({'status': 'success', 'lat': lat, 'lng': lng})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


def agent_update_bank(request):
    employee_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not employee_email or user_type != 'employee':
        return redirect('/signin/')

    if request.method == 'POST':
        account_holder = request.POST.get('account_holder_name', '').strip()
        bank_name = request.POST.get('bank_name', '').strip()
        bank_account_num = request.POST.get('bank_account_num', '').strip()
        bank_ifsc = request.POST.get('bank_ifsc', '').strip()
        branch = request.POST.get('branch_name', '').strip()
        passbook_photo = request.FILES.get('passbook_photo')
        cheque_photo = request.FILES.get('cheque_photo')

        try:
            employee = Employee.objects.get(email=employee_email)
            # Save to temporary fields awaiting admin approval
            employee.temp_account_holder_name = account_holder
            employee.temp_bank_name = bank_name
            employee.temp_bank_account_num = bank_account_num
            employee.temp_bank_ifsc = bank_ifsc
            employee.temp_branch_name = branch
            if passbook_photo:
                employee.temp_passbook_photo = passbook_photo
            if cheque_photo:
                employee.temp_cheque_photo = cheque_photo
            employee.bank_verification_status = 'Pending'
            employee.save()
            return redirect('/employeeservicebooked/?bank_status=submitted')
        except Employee.DoesNotExist:
            pass

    return redirect('/employeeservicebooked/?bank_status=failed')


def agent_request_withdrawal(request):
    employee_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not employee_email or user_type != 'employee':
        return redirect('/signin/')

    try:
        employee = Employee.objects.get(email=employee_email)

        # Calculate Wallet Balance
        wallet_transactions = WalletTransaction.objects.filter(employee=employee)
        total_earnings = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Collection' and tx.status == 'Completed')
        withdrawn_amount = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Withdrawal' and tx.status == 'Completed')
        pending_withdrawal_amount = sum(tx.amount for tx in wallet_transactions if tx.transaction_type == 'Withdrawal' and tx.status == 'Pending')
        wallet_balance = total_earnings - withdrawn_amount - pending_withdrawal_amount

        if wallet_balance > 0 and employee.bank_verification_status == 'Approved':
            # Create a pending withdrawal request transaction
            tx = WalletTransaction.objects.create(
                employee=employee,
                transaction_type='Withdrawal',
                amount=wallet_balance,
                status='Pending',
                dummy_txn_id=''
            )

            # Send Email to Service Provider
            subject = "Withdrawal Request Received"
            email_body = get_base_email_template(
                "⏳ Withdrawal Processing",
                "linear-gradient(135deg,#f59e0b,#d97706)",
                f"""
                <p>Hello <strong>{employee.name}</strong>,</p>
                <p style="color:#475569;line-height:1.6;">We have received your withdrawal payout request for <strong>₹{wallet_balance:.2f}</strong>.</p>
                <p style="color:#475569;line-height:1.6;">Funds will be credited to your verified bank account: <strong>{employee.bank_name} (Ac. No. ending in {employee.bank_account_num[-4:]})</strong> once approved by the administrator.</p>
                """
            )
            send_graphical_email(subject, email_body, employee.email)

            # Send Email to Admin
            admin_subject = "🔔 New Wallet Withdrawal Request"
            admin_html = get_base_email_template(
                "🔔 Payout Requested",
                "linear-gradient(135deg,#6c63ff,#3b82f6)",
                f"""
                <p>A new payout withdrawal has been requested:</p>
                <p style="color:#475569;line-height:1.6;"><strong>Provider:</strong> {employee.name}</p>
                <p style="color:#475569;line-height:1.6;"><strong>Amount:</strong> ₹{wallet_balance:.2f}</p>
                <p style="color:#475569;line-height:1.6;"><strong>Bank Details:</strong> {employee.bank_name} ({employee.bank_account_num})</p>
                <p style="color:#475569;line-height:1.6;">Please review and process the withdrawal request in your admin panel.</p>
                """
            )
            send_graphical_email(admin_subject, admin_html, 'bhushan.272006@gmail.com')

            return redirect('/employeeservicebooked/?withdraw_status=requested')

    except Employee.DoesNotExist:
        pass

    return redirect('/employeeservicebooked/?withdraw_status=failed')


# ─────────────────────────────────────────────
# LIVE TRACKING VIEW & SIMULATION
# ─────────────────────────────────────────────

def track_booking(request, booking_id):
    user_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not user_email or user_type not in ['user', 'employee']:
        return redirect('/signin/')

    booking = get_object_or_404(Bookings, unique=booking_id)
    employee = get_object_or_404(Employee, unique=booking.uniqueservice)
    customer = get_object_or_404(Cdetail, unique=booking.uniqueuser)

    return render(request, 'user/track.html', {
        'booking': booking, 'employee': employee, 'customer': customer,
    })


def get_booking_tracking(request, booking_id):
    booking = get_object_or_404(Bookings, unique=booking_id)
    employee = get_object_or_404(Employee, unique=booking.uniqueservice)

    # Simulate real-time enroute coordinate updates during 'Heading to Location' status
    if booking.status == 'Heading to Location':
        lat_diff = booking.user_lat - booking.emp_lat
        lng_diff = booking.user_lng - booking.emp_lng
        distance = math.sqrt(lat_diff**2 + lng_diff**2)
        if distance > 0.0001:  # About 10 meters threshold
            # Move 15% closer on every poll
            booking.emp_lat += lat_diff * 0.15
            booking.emp_lng += lng_diff * 0.15
            booking.save()
            
            # Sync employee live position
            employee.live_lat = booking.emp_lat
            employee.live_lng = booking.emp_lng
            employee.save()

    return JsonResponse({
        'status': booking.status,
        'user_lat': booking.user_lat, 'user_lng': booking.user_lng,
        'emp_lat': booking.emp_lat, 'emp_lng': booking.emp_lng,
        'employee_name': employee.name,
        'employee_phone': employee.phone,
        'employee_photo': employee.profile_image or '',
        'service_provided': employee.service_provided,
    })


@csrf_exempt
def simulation_control(request, booking_id):
    # Provider location simulation trigger from dashboard panel (Simulation control API)
    if request.method == 'POST':
        booking = get_object_or_404(Bookings, unique=booking_id)
        action = request.POST.get('action')
        if action == 'reset':
            booking.status = 'Heading to Location'
            booking.emp_lat = 21.0150
            booking.emp_lng = 75.5690
            booking.save()
            return JsonResponse({'status': 'success'})
        elif action == 'inprogress':
            booking.status = 'In Progress'
            booking.emp_lat = booking.user_lat
            booking.emp_lng = booking.user_lng
            booking.save()
            return JsonResponse({'status': 'success'})
        elif action == 'complete':
            booking.status = 'Service Completed'
            booking.save()
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


def complete_booking_helper(booking):
    if booking.status == 'Completed':
        return

    booking.status = 'Completed'
    booking.save()

    amount = booking.price - booking.discount_applied

    try:
        provider = Employee.objects.get(unique=booking.uniqueservice)
    except Employee.DoesNotExist:
        provider = None

    try:
        customer = Cdetail.objects.get(unique=booking.uniqueuser)
    except Cdetail.DoesNotExist:
        customer = None

    if provider:
        # Create Collection WalletTransaction
        dummy_id = f"TXN_CL_{booking.unique}{random.randint(1000, 9999)}"
        WalletTransaction.objects.create(
            employee=provider,
            transaction_type='Collection',
            booking_id=booking.unique,
            amount=amount,
            status='Completed',
            dummy_txn_id=dummy_id
        )

        provider.no_of_service_provided = (provider.no_of_service_provided or 0) + 1
        provider.save()

        # Send completion emails
        subject = f"Service Job Completed! Booking #{booking.unique}"

        # Customer Email - service completed
        customer_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#10b981,#059669);padding:30px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">✅ Job Confirmed Completed</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{customer.name if customer else 'Customer'}</strong>,</p>
            <p>Your booking with <strong>{provider.name}</strong> for <strong>{provider.service_provided}</strong> has been successfully marked completed.</p>
            <div style="background:rgba(255,255,255,0.05);padding:20px;border-radius:8px;margin:20px 0;">
              <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr><td style="color:#64748b;padding:6px 0;">Billing Total:</td><td style="color:#10b981;font-weight:700;text-align:right;">₹{amount:.2f}</td></tr>
                <tr><td style="color:#64748b;padding:6px 0;">Payment Method:</td><td style="color:white;text-align:right;">{booking.payment_method}</td></tr>
              </table>
            </div>
            <p>We hope you had an excellent service. Please rate your provider on your dashboard!</p>
          </div>
        </div>
        """
        if customer:
            send_graphical_email(subject, customer_html, customer.mail)

        # Provider Email - payment release
        provider_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#10b981,#059669);padding:30px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">💰 Payout Released to Wallet!</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{provider.name}</strong>,</p>
            <p>The customer has confirmed completion of Booking #<strong>{booking.unique}</strong>.</p>
            <p>An earnings credit of <strong>₹{amount:.2f}</strong> has been released and added to your Wallet balance.</p>
            <div style="background:rgba(255,255,255,0.05);padding:20px;border-radius:8px;margin:20px 0;">
              <p style="margin:0 0 6px;"><strong>Collection Ref:</strong> {dummy_id}</p>
              <p style="margin:0;"><strong>Earnings:</strong> ₹{amount:.2f}</p>
            </div>
          </div>
        </div>
        """
        send_graphical_email("💰 Payout Release Notification", provider_html, provider.email)


# ─────────────────────────────────────────────
# ADMIN DASHBOARD
# ─────────────────────────────────────────────

def admin_required(request):
    return request.session.get('user_email') and request.session.get('user_type') == 'admin'


def aadmin(request):
    if not admin_required(request):
        return redirect('/signin/')

    customer_count = Cdetail.objects.exclude(mail='admin@gmail.com').count()
    employee_count = Employee.objects.count()
    ticket_count = Ticket.objects.filter(status='Pending').count()
    bookings_count = Bookings.objects.count()
    pending_providers = ProviderRegistration.objects.filter(status='pending').count()
    active_bookings = Bookings.objects.filter(status__in=['Pending', 'Heading to Location', 'In Progress']).count()

    recent_bookings = Bookings.objects.order_by('-unique')[:5]
    recent_tickets = Ticket.objects.order_by('-unique')[:5]
    ads = Advertisement.objects.filter(is_active=True)

    # Admin Panel stats
    all_completed = Bookings.objects.filter(status='Completed')
    total_revenue = sum(b.price - b.discount_applied for b in all_completed)
    total_transactions = Bookings.objects.count() + WalletTransaction.objects.count()
    total_withdrawals = sum(tx.amount for tx in WalletTransaction.objects.filter(transaction_type='Withdrawal', status='Completed'))
    provider_payouts = sum(tx.amount for tx in WalletTransaction.objects.filter(transaction_type='Withdrawal', status__in=['Pending', 'Completed']))

    from csdata.models import AdminSetting
    setting, _ = AdminSetting.objects.get_or_create(key='global_email_active', defaults={'value': True, 'description': 'Enable/Disable global email notification service'})
    global_email_active = setting.value

    return render(request, 'admin/aadmin.html', {
        'customer_count': customer_count,
        'employee_count': employee_count,
        'ticket_count': ticket_count,
        'bookings_count': bookings_count,
        'pending_providers': pending_providers,
        'active_bookings': active_bookings,
        'recent_bookings': recent_bookings,
        'recent_tickets': recent_tickets,
        'ads': ads,
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'total_withdrawals': total_withdrawals,
        'provider_payouts': provider_payouts,
        'global_email_active': global_email_active,
    })


def addemp(request):
    if not admin_required(request):
        return redirect('/signin/')

    SERVICE_CATEGORIES = [
        'Electrician', 'Plumber', 'Carpenter', 'AC Repair',
        'Cleaning', 'Painter', 'Technician', 'Others'
    ]

    if request.method == 'POST':
        name = request.POST.get('name', '')
        phone = request.POST.get('phone', '')
        email = request.POST.get('email', '')
        passw = request.POST.get('passw', '')
        gender = request.POST.get('gender', '')
        service_provided = request.POST.get('service_provided', '')
        experience = int(request.POST.get('experience', 0) or 0)
        specialization = request.POST.get('specialization', '')
        description = request.POST.get('description', '')
        address = request.POST.get('address', '')
        service_area = request.POST.get('service_area', '')
        starting_price = float(request.POST.get('starting_price', 299) or 299)
        profile_photo = request.FILES.get('profile_photo')
        
        profile_image_url = 'https://images.unsplash.com/photo-1540569014015-19a7be504e3a?q=80&w=150&auto=format&fit=crop'
        if profile_photo:
            from django.core.files.storage import default_storage
            file_name = default_storage.save('provider_profiles/' + profile_photo.name, profile_photo)
            profile_image_url = '/media/' + file_name

        if Employee.objects.filter(email=email).exists():
            return render(request, 'admin/addemp.html', {
                'error': 'Email already registered.', 'categories': SERVICE_CATEGORIES
            })

        Employee.objects.create(
            name=name, phone=phone, email=email, passw=passw,
            gender=gender, service_provided=service_provided,
            experience=experience, specialization=specialization,
            description=description, address=address,
            service_area=service_area, starting_price=starting_price,
            profile_image=profile_image_url, is_active=True, is_verified=True,
        )
        return redirect('/employeeinfo/?added=true')

    return render(request, 'admin/addemp.html', {'categories': SERVICE_CATEGORIES})


def userinfo(request):
    if not admin_required(request):
        return redirect('/signin/')

    search = request.GET.get('q', '')
    users = Cdetail.objects.exclude(mail='admin@gmail.com')
    if search:
        users = users.filter(Q(name__icontains=search) | Q(mail__icontains=search))

    return render(request, 'admin/userinfo.html', {'users': users, 'search': search})


def suspend_user(request, user_id):
    if not admin_required(request):
        return redirect('/signin/')
    user = get_object_or_404(Cdetail, unique=user_id)
    user.is_suspended = not user.is_suspended
    user.save()
    return redirect('/userinfo/')


def employeeinfo(request):
    if not admin_required(request):
        return redirect('/signin/')

    search_query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    verification = request.GET.get('verification', '').strip()
    status = request.GET.get('status', '').strip()
    sort_by = request.GET.get('sort_by', 'unique').strip()
    order = request.GET.get('order', 'asc').strip()

    from django.core.paginator import Paginator
    employees = Employee.objects.all()

    # Search
    if search_query:
        employees = employees.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(service_provided__icontains=search_query)
        )

    # Category Filter
    if category:
        employees = employees.filter(service_provided=category)

    # Verification Filter
    if verification == 'verified':
        employees = employees.filter(is_verified=True)
    elif verification == 'unverified':
        employees = employees.filter(is_verified=False)

    # Status Filter
    if status == 'active':
        employees = employees.filter(is_active=True)
    elif status == 'suspended':
        employees = employees.filter(is_active=False)

    # Sorting
    if sort_by in ['unique', 'name', 'service_provided', 'rating', 'experience', 'created_at']:
        sort_field = sort_by
        if order == 'desc':
            sort_field = '-' + sort_field
        employees = employees.order_by(sort_field)
    else:
        employees = employees.order_by('unique')

    # Pagination
    paginator = Paginator(employees, 10)  # 10 per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    categories = ['Electrician', 'Plumber', 'Carpenter', 'AC Repair', 'Cleaning', 'Painter', 'Technician', 'Others']

    context = {
        'data': page_obj,  # Matches {% for agent in data %}
        'search_query': search_query,
        'selected_category': category,
        'selected_verification': verification,
        'selected_status': status,
        'selected_sort': sort_by,
        'selected_order': order,
        'categories': categories,
        'page_obj': page_obj
    }
    return render(request, 'admin/employeeinfo.html', context)



def employeeinfocommon(request, employee_id):
    if not admin_required(request):
        return redirect('/signin/')
    employee = get_object_or_404(Employee, unique=employee_id)
    
    # Mask bank account details
    masked_acc = mask_bank_account(employee.bank_account_num)
    masked_ifsc = employee.bank_ifsc[:4] + '*' * (len(employee.bank_ifsc) - 4) if employee.bank_ifsc else 'Unregistered'
    
    return render(request, 'admin/employeeinfocommon.html', {
        'employee': employee,
        'employeeinfocommon': employee,
        'masked_acc': masked_acc,
        'masked_ifsc': masked_ifsc,
    })


def delete_employee(request, employee_id):
    if not admin_required(request):
        return redirect('/signin/')
    employee = get_object_or_404(Employee, unique=employee_id)
    employee.delete()
    return redirect('/employeeinfo/')


def servicebooked(request):
    if not admin_required(request):
        return redirect('/signin/')

    bookings = Bookings.objects.order_by('-unique')
    employees = {e.unique: e for e in Employee.objects.all()}
    users = {u.unique: u for u in Cdetail.objects.all()}

    combined = []
    for b in bookings:
        emp = employees.get(b.uniqueservice)
        usr = users.get(b.uniqueuser)
        combined.append({'booking': b, 'employee': emp, 'user': usr})

    pending_providers = ProviderRegistration.objects.filter(status='pending').count()
    ticket_count = Ticket.objects.filter(status='Pending').count()

    return render(request, 'admin/servicebooked.html', {
        'combined': combined,
        'pending_providers': pending_providers,
        'ticket_count': ticket_count
    })



def ticketraised(request):
    if not admin_required(request):
        return redirect('/signin/')
    tickets = Ticket.objects.order_by('-unique')
    return render(request, 'admin/ticketraised.html', {'tickets': tickets})


def admin_manage_complaint(request, ticket_id, action):
    if not admin_required(request):
        return redirect('/signin/')

    ticket = get_object_or_404(Ticket, unique=ticket_id)

    if action == 'resolve' and request.method == 'POST':
        admin_response = request.POST.get('admin_response', 'Issue resolved.')
        ticket.status = 'Resolved'
        ticket.admin_response = admin_response
        ticket.resolved_at = timezone.now()
        ticket.save()

        try:
            customer = Cdetail.objects.get(mail=ticket.mail)
            customer_name = customer.name or ticket.mail
        except Cdetail.DoesNotExist:
            customer_name = ticket.mail

        send_graphical_email(
            '✅ Your Support Ticket Has Been Resolved',
            get_complaint_resolution_html(ticket, customer_name),
            ticket.mail
        )

    elif action == 'inreview':
        ticket.status = 'In Review'
        ticket.save()

        try:
            customer = Cdetail.objects.get(mail=ticket.mail)
            customer_name = customer.name or ticket.mail
        except Cdetail.DoesNotExist:
            customer_name = ticket.mail

        # Send update email to customer
        inreview_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#f59e0b,#d97706);padding:30px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">🎫 Ticket Under Review</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{customer_name}</strong>,</p>
            <p>Your support ticket <strong>#{ticket.unique}</strong> status has been updated to <strong>In Review</strong>.</p>
            <p>Our support administration is actively investigating the issue details and will provide a resolution details shortly.</p>
          </div>
        </div>
        """
        send_graphical_email('🎫 Support Ticket Update - ServiceHub', inreview_html, ticket.mail)

    return redirect('/ticketraised/')


def admin_manage_ad(request):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'add':
            title = request.POST.get('title', '')
            target_url = request.POST.get('target_url', '')
            image_file = request.FILES.get('image')
            Advertisement.objects.create(
                title=title, target_url=target_url, image=image_file, is_active=True
            )
        elif action == 'toggle':
            ad_id = request.POST.get('ad_id')
            ad = get_object_or_404(Advertisement, unique=ad_id)
            ad.is_active = not ad.is_active
            ad.save()
        elif action == 'delete':
            ad_id = request.POST.get('ad_id')
            Advertisement.objects.filter(unique=ad_id).delete()

    ads = Advertisement.objects.all().order_by('-unique')
    return render(request, 'admin/manage_ad.html', {'ads': ads})


def admin_manage_offer(request):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'add':
            code = request.POST.get('code', '').strip().upper()
            discount = int(request.POST.get('discount_percent', 10))
            desc = request.POST.get('description', '')
            if code and not Offer.objects.filter(code=code).exists():
                Offer.objects.create(
                    code=code, discount_percent=discount,
                    description=desc, created_by='Admin', is_active=True
                )
        elif action == 'toggle':
            offer_id = request.POST.get('offer_id')
            offer = get_object_or_404(Offer, unique=offer_id)
            offer.is_active = not offer.is_active
            offer.save()
        elif action == 'delete':
            offer_id = request.POST.get('offer_id')
            Offer.objects.filter(unique=offer_id).delete()

    offers = Offer.objects.all().order_by('-unique')
    return render(request, 'admin/manage_offer.html', {'offers': offers})


# ─────────────────────────────────────────────
# ADMIN: PROVIDER VERIFICATION
# ─────────────────────────────────────────────

def admin_pending_providers(request):
    if not admin_required(request):
        return redirect('/signin/')
    providers = ProviderRegistration.objects.all().order_by('-submitted_at')
    return render(request, 'admin/pending_providers.html', {'providers': providers})


def admin_review_provider(request, provider_id):
    if not admin_required(request):
        return redirect('/signin/')
    provider = get_object_or_404(ProviderRegistration, id=provider_id)
    return render(request, 'admin/review_provider.html', {'provider': provider})


def admin_approve_provider(request, provider_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        provider = get_object_or_404(ProviderRegistration, id=provider_id)

        # Generate credentials password
        name_part = provider.full_name.replace(' ', '').title()[:4]
        phone_part = provider.phone[-4:]
        email_part = provider.email.split('@')[0][:3].lower()
        password = f"{name_part}@{phone_part}{email_part}"

        profile_img_url = ''
        if provider.profile_photo:
            profile_img_url = provider.profile_photo.url

        employee = Employee.objects.create(
            name=provider.full_name,
            email=provider.email,
            phone=provider.phone,
            passw=password,
            service_provided=provider.service_category,
            address=f"{provider.address_line1}, {provider.city}, {provider.state}",
            service_area=provider.city,
            profile_image=profile_img_url,
            is_active=True,
            is_verified=True,
            allow_email_notifications=provider.allow_email_notifications,
            # Map location
            live_lat=provider.gps_lat or 21.0150,
            live_lng=provider.gps_lng or 75.5690,
        )

        provider.status = 'approved'
        provider.reviewed_at = timezone.now()
        provider.save()

        send_graphical_email(
            '🎉 Your Application is Approved!',
            get_provider_approval_html(provider.full_name, provider.email, password),
            provider.email,
            is_operational=False
        )

    return redirect('/admin/pending-providers/')


def admin_reject_provider(request, provider_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        provider = get_object_or_404(ProviderRegistration, id=provider_id)
        note = request.POST.get('admin_note', 'Application rejected.')
        provider.status = 'rejected'
        provider.admin_note = note
        provider.reviewed_at = timezone.now()
        provider.save()

        reject_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#1a1a2e;border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:40px;text-align:center;">
            <h1 style="color:white;margin:0;font-size:24px;">Application Status Update</h1>
          </div>
          <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
            <p>Hello <strong>{provider.full_name}</strong>,</p>
            <p>Unfortunately, your application has not been approved at this time.</p>
            <div style="background:rgba(239,68,68,0.1);border:1px solid #ef4444;border-radius:12px;padding:20px;margin:20px 0;">
              <p style="color:#f87171;margin:0 0 8px;font-weight:600;">Reason:</p>
              <p style="color:#e2e8f0;margin:0;font-size:14px;">{note}</p>
            </div>
            <p style="color:#64748b;">You may reapply in the future after addressing the feedback notes.</p>
          </div>
        </div>
        """
        send_graphical_email('ServiceHub Application Update', reject_html, provider.email)

    return redirect('/admin/pending-providers/')


# ─────────────────────────────────────────────
# ADMIN WALLET, WITHDRAWALS & BANK VERIFICATION
# ─────────────────────────────────────────────

def admin_wallet(request):
    if not admin_required(request):
        return redirect('/signin/')

    pending_bank_providers = Employee.objects.filter(bank_verification_status='Pending')
    pending_withdrawals = WalletTransaction.objects.filter(transaction_type='Withdrawal', status='Pending').order_by('-created_at')
    completed_transactions = WalletTransaction.objects.filter(status='Completed').order_by('-created_at')

    pending_providers = ProviderRegistration.objects.filter(status='pending').count()
    ticket_count = Ticket.objects.filter(status='Pending').count()

    # Admin Payout stats
    all_completed = Bookings.objects.filter(status='Completed')
    total_revenue = sum(b.price - b.discount_applied for b in all_completed)
    total_transactions = Bookings.objects.count() + WalletTransaction.objects.count()
    total_withdrawals = sum(tx.amount for tx in WalletTransaction.objects.filter(transaction_type='Withdrawal', status='Completed'))
    provider_payouts = sum(tx.amount for tx in WalletTransaction.objects.filter(transaction_type='Withdrawal', status__in=['Pending', 'Completed']))

    return render(request, 'admin/admin_wallet.html', {
        'pending_bank_providers': pending_bank_providers,
        'pending_withdrawals': pending_withdrawals,
        'completed_transactions': completed_transactions,
        'pending_providers': pending_providers,
        'ticket_count': ticket_count,
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'total_withdrawals': total_withdrawals,
        'provider_payouts': provider_payouts,
    })


def admin_approve_bank(request, employee_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        employee = get_object_or_404(Employee, unique=employee_id)

        # Copy temp details to approved bank details
        employee.account_holder_name = employee.temp_account_holder_name
        employee.bank_name = employee.temp_bank_name
        employee.bank_account_num = employee.temp_bank_account_num
        employee.bank_ifsc = employee.temp_bank_ifsc
        employee.branch_name = employee.temp_branch_name
        
        if employee.temp_passbook_photo:
            employee.passbook_photo = employee.temp_passbook_photo
        if employee.temp_cheque_photo:
            employee.cheque_photo = employee.temp_cheque_photo

        employee.bank_verification_status = 'Approved'
        employee.save()

        # Send confirmation email
        email_body = get_bank_verification_update_html(employee, 'Approved')
        send_graphical_email('Bank Account Verification Approved! 🏦', email_body, employee.email)

        return redirect('/admin/wallet/?bank=approved')

    return redirect('/admin/wallet/')


def admin_reject_bank(request, employee_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        employee = get_object_or_404(Employee, unique=employee_id)
        action_type = request.POST.get('action_type', 'reject')  # reject or correction
        reason = request.POST.get('reason', 'Provided documents are unclear or mismatched.')

        if action_type == 'correction':
            employee.bank_verification_status = 'Correction Requested'
        else:
            employee.bank_verification_status = 'Rejected'
            
        employee.bank_correction_reason = reason
        employee.save()

        # Send update email
        email_body = get_bank_verification_update_html(employee, employee.bank_verification_status, reason)
        send_graphical_email(f'Bank Account Verification {employee.bank_verification_status} 🏦', email_body, employee.email)

        return redirect('/admin/wallet/?bank=updated')

    return redirect('/admin/wallet/')


def admin_approve_withdrawal(request, tx_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        tx = get_object_or_404(WalletTransaction, unique=tx_id)

        tx.status = 'Completed'
        dummy_id = f"TXN_WD_{tx.unique}{random.randint(1000, 9999)}"
        tx.dummy_txn_id = dummy_id
        tx.save()

        # Send payout approval email to employee
        email_body = get_withdrawal_update_html(tx.employee, tx, 'Completed')
        send_graphical_email('Withdrawal Payout Processed! 💰', email_body, tx.employee.email)

        return redirect('/admin/wallet/?withdraw=approved')

    return redirect('/admin/wallet/')


def admin_reject_withdrawal(request, tx_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        tx = get_object_or_404(WalletTransaction, unique=tx_id)

        tx.status = 'Rejected'
        tx.save()

        # Send payout reject email to employee
        email_body = get_withdrawal_update_html(tx.employee, tx, 'Rejected')
        send_graphical_email('Withdrawal Payout Declined ❌', email_body, tx.employee.email)

        return redirect('/admin/wallet/?withdraw=rejected')

    return redirect('/admin/wallet/')


@csrf_exempt
def admin_process_refund(request, booking_id):
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        booking = get_object_or_404(Bookings, unique=booking_id)
        customer = get_object_or_404(Cdetail, unique=booking.uniqueuser)
        
        booking.refund_status = 'Processed'
        booking.status = 'Declined'
        booking.save()

        # Send Refund Success Email to Customer
        subject = "Refund Processed Successfully"
        email_body = get_base_email_template(
            "💰 Refund Processed",
            "linear-gradient(135deg,#10b981,#059669)",
            f"""
            <p>Hello <strong>{customer.name}</strong>,</p>
            <p style="color:#475569;line-height:1.6;">Your refund of <strong>₹{booking.price - booking.discount_applied:.2f}</strong> for Booking <strong>#{booking.unique}</strong> has been successfully processed.</p>
            <p style="color:#475569;line-height:1.6;">The funds will be credited back to your original source account (or UPI ID: {mask_upi_id(customer.upi_id)}) within 2-3 business days.</p>
            """
        )
        send_graphical_email(subject, email_body, customer.mail)

        return redirect('/servicebooked/?refund=processed')

    return redirect('/servicebooked/')


@csrf_exempt
def admin_cancel_booking(request, booking_id):
    if not admin_required(request):
        return redirect('/signin/')
    booking = get_object_or_404(Bookings, unique=booking_id)
    booking.status = 'Cancelled'
    booking.save()
    return redirect('/servicebooked/?action=cancelled')


@csrf_exempt
def admin_complete_booking(request, booking_id):
    if not admin_required(request):
        return redirect('/signin/')
    booking = get_object_or_404(Bookings, unique=booking_id)
    complete_booking_helper(booking)
    return redirect('/servicebooked/?action=completed')


@csrf_exempt
def admin_delete_booking(request, booking_id):
    if not admin_required(request):
        return redirect('/signin/')
    booking = get_object_or_404(Bookings, unique=booking_id)
    booking.delete()
    return redirect('/servicebooked/?action=deleted')


# ─────────────────────────────────────────────

# PASSWORD RECOVERY & EMAIL POLICY TOGGLES
# ─────────────────────────────────────────────

def get_forgot_password_email_html(otp, email):
    content = f"""
    <h2 style="color:#d97706;margin:0 0 16px;font-size:20px;font-weight:700;">Password Recovery OTP Code</h2>
    <p style="color:#475569;margin:0 0 24px;line-height:1.6;">You have requested to reset your password. Use the following One-Time Password (OTP) to complete your request:</p>
    <div style="background:#fffbeb;border:2px solid #f59e0b;border-radius:12px;padding:24px;text-align:center;margin:0 0 24px;">
      <span style="font-size:48px;font-weight:800;letter-spacing:12px;color:#d97706;">{otp}</span>
    </div>
    <p style="color:#64748b;font-size:13px;line-height:1.4;">This OTP code is valid for 10 minutes. If you did not request a password reset, please ignore this email or contact support if you suspect unauthorized access.</p>
    """
    return get_base_email_template("Password Reset Request", "linear-gradient(135deg,#f59e0b,#d97706)", content)


def forgot_password_request(request):
    if request.method == 'POST':
        mail = request.POST.get('mail', '').strip().lower()
        account_type = request.POST.get('account_type', 'customer')

        if not mail:
            return render(request, 'home/forgot_password.html', {'error': 'Email is required.', 'email_val': mail})

        # Validate existence
        exists = False
        if account_type == 'customer':
            exists = Cdetail.objects.filter(mail=mail).exists()
        elif account_type == 'provider':
            exists = Employee.objects.filter(email=mail).exists()

        if not exists:
            return render(request, 'home/forgot_password.html', {
                'error': f'This email is not registered as a {account_type.capitalize()}.',
                'email_val': mail
            })

        # Generate OTP
        otp = generate_otp()
        OTPVerification.objects.filter(email=mail, purpose='forgot_password', is_used=False).update(is_used=True)
        OTPVerification.objects.create(email=mail, otp=otp, purpose='forgot_password')

        # Store session values
        request.session['forgot_mail'] = mail
        request.session['forgot_type'] = account_type
        request.session['forgot_otp_sent'] = True

        # Send email (pass is_operational=False so it is never blocked!)
        email_html = get_forgot_password_email_html(otp, mail)
        send_graphical_email(
            'ServiceHub Password Recovery OTP',
            email_html,
            mail,
            is_operational=False
        )

        return redirect('/forgot-password/verify/')

    return render(request, 'home/forgot_password.html')


def verify_forgot_otp(request):
    email = request.session.get('forgot_mail')
    if not email:
        return redirect('/forgot-password/')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        if not entered_otp:
            return render(request, 'home/forgot_verify.html', {'email': email, 'error': 'Please enter the OTP.'})

        try:
            otp_obj = OTPVerification.objects.filter(
                email=email,
                purpose='forgot_password',
                is_used=False
            ).latest('created_at')

            if (timezone.now() - otp_obj.created_at).seconds > 600:
                return render(request, 'home/forgot_verify.html', {
                    'email': email,
                    'error': 'OTP expired. Please try again.'
                })

            if otp_obj.otp != entered_otp:
                return render(request, 'home/forgot_verify.html', {
                    'email': email,
                    'error': 'Invalid OTP. Please try again.'
                })

            otp_obj.is_used = True
            otp_obj.save()

            request.session['forgot_otp_verified'] = True
            return redirect('/forgot-password/reset/')

        except OTPVerification.DoesNotExist:
            return render(request, 'home/forgot_verify.html', {
                'email': email,
                'error': 'Verification session not found. Please request a new OTP.'
            })

    return render(request, 'home/forgot_verify.html', {'email': email})


def reset_password(request):
    email = request.session.get('forgot_mail')
    otp_verified = request.session.get('forgot_otp_verified')
    account_type = request.session.get('forgot_type')

    if not email or not otp_verified:
        return redirect('/forgot-password/')

    if request.method == 'POST':
        passw = request.POST.get('passw', '')
        rpass = request.POST.get('rpass', '')

        if not passw:
            return render(request, 'home/forgot_reset.html', {'email': email, 'error': 'Please enter a new password.'})
        if passw != rpass:
            return render(request, 'home/forgot_reset.html', {'email': email, 'error': 'Passwords do not match.'})
        if len(passw) < 6:
            return render(request, 'home/forgot_reset.html', {'email': email, 'error': 'Password must be at least 6 characters.'})

        # Update and hash password securely
        hashed_password = make_password(passw)
        if account_type == 'customer':
            Cdetail.objects.filter(mail=email).update(passw=hashed_password)
        elif account_type == 'provider':
            Employee.objects.filter(email=email).update(passw=hashed_password)

        # Clear session recovery keys
        for key in ['forgot_mail', 'forgot_type', 'forgot_otp_sent', 'forgot_otp_verified']:
            request.session.pop(key, None)

        return redirect('/signin/?reset_success=true')

    return render(request, 'home/forgot_reset.html', {'email': email})


def toggle_customer_email(request, user_id):
    if not admin_required(request):
        return redirect('/signin/')
    user = get_object_or_404(Cdetail, unique=user_id)
    user.allow_email_notifications = not user.allow_email_notifications
    user.save()
    return redirect('/userinfo/')


def toggle_provider_status(request, employee_id):
    if not admin_required(request):
        return redirect('/signin/')
    employee = get_object_or_404(Employee, unique=employee_id)
    employee.is_active = not employee.is_active
    employee.save()
    return redirect('/employeeinfo/')


def toggle_global_email(request):
    """Toggles global email sending on/off by admin."""
    if not admin_required(request):
        return redirect('/signin/')
    
    from csdata.models import AdminSetting
    setting, _ = AdminSetting.objects.get_or_create(key='global_email_active', defaults={'value': True, 'description': 'Enable/Disable global email notification service'})
    setting.value = not setting.value
    setting.save()
    return redirect('/aadmin/?email_status_toggled=true')


def api_admin_active_bookings(request):
    """JSON API of all active bookings for real-time admin map tracking."""
    if not admin_required(request):
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)

    active_bookings = Bookings.objects.exclude(status__in=['Completed', 'Cancelled', 'Declined', 'Rejected']).order_by('-unique')
    services_dict = {s.unique: s for s in Employee.objects.all()}
    users_dict = {u.unique: u for u in Cdetail.objects.all()}

    data = []
    for b in active_bookings:
        user = users_dict.get(b.uniqueuser)
        employee = services_dict.get(b.uniqueservice)
        data.append({
            'unique': b.unique,
            'status': b.status,
            'user_lat': b.user_lat,
            'user_lng': b.user_lng,
            'emp_lat': b.emp_lat,
            'emp_lng': b.emp_lng,
            'user_name': user.name if user else 'Unregistered User',
            'emp_name': employee.name if employee else 'Unassigned Provider',
            'booking_address': b.booking_address,
        })
    return JsonResponse({'bookings': data})


def admin_create_booking(request):
    """Admin-only view to manually create a new booking for a customer."""
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        try:
            customer_id = int(request.POST.get('customer'))
            employee_id = int(request.POST.get('employee'))
            service_date_str = request.POST.get('service_date')
            service_time_str = request.POST.get('service_time')
            price = float(request.POST.get('price', 299))
            payment_method = request.POST.get('payment_method', 'UPI')
            booking_address = request.POST.get('booking_address', '').strip()

            customer = Cdetail.objects.get(unique=customer_id)
            employee = Employee.objects.get(unique=employee_id)

            from datetime import datetime
            svc_date = datetime.strptime(service_date_str, '%Y-%m-%d').date() if service_date_str else None
            svc_time = datetime.strptime(service_time_str, '%H:%M').time() if service_time_str else None

            # Set user coordinates (fallback to random offset near employee if not set)
            user_lat = customer.live_lat
            user_lng = customer.live_lng
            if user_lat == 0.0 and user_lng == 0.0:
                import random
                user_lat = employee.live_lat + 0.009 + (random.random() * 0.004)
                user_lng = employee.live_lng + 0.009 + (random.random() * 0.004)

            # Create booking
            booking = Bookings.objects.create(
                uniqueuser=customer.unique,
                uniqueservice=employee.unique,
                advance=True,
                email=customer.mail,
                status='Pending Service Provider Acceptance',
                booking_address=booking_address or customer.live_address or employee.address,
                user_lat=user_lat,
                user_lng=user_lng,
                emp_lat=employee.live_lat,
                emp_lng=employee.live_lng,
                price=price,
                payment_method=payment_method,
                service_date=svc_date,
                service_time=svc_time,
            )

            # Sync customer service history
            if not customer.servicehistory:
                customer.servicehistory = []
            customer.servicehistory.append(employee.unique)
            customer.save()

            # Email notifications
            # 1. Booking Confirmation to Customer
            confirm_body = get_booking_confirmation_html(booking, employee, customer)
            send_graphical_email('Service Booking Confirmed! 🎉', confirm_body, customer.mail)

            # 2. New Booking Request to Provider
            provider_subject = "🔔 New Service Booking Request (Created by Admin)"
            provider_html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;overflow:hidden;">
              <div style="background:linear-gradient(135deg,#4f46e5,#3b82f6);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">🔔 New Booking Assigned</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;background:#1e293b;line-height:1.6;">
                <p>Hello <strong>{employee.name}</strong>,</p>
                <p>An administrator has manually scheduled a new service booking request for you:</p>
                <div style="background:rgba(255,255,255,0.05);padding:15px;border-radius:8px;">
                  <p style="margin:0 0 6px;"><strong>Booking Ref:</strong> #{booking.unique}</p>
                  <p style="margin:0 0 6px;"><strong>Customer:</strong> {customer.name}</p>
                  <p style="margin:0 0 6px;"><strong>Schedule:</strong> {booking.service_date} at {booking.service_time}</p>
                  <p style="margin:0;"><strong>Payout Price:</strong> ₹{booking.price:.2f}</p>
                </div>
                <p>Please log in to your dashboard to Accept or Decline this request.</p>
              </div>
            </div>
            """
            send_graphical_email(provider_subject, provider_html, employee.email)

            return redirect('/servicebooked/?created=success')
        except Exception as e:
            print(f"Error creating booking by admin: {e}")
            return redirect('/admin/create-booking/?error=failed')

    customers = Cdetail.objects.exclude(mail='admin@gmail.com').order_by('name')
    employees = Employee.objects.filter(is_active=True).order_by('name')

    return render(request, 'admin/admin_create_booking.html', {
        'customers': customers,
        'employees': employees,
    })


def admin_customer_detail(request, user_id):
    """Admin-only view to display details for a registered customer, masking sensitive data."""
    if not admin_required(request):
        return redirect('/signin/')

    customer = get_object_or_404(Cdetail, unique=user_id)

    # Mask bank details
    masked_acc = mask_bank_account(customer.bank_account_num)
    masked_upi = mask_upi_id(customer.upi_id)
    masked_ifsc = customer.bank_ifsc[:4] + '*' * (len(customer.bank_ifsc) - 4) if customer.bank_ifsc else 'Unregistered'

    return render(request, 'admin/customerinfocommon.html', {
        'customer': customer,
        'masked_acc': masked_acc,
        'masked_upi': masked_upi,
        'masked_ifsc': masked_ifsc,
    })


def toggle_provider_email(request, employee_id):
    """Admin-only view to toggle email notifications for a specific service provider."""
    if not admin_required(request):
        return redirect('/signin/')
    employee = get_object_or_404(Employee, unique=employee_id)
    employee.allow_email_notifications = not employee.allow_email_notifications
    employee.save()
    
    referer = request.META.get('HTTP_REFERER', '')
    if referer and 'employeeinfocommon' in referer:
        return redirect(referer)
    return redirect('/employeeinfo/')


def toggle_global_email_category(request, category):
    """Admin-only view to toggle global email notification categories (customer, provider, admin)."""
    if not admin_required(request):
        return redirect('/signin/')

    key_map = {
        'customer': 'global_customer_email_active',
        'provider': 'global_provider_email_active',
        'admin': 'global_admin_email_active',
    }

    key = key_map.get(category.lower())
    if key:
        from csdata.models import AdminSetting
        setting, _ = AdminSetting.objects.get_or_create(
            key=key,
            defaults={'value': True, 'description': f'Enable/Disable {category.lower()} emails globally'}
        )
        setting.value = not setting.value
        setting.save()

    return redirect('/aadmin/?email_status_toggled=true')


def admin_investigate_refund(request, booking_id):
    """Admin view to mark a refund request under investigation and notify the provider."""
    if not admin_required(request):
        return redirect('/signin/')
    
    if request.method == 'POST':
        booking = get_object_or_404(Bookings, unique=booking_id)
        booking.refund_status = 'Under Investigation'
        booking.status = 'Under Investigation'
        booking.save()

        # Notify the service provider
        try:
            provider = Employee.objects.get(unique=booking.uniqueservice)
            subject = f"⚠️ Action Required: Booking #{booking.unique} under Refund Investigation"
            html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #ef4444;">
              <div style="background:linear-gradient(135deg,#f59e0b,#ef4444);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">⚠️ Refund Dispute Notice</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;line-height:1.6;">
                <p>Hello <strong>{provider.name}</strong>,</p>
                <p>The customer has requested a refund for Booking <strong>#{booking.unique}</strong> with the following reason:</p>
                <div style="background:rgba(255,255,255,0.05);padding:15px;border-radius:8px;margin-bottom:20px;border-left:4px solid #f59e0b;">
                  <em>"{booking.refund_reason}"</em>
                </div>
                <p>The administrator has marked this transaction for investigation. You must review this in your dashboard to either accept the refund or provide a dispute rebuttal.</p>
              </div>
            </div>
            """
            send_graphical_email(subject, html, provider.email)
        except Exception as e:
            print(f"Error notifying provider of investigation: {e}")

        return redirect('/servicebooked/?refund=investigating')
    return redirect('/servicebooked/')


def admin_confirm_refund(request, booking_id):
    """Admin view to approve and process the refund payout."""
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        booking = get_object_or_404(Bookings, unique=booking_id)
        
        # 1. Update status
        booking.refund_status = 'Processed'
        booking.status = 'Refunded'
        booking.save()

        # 2. Reverse wallet transactions for the employee/provider
        try:
            provider = Employee.objects.get(unique=booking.uniqueservice)
            # Find and set the collection transaction for this booking to 'Refunded'
            txs = WalletTransaction.objects.filter(booking_id=booking.unique, transaction_type='Collection')
            for tx in txs:
                tx.status = 'Refunded'
                tx.save()
            
            # Decrement provider service count
            if provider.no_of_service_provided and provider.no_of_service_provided > 0:
                provider.no_of_service_provided -= 1
                provider.save()
        except Exception as e:
            print(f"Error reversing provider transaction: {e}")

        # 3. Credit Customer Wallet & Notify Customer
        try:
            customer = Cdetail.objects.get(unique=booking.uniqueuser)
            customer.wallet_balance = (customer.wallet_balance or 0.0) + booking.price
            customer.save()

            subject = f"🎉 Refund Processed Successfully - Booking #{booking.unique}"
            html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#0f172a;border-radius:16px;overflow:hidden;border:1px solid #10b981;">
              <div style="background:linear-gradient(135deg,#10b981,#059669);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">🎉 Refund Approved</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;line-height:1.6;">
                <p>Hello <strong>{customer.name}</strong>,</p>
                <p>We are pleased to inform you that your refund claim for Booking <strong>#{booking.unique}</strong> has been approved by the administrator.</p>
                <p>A refund amount of <strong>₹{booking.price:.2f}</strong> has been credited to your <strong>ServiceHub Wallet</strong>.</p>
                <p>Your current wallet balance is <strong>₹{customer.wallet_balance:.2f}</strong>.</p>
                <p>This balance can be used to pay for future service bookings on our platform.</p>
                <p>Thank you for choosing ServiceHub!</p>
              </div>
            </div>
            """
            send_graphical_email(subject, html, customer.mail)
        except Exception as e:
            print(f"Error sending customer refund approval email: {e}")

        # 4. Notify Provider
        try:
            provider = Employee.objects.get(unique=booking.uniqueservice)
            subject = f"ℹ️ Refund Approved Notice - Booking #{booking.unique}"
            html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#1e293b;border-radius:16px;overflow:hidden;">
              <div style="background:#475569;padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">Refund Processed</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;line-height:1.6;">
                <p>Hello <strong>{provider.name}</strong>,</p>
                <p>This is to notify you that the administrator has approved the customer refund claim for Booking <strong>#{booking.unique}</strong>.</p>
                <p>The collection amount of ₹{booking.price:.2f} has been deducted from your wallet ledger records.</p>
              </div>
            </div>
            """
            send_graphical_email(subject, html, provider.email)
        except Exception as e:
            print(f"Error sending provider refund notice: {e}")

        return redirect('/servicebooked/?refund=processed')
    return redirect('/servicebooked/')


def admin_decline_refund(request, booking_id):
    """Admin view to reject the refund request."""
    if not admin_required(request):
        return redirect('/signin/')

    if request.method == 'POST':
        booking = get_object_or_404(Bookings, unique=booking_id)
        booking.refund_status = 'Declined'
        booking.status = 'Refund Declined'
        booking.save()

        # Ensure that the provider's collection transaction status is 'Completed'
        try:
            provider = Employee.objects.get(unique=booking.uniqueservice)
            txs = WalletTransaction.objects.filter(booking_id=booking.unique, transaction_type='Collection')
            if txs.exists():
                for tx in txs:
                    tx.status = 'Completed'
                    tx.save()
            else:
                # If for some reason the transaction doesn't exist, create it!
                amount = booking.price - booking.discount_applied
                dummy_id = f"TXN_CL_{booking.unique}{random.randint(1000, 9999)}"
                WalletTransaction.objects.create(
                    employee=provider,
                    transaction_type='Collection',
                    booking_id=booking.unique,
                    amount=amount,
                    status='Completed',
                    dummy_txn_id=dummy_id
                )
        except Exception as e:
            print(f"Error restoring provider transaction on refund decline: {e}")

        # Notify Customer
        try:
            customer = Cdetail.objects.get(unique=booking.uniqueuser)
            subject = f"❌ Refund Claim Declined - Booking #{booking.unique}"
            html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #ef4444;">
              <div style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">❌ Refund Declined</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;line-height:1.6;">
                <p>Hello <strong>{customer.name}</strong>,</p>
                <p>We regret to inform you that your refund claim for Booking <strong>#{booking.unique}</strong> has been reviewed and declined by the administration.</p>
                <p style="margin-top:20px;color:#94a3b8;font-size:14px;">The amount will not be refunded to your account, and the service payment has been finalized to the provider.</p>
                <p>If you believe this is in error, please raise a formal support complaint ticket via your dashboard.</p>
              </div>
            </div>
            """
            send_graphical_email(subject, html, customer.mail)
        except Exception as e:
            print(f"Error sending customer refund decline email: {e}")

        return redirect('/servicebooked/?refund=declined')
    return redirect('/servicebooked/')


def agent_dispute_refund(request, booking_id, action):
    """View for service provider to accept or dispute a customer refund request during investigation."""
    emp_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not emp_email or user_type != 'employee':
        return redirect('/signin/')

    employee = get_object_or_404(Employee, email=emp_email)
    booking = get_object_or_404(Bookings, unique=booking_id)

    # Security check: verify this booking belongs to this employee
    if booking.uniqueservice != employee.unique:
        return redirect('/employeeservicebooked/')

    if request.method == 'POST':
        action_clean = action.lower()
        if action_clean == 'concede':
            booking.status = 'Provider Conceded'
            booking.refund_status = 'Provider Conceded'
            booking.save()

            # Notify Admin
            subject = f"📢 Refund Request Update: Provider Accepted - Booking #{booking.unique}"
            html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#0f172a;border-radius:16px;overflow:hidden;border:1px solid #10b981;">
              <div style="background:linear-gradient(135deg,#10b981,#059669);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">Refund Accepted by Provider</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;line-height:1.6;">
                <p>Hello Admin,</p>
                <p>Service provider <strong>{employee.name}</strong> has conceded to the refund claim for Booking <strong>#{booking.unique}</strong>.</p>
                <p>Please log in to the admin panel to confirm the refund payout processing to the customer.</p>
              </div>
            </div>
            """
            send_graphical_email(subject, html, 'bh.ja.ingale@gmail.com')

        elif action_clean == 'dispute':
            rebuttal = request.POST.get('provider_dispute_reason', '').strip()
            booking.status = 'Provider Disputed'
            booking.refund_status = 'Provider Disputed'
            booking.provider_dispute_reason = rebuttal
            booking.save()

            # Notify Admin
            subject = f"⚖️ Refund Claim Disputed by Provider - Booking #{booking.unique}"
            html = f"""
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:auto;background:#1e293b;border-radius:16px;overflow:hidden;border:1px solid #ef4444;">
              <div style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">Dispute Rebuttal Submitted</h1>
              </div>
              <div style="padding:40px;color:#e2e8f0;line-height:1.6;">
                <p>Hello Admin,</p>
                <p>Service provider <strong>{employee.name}</strong> has disputed the refund request for Booking <strong>#{booking.unique}</strong>.</p>
                <p><strong>Rebuttal/Explanation:</strong></p>
                <div style="background:rgba(255,255,255,0.05);padding:15px;border-radius:8px;border-left:4px solid #ef4444;">
                  <em>"{rebuttal}"</em>
                </div>
                <p>Please log in to the admin panel to review statements and finalize the investigation.</p>
              </div>
            </div>
            """
            send_graphical_email(subject, html, 'bh.ja.ingale@gmail.com')

        return redirect('/employeeservicebooked/?dispute_status=submitted')
    return redirect('/employeeservicebooked/')


def admin_refunds_list(request):
    """View to list and manage all customer refunds and complaints."""
    if not admin_required(request):
        return redirect('/signin/')

    bookings_qs = Bookings.objects.exclude(refund_status='None').order_by('-created_at')
    combined = []
    for b in bookings_qs:
        try:
            customer = Cdetail.objects.get(unique=b.uniqueuser)
        except Cdetail.DoesNotExist:
            customer = None
        try:
            provider = Employee.objects.get(unique=b.uniqueservice)
        except Employee.DoesNotExist:
            provider = None
        combined.append({
            'booking': b,
            'user': customer,
            'provider': provider
        })

    # Counts for verification and tickets badges
    pending_providers = Employee.objects.filter(is_verified=False).count()
    try:
        ticket_count = Ticket.objects.filter(status='Pending').count()
    except Exception:
        ticket_count = 0

    return render(request, 'admin/admin_refunds.html', {
        'combined': combined,
        'pending_providers': pending_providers,
        'ticket_count': ticket_count
    })


def agent_refund_complaints(request):
    """View for service providers to view refund complaints under investigation and submit rebuttals."""
    emp_email = request.session.get('user_email')
    user_type = request.session.get('user_type')
    if not emp_email or user_type != 'employee':
        return redirect('/signin/')

    employee = get_object_or_404(Employee, email=emp_email)
    
    # Query complaints under investigation
    complaints = Bookings.objects.filter(
        uniqueservice=employee.unique,
        refund_status='Under Investigation'
    ).order_by('-created_at')

    combined = []
    for c in complaints:
        try:
            customer = Cdetail.objects.get(unique=c.uniqueuser)
        except Cdetail.DoesNotExist:
            customer = None
        combined.append({
            'booking': c,
            'user': customer
        })

    under_investigation_count = len(combined)

    return render(request, 'employee/agent_refund_complaints.html', {
        'employee': employee,
        'combined': combined,
        'under_investigation_count': under_investigation_count,
    })