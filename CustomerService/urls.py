from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from CustomerService import views

urlpatterns = [
    # Django admin
    path('django-admin/', admin.site.urls),

    # ── Public pages ──
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('provider/<int:unique>/', views.provider_profile_public, name='provider_profile_public'),

    # ── Authentication ──
    path('signup/', views.signup, name='signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('register-provider/', views.register_provider, name='register_provider'),
    path('signin/', views.signin, name='signin'),
    path('send-login-otp/', views.send_login_otp, name='send_login_otp'),
    path('logout/', views.logout_view, name='logout'),

    # ── Customer panel ──
    path('bookservice/', views.bookservice, name='bookservice'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('favorites/', views.favorites, name='favorites'),
    path('toggle_favorite/<int:employee_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('servicehistory/', views.servicehistory, name='servicehistory'),
    path('usercommon/<int:unique>/', views.usercommon, name='usercommon'),
    path('payment/<int:unique>/', views.payment_page, name='payment_page'),
    path('book/<int:unique>/', views.payment_page, name='book_service'),
    path('process_payment/', views.process_payment, name='process_payment'),
    path('validate_coupon/', views.validate_coupon, name='validate_coupon'),
    path('request_refund/<int:booking_id>/', views.request_refund, name='request_refund'),
    path('raiseticket/', views.raiseticket, name='raiseticket'),

    # ── Live tracking ──
    path('track/<int:booking_id>/', views.track_booking, name='track_booking'),
    path('api/track/<int:booking_id>/', views.get_booking_tracking, name='get_booking_tracking'),
    path('api/track/<int:booking_id>/control/', views.simulation_control, name='simulation_control'),

    # ── Service Provider (Employee) panel ──
    path('employeeservicebooked/', views.employeeservicebooked, name='employeeservicebooked'),
    path('agent/add_offer/', views.agent_add_offer, name='agent_add_offer'),
    path('agent/toggle_booking/<int:booking_id>/<str:action>/', views.agent_toggle_booking, name='agent_toggle_booking'),
    path('agent/update_bank/', views.agent_update_bank, name='agent_update_bank'),
    path('agent/request_withdrawal/', views.agent_request_withdrawal, name='agent_request_withdrawal'),

    # ── Admin panel ──
    path('aadmin/', views.aadmin, name='aadmin'),
    path('addemp/', views.addemp, name='addemp'),
    path('userinfo/', views.userinfo, name='userinfo'),
    path('suspend_user/<int:user_id>/', views.suspend_user, name='suspend_user'),
    path('employeeinfo/', views.employeeinfo, name='employeeinfo'),
    path('servicebooked/', views.servicebooked, name='servicebooked'),
    path('ticketraised/', views.ticketraised, name='ticketraised'),
    path('employeeinfocommon/<int:employee_id>/', views.employeeinfocommon, name='employeeinfocommon'),
    path('delete_employee/<int:employee_id>/', views.delete_employee, name='delete_employee'),
    path('admin/manage_complaint/<int:ticket_id>/<str:action>/', views.admin_manage_complaint, name='admin_manage_complaint'),
    path('admin/manage_ad/', views.admin_manage_ad, name='admin_manage_ad'),
    path('admin/manage_offer/', views.admin_manage_offer, name='admin_manage_offer'),
    path('admin/pending-providers/', views.admin_pending_providers, name='admin_pending_providers'),
    path('admin/review-provider/<int:provider_id>/', views.admin_review_provider, name='admin_review_provider'),
    path('admin/approve-provider/<int:provider_id>/', views.admin_approve_provider, name='admin_approve_provider'),
    path('admin/reject-provider/<int:provider_id>/', views.admin_reject_provider, name='admin_reject_provider'),
    path('admin/wallet/', views.admin_wallet, name='admin_wallet'),
    path('admin/approve_bank/<int:employee_id>/', views.admin_approve_bank, name='admin_approve_bank'),
    path('admin/reject_bank/<int:employee_id>/', views.admin_reject_bank, name='admin_reject_bank'),
    path('admin/approve_withdrawal/<int:tx_id>/', views.admin_approve_withdrawal, name='admin_approve_withdrawal'),
    path('admin/reject_withdrawal/<int:tx_id>/', views.admin_reject_withdrawal, name='admin_reject_withdrawal'),
    path('admin/process_refund/<int:booking_id>/', views.admin_process_refund, name='admin_process_refund'),
    path('admin/cancel_booking/<int:booking_id>/', views.admin_cancel_booking, name='admin_cancel_booking'),
    path('admin/complete_booking/<int:booking_id>/', views.admin_complete_booking, name='admin_complete_booking'),
    path('admin/delete_booking/<int:booking_id>/', views.admin_delete_booking, name='admin_delete_booking'),
    
    # ── Additional features ──
    path('booking/confirm/<int:booking_id>/', views.customer_confirm_booking, name='customer_confirm_booking'),
    path('booking/raise_issue/<int:booking_id>/', views.customer_raise_issue, name='customer_raise_issue'),
    path('booking/cancel/<int:booking_id>/', views.customer_cancel_booking, name='customer_cancel_booking'),
    path('api/track/<int:booking_id>/update_location/', views.provider_update_location, name='provider_update_location'),

    # ── Password Recovery & Email Policy Toggles ──
    path('forgot-password/', views.forgot_password_request, name='forgot_password_request'),
    path('forgot-password/verify/', views.verify_forgot_otp, name='forgot_verify_otp'),
    path('forgot-password/reset/', views.reset_password, name='forgot_reset_password'),
    path('admin/toggle_customer_email/<int:user_id>/', views.toggle_customer_email, name='toggle_customer_email'),
    path('admin/toggle_provider_status/<int:employee_id>/', views.toggle_provider_status, name='toggle_provider_status'),
    path('admin/toggle_global_email/', views.toggle_global_email, name='toggle_global_email'),
    path('api/admin/active_bookings/', views.api_admin_active_bookings, name='api_admin_active_bookings'),
    path('admin/create-booking/', views.admin_create_booking, name='admin_create_booking'),
    path('admin/customer-detail/<int:user_id>/', views.admin_customer_detail, name='admin_customer_detail'),
    path('admin/toggle_provider_email/<int:employee_id>/', views.toggle_provider_email, name='toggle_provider_email'),
    path('admin/toggle_global_email_category/<str:category>/', views.toggle_global_email_category, name='toggle_global_email_category'),
    path('admin/investigate_refund/<int:booking_id>/', views.admin_investigate_refund, name='admin_investigate_refund'),
    path('admin/confirm_refund/<int:booking_id>/', views.admin_confirm_refund, name='admin_confirm_refund'),
    path('admin/decline_refund/<int:booking_id>/', views.admin_decline_refund, name='admin_decline_refund'),
    path('agent/dispute_refund/<int:booking_id>/<str:action>/', views.agent_dispute_refund, name='agent_dispute_refund'),
    path('admin/refunds/', views.admin_refunds_list, name='admin_refunds_list'),
    path('agent/refund_complaints/', views.agent_refund_complaints, name='agent_refund_complaints'),
]

# Serve media files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
