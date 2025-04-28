from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date
from models import MoodType, FeedbackType, RewardType, LearningCourseStatus, RAGStatus, ComplianceReportType

# Mood Tracker schemas
class MoodTrackerSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    mood = fields.String(dump_only=True)
    note = fields.String(dump_only=True)
    date = fields.Date(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

class MoodTrackerCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    mood = fields.String(
        required=True,
        validate=validate.OneOf([mt.value for mt in MoodType])
    )
    note = fields.String()
    date = fields.Date()

class MoodTrackerUpdateSchema(Schema):
    mood = fields.String(
        validate=validate.OneOf([mt.value for mt in MoodType])
    )
    note = fields.String()

# Performance Feedback schemas
class PerformanceFeedbackSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'position'), 
        dump_only=True
    )
    reviewer_id = fields.Integer(dump_only=True)
    reviewer = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    feedback_type = fields.String(dump_only=True)
    content = fields.String(dump_only=True)
    strengths = fields.String(dump_only=True)
    areas_of_improvement = fields.String(dump_only=True)
    rating = fields.Integer(dump_only=True)
    is_draft = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class PerformanceFeedbackCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    reviewer_id = fields.Integer()  # Optional for AI-generated feedback
    feedback_type = fields.String(
        required=True,
        validate=validate.OneOf([ft.value for ft in FeedbackType])
    )
    content = fields.String(required=True)
    strengths = fields.String()
    areas_of_improvement = fields.String()
    rating = fields.Integer(validate=validate.Range(min=1, max=5))
    is_draft = fields.Boolean()

class PerformanceFeedbackUpdateSchema(Schema):
    content = fields.String()
    strengths = fields.String()
    areas_of_improvement = fields.String()
    rating = fields.Integer(validate=validate.Range(min=1, max=5))
    is_draft = fields.Boolean()

class AIFeedbackGenerateSchema(Schema):
    employee_id = fields.Integer(required=True)
    timeframe = fields.String(
        required=True,
        validate=validate.OneOf(['week', 'month', 'quarter', 'year'])
    )
    metrics_to_include = fields.List(
        fields.String(
            validate=validate.OneOf(['tasks', 'attendance', 'communication', 'collaboration'])
        )
    )

# Gamified Task System schemas
class TaskRewardSchema(Schema):
    id = fields.Integer(dump_only=True)
    task_id = fields.Integer(dump_only=True)
    task = fields.Nested(
        'TaskSchema', 
        only=('id', 'title'), 
        dump_only=True
    )
    reward_type = fields.String(dump_only=True)
    points = fields.Integer(dump_only=True)
    name = fields.String(dump_only=True)
    description = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

class TaskRewardCreateSchema(Schema):
    task_id = fields.Integer(required=True)
    reward_type = fields.String(
        required=True,
        validate=validate.OneOf([rt.value for rt in RewardType])
    )
    points = fields.Integer()
    name = fields.String()
    description = fields.String()
    
    @validates('points')
    def validate_points(self, value):
        if value < 0:
            raise ValidationError("Points cannot be negative")

class EmployeeRewardSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    task_reward_id = fields.Integer(dump_only=True)
    task_reward = fields.Nested(TaskRewardSchema, dump_only=True)
    earned_at = fields.DateTime(dump_only=True)
    claimed = fields.Boolean(dump_only=True)
    claimed_at = fields.DateTime(dump_only=True)

class EmployeeRewardCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    task_reward_id = fields.Integer(required=True)
    claimed = fields.Boolean()

class EmployeeRewardUpdateSchema(Schema):
    claimed = fields.Boolean(required=True)

# Workload Heatmap schemas
class WorkloadEntrySchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    date = fields.Date(dump_only=True)
    workload_percent = fields.Integer(dump_only=True)
    estimated_hours = fields.Float(dump_only=True)
    actual_hours = fields.Float(dump_only=True)
    stress_level = fields.Integer(dump_only=True)
    notes = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class WorkloadEntryCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    date = fields.Date(required=True)
    workload_percent = fields.Integer(required=True, validate=validate.Range(min=0, max=100))
    estimated_hours = fields.Float(required=True)
    actual_hours = fields.Float()
    stress_level = fields.Integer(validate=validate.Range(min=1, max=5))
    notes = fields.String()
    
    @validates('estimated_hours')
    def validate_estimated_hours(self, value):
        if value < 0:
            raise ValidationError("Estimated hours cannot be negative")
    
    @validates('actual_hours')
    def validate_actual_hours(self, value):
        if value < 0:
            raise ValidationError("Actual hours cannot be negative")

class WorkloadEntryUpdateSchema(Schema):
    workload_percent = fields.Integer(validate=validate.Range(min=0, max=100))
    estimated_hours = fields.Float()
    actual_hours = fields.Float()
    stress_level = fields.Integer(validate=validate.Range(min=1, max=5))
    notes = fields.String()
    
    @validates('estimated_hours')
    def validate_estimated_hours(self, value):
        if value < 0:
            raise ValidationError("Estimated hours cannot be negative")
    
    @validates('actual_hours')
    def validate_actual_hours(self, value):
        if value < 0:
            raise ValidationError("Actual hours cannot be negative")

# Learning Portal schemas
class LearningCategorySchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(dump_only=True)
    description = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    courses = fields.List(
        fields.Nested(
            'LearningCourseSchema', 
            exclude=('category',)
        ), 
        dump_only=True
    )

class LearningCategoryCreateSchema(Schema):
    name = fields.String(required=True)
    description = fields.String()

