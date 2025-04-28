from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date
from models import TaskStatus, TaskPriority

class TaskCommentSchema(Schema):
    id = fields.Integer(dump_only=True)
    task_id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'profile_image'), 
        dump_only=True
    )
    comment = fields.String(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class TaskSchema(Schema):
    id = fields.Integer(dump_only=True)
    title = fields.String(required=True)
    description = fields.String()
    project_id = fields.Integer(required=True)
    project = fields.Nested(
        'ProjectSchema', 
        only=('id', 'name'), 
        dump_only=True
    )
    assignee_id = fields.Integer()
    assignee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'profile_image'), 
        dump_only=True
    )
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    status = fields.String(dump_only=True)
    priority = fields.String(dump_only=True)
    progress = fields.Integer(validate=validate.Range(min=0, max=100))
    estimated_hours = fields.Float(validate=validate.Range(min=0))
    due_date = fields.Date()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    completed_at = fields.DateTime(dump_only=True)
    
    # Relationships
    comments = fields.List(fields.Nested(TaskCommentSchema), dump_only=True)

class TaskCreateSchema(Schema):
    title = fields.String(required=True)
    description = fields.String()
    project_id = fields.Integer(required=True)
    assignee_id = fields.Integer()
    status = fields.String(
        validate=validate.OneOf([ts.value for ts in TaskStatus])
        # Removed default parameter
    )
    priority = fields.String(
        validate=validate.OneOf([tp.value for tp in TaskPriority])
        # Removed default parameter
    )
    progress = fields.Integer(validate=validate.Range(min=0, max=100))
    estimated_hours = fields.Float(validate=validate.Range(min=0))
    due_date = fields.Date()
    
    @validates('status')
    def validate_status(self, value):
        try:
            TaskStatus[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid status: {value}")
    
    @validates('priority')
    def validate_priority(self, value):
        try:
            TaskPriority[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid priority: {value}")
    
    @validates('due_date')
    def validate_due_date(self, value):
        if value and value < date.today():
            raise ValidationError("Due date cannot be in the past")

class TaskUpdateSchema(Schema):
    title = fields.String()
    description = fields.String()
    assignee_id = fields.Integer(allow_none=True)
    status = fields.String(validate=validate.OneOf([ts.value for ts in TaskStatus]))
    priority = fields.String(validate=validate.OneOf([tp.value for tp in TaskPriority]))
    progress = fields.Integer(validate=validate.Range(min=0, max=100))
    estimated_hours = fields.Float(validate=validate.Range(min=0))
    due_date = fields.Date()
    
    @validates('status')
    def validate_status(self, value):
        try:
            TaskStatus[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid status: {value}")
    
    @validates('priority')
    def validate_priority(self, value):
        try:
            TaskPriority[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid priority: {value}")
    
    @validates('due_date')
    def validate_due_date(self, value):
        if value and value < date.today():
            raise ValidationError("Due date cannot be in the past")
