from django.contrib import admin
from tests.models import Answer, Question, QuestionOption, ScoreRange, Stage, Test, TestResult, TestSession


# ─── Инлайны ───────────────────────────────────────

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2
    fields = ['option_text', 'score', 'order']
    ordering = ['order']


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    fields = ['block_title', 'question_text', 'question_type', 'order', 'is_required',
              'scale_min', 'scale_max', 'scale_labels']
    ordering = ['order']
    show_change_link = True


class StageInline(admin.StackedInline):
    model = Stage
    extra = 1
    fields = ['name', 'description', 'page_title', 'annotation', 'order', 'sidebar_step']
    ordering = ['order']
    show_change_link = True


class ScoreRangeInline(admin.TabularInline):
    model = ScoreRange
    extra = 1
    fields = ['sidebar_step', 'min_score', 'max_score', 'label', 'conclusion']


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question', 'get_selected_options', 'scale_value', 'score']
    can_delete = False

    def get_selected_options(self, obj):
        return ', '.join(str(o) for o in obj.selected_options.all()) or '—'
    get_selected_options.short_description = 'Выбранные варианты'


# ─── Регистрация моделей ────────────────────────────

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'is_active', 'get_stages_count', 'created_at']
    list_filter = ['is_active', 'created_by']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [StageInline, ScoreRangeInline]

    fieldsets = (
        ('Основная информация', {'fields': ('title', 'description', 'is_active', 'created_by')}),
        ('Метаданные', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_stages_count(self, obj):
        return obj.stages.count()
    get_stages_count.short_description = 'Этапов'


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['page_title', 'test', 'order', 'sidebar_step', 'get_questions_count']
    list_filter = ['test']
    search_fields = ['name', 'page_title', 'test__title']
    ordering = ['test', 'order']
    inlines = [QuestionInline]

    fieldsets = (
        ('Сайдбар', {'fields': ('test', 'name', 'description', 'sidebar_step', 'order')}),
        ('Страница', {'fields': ('page_title', 'annotation')}),
    )

    def get_questions_count(self, obj):
        return obj.questions.count()
    get_questions_count.short_description = 'Вопросов'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_short', 'stage', 'question_type', 'order', 'is_required']
    list_filter = ['question_type', 'stage__test', 'is_required']
    search_fields = ['question_text', 'block_title']
    ordering = ['stage', 'order']
    inlines = [QuestionOptionInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('stage', 'block_title', 'question_text', 'question_type', 'order', 'is_required'),
        }),
        ('Настройки шкалы (только для типа «Шкала»)', {
            'fields': ('scale_min', 'scale_max', 'scale_labels'),
            'classes': ('collapse',),
        }),
    )

    def question_short(self, obj):
        text = obj.question_text
        return text[:80] + '...' if len(text) > 80 else text
    question_short.short_description = 'Текст вопроса'


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ['option_text', 'question', 'score', 'order']
    list_filter = ['question__stage__test']
    search_fields = ['option_text']
    ordering = ['question', 'order']


@admin.register(ScoreRange)
class ScoreRangeAdmin(admin.ModelAdmin):
    list_display = ['test', 'sidebar_step', 'min_score', 'max_score', 'label']
    list_filter = ['test', 'sidebar_step']
    search_fields = ['label', 'conclusion']
    ordering = ['test', 'sidebar_step', 'min_score']


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'test', 'get_patient_name', 'taken_by', 'status', 'current_stage_order', 'started_at']
    list_filter = ['status', 'test', 'started_at']
    search_fields = ['patient__user__first_name', 'patient__user__last_name']
    readonly_fields = ['id', 'started_at', 'answers_data']
    ordering = ['-started_at']

    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()
    get_patient_name.short_description = 'Пациент'

    def has_add_permission(self, request):
        return False


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ['test', 'get_patient_name', 'taken_by', 'status', 'total_score', 'conclusion_label', 'completed_at']
    list_filter = ['status', 'test', 'completed_at']
    search_fields = ['patient__user__first_name', 'patient__user__last_name', 'test__title']
    readonly_fields = ['session', 'started_at', 'completed_at', 'reviewed_at', 'total_score',
                       'conclusion_label', 'conclusion_text']
    ordering = ['-completed_at']
    inlines = [AnswerInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('session', 'test', 'patient', 'taken_by', 'status', 'total_score'),
        }),
        ('Заключение', {
            'fields': ('conclusion_label', 'conclusion_text'),
        }),
        ('Проверка врачом', {
            'fields': ('reviewed_by', 'doctor_notes', 'reviewed_at'),
        }),
        ('Даты', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',),
        }),
    )

    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()
    get_patient_name.short_description = 'Пациент'
