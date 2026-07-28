import logging

logger = logging.getLogger("accounts.sms")


def send_sms(phone_e164, text):
    """MVP stub — logs the message. Codes are also visible in the OtpCode
    admin. Real provider (Twilio / 019 / InforU) drops in here later; keep
    this exact signature."""
    logger.warning("SMS→%s: %s", phone_e164, text)
