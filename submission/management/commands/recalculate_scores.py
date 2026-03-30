from django.core.management.base import BaseCommand

from submission.models import Submission


class Command(BaseCommand):
    help = "Recalculate score, raw_score, and zone for all rated submissions"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = Submission.objects.filter(ratings__isnull=False).distinct()
        total = qs.count()
        self.stdout.write(f"Found {total} rated submission(s).")

        if dry_run:
            self.stdout.write("Dry run — no changes made.")
            return

        for i, s in enumerate(qs, 1):
            old_score = s.score
            s.update_score()
            self.stdout.write(f"[{i}/{total}] {s.user.username}/{s.task.title}: {old_score:.3f} → {s.score:.3f}  zone={s.zone}")

        self.stdout.write(self.style.SUCCESS("Done."))
