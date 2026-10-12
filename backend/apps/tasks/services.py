from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Task, TaskStatus, TaskPriority, TaskActivityLog, TaskComment, TaskChecklistItem


class TaskService:
    @staticmethod
    def create_task(store, creator, data, checklist_items=None):
        checklist_items = checklist_items or []
        task = Task.objects.create(
            store=store,
            creator=creator,
            **data
        )

        TaskActivityLog.objects.create(
            task=task,
            actor=creator,
            action_type="CREATED",
            new_value=task.status,
            note=f"وظیفه '{task.title}' ایجاد شد."
        )

        for idx, item_title in enumerate(checklist_items):
            if isinstance(item_title, dict):
                title = item_title.get('title', '')
                is_done = item_title.get('is_completed', False)
            else:
                title = str(item_title)
                is_done = False

            if title.strip():
                TaskChecklistItem.objects.create(
                    task=task,
                    title=title.strip(),
                    is_completed=is_done,
                    order=idx
                )

        return task

    @staticmethod
    def update_task_status(task, new_status, actor, completion_evidence=None):
        if new_status not in TaskStatus.values:
            raise ValidationError({"status": f"وضعیت نامعتبر است: {new_status}"})

        old_status = task.status
        if old_status == new_status and not completion_evidence:
            return task

        if completion_evidence:
            task.completion_evidence = completion_evidence

        # Check verification requirement
        final_status = new_status
        if new_status == TaskStatus.COMPLETED and task.requires_verification:
            is_reviewer = task.reviewer_id and task.reviewer_id == actor.id
            is_creator = task.creator_id == actor.id
            # If actor is not reviewer or creator, force IN_REVIEW state
            if not (is_reviewer or is_creator):
                final_status = TaskStatus.IN_REVIEW

        task.status = final_status
        if final_status == TaskStatus.COMPLETED:
            task.completed_at = timezone.now()
        else:
            task.completed_at = None

        task.save()

        note = f"وضعیت وظیفه از '{old_status}' به '{final_status}' تغییر یافت."
        if final_status == TaskStatus.IN_REVIEW and new_status == TaskStatus.COMPLETED:
            note += " (با توجه به الزام بازبینی، برای تایید به ناظر ارجاع شد)"

        TaskActivityLog.objects.create(
            task=task,
            actor=actor,
            action_type="STATUS_CHANGED",
            old_value=old_status,
            new_value=final_status,
            note=note
        )

        return task

    @staticmethod
    def verify_task(task, reviewer, approved=True, feedback=""):
        old_status = task.status
        if approved:
            task.status = TaskStatus.COMPLETED
            task.completed_at = timezone.now()
            action_type = "VERIFIED_APPROVED"
            reviewer_name = getattr(reviewer, 'full_name', '') or getattr(reviewer, 'email', str(reviewer))
            note = f"وظیفه توسط {reviewer_name} تأیید شد."
            if feedback:
                note += f" بازخورد: {feedback}"
        else:
            task.status = TaskStatus.IN_PROGRESS
            task.completed_at = None
            action_type = "VERIFIED_REJECTED"
            reviewer_name = getattr(reviewer, 'full_name', '') or getattr(reviewer, 'email', str(reviewer))
            note = f"وظیفه توسط {reviewer_name} رد شد و به وضعیت در حال انجام بازگشت."
            if feedback:
                note += f" دلایل/اصلاحات درخواستی: {feedback}"

        task.save()

        TaskActivityLog.objects.create(
            task=task,
            actor=reviewer,
            action_type=action_type,
            old_value=old_status,
            new_value=task.status,
            note=note
        )

        return task

    @staticmethod
    def assign_task(task, assignee, actor):
        old_assignee_name = str(task.assignee) if task.assignee else "بدون مسئول"
        task.assignee = assignee
        task.save()

        new_assignee_name = str(assignee) if assignee else "بدون مسئول"
        TaskActivityLog.objects.create(
            task=task,
            actor=actor,
            action_type="ASSIGNED",
            old_value=old_assignee_name,
            new_value=new_assignee_name,
            note=f"مسئول انجام وظیفه تغییر کرد به: {new_assignee_name}"
        )
        return task

    @staticmethod
    def add_comment(task, author, content):
        if not content or not content.strip():
            raise ValidationError({"content": "متن نظر نمی‌تواند خالی باشد."})

        comment = TaskComment.objects.create(
            task=task,
            author=author,
            content=content.strip()
        )

        TaskActivityLog.objects.create(
            task=task,
            actor=author,
            action_type="COMMENTED",
            new_value=str(comment.id),
            note="نظر جدیدی روی وظیفه ثبت شد."
        )
        return comment

    @staticmethod
    def toggle_checklist_item(checklist_item, user):
        checklist_item.is_completed = not checklist_item.is_completed
        if checklist_item.is_completed:
            checklist_item.completed_by = user
            checklist_item.completed_at = timezone.now()
        else:
            checklist_item.completed_by = None
            checklist_item.completed_at = None
        checklist_item.save()

        TaskActivityLog.objects.create(
            task=checklist_item.task,
            actor=user,
            action_type="CHECKLIST_TOGGLED",
            old_value="done" if not checklist_item.is_completed else "pending",
            new_value="done" if checklist_item.is_completed else "pending",
            note=f"مورد چک‌لیست '{checklist_item.title}' {'تکمیل شد' if checklist_item.is_completed else 'از حالت تکمیل خارج شد'}."
        )

        # Check if all checklist items completed
        all_items = checklist_item.task.checklist_items.all()
        if all_items.exists() and all(item.is_completed for item in all_items):
            # Auto suggest or log
            pass

        return checklist_item
