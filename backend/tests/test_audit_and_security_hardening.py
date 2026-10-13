import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.tenancy.models import (
    Business, Store, StoreMembership, Role, MembershipStatus,
    TeamInvitation, InvitationStatus
)
import secrets
from django.utils import timezone
from apps.inventory.models import Warehouse
from apps.catalog.models import Product, ProductVariant
from apps.orders.models import Order, Customer, PaymentStatus, OrderStatus
from apps.payments.models import PaymentTransaction, PaymentVerificationStatus


@pytest.mark.django_db
class TestAuditAndSecurityHardening:
    @pytest.fixture
    def setup_platform(self):
        owner = User.objects.create_user(email="owner_sec@test.com", password="pass123", full_name="Sec Owner")
        biz = Business.objects.create(name="Sec Biz", owner=owner)
        store = Store.objects.create(business=biz, name="Sec Store")
        owner_membership = StoreMembership.objects.create(
            store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE, is_active=True
        )

        staff = User.objects.create_user(email="staff_sec@test.com", password="pass123", full_name="Sec Staff")
        staff_membership = StoreMembership.objects.create(
            store=store, user=staff, role=Role.OPS_MANAGER, status=MembershipStatus.ACTIVE, is_active=True
        )

        return {
            'owner': owner,
            'biz': biz,
            'store': store,
            'staff': staff,
            'staff_membership': staff_membership,
            'owner_membership': owner_membership,
        }

    def test_suspended_member_blocked_across_endpoints(self, setup_platform):
        store = setup_platform['store']
        staff = setup_platform['staff']
        membership = setup_platform['staff_membership']

        # Suspend the staff membership
        membership.status = MembershipStatus.SUSPENDED
        membership.is_active = False
        membership.save()

        client = APIClient()
        client.force_authenticate(user=staff)

        # 1. Catalog access attempt
        res1 = client.get('/api/v1/catalog/products/', HTTP_X_STORE_ID=str(store.id))
        assert res1.status_code == status.HTTP_403_FORBIDDEN

        # 2. Orders access attempt
        res2 = client.get('/api/v1/orders/', HTTP_X_STORE_ID=str(store.id))
        assert res2.status_code == status.HTTP_403_FORBIDDEN

        # 3. Tasks access attempt
        res3 = client.get('/api/v1/tasks/tasks/', HTTP_X_STORE_ID=str(store.id))
        assert res3.status_code == status.HTTP_403_FORBIDDEN

    def test_privilege_escalation_role_assignment(self, setup_platform):
        store = setup_platform['store']
        staff = setup_platform['staff']
        owner = setup_platform['owner']

        client = APIClient()
        client.force_authenticate(user=staff)

        # Staff lacks admin permission to create invitations -> 403 Forbidden
        res_staff = client.post(
            '/api/v1/tenancy/invitations/',
            {'email': 'new_owner@test.com', 'role': Role.OWNER},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_staff.status_code == status.HTTP_403_FORBIDDEN

        # Owner cannot invite someone directly as OWNER -> 400 Bad Request
        owner_client = APIClient()
        owner_client.force_authenticate(user=owner)
        res_owner_invite = owner_client.post(
            '/api/v1/tenancy/invitations/',
            {'email': 'new_owner@test.com', 'role': Role.OWNER},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_owner_invite.status_code == status.HTTP_400_BAD_REQUEST
        assert 'OWNER' in str(res_owner_invite.data)

        # Owner attempts to demote self as last active owner -> rejected
        owner_mem = setup_platform['owner_membership']
        res_demote = owner_client.patch(
            f'/api/v1/tenancy/memberships/{owner_mem.id}/',
            {'role': Role.READ_ONLY},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_demote.status_code == status.HTTP_400_BAD_REQUEST

    def test_store_creation_cross_business_protection(self, setup_platform):
        attacker = User.objects.create_user(email="attacker@test.com", password="pass123", full_name="Attacker")
        victim_biz = setup_platform['biz']

        client = APIClient()
        client.force_authenticate(user=attacker)

        res = client.post('/api/v1/tenancy/stores/', {
            'business': str(victim_biz.id),
            'name': 'Hacked Store'
        })
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'business' in res.data

    def test_invitation_email_binding_and_cross_user_acceptance(self, setup_platform):
        store = setup_platform['store']
        owner = setup_platform['owner']

        # Issue invitation to intended user
        invite = TeamInvitation.objects.create(
            store=store,
            email="intended_user@test.com",
            role=Role.CONTENT_CREATOR,
            inviter=owner,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )

        # Attacker tries to accept intended user's invitation
        attacker = User.objects.create_user(email="impostor@test.com", password="pass123", full_name="Impostor")
        client = APIClient()
        client.force_authenticate(user=attacker)

        res_impostor = client.post('/api/v1/tenancy/invitations/accept/', {'token': invite.token})
        assert res_impostor.status_code == status.HTTP_403_FORBIDDEN

        # Intended user accepts -> success
        intended = User.objects.create_user(email="intended_user@test.com", password="pass123", full_name="Intended")
        intended_client = APIClient()
        intended_client.force_authenticate(user=intended)

        res_ok = intended_client.post('/api/v1/tenancy/invitations/accept/', {'token': invite.token})
        assert res_ok.status_code == status.HTTP_200_OK
        invite.refresh_from_db()
        assert invite.status == InvitationStatus.ACCEPTED

    def test_payment_verification_role_protection(self, setup_platform):
        store = setup_platform['store']
        customer = Customer.objects.create(store=store, full_name="Payer", phone_number="09121112233")
        warehouse = Warehouse.objects.create(store=store, name="Payment WH", is_default=True)
        order = Order.objects.create(
            store=store, customer=customer, warehouse=warehouse, order_number="ORD-PAY-01",
            total_items_price=100000, grand_total=100000
        )
        payment = PaymentTransaction.objects.create(
            store=store, order=order, amount=100000,
            status=PaymentVerificationStatus.PENDING_VERIFICATION
        )

        unauthorized_staff = User.objects.create_user(email="creator@test.com", password="pass123", full_name="Creator")
        StoreMembership.objects.create(
            store=store, user=unauthorized_staff, role=Role.CONTENT_CREATOR,
            status=MembershipStatus.ACTIVE, is_active=True
        )

        client = APIClient()
        client.force_authenticate(user=unauthorized_staff)

        res_verify = client.post(f'/api/v1/payments/{payment.id}/verify/', HTTP_X_STORE_ID=str(store.id))
        assert res_verify.status_code == status.HTTP_403_FORBIDDEN

        # Owner can verify
        owner_client = APIClient()
        owner_client.force_authenticate(user=setup_platform['owner'])
        res_ok = owner_client.post(f'/api/v1/payments/{payment.id}/verify/', HTTP_X_STORE_ID=str(store.id))
        assert res_ok.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.status == PaymentVerificationStatus.VERIFIED
