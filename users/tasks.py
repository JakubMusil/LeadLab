"""
Celery tasks for Users — invitation emails and password-reset emails.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invitation_email(self, invitation_id: str):
    """
    Send an invitation email for a pending Invitation.

    The email contains a link the recipient follows to accept the invitation
    (creating an account if they do not already have one).
    """
    from django.core.mail import send_mail
    from django.conf import settings

    from firms.models import Invitation

    try:
        invitation = Invitation.objects.select_related("firm", "invited_by").get(
            id=invitation_id
        )
    except Invitation.DoesNotExist:
        logger.error("send_invitation_email: Invitation %s not found.", invitation_id)
        return

    frontend_url = getattr(settings, "FRONTEND_URL", "")
    accept_url = f"{frontend_url}/invitations/{invitation.token}/accept"

    invited_by_name = (
        invitation.invited_by.full_name if invitation.invited_by else "Someone"
    )

    subject = f"You've been invited to join {invitation.firm.name} on LeadLab"
    message = (
        f"Hi,\n\n"
        f"{invited_by_name} has invited you to join {invitation.firm.name} on LeadLab "
        f"as a {invitation.get_role_display()}.\n\n"
        f"Accept your invitation here:\n{accept_url}\n\n"
        f"This link expires in 7 days.\n\n"
        f"If you did not expect this invitation, you can safely ignore this email.\n\n"
        f"— The LeadLab Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
        logger.info(
            "send_invitation_email: Sent invitation %s to '%s'.",
            invitation_id,
            invitation.email,
        )
    except Exception as exc:
        logger.error(
            "send_invitation_email: Failed to send invitation %s: %s",
            invitation_id,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id: str, token: str, uid: str):
    """
    Send a password-reset email containing a one-time token link.
    """
    from django.core.mail import send_mail
    from django.conf import settings

    from users.models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("send_password_reset_email: User %s not found.", user_id)
        return

    frontend_url = getattr(settings, "FRONTEND_URL", "")
    reset_url = f"{frontend_url}/password-reset/confirm/{uid}/{token}"

    subject = "Reset your LeadLab password"
    message = (
        f"Hi {user.full_name},\n\n"
        f"You requested a password reset for your LeadLab account.\n\n"
        f"Click the link below to set a new password (valid for 24 hours):\n"
        f"{reset_url}\n\n"
        f"If you did not request a password reset, please ignore this email.\n\n"
        f"— The LeadLab Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(
            "send_password_reset_email: Sent reset email to user %s.", user_id
        )
    except Exception as exc:
        logger.error(
            "send_password_reset_email: Failed to send reset email for user %s: %s",
            user_id,
            exc,
        )
        raise self.retry(exc=exc)
