from django.contrib import admin
from tests.models import Test, Question, QuestionOption, TestResult, Answer


class QuestionInline(admin.TabularInline):
    """Inline для вопросов теста"""
    model = Question
    extra = 1
    fields = ['question_text', 'question_type', 'order', 'is_required']


class QuestionOptionInline(admin.TabularInline):
    """Inline для вариантов ответов"""
    model = QuestionOption
    extra = 2
    fields = ['option_text', 'order', 'score']


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    """Админка для тестов"""

    list_display = ['title', 'created_by', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'created_by']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [QuestionInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'instructions')
        }),
        ('Настройки', {
            'fields': ('is_active', 'created_by')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Админка для вопросов"""

    list_display = ['question_text_short', 'test', 'question_type', 'order', 'is_required']
    list_filter = ['question_type', 'test', 'is_required']
    search_fields = ['question_text']
    ordering = ['test', 'order']
    inlines = [QuestionOptionInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('test', 'question_text', 'question_type', 'order', 'is_required')
        }),
        ('Настройки шкалы', {
            'fields': ('scale_min', 'scale_max', 'scale_min_label', 'scale_max_label'),
            'classes': ('collapse',)
        }),
    )

    def question_text_short(self, obj):
        """Сокращенный текст вопроса"""
        return obj.question_text[:100] + '...' if len(obj.question_text) > 100 else obj.question_text
    question_text_short.short_description = 'Текст вопроса'


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    """Админка для вариантов ответов"""

    list_display = ['option_text', 'question', 'order', 'score']
    list_filter = ['question__test']
    search_fields = ['option_text']
    ordering = ['question', 'order']


class AnswerInline(admin.TabularInline):
    """Inline для ответов"""
    model = Answer
    extra = 0
    readonly_fields = ['question', 'text_answer', 'scale_value', 'score']
    can_delete = False


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    """Админка для результатов тестов"""

    list_display = ['test', 'get_patient_name', 'status', 'total_score', 'started_at', 'completed_at']
    list_filter = ['status', 'test', 'started_at']
    search_fields = ['patient__user__first_name', 'patient__user__last_name', 'test__title']
    readonly_fields = ['started_at', 'completed_at', 'reviewed_at']
    ordering = ['-started_at']
    inlines = [AnswerInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('test', 'patient', 'status', 'total_score')
        }),
        ('Проверка', {
            'fields': ('reviewed_by', 'doctor_notes')
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at', 'reviewed_at'),
            'classes': ('collapse',)
        }),
    )

    def get_patient_name(self, obj):
        """Получение имени пациента"""
        return obj.patient.user.get_full_name()
    get_patient_name.short_description = 'Пациент'


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Админка для ответов"""

    list_display = ['get_patient_name', 'question_short', 'score']
    list_filter = ['result__test', 'result__patient']
    search_fields = ['result__patient__user__first_name', 'question__question_text', 'text_answer']
    readonly_fields = ['result', 'question']
    ordering = ['-result__started_at']

    def get_patient_name(self, obj):
        """Получение имени пациента"""
        return obj.result.patient.user.get_full_name()
    get_patient_name.short_description = 'Пациент'

    def question_short(self, obj):
        """Сокращенный текст вопроса"""
        text = obj.question.question_text
        return text[:50] + '...' if len(text) > 50 else text
    question_short.short_description = 'Вопрос'
