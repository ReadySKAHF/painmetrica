from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    # Регистрация (3 шага)
    path('register/', views.RegisterStepOneView.as_view(), name='register_step_one'),
    path('register/professional/', views.RegisterStepTwoView.as_view(), name='register_step_two'),
    path('register/verify/', views.RegisterVerifyOTPView.as_view(), name='register_verify'),

    # Вход (2 экрана)
    path('login/', views.LoginView.as_view(), name='login'),
    path('login/verify/', views.LoginVerifyOTPView.as_view(), name='login_verify'),

    # Выход
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # API повторной отправки OTP
    path('api/resend-otp/', views.ResendOTPView.as_view(), name='resend_otp'),

    # Регистрация пациентов
    path('api/send-patient-invitation/', views.SendPatientInvitationView.as_view(), name='send_patient_invitation'),
    path('api/manual-patient-create/', views.ManualPatientCreateView.as_view(), name='manual_patient_create'),
    path('register/patient/invite/<uuid:token>/', views.PatientRegisterViaInviteStep1View.as_view(), name='patient_register_invite'),
    path('register/patient/verify/', views.PatientRegisterViaInviteVerifyView.as_view(), name='patient_register_invite_verify'),
]
