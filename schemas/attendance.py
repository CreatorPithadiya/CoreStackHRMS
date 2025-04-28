from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import datetime, date

class AttendanceSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'employee_id'), 
        dump_only=True
    )
    date = fields.Date(dump_only=True)
    clock_in = fields.DateTime()
    clock_out = fields.DateTime()
    status = fields.String(validate=validate.OneOf(['present', 'absent', 'half-day']))
    work_from = fields.String(validate=validate.OneOf(['office', 'home', 'remote']))
    notes = fields.String()
    hours_worked = fields.Float(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    @validates('clock_out')
    def validate_clock_out(self, value):
        if value and 'clock_in' in self.context and self.context['clock_in']:
            if value < self.context['clock_in']:
                raise ValidationError("Clock out time must be after clock in time")

class AttendanceCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    date = fields.Date(required=True)
    clock_in = fields.DateTime()
    clock_out = fields.DateTime()
    status = fields.String(required=True, validate=validate.OneOf(['present', 'absent', 'half-day']))
    work_from = fields.String(validate=validate.OneOf(['office', 'home', 'remote']))
    notes = fields.String()
    
    @validates('date')
    def validate_date(self, value):
        if value > date.today():
            raise ValidationError("Cannot record attendance for future dates")
    
    @validates('clock_out')
    def validate_clock_out(self, value):
        if value and 'clock_in' in self.context and self.context['clock_in']:
            if value < self.context['clock_in']:
                raise ValidationError("Clock out time must be after clock in time")

class AttendanceUpdateSchema(Schema):
    clock_in = fields.DateTime()
    clock_out = fields.DateTime()
    status = fields.String(validate=validate.OneOf(['present', 'absent', 'half-day']))
    work_from = fields.String(validate=validate.OneOf(['office', 'home', 'remote']))
    notes = fields.String()
    
    @validates('clock_out')
    def validate_clock_out(self, value):
        if value and 'clock_in' in self.context and self.context['clock_in']:
            if value < self.context['clock_in']:
                raise ValidationError("Clock out time must be after clock in time")

class AttendanceReportSchema(Schema):
    period = fields.Dict(keys=fields.String(), values=fields.String())
    attendance = fields.Dict(keys=fields.String(), values=fields.Number())
    work_hours = fields.Dict(keys=fields.String(), values=fields.Number())
    location = fields.Dict(keys=fields.String(), values=fields.Integer())
    punctuality = fields.Dict(keys=fields.String(), values=fields.Number())
