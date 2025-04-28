from marshmallow import Schema, fields, validate

class ClientAccessSchema(Schema):
    id = fields.Integer(dump_only=True)
    client_id = fields.Integer(dump_only=True)
    client = fields.Nested(
        'UserSchema', 
        only=('id', 'email', 'role'), 
        dump_only=True
    )
    project_id = fields.Integer(dump_only=True)
    project = fields.Nested(
        'ProjectSchema', 
        only=('id', 'name', 'status'), 
        dump_only=True
    )
    can_view_files = fields.Boolean(dump_only=True)
    can_view_tasks = fields.Boolean(dump_only=True)
    can_view_comments = fields.Boolean(dump_only=True)
    can_view_team = fields.Boolean(dump_only=True)
    created_by = fields.Integer(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class ClientAccessCreateSchema(Schema):
    client_id = fields.Integer(required=True)
    project_id = fields.Integer(required=True)
    can_view_files = fields.Boolean()
    can_view_tasks = fields.Boolean()
    can_view_comments = fields.Boolean()
    can_view_team = fields.Boolean()

class ClientAccessUpdateSchema(Schema):
    can_view_files = fields.Boolean()
    can_view_tasks = fields.Boolean()
    can_view_comments = fields.Boolean()
    can_view_team = fields.Boolean()

class ClientProjectViewSchema(Schema):
    project = fields.Nested(
        'ProjectSchema', 
        exclude=('created_by', 'created_at', 'updated_at', 'budget'), 
        dump_only=True
    )
    tasks = fields.List(
        fields.Nested(
            'TaskSchema', 
            only=('id', 'title', 'description', 'status', 'priority', 'progress', 'due_date')
        ), 
        dump_only=True
    )
    members = fields.List(
        fields.Nested(
            'EmployeeSchema', 
            only=('id', 'first_name', 'last_name', 'position')
        ), 
        dump_only=True
    )
    comments = fields.List(
        fields.Nested(
            'TaskCommentSchema', 
            only=('id', 'task_id', 'comment', 'created_at')
        ), 
        dump_only=True
    )