from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import CustomUser

class CitizenProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded p-3 text-white', 'required': True}),
            'last_name': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded p-3 text-white', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded p-3 text-white', 'required': True}),
        }

class TailwindPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-gray-700 border border-gray-600 rounded p-3 text-white mb-4'})

