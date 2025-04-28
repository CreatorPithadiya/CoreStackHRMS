from marshmallow import Schema, fields, validate, validates, ValidationError
from models import Role

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)

class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))
    role = fields.String(
        required=True,
        validate=validate.OneOf([r.value for r in Role])
    )
    
    @validates('role')
    def validate_role(self, value):
        try:
            Role[value.upper()]
        except KeyError:
            raise ValidationError(f"Invalid role: {value}")

class ChangePasswordSchema(Schema):
    current_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=validate.Length(min=8))

class UserSchema(Schema):
    id = fields.Integer(dump_only=True)
    email = fields.Email(dump_only=True)
    role = fields.String(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    last_login = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
