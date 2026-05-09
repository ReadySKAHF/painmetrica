from django.db import migrations

DEFAULT_ORG_NAME = 'Painmetrica — общее учреждение'


def forward(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    DoctorProfile = apps.get_model('accounts', 'DoctorProfile')
    Patient = apps.get_model('patients', 'Patient')

    org, _ = Organization.objects.get_or_create(
        name=DEFAULT_ORG_NAME,
        defaults={'is_active': True},
    )

    DoctorProfile.objects.filter(organization__isnull=True).update(organization=org)

    for patient in Patient.objects.filter(organization__isnull=True):
        if patient.assigned_doctor_id:
            try:
                profile = DoctorProfile.objects.get(user_id=patient.assigned_doctor_id)
                patient.organization = profile.organization
            except DoctorProfile.DoesNotExist:
                patient.organization = org
        else:
            patient.organization = org
        patient.save(update_fields=['organization'])


def reverse(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    apps.get_model('accounts', 'DoctorProfile').objects.all().update(organization=None)
    apps.get_model('patients', 'Patient').objects.all().update(organization=None)
    Organization.objects.filter(name=DEFAULT_ORG_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_organization_and_doctorprofile_fk'),
        ('patients', '0005_patient_organization_fk'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
