from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Barbershop

from .forms import CodeForm, PhoneForm
from .models import Member, OtpCode
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


def verify_view(request):
    phone = request.session.get("otp_phone")
    if not phone:
        return redirect("accounts:login")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if OtpCode.check_code(phone, form.cleaned_data["code"]):
            app = find_approved_application(phone)
            if app is None:  # approval revoked between request and verify
                return redirect("accounts:login")
            user, _ = User.objects.get_or_create(username=phone)
            member, _ = Member.objects.get_or_create(
                user=user,
                defaults={"application": app, "phone_e164": phone,
                          "display_name": app.owner_name[:50]},
            )
            auth_login(request, user)
            del request.session["otp_phone"]
            return redirect("/" if member.onboarded else "/welcome")
        form.add_error("code", "קוד שגוי או שפג תוקפו")
    return render(request, "community/verify.html", {"form": form})


def onboarding_view(request):  # replaced in Task 8
    return redirect("/")


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("accounts:login")
