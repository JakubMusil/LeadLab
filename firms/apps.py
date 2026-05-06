from django.apps import AppConfig


# ---------------------------------------------------------------------------
# Thread-local helpers – mirror of crm.apps pattern so that firms-level code
# (e.g. invitation acceptance) can attach the acting user to audit entries.
# ---------------------------------------------------------------------------

import logging
import threading

_local = threading.local()
_logger = logging.getLogger(__name__)


def set_current_user(user) -> None:
    """Store *user* in thread-local storage for the duration of the request."""
    _local.user = user


def get_current_user():
    """Return the user stored for the current thread, or ``None``."""
    return getattr(_local, "user", None)


def _is_firm_being_deleted(firm_pk) -> bool:
    """Return True if this Firm is currently being cascade-deleted."""
    deleting = getattr(_local, "deleting_firm_pks", None)
    return deleting is not None and str(firm_pk) in deleting


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _log_audit(firm, actor, action, target_type, target_id, payload=None):
    """Create a PermissionAuditLog entry.  Skips during cascade deletes or migrations."""
    # Skip if this firm is currently being deleted (cascade)
    if _is_firm_being_deleted(firm.pk):
        return
    try:
        from firms.models import PermissionAuditLog
        PermissionAuditLog.objects.create(
            firm=firm,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            payload=payload or {},
        )
    except Exception:
        # The most likely cause is a DB error during migrations or an unexpected
        # table state.  We log at WARNING level so it's visible but does not
        # break the main operation.
        _logger.warning(
            "Failed to create PermissionAuditLog entry: action=%s target=%s/%s",
            action,
            target_type,
            target_id,
            exc_info=True,
        )


def _on_firm_pre_delete(sender, instance, **kwargs):
    """Mark the Firm as being deleted so child signal handlers can skip audit logging."""
    if not hasattr(_local, "deleting_firm_pks"):
        _local.deleting_firm_pks = set()
    _local.deleting_firm_pks.add(str(instance.pk))


def _on_firm_post_delete(sender, instance, **kwargs):
    """Clear the deletion marker for this Firm after deletion completes."""
    deleting = getattr(_local, "deleting_firm_pks", None)
    if deleting is not None:
        deleting.discard(str(instance.pk))


def _on_firm_post_save(sender, instance, created, **kwargs):
    """Seed system roles for a newly created Firm."""
    if not created:
        return
    try:
        from firms.migrations._seed_helpers import create_system_roles_for_firm
        create_system_roles_for_firm(instance)
    except Exception:
        _logger.warning(
            "Failed to seed system roles for new Firm %s",
            instance.pk,
            exc_info=True,
        )


def _on_role_post_save(sender, instance, created, **kwargs):
    action = "role.created" if created else "role.updated"
    _log_audit(
        firm=instance.firm,
        actor=get_current_user(),
        action=action,
        target_type="role",
        target_id=instance.pk,
        payload={"code": instance.code, "name": instance.name, "is_system": instance.is_system},
    )


def _on_role_post_delete(sender, instance, **kwargs):
    _log_audit(
        firm=instance.firm,
        actor=get_current_user(),
        action="role.deleted",
        target_type="role",
        target_id=instance.pk,
        payload={"code": instance.code, "name": instance.name},
    )


def _on_membership_post_save(sender, instance, created, **kwargs):
    action = "membership.created" if created else "membership.updated"
    _log_audit(
        firm=instance.firm,
        actor=get_current_user(),
        action=action,
        target_type="membership",
        target_id=instance.pk,
        payload={"user_id": str(instance.user_id), "role": instance.role},
    )


def _on_membership_post_delete(sender, instance, **kwargs):
    _log_audit(
        firm=instance.firm,
        actor=get_current_user(),
        action="membership.deleted",
        target_type="membership",
        target_id=instance.pk,
        payload={"user_id": str(instance.user_id), "role": instance.role},
    )


class FirmsConfig(AppConfig):
    name = 'firms'

    def ready(self) -> None:
        from django.db.models.signals import pre_delete, post_save, post_delete
        from firms.models import Firm, Role, Membership

        # Track firm deletions to avoid orphaned audit log entries
        pre_delete.connect(
            _on_firm_pre_delete,
            sender=Firm,
            weak=False,
            dispatch_uid="firms_audit_firm_pre_delete",
        )
        post_delete.connect(
            _on_firm_post_delete,
            sender=Firm,
            weak=False,
            dispatch_uid="firms_audit_firm_post_delete",
        )
        post_save.connect(
            _on_firm_post_save,
            sender=Firm,
            weak=False,
            dispatch_uid="firms_seed_roles_firm_post_save",
        )

        post_save.connect(
            _on_role_post_save,
            sender=Role,
            weak=False,
            dispatch_uid="firms_audit_role_post_save",
        )
        post_delete.connect(
            _on_role_post_delete,
            sender=Role,
            weak=False,
            dispatch_uid="firms_audit_role_post_delete",
        )
        post_save.connect(
            _on_membership_post_save,
            sender=Membership,
            weak=False,
            dispatch_uid="firms_audit_membership_post_save",
        )
        post_delete.connect(
            _on_membership_post_delete,
            sender=Membership,
            weak=False,
            dispatch_uid="firms_audit_membership_post_delete",
        )
