import enum
from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash

# Role enum for RBAC
class Role(enum.Enum):
    ADMIN = "admin"
    HR = "hr"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    CLIENT = "client"  # For future use

# User model for authentication
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(Role), default=Role.EMPLOYEE, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Link to employee
    employee = db.relationship('Employee', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

# Department model
class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employees = db.relationship('Employee', backref='department', lazy=True)
    
    def __repr__(self):
        return f'<Department {self.name}>'

# Employee model
class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)  # Company employee ID
    position = db.Column(db.String(100), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    date_of_joining = db.Column(db.Date, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)  # URL to profile image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    team_members = db.relationship('Employee', backref=db.backref('manager', remote_side=[id]), lazy='dynamic')
    attendance_records = db.relationship('Attendance', backref='employee', lazy=True)
    leave_requests = db.relationship('LeaveRequest', backref='employee', lazy=True, foreign_keys='LeaveRequest.employee_id')
    projects = db.relationship('ProjectMember', backref='employee', lazy=True)
    assigned_tasks = db.relationship('Task', backref='assignee', lazy=True, foreign_keys='Task.assignee_id')
    created_tasks = db.relationship('Task', backref='creator', lazy=True, foreign_keys='Task.created_by')
    task_comments = db.relationship('TaskComment', backref='employee', lazy=True)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<Employee {self.full_name}>'

# Attendance model
class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    clock_in = db.Column(db.DateTime, nullable=True)
    clock_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='present', nullable=False)  # present, absent, half-day
    work_from = db.Column(db.String(20), default='office', nullable=False)  # office, home, remote
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='uix_employee_date'),
    )
    
    @property
    def hours_worked(self):
        if self.clock_in and self.clock_out:
            delta = self.clock_out - self.clock_in
            return round(delta.total_seconds() / 3600, 2)
        return 0
    
    def __repr__(self):
        return f'<Attendance {self.employee_id} on {self.date}>'

# Leave types enum
class LeaveType(enum.Enum):
    ANNUAL = "annual"
    SICK = "sick"
    PERSONAL = "personal"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    BEREAVEMENT = "bereavement"
    UNPAID = "unpaid"
    OTHER = "other"

# Leave status enum
class LeaveStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

# Leave Request model
class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.Enum(LeaveType), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Float, nullable=False)  # Support for half-days
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to reviewer
    reviewer = db.relationship('Employee', foreign_keys=[reviewed_by], backref='reviewed_leaves')
    
    def __repr__(self):
        return f'<LeaveRequest {self.employee_id} from {self.start_date} to {self.end_date}>'

# Project status enum
class ProjectStatus(enum.Enum):
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# Project model
class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(ProjectStatus), default=ProjectStatus.PLANNING, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    budget = db.Column(db.Float, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = db.relationship('ProjectMember', backref='project', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='project', lazy=True, cascade='all, delete-orphan')
    
    # Relationship to creator
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='created_projects')
    
    @property
    def task_completion_rate(self):
        if not self.tasks:
            return 0
        completed = sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)
        return round((completed / len(self.tasks)) * 100, 2)
    
    def __repr__(self):
        return f'<Project {self.name}>'

# Project Member model (for many-to-many relationship)
class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    role = db.Column(db.String(50), default='member', nullable=False)  # project manager, team lead, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('project_id', 'employee_id', name='uix_project_employee'),
    )
    
    def __repr__(self):
        return f'<ProjectMember {self.employee_id} in Project {self.project_id}>'

# Task priority enum
class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Task status enum
class TaskStatus(enum.Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"

# Task model
class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = db.Column(db.Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)  # 0-100 percent
    estimated_hours = db.Column(db.Float, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    comments = db.relationship('TaskComment', backref='task', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Task {self.title}>'

# Task Comment model
class TaskComment(db.Model):
    __tablename__ = 'task_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskComment {self.id} by {self.employee_id}>'

# Phase 2 Models

# Payroll related models
class PayrollFrequency(enum.Enum):
    MONTHLY = "monthly"
    BIWEEKLY = "biweekly"
    WEEKLY = "weekly"

class SalaryType(enum.Enum):
    FIXED = "fixed"
    HOURLY = "hourly"
    COMMISSION = "commission"

class PayrollStatus(enum.Enum):
    DRAFT = "draft"
    PROCESSED = "processed"
    PAID = "paid"
    CANCELLED = "cancelled"

class Salary(db.Model):
    __tablename__ = 'salaries'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    base_salary = db.Column(db.Float, nullable=False)
    salary_type = db.Column(db.Enum(SalaryType), default=SalaryType.FIXED, nullable=False)
    frequency = db.Column(db.Enum(PayrollFrequency), default=PayrollFrequency.MONTHLY, nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)  # Null means current
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='salaries')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='salary_adjustments_made')
    
    def __repr__(self):
        return f'<Salary {self.employee_id} {self.base_salary}>'

class Payroll(db.Model):
    __tablename__ = 'payrolls'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    base_salary = db.Column(db.Float, nullable=False)
    overtime_hours = db.Column(db.Float, default=0, nullable=False)
    overtime_amount = db.Column(db.Float, default=0, nullable=False)
    bonus = db.Column(db.Float, default=0, nullable=False)
    bonus_description = db.Column(db.Text, nullable=True)
    deductions = db.Column(db.Float, default=0, nullable=False)
    deduction_description = db.Column(db.Text, nullable=True)
    tax = db.Column(db.Float, default=0, nullable=False)
    net_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(PayrollStatus), default=PayrollStatus.DRAFT, nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='payrolls')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='payrolls_created')
    
    def __repr__(self):
        return f'<Payroll {self.employee_id} for {self.period_start} to {self.period_end}>'

