from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("submission", "0011_add_award_submissionaward"),
    ]

    operations = [
        migrations.AddField(
            model_name="submissionaward",
            name="is_stale",
            field=models.BooleanField(default=False, verbose_name="有更新提交"),
        ),
    ]
