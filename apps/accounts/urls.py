from django.urls import path, reverse_lazy

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.PCMSLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('mfa/enroll/', views.MFAEnrollmentView.as_view(), name='mfa_enroll'),
    path('mfa/verify/', views.MFAVerifyView.as_view(), name='mfa_verify'),
    path('password-reset/', views.PasswordResetRequestView.as_view(
        template_name='accounts/password_reset_form.html',
        email_template_name='accounts/password_reset_email.txt',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', views.PasswordResetRequestDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', views.PasswordResetRequestConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', views.PasswordResetRequestCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('staff/', views.StaffDirectoryView.as_view(), name='staff_list'),
]