# OKR related models
class OKRStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class OKRTimeframe(enum.Enum):
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"

class OKR(db.Model):
    __tablename__ = 'okrs'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    timeframe = db.Column(db.Enum(OKRTimeframe), default=OKRTimeframe.QUARTERLY, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(OKRStatus), default=OKRStatus.DRAFT, nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)  # 0-100 percent
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='okrs')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='okrs_created')
    key_results = db.relationship('KeyResult', backref='objective', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<OKR {self.title} for {self.employee_id}>'

class KeyResult(db.Model):
    __tablename__ = 'key_results'
    
    id = db.Column(db.Integer, primary_key=True)
    okr_id = db.Column(db.Integer, db.ForeignKey('okrs.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_value = db.Column(db.Float, nullable=False)
    current_value = db.Column(db.Float, default=0, nullable=False)
    unit = db.Column(db.String(50), nullable=True)  # e.g., "percent", "count", "dollars"
    progress = db.Column(db.Integer, default=0, nullable=False)  # 0-100 percent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<KeyResult {self.title} for OKR {self.okr_id}>'

# Client Access related models
class ClientAccess(db.Model):
    __tablename__ = 'client_access'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    can_view_files = db.Column(db.Boolean, default=False, nullable=False)
    can_view_tasks = db.Column(db.Boolean, default=True, nullable=False)
    can_view_comments = db.Column(db.Boolean, default=False, nullable=False)
    can_view_team = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = db.relationship('User', foreign_keys=[client_id], backref='client_access')
    project = db.relationship('Project', backref='client_access')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='client_access_granted')
    
    __table_args__ = (
        db.UniqueConstraint('client_id', 'project_id', name='uix_client_project'),
    )
    
    def __repr__(self):
        return f'<ClientAccess client={self.client_id} project={self.project_id}>'

# Advanced Features Models

# Employee Mood Tracker
class MoodType(enum.Enum):
    VERY_HAPPY = "very_happy"
    HAPPY = "happy"
    NEUTRAL = "neutral"
    UNHAPPY = "unhappy"
    VERY_UNHAPPY = "very_unhappy"

class MoodTracker(db.Model):
    __tablename__ = 'mood_tracker'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    mood = db.Column(db.Enum(MoodType), nullable=False)
    note = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref='mood_records')
    
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='uix_employee_mood_date'),
    )
    
    def __repr__(self):
        return f'<MoodTracker {self.employee_id} on {self.date} is {self.mood.value}>'

# Performance Feedback
class FeedbackType(enum.Enum):
    PEER = "peer"
    MANAGER = "manager"
    SELF = "self"
    AI_GENERATED = "ai_generated"

class PerformanceFeedback(db.Model):
    __tablename__ = 'performance_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)  # Null for AI generated
    feedback_type = db.Column(db.Enum(FeedbackType), nullable=False)
    content = db.Column(db.Text, nullable=False)
    strengths = db.Column(db.Text, nullable=True)
    areas_of_improvement = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)  # 1-5 scale
    is_draft = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='received_feedback')
    reviewer = db.relationship('Employee', foreign_keys=[reviewer_id], backref='given_feedback')
    
    def __repr__(self):
        return f'<PerformanceFeedback for {self.employee_id} by {self.reviewer_id or "AI"}>'

# Gamified Task System
class RewardType(enum.Enum):
    POINTS = "points"
    BADGE = "badge"
    CERTIFICATE = "certificate"
    BONUS = "bonus"

