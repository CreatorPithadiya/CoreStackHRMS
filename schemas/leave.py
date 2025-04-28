from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date
from models import LeaveType, LeaveStatus

class LeaveRequestSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'employee_id'), 
        dump_only=True
    )
    leave_type = fields.String(dump_only=True)
    start_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)
    days = fields.Float(dump_only=True)
    reason = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    reviewed_by = fields.Integer(dump_only=True)
    reviewer = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    reviewed_at = fields.DateTime(dump_only=True)
    review_note = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class LeaveRequestCreateSchema(Schema):
    leave_type = fields.String(
        required=True, 
        validate=validate.OneOf([lt.value for lt in LeaveType])
    )
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    days = fields.Float()
    reason = fields.String()
    
    @validates('leave_type')
    def validate_leave_type(self, value):
        try:
            LeaveType[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid leave type: {value}")
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value < date.today():
            raise ValidationError("Start date cannot be in the past")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if 'start_date' in self.context and value < self.context['start_date']:
            raise ValidationError("End date must be on or after start date")
    
    @validates('days')
    def validate_days(self, value):
        if value <= 0:
            raise ValidationError("Days must be greater than 0")

class LeaveRequestUpdateSchema(Schema):
    leave_type = fields.String(validate=validate.OneOf([lt.value for lt in LeaveType]))
    start_date = fields.Date()
    end_date = fields.Date()
    days = fields.Float()
    reason = fields.String()
    
    @validates('leave_type')
    def validate_leave_type(self, value):
        try:
            LeaveType[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid leave type: {value}")
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value < date.today():
            raise ValidationError("Start date cannot be in the past")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if 'start_date' in self.context and value < self.context['start_date']:
            raise ValidationError("End date must be on or after start date")
    
    @validates('days')
    def validate_days(self, value):
        if value <= 0:
            raise ValidationError("Days must be greater than 0")

class LeaveRequestActionSchema(Schema):
    action = fields.String(required=True, validate=validate.OneOf(['approve', 'reject']))
    note = fields.String()

class LeaveBalanceSchema(Schema):
    employee = fields.Dict(keys=fields.String(), values=fields.Field())
    leave_balances = fields.List(fields.Dict(keys=fields.String(), values=fields.Field()))
