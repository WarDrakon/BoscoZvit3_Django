from django.db import migrations

GROUP_NAME = "Модератори"


def create_group(apps, schema_editor):
    """Створює групу модераторів (ідемпотентно). Права їй призначає адміністратор в адмінці."""
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=GROUP_NAME)


def remove_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=GROUP_NAME, permissions__isnull=True, user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_person_validation"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_group, remove_group)]
