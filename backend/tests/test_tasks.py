import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.tasks.models import Task, TaskStatus, TaskPriority, TaskCategory, TaskChecklistItem
from apps.tasks.services import TaskService


@pytest.mark.django_db
class TestTaskEngine:
    @pytest.fixture
    def setup_data(self):
        owner = User.objects.create_user(email="owner_task@test.com", password="password123", full_name="Store Owner")
        employee = User.objects.create_user(email="emp_task@test.com", password="password123", full_name="Worker")
        reviewer = User.objects.create_user(email="rev_task@test.com", password="password123", full_name="Lead Reviewer")

        biz = Business.objects.create(name="Task Biz", owner=owner)
        store = Store.objects.create(business=biz, name="Task Store")

        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=employee, role=Role.CONTENT_CREATOR, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=reviewer, role=Role.BUSINESS_MANAGER, status=MembershipStatus.ACTIVE)

        category = TaskCategory.objects.create(store=store, name="انبارداری و لجستیک")

        return {
            'owner': owner,
            'employee': employee,
            'reviewer': reviewer,
            'store': store,
            'category': category
        }

    def test_create_task_with_checklists_and_service(self, setup_data):
        store = setup_data['store']
        creator = setup_data['owner']
        assignee = setup_data['employee']
        category = setup_data['category']

        task = TaskService.create_task(
            store=store,
            creator=creator,
            data={
                "title": "بررسی موجودی فیزیکی قفسه A",
                "description": "شمارش دقیق و تطبیق با سیستم",
                "category": category,
                "assignee": assignee,
                "priority": TaskPriority.HIGH,
                "requires_verification": True
            },
            checklist_items=["شمارش ردیف ۱", "شمارش ردیف ۲", "ثبت مغایرت‌ها"]
        )

        assert task.title == "بررسی موجودی فیزیکی قفسه A"
        assert task.status == TaskStatus.TODO
        assert task.checklist_items.count() == 3
        assert task.activity_logs.count() == 1
        assert task.activity_logs.first().action_type == "CREATED"

    def test_verification_enforcement_on_status_change(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']
        employee = setup_data['employee']
        reviewer = setup_data['reviewer']

        task = Task.objects.create(
            store=store,
            creator=owner,
            assignee=employee,
            reviewer=reviewer,
            title="آماده‌سازی سفارش شماره ۱۰۲",
            requires_verification=True,
            status=TaskStatus.IN_PROGRESS
        )

        # 1. Employee tries to mark as COMPLETED -> Forced to IN_REVIEW due to verification requirement
        TaskService.update_task_status(
            task=task,
            new_status=TaskStatus.COMPLETED,
            actor=employee,
            completion_evidence="بسته‌بندی در قفسه ارسال قرار داده شد."
        )
        task.refresh_from_db()
        assert task.status == TaskStatus.IN_REVIEW
        assert task.completed_at is None
        assert task.completion_evidence == "بسته‌بندی در قفسه ارسال قرار داده شد."

        # 2. Reviewer reviews and approves -> becomes COMPLETED
        TaskService.verify_task(
            task=task,
            reviewer=reviewer,
            approved=True,
            feedback="عالی، تأیید شد."
        )
        task.refresh_from_db()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_checklist_toggle(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']
        employee = setup_data['employee']

        task = Task.objects.create(store=store, creator=owner, title="وظیفه تستی")
        item = TaskChecklistItem.objects.create(task=task, title="قدم اول", is_completed=False)

        # Toggle item
        TaskService.toggle_checklist_item(item, user=employee)
        item.refresh_from_db()
        assert item.is_completed is True
        assert item.completed_by == employee
        assert item.completed_at is not None

    def test_api_tasks_endpoints(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']
        employee = setup_data['employee']

        client = APIClient()
        client.force_authenticate(user=owner)

        # Create task via API
        res = client.post(
            "/api/v1/tasks/tasks/",
            {
                "title": "عکاسی از محصولات جدید",
                "priority": "HIGH",
                "status": "TODO",
                "assignee": str(employee.id),
                "checklist_items": ["عکس زاویه روبرو", "عکس جزئیات"]
            },
            format='json',
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res.status_code == 201
        task_id = res.data["id"]

        # Employee views tasks (my_tasks filter)
        emp_client = APIClient()
        emp_client.force_authenticate(user=employee)
        list_res = emp_client.get(
            "/api/v1/tasks/tasks/?my_tasks=true",
            HTTP_X_STORE_ID=str(store.id)
        )
        assert list_res.status_code == 200
        assert len(list_res.data) >= 1
