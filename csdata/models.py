from django.db import models
from django.utils import timezone


class Cdetail(models.Model):
    """Customer model with full profile, addresses, and payment info."""
    unique = models.AutoField(primary_key=True)
    profile_image = models.CharField(max_length=5000, blank=True, default='')
    name = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    mail = models.CharField(max_length=100, unique=True)
    passw = models.CharField(max_length=256)
    gender = models.CharField(max_length=10, blank=True, default='')
    is_verified = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)

    # Addresses as JSON list:
    # [{label, address_line1, address_line2, area, city, district, state, pincode, is_default}]
    addresses = models.JSONField(default=list, blank=True)

    # Legacy single address (kept for backward compat)
    address = models.CharField(max_length=500, blank=True, default='')

    # Current live location
    live_address = models.CharField(max_length=500, blank=True, default='')
    live_lat = models.FloatField(default=0.0)
    live_lng = models.FloatField(default=0.0)

    # Bank/UPI (stored encrypted conceptually, displayed masked)
    bank_account_num = models.CharField(max_length=100, blank=True, default='')
    bank_ifsc = models.CharField(max_length=50, blank=True, default='')
    upi_id = models.CharField(max_length=100, blank=True, default='')

    service = models.JSONField(default=list, blank=True)       # favorites list
    servicehistory = models.JSONField(default=list, blank=True)
    wallet_balance = models.FloatField(default=0.0)
    allow_email_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.mail})"


class OTPVerification(models.Model):
    """OTP tokens for email verification and login."""
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)
    purpose = models.CharField(max_length=50, default='registration')  # registration, login

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.email} ({self.purpose})"


class ProviderRegistration(models.Model):
    """Pending service provider registrations awaiting admin approval."""
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('info_requested', 'Information Requested'),
    ]

    full_name = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    profile_photo = models.ImageField(upload_to='provider_profiles/', null=True, blank=True)
    service_category = models.CharField(max_length=100)

    aadhaar_card = models.FileField(upload_to='documents/aadhaar/', null=True, blank=True)
    pan_card = models.FileField(upload_to='documents/pan/', null=True, blank=True)
    has_business_registration = models.BooleanField(default=False)
    business_registration_cert = models.FileField(upload_to='documents/business/', null=True, blank=True)

    # Address fields
    address_line1 = models.CharField(max_length=200, blank=True, default='')
    address_line2 = models.CharField(max_length=200, blank=True, default='')
    area = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    district = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=10, blank=True, default='')
    gps_lat = models.FloatField(default=0.0)
    gps_lng = models.FloatField(default=0.0)
    gps_address = models.CharField(max_length=500, blank=True, default='')

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    terms_accepted = models.BooleanField(default=False)
    admin_note = models.TextField(blank=True, default='')
    allow_email_notifications = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.service_category} ({self.status})"


class Employee(models.Model):
    """Approved service provider / agent."""
    unique = models.AutoField(primary_key=True)
    profile_image = models.CharField(max_length=3000, blank=True, default='')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, default='')
    email = models.CharField(max_length=100, unique=True)
    passw = models.CharField(max_length=256, default='')
    gender = models.CharField(max_length=10, default='')
    service_provided = models.CharField(max_length=500)
    experience = models.PositiveIntegerField(default=0)
    specialization = models.CharField(max_length=1000, default='')
    description = models.TextField(max_length=2000, default='')
    address = models.TextField(max_length=600, default='')
    service_area = models.CharField(max_length=500, default='')
    starting_price = models.FloatField(default=299.0)
    certifications = models.TextField(blank=True, default='')
    no_of_service_provided = models.IntegerField(default=0)
    rating = models.FloatField(default=4.5)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=True)

    live_lat = models.FloatField(default=21.0150)
    live_lng = models.FloatField(default=75.5690)
    allow_email_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Bank Account Details (Approved)
    account_holder_name = models.CharField(max_length=200, blank=True, default='')
    bank_account_num = models.CharField(max_length=100, blank=True, default='')
    bank_ifsc = models.CharField(max_length=50, blank=True, default='')
    bank_name = models.CharField(max_length=100, blank=True, default='')
    branch_name = models.CharField(max_length=200, blank=True, default='')
    passbook_photo = models.ImageField(upload_to='passbooks/', null=True, blank=True)
    cheque_photo = models.ImageField(upload_to='cheques/', null=True, blank=True)
    
    # Bank verification tracking
    bank_verification_status = models.CharField(max_length=30, default='Unverified') # Unverified, Pending, Approved, Rejected, Correction Requested
    bank_correction_reason = models.TextField(blank=True, default='')
    
    # Temporary / Pending Bank details
    temp_account_holder_name = models.CharField(max_length=200, blank=True, default='')
    temp_bank_account_num = models.CharField(max_length=100, blank=True, default='')
    temp_bank_ifsc = models.CharField(max_length=50, blank=True, default='')
    temp_bank_name = models.CharField(max_length=100, blank=True, default='')
    temp_branch_name = models.CharField(max_length=200, blank=True, default='')
    temp_passbook_photo = models.ImageField(upload_to='passbooks/', null=True, blank=True)
    temp_cheque_photo = models.ImageField(upload_to='cheques/', null=True, blank=True)

    @property
    def wallet_balance(self):
        from csdata.models import WalletTransaction
        txs = WalletTransaction.objects.filter(employee=self)
        total_earnings = sum(tx.amount for tx in txs if tx.transaction_type == 'Collection' and tx.status == 'Completed')
        withdrawn_amount = sum(tx.amount for tx in txs if tx.transaction_type == 'Withdrawal' and tx.status == 'Completed')
        return total_earnings - withdrawn_amount

    def __str__(self):
        return f"{self.name} - {self.service_provided}"


