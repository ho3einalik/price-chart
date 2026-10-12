import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus, TeamInvitation, InvitationStatus
from apps.tenancy.permissions import user_has_store_permission


@pytest.mark.django_db
class TestTeamRBAC:
    def test_invitation_lifecycle_and_acceptance(self):
        owner = User.objects.create_user(email="owner@test.com", password="password123", full_name="Owner User")
        business = Business.objects.create(name="Test Biz", owner=owner)
        store = Store.objects.create(business=business, name="Test Store")
        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)

        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. Send invite
        invite_res = client.post(
            "/api/v1/tenancy/invitations/",
            {
                "email": "employee@test.com",
                "role": Role.CONTENT_CREATOR,
                "custom_permissions": ["content.create", "content.submit"]
            },
            HTTP_X_STORE_ID=str(store.id)
        )
        assert invite_res.status_code == 201
        token = invite_res.data["token"]
        assert token.startswith("inv_")

        # 2. Accept invite as new user
        employee = User.objects.create_user(email="employee@test.com", password="password123", full_name="Staff User")
        emp_client = APIClient()
        emp_client.force_authenticate(user=employee)

        accept_res = emp_client.post(f"/api/v1/tenancy/invitations/{invite_res.data['id']}/accept/")
        assert accept_res.status_code == 200

        membership = StoreMembership.objects.get(store=store, user=employee)
        assert membership.role == Role.CONTENT_CREATOR
        assert membership.status == MembershipStatus.ACTIVE
        assert "content.create" in membership.custom_permissions

    def test_member_suspension_blocks_access(self):
        owner = User.objects.create_user(email="owner2@test.com", password="password123")
        business = Business.objects.create(name="Biz 2", owner=owner)
        store = Store.objects.create(business=business, name="Store 2")
        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER)

        staff = User.objects.create_user(email="staff2@test.com", password="password123")
        membership = StoreMembership.objects.create(
            store=store,
            user=staff,
            role=Role.SOCIAL_MEDIA_MANAGER,
            status=MembershipStatus.ACTIVE
        )

        assert user_has_store_permission(membership, "content.create") is True

        # Suspend member
        client = APIClient()
        client.force_authenticate(user=owner)
        res = client.post(f"/api/v1/tenancy/memberships/{membership.id}/suspend/", HTTP_X_STORE_ID=str(store.id))
        assert res.status_code == 200

        membership.refresh_from_db()
        assert membership.status == MembershipStatus.SUSPENDED
        assert user_has_store_permission(membership, "content.create") is False

        # Reactivate member
        reactivate_res = client.post(f"/api/v1/tenancy/memberships/{membership.id}/reactivate/", HTTP_X_STORE_ID=str(store.id))
        assert reactivate_res.status_code == 200
        membership.refresh_from_db()
        assert membership.status == MembershipStatus.ACTIVE
        assert user_has_store_permission(membership, "content.create") is True

    def test_granular_role_permission_enforcement(self):
        owner = User.objects.create_user(email="owner3@test.com", password="password123")
        business = Business.objects.create(name="Biz 3", owner=owner)
        store = Store.objects.create(business=business, name="Store 3")
        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER)

        creator = User.objects.create_user(email="creator@test.com", password="password123")
        creator_mem = StoreMembership.objects.create(
            store=store,
            user=creator,
            role=Role.CONTENT_CREATOR,
            status=MembershipStatus.ACTIVE
        )

        # Content Creator can create and submit, but cannot publish or approve
        assert user_has_store_permission(creator_mem, "content.create") is True
        assert user_has_store_permission(creator_mem, "content.submit") is True
        assert user_has_store_permission(creator_mem, "content.approve") is False
        assert user_has_store_permission(creator_mem, "content.publish") is False

        # Social Media Manager can approve and publish
        manager = User.objects.create_user(email="smm@test.com", password="password123")
        manager_mem = StoreMembership.objects.create(
            store=store,
            user=manager,
            role=Role.SOCIAL_MEDIA_MANAGER,
            status=MembershipStatus.ACTIVE
        )
        assert user_has_store_permission(manager_mem, "content.approve") is True
        assert user_has_store_permission(manager_mem, "content.publish") is True
