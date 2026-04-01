from django.core.management.base import BaseCommand

from prompt.models import Conversation
from submission.classifier import classify_conversation_messages


class Command(BaseCommand):
    help = "为所有缺失 Bloom 等级的用户消息补全分类"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="重新分类所有消息（包括已有等级的）",
        )

    def handle(self, *args, **options):
        force = options["force"]
        convs = Conversation.objects.all()
        total = convs.count()
        self.stdout.write(f"共 {total} 个对话，开始分类...")

        for i, conv in enumerate(convs, 1):
            classify_conversation_messages(conv.id, force=force)
            self.stdout.write(f"[{i}/{total}] {conv}", ending="\r")
            self.stdout.flush()

        self.stdout.write(self.style.SUCCESS(f"\n完成，处理了 {total} 个对话。"))
