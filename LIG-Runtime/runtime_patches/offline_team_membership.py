from __future__ import annotations

import hashlib
from pathlib import Path


EXPECTED_SHA256 = "b9d35dd742e94f8fa372bef8aac0c3d6a200fa7f51b48a2d2f7b50ad45874841"


def apply_offline_team_membership_patch(path: Path) -> None:
    source = path.read_bytes().replace(b"\r\n", b"\n")
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow api/apps/restful_apis/tenant_api.py: "
            f"expected {EXPECTED_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    text = _replace_once(text, "import asyncio\nimport logging\nfrom typing import Set\n\n", "import hashlib\n\n", "mail invitation imports")
    text = _replace_once(text, "from api.db.db_models import UserTenant\n", "from api.db.db_models import DB, UserTenant\n", "membership database dependency")
    text = _replace_once(text, "from api.utils.web_utils import send_invite_email\nfrom common import settings\n", "", "mail invitation dependencies")
    text = _replace_once(
        text,
        "# Keeps strong references to fire-and-forget tasks so they are not GC'd before completion.\n"
        "_background_tasks: Set[asyncio.Task] = set()\n\n\n",
        "",
        "mail invitation background task registry",
    )
    old = '''    invite_user_email = req["email"]
    invite_users = UserService.query(email=invite_user_email)
    if not invite_users:
        return get_data_error_result(message="User not found.")

    user_id_to_invite = invite_users[0].id
    user_tenants = UserTenantService.query(user_id=user_id_to_invite, tenant_id=tenant_id)
    if user_tenants:
        user_tenant_role = user_tenants[0].role
        if user_tenant_role == UserTenantRole.NORMAL:
            return get_data_error_result(message=f"{invite_user_email} is already in the team.")
        if user_tenant_role == UserTenantRole.OWNER:
            return get_data_error_result(message=f"{invite_user_email} is the owner of the team.")
        return get_data_error_result(message=f"{invite_user_email} is in the team, but the role: {user_tenant_role} is invalid.")

    UserTenantService.save(
        id=get_uuid(),
        user_id=user_id_to_invite,
        tenant_id=tenant_id,
        invited_by=current_user.id,
        role=UserTenantRole.INVITE,
        status=StatusEnum.VALID.value,
    )

    try:
        user_name = ""
        _, user = UserService.get_by_id(current_user.id)
        if user:
            user_name = user.nickname

        def _on_invite_email_done(done_task: asyncio.Task) -> None:
            _background_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                logging.warning("Invite email task cancelled: tenant_id=%s to=%s", tenant_id, invite_user_email)
            except Exception:
                logging.exception("Invite email task failed: tenant_id=%s to=%s", tenant_id, invite_user_email)

        task = asyncio.create_task(
            send_invite_email(
                to_email=invite_user_email,
                invite_url=settings.MAIL_FRONTEND_URL,
                tenant_id=tenant_id,
                inviter=user_name or current_user.email,
            )
        )
        if isinstance(task, asyncio.Task):
            _background_tasks.add(task)
            task.add_done_callback(_on_invite_email_done)
    except Exception as exc:
        logging.exception(f"Failed to send invite email to {invite_user_email}: {exc}")
        return get_json_result(
            data=False,
            message="Failed to send invite email.",
            code=RetCode.SERVER_ERROR,
        )

    user = invite_users[0].to_dict()
'''
    new = '''    member_email = req["email"].strip()
    members = UserService.query(email=member_email, status=StatusEnum.VALID.value)
    if not members:
        return get_data_error_result(message="Registered active user not found.")

    member_id = members[0].id
    lock_digest = hashlib.sha256(f"{tenant_id}:{member_id}".encode()).hexdigest()
    with DB.lock(f"team_member:{lock_digest[:52]}", timeout=10):
        memberships = UserTenantService.query(user_id=member_id, tenant_id=tenant_id)
        if memberships:
            membership = memberships[0]
            if membership.role == UserTenantRole.NORMAL:
                return get_data_error_result(message=f"{member_email} is already in the team.")
            if membership.role == UserTenantRole.OWNER:
                return get_data_error_result(message=f"{member_email} is the owner of the team.")
            UserTenantService.filter_update(
                [UserTenant.tenant_id == tenant_id, UserTenant.user_id == member_id],
                {
                    "role": UserTenantRole.NORMAL,
                    "status": StatusEnum.VALID.value,
                    "invited_by": current_user.id,
                },
            )
        else:
            UserTenantService.save(
                id=get_uuid(),
                user_id=member_id,
                tenant_id=tenant_id,
                invited_by=current_user.id,
                role=UserTenantRole.NORMAL,
                status=StatusEnum.VALID.value,
            )

    user = members[0].to_dict()
'''
    text = _replace_once(text, old, new, "email invitation workflow")
    path.write_text(text, encoding="utf-8")


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one {label} site")
    return text.replace(old, new)
