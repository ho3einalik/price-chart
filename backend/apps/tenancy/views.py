from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import uuid
from .models import Business, Store, StoreMembership, Role, MembershipStatus, TeamInvitation, InvitationStatus
from .serializers import (
    BusinessSerializer, StoreSerializer, StoreMembershipSerializer,
    TeamInvitationSerializer, CreateInvitationInputSerializer
)
from .permissions import IsStoreMemberPermission, IsStoreAdminOrOwnerPermission
from apps.audit.services import record_audit_event

class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Business.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Store.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True
        ).distinct()

    def perform_create(self, serializer):
        store = serializer.save()
        StoreMembership.objects.create(
            store=store,
            user=self.request.user,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
            is_active=True
        )

class StoreMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = StoreMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return StoreMembership.objects.none()
        return StoreMembership.objects.filter(store=store).select_related('user', 'store')

    def perform_create(self, serializer):
        store = getattr(self.request, 'store', None)
        serializer.save(store=store)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        membership = self.get_object()
        if membership.role == Role.OWNER and membership.store.business.owner == membership.user:
            return Response({'error': 'مالک اصلی فروشگاه قابل تعلیق نیست.'}, status=status.HTTP_400_BAD_REQUEST)
        membership.status = MembershipStatus.SUSPENDED
        membership.save()
        record_audit_event(
            store=membership.store,
            user=request.user,
            action="MEMBER_SUSPENDED",
            target_type="StoreMembership",
            target_id=str(membership.id),
            changes={'user': membership.user.full_name}
        )
        return Response(StoreMembershipSerializer(membership).data)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        membership = self.get_object()
        membership.status = MembershipStatus.ACTIVE
        membership.save()
        record_audit_event(
            store=membership.store,
            user=request.user,
            action="MEMBER_REACTIVATED",
            target_type="StoreMembership",
            target_id=str(membership.id),
            changes={'user': membership.user.full_name}
        )
        return Response(StoreMembershipSerializer(membership).data)

class TeamInvitationViewSet(viewsets.ModelViewSet):
    serializer_class = TeamInvitationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return TeamInvitation.objects.none()
        return TeamInvitation.objects.filter(store=store).select_related('inviter')

    def create(self, request, *args, **kwargs):
        serializer = CreateInvitationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = getattr(request, 'store', None)
        data = serializer.validated_data

        # Check if user is already a member
        from apps.accounts.models import User
        existing_user = User.objects.filter(email=data['email']).first()
        if existing_user and StoreMembership.objects.filter(store=store, user=existing_user).exists():
            return Response({'error': 'این کاربر در حال حاضر عضو این فروشگاه است.'}, status=status.HTTP_400_BAD_REQUEST)

        # Invalidate previous pending invites to same email in this store
        TeamInvitation.objects.filter(store=store, email=data['email'], status=InvitationStatus.PENDING).update(
            status=InvitationStatus.REVOKED
        )

        invite = TeamInvitation.objects.create(
            store=store,
            email=data['email'],
            role=data['role'],
            custom_permissions=data.get('custom_permissions', []),
            inviter=request.user,
            token=f"inv_{uuid.uuid4().hex}",
            status=InvitationStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=7)
        )

        record_audit_event(
            store=store,
            user=request.user,
            action="TEAM_INVITE_SENT",
            target_type="TeamInvitation",
            target_id=str(invite.id),
            changes={'email': invite.email, 'role': invite.role}
        )
        return Response(TeamInvitationSerializer(invite).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        invite = self.get_object()
        invite.status = InvitationStatus.REVOKED
        invite.save()
        return Response(TeamInvitationSerializer(invite).data)

    def get_permissions(self):
        if self.action in ['accept', 'accept_detail']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], url_path='accept')
    def accept_detail(self, request, pk=None):
        try:
            invite = TeamInvitation.objects.get(id=pk)
        except (TeamInvitation.DoesNotExist, ValueError):
            return Response({'error': 'دعوت‌نامه یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)
        return self._process_accept(request, invite)

    @action(detail=False, methods=['post'], url_path='accept')
    def accept(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'توکن دعوت الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        invite = TeamInvitation.objects.filter(token=token).first()
        if not invite:
            return Response({'error': 'دعوت‌نامه نامعتبر است یا قبلاً استفاده شده است.'}, status=status.HTTP_404_NOT_FOUND)
        return self._process_accept(request, invite)

    def _process_accept(self, request, invite):
        if invite.status != InvitationStatus.PENDING:
            return Response({'error': 'این دعوت‌نامه قبلاً پذیرفته یا لغو شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        if invite.expires_at < timezone.now():
            invite.status = InvitationStatus.EXPIRED
            invite.save()
            return Response({'error': 'مهلت این دعوت‌نامه منقضی شده است.'}, status=status.HTTP_400_BAD_REQUEST)

        membership, _ = StoreMembership.objects.update_or_create(
            store=invite.store,
            user=request.user,
            defaults={
                'role': invite.role,
                'custom_permissions': invite.custom_permissions,
                'status': MembershipStatus.ACTIVE,
                'is_active': True,
            }
        )
        invite.status = InvitationStatus.ACCEPTED
        invite.save()

        record_audit_event(
            store=invite.store,
            user=request.user,
            action="TEAM_INVITE_ACCEPTED",
            target_type="TeamInvitation",
            target_id=str(invite.id),
            changes={'email': invite.email}
        )
        return Response({
            'message': f'شما با موفقیت به عنوان {membership.get_role_display()} به فروشگاه {invite.store.name} ملحق شدید.',
            'store_id': str(invite.store.id),
        }, status=status.HTTP_200_OK)

