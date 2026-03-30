from django.core.management.base import BaseCommand

from prompt.models import Message
from submission.classifier import classify_message


class Command(BaseCommand):
    help = "Classify prompt levels (L1-L6) for user messages using LLM"

    def add_arguments(self, parser):
        parser.add_argument("--task-id", type=int, help="Only classify messages for this task ID")
        parser.add_argument("--force", action="store_true", help="Re-classify already classified messages")
        parser.add_argument("--dry-run", action="store_true", help="Show count without classifying")

    def handle(self, *args, **options):
        qs = Message.objects.filter(role="user")
        if options["task_id"]:
            qs = qs.filter(conversation__task_id=options["task_id"])
        if not options["force"]:
            qs = qs.filter(prompt_level__isnull=True)

        ids = list(qs.values_list("id", flat=True))
        self.stdout.write(f"Found {len(ids)} message(s) to classify.")

        if options["dry_run"]:
            self.stdout.write("Dry run — no changes made.")
            return

        for i, mid in enumerate(ids, 1):
            level = classify_message(mid)
            self.stdout.write(
                f"[{i}/{len(ids)}] msg#{mid} → L{level}" if level else f"[{i}/{len(ids)}] msg#{mid} → (skipped)"
            )

        self.stdout.write(self.style.SUCCESS("Done."))
