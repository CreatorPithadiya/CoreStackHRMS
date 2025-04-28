from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date
from models import PayrollStatus, PayrollFrequency, SalaryType

class SalarySchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'employee_id'), 
        dump_only=True
    )
    base_salary = fields.Float(dump_only=True)
    salary_type = fields.String(dump_only=True)
    frequency = fields.String(dump_only=True)
    effective_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class SalaryCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    base_salary = fields.Float(required=True)
    salary_type = fields.String(
        validate=validate.OneOf([st.value for st in SalaryType])
    )
    frequency = fields.String(
        validate=validate.OneOf([pf.value for pf in PayrollFrequency])
    )
    effective_date = fields.Date(required=True)
    end_date = fields.Date()
    
    @validates('base_salary')
    def validate_base_salary(self, value):
        if value < 0:
            raise ValidationError("Base salary cannot be negative")
    
    @validates('effective_date')
    def validate_effective_date(self, value):
        if value < date.today():
            raise ValidationError("Effective date cannot be in the past")
    
    @validates('end_date')
    def validate_end_date(self, value):
        if value and 'effective_date' in self.context and value < self.context['effective_date']:
            raise ValidationError("End date must be on or after effective date")

class PayrollSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee_id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'employee_id', 'position'), 
        dump_only=True
    )
    period_start = fields.Date(dump_only=True)
    period_end = fields.Date(dump_only=True)
    base_salary = fields.Float(dump_only=True)
    overtime_hours = fields.Float(dump_only=True)
    overtime_amount = fields.Float(dump_only=True)
    bonus = fields.Float(dump_only=True)
    bonus_description = fields.String(dump_only=True)
    deductions = fields.Float(dump_only=True)
    deduction_description = fields.String(dump_only=True)
    tax = fields.Float(dump_only=True)
    net_amount = fields.Float(dump_only=True)
    status = fields.String(dump_only=True)
    payment_date = fields.Date(dump_only=True)
    notes = fields.String(dump_only=True)
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class PayrollCreateSchema(Schema):
    employee_id = fields.Integer(required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    base_salary = fields.Float(required=True)
    overtime_hours = fields.Float()
    overtime_amount = fields.Float()
    bonus = fields.Float()
    bonus_description = fields.String()
    deductions = fields.Float()
    deduction_description = fields.String()
    tax = fields.Float()
    net_amount = fields.Float(required=True)
    status = fields.String(
        validate=validate.OneOf([ps.value for ps in PayrollStatus])
    )
    payment_date = fields.Date()
    notes = fields.String()
    
    @validates('period_end')
    def validate_period_end(self, value):
        if 'period_start' in self.context and value < self.context['period_start']:
            raise ValidationError("Period end date must be on or after period start date")
    
    @validates('net_amount')
    def validate_net_amount(self, value):
        if value < 0:
            raise ValidationError("Net amount cannot be negative")

class PayrollUpdateSchema(Schema):
    overtime_hours = fields.Float()
    overtime_amount = fields.Float()
    bonus = fields.Float()
    bonus_description = fields.String()
    deductions = fields.Float()
    deduction_description = fields.String()
    tax = fields.Float()
    net_amount = fields.Float()
    status = fields.String(
        validate=validate.OneOf([ps.value for ps in PayrollStatus])
    )
    payment_date = fields.Date()
    notes = fields.String()
    
    @validates('net_amount')
    def validate_net_amount(self, value):
        if value < 0:
            raise ValidationError("Net amount cannot be negative")

class PayslipGenerateSchema(Schema):
    payroll_id = fields.Integer(required=True)
    include_breakdown = fields.Boolean()
    include_company_logo = fields.Boolean()
    include_signature = fields.Boolean()