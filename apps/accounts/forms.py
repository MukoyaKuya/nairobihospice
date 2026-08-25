from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import RoleChoices, StaffProfile, User


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition duration-150',
            'placeholder': 'clinician@nairobihospice.or.ke',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition duration-150',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        })
    )


class MFAEnrollmentForm(forms.Form):
    token = forms.CharField(
        max_length=6,
        min_length=6,
        label='Authenticator code',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 text-center tracking-widest text-lg font-mono rounded-xl border border-slate-300 focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
            'placeholder': '123456',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autofocus': 'autofocus',
        })
    )


class MFAVerifyForm(forms.Form):
    token = forms.CharField(
        max_length=6,
        min_length=6,
        required=False,
        label='Authenticator code',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 text-center tracking-widest text-lg font-mono rounded-xl border border-slate-300 focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
            'placeholder': '123456',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autofocus': 'autofocus',
        })
    )
    recovery_code = forms.CharField(
        max_length=32,
        required=False,
        label='Recovery code',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 text-center uppercase tracking-widest font-mono text-sm rounded-xl border border-slate-300 focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
            'placeholder': 'e.g. A1B2C3D4E5',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('token') and not cleaned_data.get('recovery_code'):
            raise forms.ValidationError('Enter an authenticator code or a recovery code.')
        if cleaned_data.get('token') and cleaned_data.get('recovery_code'):
            raise forms.ValidationError('Use one verification method at a time.')
        return cleaned_data


class StaffUserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input'}))
    role = forms.ChoiceField(choices=RoleChoices.choices)
    license_number = forms.CharField(required=False)
    department = forms.CharField(required=False, initial='Palliative Care Unit')
    qualifications = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            StaffProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                license_number=self.cleaned_data.get('license_number', ''),
                department=self.cleaned_data.get('department', 'Palliative Care Unit'),
                qualifications=self.cleaned_data.get('qualifications', ''),
            )
        return user


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    profile_picture = forms.ImageField(required=False)

    class Meta:
        model = StaffProfile
        fields = ['profile_picture', 'qualifications', 'license_number']
