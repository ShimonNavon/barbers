from django.shortcuts import redirect, render

from catalog.models import Barbershop

from .forms import CodeForm, PhoneForm
from .models import OtpCode
from .phones import normalize_il_phone
from .sms import send_sms
from .throttle import allow


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() or
            request.META.get("REMOTE_ADDR", "unknown"))


def find_approved_application(phone_e164):
    """Match a normalized phone against approved applications. Their `phone`
    is free text, so normalize each candidate at comparison time. Community
    scale is hundreds of rows — a scan is fine."""
    for app in Barbershop.objects.filter(approved=True):
        if normalize_il_phone(app.phone) == phone_e164:
            return app
    return None


def login_view(request):
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        # throttle first — throttled requests look identical (no oracle)
        if (allow(f"otp-ip:{client_ip(request)}", 10, 3600)
                and allow(f"otp-phone:{phone}", 3, 900)):
            app = find_approved_application(phone)
            if app is not None:
                otp = OtpCode.issue(phone)
                send_sms(phone, f"קוד הכניסה שלך לקהילה: {otp.code}")
        request.session["otp_phone"] = phone
        return redirect("accounts:verify")
    return render(request, "community/login.html", {"form": form})


def verify_view(request):  # replaced in Task 6
    return render(request, "community/verify.html", {"form": CodeForm()})


def onboarding_view(request):  # replaced in Task 8
    return redirect("/")


def logout_view(request):  # replaced in Task 6
    return redirect("accounts:login")