class Bookings(models.Model):
    """Service bookings with full tracking and payment info."""
    unique = models.AutoField(primary_key=True)
    email = models.CharField(max_length=100)
    uniqueuser = models.IntegerField()
    uniqueservice = models.IntegerField()
    advance = models.BooleanField(default=False)

    # Scheduled date and time
    service_date = models.DateField(null=True, blank=True)
    service_time = models.TimeField(null=True, blank=True)

    # Status flow: Pending → Accepted/Declined → Heading to Location → Arrived → In Progress → Completed
    status = models.CharField(max_length=50, default='Pending')

    booking_address = models.CharField(max_length=500, default='')
    user_lat = models.FloatField(default=0.0)
    user_lng = models.FloatField(default=0.0)
    emp_lat = models.FloatField(default=21.0150)
    emp_lng = models.FloatField(default=75.5690)

    price = models.FloatField(default=299.00)
    discount_applied = models.FloatField(default=0.0)
    promo_code = models.CharField(max_length=50, default='', blank=True)
    payment_method = models.CharField(max_length=50, default='UPI')
    refund_status = models.CharField(max_length=50, default='None')  # None, Requested, Processed
    refund_reason = models.CharField(max_length=500, default='', blank=True)
    provider_dispute_reason = models.CharField(max_length=500, default='', blank=True)
    refund_proof_pic = models.ImageField(upload_to='refund_proofs/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def dummy_txn_id(self):
        if self.payment_method in ['Cash On Delivery', 'Pay After Service', 'Cash', 'Cash on Service', 'Pay on Delivery']:
            return 'Pay After Service'
        return f"TXN_SH_{100000000 + self.unique * 3}"

    def __str__(self):
        return f"Booking #{self.unique} - {self.status}"


class Ticket(models.Model):
    """Customer support tickets / complaints."""
    unique = models.AutoField(primary_key=True)
    mail = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, default='')
    ticketdetail = models.TextField(max_length=2000)
    attachment = models.FileField(upload_to='complaints/', null=True, blank=True)
    status = models.CharField(max_length=50, default='Pending')  # Pending, In Review, Resolved
    admin_response = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ticket #{self.unique} ({self.status})"


class Offer(models.Model):
    """Promotional coupons and discount offers."""
    unique = models.AutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.IntegerField(default=10)
    created_by = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    valid_till = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.code} - {self.discount_percent}% off"


class Advertisement(models.Model):
    """Platform advertisements managed by admin."""
    unique = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='advertisements/', null=True, blank=True)
    image_url = models.CharField(max_length=2000, blank=True, default='')
    target_url = models.CharField(max_length=1000, blank=True, default='')
    is_active = models.BooleanField(default=True)
    display_from = models.DateField(null=True, blank=True)
    display_till = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


class WalletTransaction(models.Model):
    """Transactions relating to service provider earnings collection and bank withdrawals."""
    unique = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=50) # Collection, Withdrawal
    booking_id = models.IntegerField(null=True, blank=True)
    amount = models.FloatField()
    status = models.CharField(max_length=50, default='Completed') # Pending, Completed, Rejected
    dummy_txn_id = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.transaction_type} #{self.unique} - {self.employee.name} - ₹{self.amount} ({self.status})"


class AdminSetting(models.Model):
    """System settings managed by admin."""
    key = models.CharField(max_length=100, unique=True)
    value = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.key}: {self.value}"

