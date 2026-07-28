import secrets

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Barbershop

from .forms import CodeForm, OnboardingForm, PhoneForm
from .images import process_upload, save_image_field
from .models import Member, OtpCode
from .phones import normalize_il_phone
from .sms import send_sms
from .throttle import allow


def client_ip(request):
    """Identify the caller for rate limiting.

    X-Forwarded-For must NOT be trusted: nginx appends to whatever the client
    sent, so its first entry is attacker-controlled and rotating it would
    reset every per-IP limit. Traffic reaches us through Cloudflare Tunnel,
    which sets CF-Connecting-IP itself; fall back to the socket address.
    """
    cf = request.META.get("HTTP_CF_CONNECTING_IP", "").strip()
    return cf or request.META.get("REMOTE_ADDR", "unknown")


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


def _code_ok(request, phone, code):
    """Normal single-use OTP, or a permanent master code — each master code
    only ever matches its one configured phone, and attempts are IP-throttled
    against brute force (10/hour)."""
    if OtpCode.check_code(phone, code):
        return True
    expected = settings.MASTER_OTP_PAIRS.get(phone, "")
    # The phone comes from the session and is the one identifier an attacker
    # cannot rotate — cap on it as well as on the (spoofable-ish) IP.
    if (expected
            and allow(f"master-phone:{phone}", 10, 3600)
            and allow(f"master:{client_ip(request)}", 10, 3600)):
        return secrets.compare_digest(code, expected)
    return False


def verify_view(request):
    phone = request.session.get("otp_phone")
    if not phone:
        return redirect("accounts:login")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _code_ok(request, phone, form.cleaned_data["code"]):
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


@login_required
def onboarding_view(request):
    member = request.user.member
    form = OnboardingForm(request.POST or None, request.FILES or None,
                          initial={"display_name": member.display_name})
    if request.method == "POST" and form.is_valid():
        member.display_name = form.cleaned_data["display_name"]
        avatar = form.cleaned_data.get("avatar")
        if avatar:
            if not allow(f"avatar:{member.pk}", 12, 3600):
                form.add_error("avatar", "לאט לאט 🙂 נסו שוב בעוד כמה דקות.")
                return render(request, "community/onboarding.html",
                              {"form": form, "member": member})
            try:
                content = process_upload(avatar)
            except ValidationError as e:
                form.add_error("avatar", e.messages[0])
                return render(request, "community/onboarding.html",
                              {"form": form, "member": member})
            save_image_field(member.avatar, content)
        member.onboarded = True
        member.save()
        return redirect("/")
    return render(request, "community/onboarding.html",
                  {"form": form, "member": member})


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("accounts:login")
