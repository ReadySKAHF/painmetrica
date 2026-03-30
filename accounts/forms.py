from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from accounts.models import DoctorProfile, PatientProfile

User = get_user_model()


class RegisterStepOneForm(forms.ModelForm):
    """Форма первого шага регистрации - личные данные (только для докторов)"""

    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8,
        max_length=20
    )

    class Meta:
        model = User
        fields = ['first_name', 'middle_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        """Проверка уникальности и корректности email"""
        email = self.cleaned_data.get('email')
        if not email:
            return email
        if len(email) > 50:
            raise ValidationError('Электронная почта не должна превышать 50 символов.')
        if User.objects.filter(email__iexact=email, is_email_verified=True).exists():
            raise ValidationError('Пользователь с такой Электронной почтой уже зарегистрирован')
        return email.lower()

    def clean_password(self):
        """Проверка пароля: только латиница, 8–20 символов, сложность"""
        import re
        password = self.cleaned_data.get('password')
        if not password:
            return password
        if re.search(r'[а-яА-ЯёЁ]', password):
            raise ValidationError('Пароль должен содержать только латинские буквы')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Пароль должен содержать как минимум 1 заглавную букву')
        if not re.search(r'\d', password):
            raise ValidationError('Пароль должен содержать как минимум 1 цифру')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;\'`~]', password):
            raise ValidationError('Пароль должен содержать как минимум 1 спец. символ')
        return password


class DoctorProfileForm(forms.ModelForm):
    """Форма второго шага регистрации - профессиональные данные доктора"""

    position = forms.CharField(
        label='Должность',
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50'})
    )
    workplace = forms.CharField(
        label='Место работы',
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': '50'})
    )

    class Meta:
        model = DoctorProfile
        fields = ['specialty', 'position', 'workplace', 'city', 'area_of_interest']
        widgets = {
            'specialty': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'area_of_interest': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class OTPVerificationForm(forms.Form):
    """Форма для проверки OTP кода"""

    otp_code = forms.CharField(
        label='OTP код',
        max_length=4,
        min_length=4,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '4',
            'pattern': '[0-9]{4}',
            'inputmode': 'numeric'
        })
    )

    def clean_otp_code(self):
        """Проверка формата OTP кода"""
        code = self.cleaned_data.get('otp_code')
        if not code.isdigit():
            raise ValidationError('OTP код должен состоять только из цифр.')
        return code


class LoginForm(forms.Form):
    """Форма входа в систему"""

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )


class PatientManualCreateForm(forms.Form):
    """Форма ручного создания пациента доктором (без email/пароля)"""

    DURATION_CHOICES = [
        ('', 'Длительность не указана'),
        ('1w', 'Менее 1 недели'),
        ('1m', '1–4 недели'),
        ('3m', '1–3 месяца'),
        ('6m', '3–6 месяцев'),
        ('1y', '6–12 месяцев'),
        ('1y+', 'Более 1 года'),
    ]

    first_name = forms.CharField(label='Имя', max_length=150)
    middle_name = forms.CharField(label='Отчество', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150)
    date_of_birth = forms.DateField(label='Дата рождения', required=False)
    diagnosis = forms.CharField(label='Диагноз', max_length=500, required=False)
    pain_location = forms.CharField(label='Локализация боли', max_length=200, required=False)
    pain_duration = forms.ChoiceField(label='Длительность', choices=DURATION_CHOICES, required=False)


class PatientRegisterViaInviteForm(forms.Form):
    """Форма регистрации пациента по ссылке-приглашению"""

    first_name = forms.CharField(label='Имя', max_length=150)
    middle_name = forms.CharField(label='Отчество', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150)
    date_of_birth = forms.DateField(label='Дата рождения', required=True)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput(), min_length=8)
