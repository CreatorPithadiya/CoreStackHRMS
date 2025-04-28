from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date
from models import OKRStatus, OKRTimeframe

class KeyResultSchema(Schema):
    id = fields.Integer(dump_only=True)
    okr_id = fields.Integer(dump_only=True)
    title = fields.String(required=True)
    description = fields.String()
    target_value = fields.Float(required=True)
    current_value = fields.Float(dump_only=True)
    unit = fields.String()
    progress = fields.Integer(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    @validates('target_value')
    def validate_target_value(self, value):
        if value <= 0:
            raise ValidationError("Target value must be greater than 0")

class KeyResultUpdateSchema(Schema):
    title = fields.String()
    description = fields.String()
    target_value = fields.Float()
    current_value = fields.Float()
    unit = fields.String()
    
    @validates('target_value')
    def validate_target_value(self, value):
        if value <= 0:
            raise ValidationError("Target value must be greater than 0")
    
    @validates('current_value')
    def validate_current_value(self, value):
        if value < 0:
            raise ValidationError("Current value cannot be negative")

class OKRSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'position'), 
        dump_only=True
    )
    title = fields.String(dump_only=True)
    description = fields.String(dump_only=True)
    timeframe = fields.String(dump_only=True)
    start_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)
    status = fields.String(dump_only=True)
    progress = fields.Integer(dump_only=True)
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    key_results = fields.List(fields.Nested(KeyResultSchema), dump_only=True)

class OKRCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    title = fields.String(required=True)
    description = fields.String()
    timeframe = fields.String(
        validate=validate.OneOf([tf.value for tf in OKRTimeframe])
    )
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    status = fields.String(
        validate=validate.OneOf([s.value for s in OKRStatus])
    )
    key_results = fields.List(fields.Nested(KeyResultSchema))
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value < date.today():
            raise ValidationError("Start date cannot be in the past")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if 'start_date' in self.context and value < self.context['start_date']:
            raise ValidationError("End date must be on or after start date")

class OKRUpdateSchema(Schema):
    title = fields.String()
    description = fields.String()
    timeframe = fields.String(
        validate=validate.OneOf([tf.value for tf in OKRTimeframe])
    )
    start_date = fields.Date()
    end_date = fields.Date()
    status = fields.String(
        validate=validate.OneOf([s.value for s in OKRStatus])
    )
    progress = fields.Integer(validate=validate.Range(min=0, max=100))
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value < date.today():
            raise ValidationError("Start date cannot be in the past")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if 'start_date' in self.context and value < self.context['start_date']:
            raise ValidationError("End date must be on or after start date")