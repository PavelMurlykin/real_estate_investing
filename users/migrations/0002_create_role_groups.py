from django.db import migrations


ROLE_GROUP_NAMES = (
    'moderators',
    'application_administrators',
)


def create_role_groups(apps, schema_editor):
    """Create application role groups."""
    group_model = apps.get_model('auth', 'Group')
    for group_name in ROLE_GROUP_NAMES:
        group_model.objects.get_or_create(name=group_name)


def delete_role_groups(apps, schema_editor):
    """Delete empty application role groups on migration rollback."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_role_groups, delete_role_groups),
    ]
