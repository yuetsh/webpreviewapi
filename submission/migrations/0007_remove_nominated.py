from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("submission", "0006_add_raw_score_nominated"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="submission",
            name="nominated",
        ),
    ]
