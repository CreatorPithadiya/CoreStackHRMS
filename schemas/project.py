from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date
from models import ProjectStatus

class ProjectMemberSchema(Schema):
    id = fields.Integer(dump_only=True)
    project_id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(required=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'position'), 
        dump_only=True
    )
    role = fields.String()  # Removed default parameter
    joined_at = fields.DateTime(dump_only=True)

class ProjectSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True)
    description = fields.String()
    status = fields.String(dump_only=True)
    start_date = fields.Date()
    end_date = fields.Date()
    budget = fields.Float()
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    # Relationships
    members = fields.List(fields.Nested(ProjectMemberSchema), dump_only=True)
    tasks_count = fields.Integer(dump_only=True)
    task_completion_rate = fields.Float(dump_only=True)
    
    @validates('end_date')
    def validate_end_date(self, value):
        if value and 'start_date' in self.context and self.context['start_date']:
            if value < self.context['start_date']:
                raise ValidationError("End date must be on or after start date")

class ProjectCreateSchema(Schema):
    name = fields.String(required=True)
    description = fields.String()
    status = fields.String(
        validate=validate.OneOf([ps.value for ps in ProjectStatus])
        # Removed default parameter
    )
    start_date = fields.Date()
    end_date = fields.Date()
    budget = fields.Float()
    members = fields.List(fields.Nested(ProjectMemberSchema))
    
    @validates('status')
    def validate_status(self, value):
        try:
            ProjectStatus[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid status: {value}")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if value and 'start_date' in self.context and self.context['start_date']:
            if value < self.context['start_date']:
                raise ValidationError("End date must be on or after start date")

class ProjectUpdateSchema(Schema):
    name = fields.String()
    description = fields.String()
    status = fields.String(validate=validate.OneOf([ps.value for ps in ProjectStatus]))
    start_date = fields.Date()
    end_date = fields.Date()
    budget = fields.Float()
    
    @validates('status')
    def validate_status(self, value):
        try:
            ProjectStatus[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid status: {value}")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if value and 'start_date' in self.context and self.context['start_date']:
            if value < self.context['start_date']:
                raise ValidationError("End date must be on or after start date")
