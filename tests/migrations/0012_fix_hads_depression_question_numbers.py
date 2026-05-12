from django.db import migrations

RENAMES = [
    ('8. То, что приносило мне большое удовольствие, и сейчас вызывает такое же чувство',
     '1. То, что приносило мне большое удовольствие, и сейчас вызывает такое же чувство'),
    ('9. Я способен рассмеяться и увидеть в том или ином событии смешное',
     '2. Я способен рассмеяться и увидеть в том или ином событии смешное'),
    ('10. Я испытываю бодрость',
     '3. Я испытываю бодрость'),
    ('11. Мне кажется, что я стал все делать очень медленно',
     '4. Мне кажется, что я стал все делать очень медленно'),
    ('12. Я не слежу за своей внешностью',
     '5. Я не слежу за своей внешностью'),
    ('13. Я считаю, что мои дела (занятия, увлечения) могут принести мне чувство удовлетворения',
     '6. Я считаю, что мои дела (занятия, увлечения) могут принести мне чувство удовлетворения'),
    ('14. Я могу получить удовольствие от хорошей книги, радио- или телепрограммы',
     '7. Я могу получить удовольствие от хорошей книги, радио- или телепрограммы'),
]


def rename_questions(apps, schema_editor):
    Question = apps.get_model('tests', 'Question')
    for old_text, new_text in RENAMES:
        Question.objects.filter(question_text=old_text).update(question_text=new_text)


def reverse_rename_questions(apps, schema_editor):
    Question = apps.get_model('tests', 'Question')
    for old_text, new_text in RENAMES:
        Question.objects.filter(question_text=new_text).update(question_text=old_text)


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0011_fix_ncsr_labels'),
    ]

    operations = [
        migrations.RunPython(rename_questions, reverse_rename_questions),
    ]
