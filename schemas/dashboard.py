from marshmallow import Schema, fields

class DashboardEmployeeSchema(Schema):
    id = fields.Integer(dump_only=True)
    first_name = fields.String(dump_only=True)
    last_name = fields.String(dump_only=True)
    full_name = fields.String(dump_only=True)
    employee_id = fields.String(dump_only=True)
    position = fields.String(dump_only=True)
    department = fields.Nested(
        'DepartmentSchema', 
        only=('id', 'name'), 
        dump_only=True
    )
    date_of_joining = fields.Date(dump_only=True)
    date_of_birth = fields.Date(dump_only=True)
    profile_image = fields.String(dump_only=True)

class DashboardProjectSchema(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    start_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)
    task_completion_rate = fields.Float(dump_only=True)
    creator = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )

class DashboardTaskSchema(Schema):
    id = fields.Integer(dump_only=True)
    title = fields.String(dump_only=True)
    project = fields.Nested(
        'ProjectSchema', 
        only=('id', 'name'), 
        dump_only=True
    )
    status = fields.String(dump_only=True)
    priority = fields.String(dump_only=True)
    progress = fields.Integer(dump_only=True)
    due_date = fields.Date(dump_only=True)
    is_overdue = fields.Boolean(dump_only=True)

class DashboardLeaveSchema(Schema):
    id = fields.Integer(dump_only=True)
    employee = fields.Nested(
        'EmployeeSchema', 
        only=('id', 'first_name', 'last_name', 'full_name'), 
        dump_only=True
    )
    leave_type = fields.String(dump_only=True)
    start_date = fields.Date(dump_only=True)
    end_date = fields.Date(dump_only=True)
    days = fields.Float(dump_only=True)
    status = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

class DashboardOverviewSchema(Schema):
    total_employees = fields.Integer(dump_only=True)
    present_today = fields.Integer(dump_only=True)
    absent_today = fields.Integer(dump_only=True)
    on_leave_today = fields.Integer(dump_only=True)
    pending_leaves = fields.Integer(dump_only=True)
    active_projects = fields.Integer(dump_only=True)
    completed_tasks = fields.Integer(dump_only=True)
    overdue_tasks = fields.Integer(dump_only=True)

class DashboardAttendanceSchema(Schema):
    date = fields.Date(dump_only=True)
    status = fields.String(dump_only=True)
    clock_in = fields.DateTime(dump_only=True)
    clock_out = fields.DateTime(dump_only=True)
    hours_worked = fields.Float(dump_only=True)
    work_from = fields.String(dump_only=True)