class LearningCourseSchema(Schema):
    id = fields.Integer(dump_only=True)
    category_id = fields.Integer(dump_only=True)
    category = fields.Nested(
        LearningCategorySchema, 
        exclude=('courses', 'created_at'), 
        dump_only=True
    )
    title = fields.String(dump_only=True)
    description = fields.String(dump_only=True)
    content = fields.String(dump_only=True)
    estimated_hours = fields.Float(dump_only=True)
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class LearningCourseCreateSchema(Schema):
    category_id = fields.Integer(required=True)
    title = fields.String(required=True)
    description = fields.String()
    content = fields.String()
    estimated_hours = fields.Float()
    
    @validates('estimated_hours')
    def validate_estimated_hours(self, value):
        if value < 0:
            raise ValidationError("Estimated hours cannot be negative")

class LearningCourseUpdateSchema(Schema):
    category_id = fields.Integer()
    title = fields.String()
    description = fields.String()
    content = fields.String()
    estimated_hours = fields.Float()
    
    @validates('estimated_hours')
    def validate_estimated_hours(self, value):
        if value < 0:
            raise ValidationError("Estimated hours cannot be negative")

class EmployeeCourseSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    course_id = fields.Integer(dump_only=True)
    course = fields.Nested(LearningCourseSchema, dump_only=True)
    status = fields.String(dump_only=True)
    progress = fields.Integer(dump_only=True)
    started_at = fields.DateTime(dump_only=True)
    completed_at = fields.DateTime(dump_only=True)

class EmployeeCourseCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    course_id = fields.Integer(required=True)
    status = fields.String(
        validate=validate.OneOf([lcs.value for lcs in LearningCourseStatus])
    )
    progress = fields.Integer(validate=validate.Range(min=0, max=100))
    started_at = fields.DateTime()
    completed_at = fields.DateTime()

class EmployeeCourseUpdateSchema(Schema):
    status = fields.String(
        validate=validate.OneOf([lcs.value for lcs in LearningCourseStatus])
    )
    progress = fields.Integer(validate=validate.Range(min=0, max=100))
    started_at = fields.DateTime()
    completed_at = fields.DateTime()

# HR Chatbot schemas
class HRQuerySchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    query = fields.String(dump_only=True)
    response = fields.String(dump_only=True)
    is_private = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

class HRQueryCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    query = fields.String(required=True)
    is_private = fields.Boolean()

class HRQueryResponseSchema(Schema):
    response = fields.String(required=True)

# Shadow Login schemas
class ShadowLoginSchema(Schema):
    id = fields.Integer(dump_only=True)
    admin_id = fields.Integer(dump_only=True)
    admin = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    target_id = fields.Integer(dump_only=True)
    target = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    reason = fields.String(dump_only=True)
    started_at = fields.DateTime(dump_only=True)
    ended_at = fields.DateTime(dump_only=True)
    actions_logged = fields.String(dump_only=True)

class ShadowLoginCreateSchema(Schema):
    admin_id = fields.Integer(required=True)
    target_id = fields.Integer(required=True)
    reason = fields.String(required=True)

class ShadowLoginUpdateSchema(Schema):
    ended_at = fields.DateTime(required=True)
    actions_logged = fields.String()

# RAG Project Progress schemas
class RAGUpdateSchema(Schema):
    id = fields.Integer(dump_only=True)
    project_id = fields.Integer(dump_only=True)
    project = fields.Nested(
        'ProjectSchema', 
        only=('id', 'name', 'status'), 
        dump_only=True
    )
    status = fields.String(dump_only=True)
    update_date = fields.Date(dump_only=True)
    description = fields.String(dump_only=True)
    action_items = fields.String(dump_only=True)
    updated_by = fields.Integer(dump_only=True)
    updater = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)

class RAGUpdateCreateSchema(Schema):
    project_id = fields.Integer(required=True)
    status = fields.String(
        required=True,
        validate=validate.OneOf([rs.value for rs in RAGStatus])
    )
    update_date = fields.Date()
    description = fields.String(required=True)
    action_items = fields.String()

# Behavioral Analytics schemas
class BehavioralMetricSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    metric_date = fields.Date(dump_only=True)
    response_time_avg = fields.Float(dump_only=True)
    task_completion_rate = fields.Float(dump_only=True)
    communication_frequency = fields.Integer(dump_only=True)
    collaboration_score = fields.Float(dump_only=True)
    initiative_score = fields.Float(dump_only=True)
    punctuality_score = fields.Float(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

class BehavioralMetricCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    metric_date = fields.Date()
    response_time_avg = fields.Float()
    task_completion_rate = fields.Float(validate=validate.Range(min=0, max=100))
    communication_frequency = fields.Integer()
    collaboration_score = fields.Float(validate=validate.Range(min=0, max=100))
    initiative_score = fields.Float(validate=validate.Range(min=0, max=100))
    punctuality_score = fields.Float(validate=validate.Range(min=0, max=100))
    
    @validates('response_time_avg')
    def validate_response_time_avg(self, value):
        if value < 0:
            raise ValidationError("Response time average cannot be negative")
    
    @validates('communication_frequency')
    def validate_communication_frequency(self, value):
        if value < 0:
            raise ValidationError("Communication frequency cannot be negative")

# Compliance Report schemas
class ComplianceReportSchema(Schema):
    id = fields.Integer(dump_only=True)
    report_type = fields.String(dump_only=True)
    title = fields.String(dump_only=True)
    description = fields.String(dump_only=True)
    generated_by = fields.Integer(dump_only=True)
    generator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    generated_at = fields.DateTime(dump_only=True)
    data = fields.String(dump_only=True)
    pdf_url = fields.String(dump_only=True)

class ComplianceReportCreateSchema(Schema):
    report_type = fields.String(
        required=True,
        validate=validate.OneOf([crt.value for crt in ComplianceReportType])
    )
    title = fields.String(required=True)
    description = fields.String()
    generated_by = fields.Integer(required=True)
    data = fields.String(required=True)
    pdf_url = fields.String()