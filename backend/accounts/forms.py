from django import forms

from .phones import normalize_il_phone


class PhoneForm(forms.Form):
    phone = forms.CharField(label="טלפון", max_length=20)

    def clean_phone(self):
        normalized = normalize_il_phone(self.cleaned_data["phone"])
        if normalized is None:
            raise forms.ValidationError("מספר טלפון לא תקין")
        return normalized


class CodeForm(forms.Form):
    code = forms.RegexField(label="קוד", regex=r"^\d{6}$",
                            error_messages={"invalid": "קוד בן 6 ספרות"})


class OnboardingForm(forms.Form):
    display_name = forms.CharField(label="שם תצוגה", max_length=50)
    avatar = forms.FileField(label="תמונת פרופיל", required=False)
