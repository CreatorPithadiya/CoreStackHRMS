from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date

class DepartmentSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True)
    description = fields.String()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class EmployeeSchema(Schema):
    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    user = fields.Nested('UserSchema', only=('email', 'role', 'is_active'), dump_only=True)
    department_id = fields.Integer()
    department = fields.Nested(DepartmentSchema, only=('id', 'name'), dump_only=True)
    first_name = fields.String()
    last_name = fields.String()
    full_name = fields.String(dump_only=True)
    employee_id = fields.String()
    position = fields.String()
    date_of_birth = fields.Date()
    date_of_joining = fields.Date()
    phone_number = fields.String()
    address = fields.String()
    gender = fields.String(validate=validate.OneOf(['male', 'female', 'other', '']))
    manager_id = fields.Integer(allow_none=True)
    manager = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name', 'position'), 
        dump_only=True
    )
    profile_image = fields.String()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    @validates('date_of_birth')
    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise ValidationError("Date of birth cannot be in the future")

class EmployeeCreateSchema(Schema):
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    employee_id = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String()
    department_id = fields.Integer()
    position = fields.String()
    date_of_birth = fields.Date()
    date_of_joining = fields.Date(required=True)
    phone_number = fields.String()
    address = fields.String()
    gender = fields.String(validate=validate.OneOf(['male', 'female', 'other', '']))
    manager_id = fields.Integer()
    profile_image = fields.String()
    
    @validates('date_of_birth')
    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise ValidationError("Date of birth cannot be in the future")
    
    @validates('date_of_joining')
    def validate_date_of_joining(self, value):
        if value and value > date.today():
            raise ValidationError("Date of joining cannot be in the future")

class EmployeeUpdateSchema(Schema):
    first_name = fields.String()
    last_name = fields.String()
    department_id = fields.Integer(allow_none=True)
    position = fields.String()
    date_of_birth = fields.Date()
    phone_number = fields.String()
    address = fields.String()
    gender = fields.String(validate=validate.OneOf(['male', 'female', 'other', '']))
    manager_id = fields.Integer(allow_none=True)
    profile_image = fields.String()
    
    @validates('date_of_birth')
    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise ValidationError("Date of birth cannot be in the future")