class TaskReward(db.Model):
    __tablename__ = 'task_rewards'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    reward_type = db.Column(db.Enum(RewardType), nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    name = db.Column(db.String(100), nullable=True)  # For badges/certificates
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    task = db.relationship('Task', backref='rewards')
    
    def __repr__(self):
        return f'<TaskReward {self.reward_type.value} for Task {self.task_id}>'

class EmployeeReward(db.Model):
    __tablename__ = 'employee_rewards'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    task_reward_id = db.Column(db.Integer, db.ForeignKey('task_rewards.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    claimed = db.Column(db.Boolean, default=False, nullable=False)
    claimed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    employee = db.relationship('Employee', backref='rewards')
    task_reward = db.relationship('TaskReward', backref='earned_by')
    
    def __repr__(self):
        return f'<EmployeeReward {self.employee_id} earned {self.task_reward_id}>'

# Workload Heatmap
class WorkloadEntry(db.Model):
    __tablename__ = 'workload_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    workload_percent = db.Column(db.Integer, nullable=False)  # 0-100
    estimated_hours = db.Column(db.Float, nullable=False)
    actual_hours = db.Column(db.Float, nullable=True)
    stress_level = db.Column(db.Integer, nullable=True)  # 1-5 scale
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref='workload_entries')
    
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='uix_employee_workload_date'),
    )
    
    def __repr__(self):
        return f'<WorkloadEntry {self.employee_id} on {self.date} at {self.workload_percent}%>'

# Learning/Upskilling Portal
class LearningCourseStatus(enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class LearningCategory(db.Model):
    __tablename__ = 'learning_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    courses = db.relationship('LearningCourse', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<LearningCategory {self.name}>'

class LearningCourse(db.Model):
    __tablename__ = 'learning_courses'
    
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('learning_categories.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=True)
    estimated_hours = db.Column(db.Float, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='created_courses')
    
    def __repr__(self):
        return f'<LearningCourse {self.title}>'

class EmployeeCourse(db.Model):
    __tablename__ = 'employee_courses'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('learning_courses.id'), nullable=False)
    status = db.Column(db.Enum(LearningCourseStatus), default=LearningCourseStatus.NOT_STARTED, nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)  # 0-100 percent
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    employee = db.relationship('Employee', backref='courses')
    course = db.relationship('LearningCourse', backref='enrolled_employees')
    
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'course_id', name='uix_employee_course'),
    )
    
    def __repr__(self):
        return f'<EmployeeCourse {self.employee_id} taking {self.course_id}>'

# AI Chatbot for HR Queries
class HRQuery(db.Model):
    __tablename__ = 'hr_queries'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    query = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)
    is_private = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref='hr_queries')
    
    def __repr__(self):
        return f'<HRQuery {self.id} by {self.employee_id}>'

# Shadow Login feature for Admins
class ShadowLogin(db.Model):
    __tablename__ = 'shadow_logins'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    actions_logged = db.Column(db.Text, nullable=True)  # JSON string of actions taken during shadow
    
    # Relationships
    admin = db.relationship('Employee', foreign_keys=[admin_id], backref='shadow_logins_performed')
    target = db.relationship('Employee', foreign_keys=[target_id], backref='shadow_logins_received')
    
    def __repr__(self):
        return f'<ShadowLogin admin={self.admin_id} target={self.target_id}>'

# RAG (Red-Amber-Green) Project Progress System
class RAGStatus(enum.Enum):
    RED = "red"
    AMBER = "amber"
    GREEN = "green"

class RAGUpdate(db.Model):
    __tablename__ = 'rag_updates'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    status = db.Column(db.Enum(RAGStatus), nullable=False)
    update_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    description = db.Column(db.Text, nullable=False)
    action_items = db.Column(db.Text, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='rag_updates')
    updater = db.relationship('Employee', foreign_keys=[updated_by], backref='rag_updates_made')
    
    def __repr__(self):
        return f'<RAGUpdate {self.project_id} is {self.status.value} on {self.update_date}>'

# Behavioral Analytics
class BehavioralMetric(db.Model):
    __tablename__ = 'behavioral_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    metric_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    response_time_avg = db.Column(db.Float, nullable=True)  # In minutes
    task_completion_rate = db.Column(db.Float, nullable=True)  # Percentage
    communication_frequency = db.Column(db.Integer, nullable=True)  # Count of communications
    collaboration_score = db.Column(db.Float, nullable=True)  # 0-100 scale
    initiative_score = db.Column(db.Float, nullable=True)  # 0-100 scale
    punctuality_score = db.Column(db.Float, nullable=True)  # 0-100 scale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Employee', backref='behavioral_metrics')
    
    __table_args__ = (
        db.UniqueConstraint('employee_id', 'metric_date', name='uix_employee_metric_date'),
    )
    
    def __repr__(self):
        return f'<BehavioralMetric for {self.employee_id} on {self.metric_date}>'

# Compliance Report System
class ComplianceReportType(enum.Enum):
    GDPR = "gdpr"
    ISO27001 = "iso27001"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    CUSTOM = "custom"

class ComplianceReport(db.Model):
    __tablename__ = 'compliance_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.Enum(ComplianceReportType), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    generated_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data = db.Column(db.Text, nullable=False)  # JSON string of report data
    pdf_url = db.Column(db.String(255), nullable=True)
    
    # Relationships
    generator = db.relationship('Employee', foreign_keys=[generated_by], backref='generated_compliance_reports')
    
    def __repr__(self):
        return f'<ComplianceReport {self.report_type.value} by {self.generated_by}>'
