from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, case, extract
from datetime import datetime, date, timedelta
from app import db
from models import (
    User, Employee, Attendance, LeaveRequest, LeaveStatus,
    Project, Task, TaskStatus, Role
)
from schemas.dashboard import (
    DashboardEmployeeSchema, DashboardProjectSchema,
    DashboardOverviewSchema, DashboardAttendanceSchema
)
from utils.responses import success_response, error_response

dashboard_bp = Blueprint('dashboard', __name__)

# Get dashboard data
@dashboard_bp.route('', methods=['GET'])
@jwt_required()
def get_dashboard():
    """
    Get dashboard data
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    responses:
      200:
        description: Dashboard data
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Different data based on user role
    if current_user.role in [Role.ADMIN, Role.HR]:
        return get_admin_dashboard()
    elif current_user.role == Role.MANAGER:
        return get_manager_dashboard(employee.id)
    else:
        return get_employee_dashboard(employee.id)

def get_admin_dashboard():
    """Get dashboard data for admin and HR roles"""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Employee counts
    total_employees = Employee.query.count()
    
    # Attendance stats for today
    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status == 'present'
    ).count()
    
    absent_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status == 'absent'
    ).count()
    
    # Leave stats for this month
    leave_counts = db.session.query(
        LeaveRequest.status,
        func.count(LeaveRequest.id)
    ).filter(
        LeaveRequest.start_date >= current_month_start
    ).group_by(LeaveRequest.status).all()
    
    leave_stats = {status.value: 0 for status in LeaveStatus}
    for status, count in leave_counts:
        leave_stats[status.value] = count
    
    # Project stats
    project_counts = db.session.query(
        Project.status,
        func.count(Project.id)
    ).group_by(Project.status).all()
    
    project_stats = {status.value: 0 for status in Project.status.property.columns[0].type.enums}
    for status, count in project_counts:
        project_stats[status.value] = count
    
    # Task stats
    task_counts = db.session.query(
        Task.status,
        func.count(Task.id)
    ).group_by(Task.status).all()
    
    task_stats = {status.value: 0 for status in Task.status.property.columns[0].type.enums}
    for status, count in task_counts:
        task_stats[status.value] = count
    
    # Recently joined employees
    recent_employees = Employee.query.order_by(
        Employee.date_of_joining.desc()
    ).limit(5).all()
    
    # Upcoming birthdays
    upcoming_birthdays = Employee.query.filter(
        extract('month', Employee.date_of_birth) == today.month,
        extract('day', Employee.date_of_birth) >= today.day
    ).order_by(
        extract('day', Employee.date_of_birth)
    ).limit(5).all()
    
    # Projects nearing deadline (ending in next 7 days)
    upcoming_deadlines = Project.query.filter(
        Project.end_date.between(today, today + timedelta(days=7))
    ).order_by(Project.end_date).limit(5).all()
    
    # Pending leave requests
    pending_leaves = LeaveRequest.query.filter(
        LeaveRequest.status == LeaveStatus.PENDING
    ).order_by(LeaveRequest.created_at.desc()).limit(10).all()
    
    return success_response({
        "overview": {
            "total_employees": total_employees,
            "present_today": present_today,
            "absent_today": absent_today,
            "on_leave_today": LeaveRequest.query.filter(
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
                LeaveRequest.status == LeaveStatus.APPROVED
            ).count(),
            "pending_leaves": leave_stats.get('pending', 0),
            "active_projects": project_stats.get('in_progress', 0),
            "completed_tasks": task_stats.get('completed', 0),
            "overdue_tasks": Task.query.filter(
                Task.due_date < today,
                Task.status != TaskStatus.COMPLETED
            ).count()
        },
        "employees": {
            "recent_joins": DashboardEmployeeSchema(many=True).dump(recent_employees),
            "upcoming_birthdays": DashboardEmployeeSchema(many=True).dump(upcoming_birthdays)
        },
        "projects": {
            "upcoming_deadlines": DashboardProjectSchema(many=True).dump(upcoming_deadlines),
            "by_status": project_stats
        },
        "tasks": {
            "by_status": task_stats
        },
        "leaves": {
            "by_status": leave_stats,
            "pending_requests": [{
                "id": leave.id,
                "employee": f"{leave.employee.first_name} {leave.employee.last_name}",
                "employee_id": leave.employee.id,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "days": leave.days,
                "leave_type": leave.leave_type.value,
                "created_at": leave.created_at.isoformat()
            } for leave in pending_leaves]
        }
    })

def get_manager_dashboard(manager_id):
    """Get dashboard data for managers"""
    today = date.today()
    
    # Get team members
    team_members = Employee.query.filter_by(manager_id=manager_id).all()
    team_ids = [employee.id for employee in team_members] + [manager_id]
    
    # Team size
    team_size = len(team_members)
    
    # Team attendance today
    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status == 'present',
        Attendance.employee_id.in_(team_ids)
    ).count()
    
    # Team members on leave today
    on_leave_today = LeaveRequest.query.filter(
        LeaveRequest.start_date <= today,
        LeaveRequest.end_date >= today,
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.employee_id.in_(team_ids)
    ).count()
    
    # Get projects where manager is a member
    manager_projects = db.session.query(Project.id).join(
        Project.members
    ).filter(
        Project.members.any(employee_id=manager_id)
    ).all()
    
    project_ids = [p[0] for p in manager_projects]
    
    # Pending tasks in manager's projects
    pending_tasks = Task.query.filter(
        Task.project_id.in_(project_ids),
        Task.status != TaskStatus.COMPLETED
    ).count()
    
    # Tasks assigned to team
    team_tasks = Task.query.filter(
        Task.assignee_id.in_(team_ids)
    ).count()
    
    # Pending leave requests from team
    pending_leaves = LeaveRequest.query.filter(
        LeaveRequest.employee_id.in_(team_ids),
        LeaveRequest.status == LeaveStatus.PENDING
    ).order_by(LeaveRequest.created_at.desc()).all()
    
    # Team tasks by status
    task_status_counts = db.session.query(
        Task.status,
        func.count(Task.id)
    ).filter(
        Task.assignee_id.in_(team_ids)
    ).group_by(Task.status).all()
    
    task_stats = {status.value: 0 for status in Task.status.property.columns[0].type.enums}
    for status, count in task_status_counts:
        task_stats[status.value] = count
    
    # Team projects with progress
    team_projects = Project.query.filter(
        Project.id.in_(project_ids)
    ).order_by(Project.end_date).limit(5).all()
    
    return success_response({
        "overview": {
            "team_size": team_size,
            "present_today": present_today,
            "on_leave_today": on_leave_today,
            "pending_tasks": pending_tasks,
            "team_task_completion_rate": calculate_completion_rate(task_stats),
            "pending_leave_requests": len(pending_leaves)
        },
        "team": {
            "members": DashboardEmployeeSchema(many=True).dump(team_members)
        },
        "tasks": {
            "by_status": task_stats,
            "total": team_tasks
        },
        "projects": {
            "active": DashboardProjectSchema(many=True).dump(team_projects)
        },
        "leaves": {
            "pending_requests": [{
                "id": leave.id,
                "employee": f"{leave.employee.first_name} {leave.employee.last_name}",
                "employee_id": leave.employee.id,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "days": leave.days,
                "leave_type": leave.leave_type.value,
                "created_at": leave.created_at.isoformat()
            } for leave in pending_leaves]
        }
    })

def get_employee_dashboard(employee_id):
    """Get dashboard data for regular employees"""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Get today's attendance
    today_attendance = Attendance.query.filter_by(
        employee_id=employee_id,
        date=today
    ).first()
    
    # Get monthly attendance summary
    month_attendance = Attendance.query.filter(
        Attendance.employee_id == employee_id,
        Attendance.date >= current_month_start,
        Attendance.date <= today
    ).all()
    
    present_days = sum(1 for a in month_attendance if a.status == 'present')
    absent_days = sum(1 for a in month_attendance if a.status == 'absent')
    half_days = sum(1 for a in month_attendance if a.status == 'half-day')
    
    # Calculate working days in the month
    business_days = sum(1 for d in (current_month_start + timedelta(days=x) 
                      for x in range((today - current_month_start).days + 1)) 
                      if d.weekday() < 5)
    
    # Get leave balance (simplified version)
    leave_taken = db.session.query(func.sum(LeaveRequest.days)).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        extract('year', LeaveRequest.start_date) == today.year
    ).scalar() or 0
    
    # Tasks assigned to employee
    my_tasks = Task.query.filter_by(
        assignee_id=employee_id
    ).all()
    
    # Tasks by status
    task_counts = {status.value: 0 for status in Task.status.property.columns[0].type.enums}
    for task in my_tasks:
        task_counts[task.status.value] += 1
    
    # Upcoming deadlines (tasks due in next 7 days)
    upcoming_deadlines = Task.query.filter(
        Task.assignee_id == employee_id,
        Task.status != TaskStatus.COMPLETED,
        Task.due_date.between(today, today + timedelta(days=7))
    ).order_by(Task.due_date).all()
    
    # Projects employee is part of
    my_projects = Project.query.join(
        Project.members
    ).filter(
        Project.members.any(employee_id=employee_id)
    ).all()
    
    # Recent leave requests
    recent_leaves = LeaveRequest.query.filter_by(
        employee_id=employee_id
    ).order_by(LeaveRequest.created_at.desc()).limit(5).all()
    
    return success_response({
        "attendance": {
            "today": {
                "status": today_attendance.status if today_attendance else "not_recorded",
                "clock_in": today_attendance.clock_in.isoformat() if today_attendance and today_attendance.clock_in else None,
                "clock_out": today_attendance.clock_out.isoformat() if today_attendance and today_attendance.clock_out else None,
                "hours_worked": today_attendance.hours_worked if today_attendance else 0
            },
            "monthly": {
                "present_days": present_days,
                "absent_days": absent_days,
                "half_days": half_days,
                "not_recorded": business_days - present_days - absent_days - half_days,
                "attendance_rate": round((present_days + (half_days * 0.5)) / business_days * 100, 2) if business_days > 0 else 0
            }
        },
        "leaves": {
            "balance": {
                "annual": {
                    "entitled": 20,  # Simplified, would come from policy
                    "taken": leave_taken,
                    "remaining": 20 - leave_taken
                }
            },
            "recent_requests": [{
                "id": leave.id,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "days": leave.days,
                "leave_type": leave.leave_type.value,
                "status": leave.status.value,
                "created_at": leave.created_at.isoformat()
            } for leave in recent_leaves]
        },
        "tasks": {
            "by_status": task_counts,
            "total": len(my_tasks),
            "upcoming_deadlines": [{
                "id": task.id,
                "title": task.title,
                "project_name": task.project.name,
                "priority": task.priority.value,
                "due_date": task.due_date.isoformat(),
                "progress": task.progress
            } for task in upcoming_deadlines]
        },
        "projects": {
            "count": len(my_projects),
            "list": [{
                "id": project.id,
                "name": project.name,
                "status": project.status.value,
                "my_tasks_count": sum(1 for t in project.tasks if t.assignee_id == employee_id)
            } for project in my_projects]
        }
    })

def calculate_completion_rate(task_stats):
    """Calculate task completion rate from status counts"""
    total = sum(task_stats.values())
    if total == 0:
        return 0
    
    completed = task_stats.get('completed', 0)
    return round((completed / total) * 100, 2)

# Get attendance statistics
@dashboard_bp.route('/attendance', methods=['GET'])
@jwt_required()
def get_attendance_stats():
    """
    Get attendance statistics for dashboard
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    parameters:
      - name: period
        in: query
        type: string
        enum: [day, week, month]
        default: day
    responses:
      200:
        description: Attendance statistics
      401:
        description: Unauthorized
    """
    period = request.args.get('period', 'day')
    today = date.today()
    
    # Determine date range based on period
    if period == 'week':
        # Get current week (last 7 days)
        start_date = today - timedelta(days=6)
        date_range = [start_date + timedelta(days=i) for i in range(7)]
        label_format = '%a'  # Abbreviated weekday
    elif period == 'month':
        # Get current month
        start_date = date(today.year, today.month, 1)
        days_in_month = (date(today.year, today.month % 12 + 1, 1) if today.month < 12 
                         else date(today.year + 1, 1, 1)) - timedelta(days=1)
        date_range = [start_date + timedelta(days=i) for i in range(days_in_month.day)]
        label_format = '%d'  # Day of month
    else:  # day
        # Get hourly breakdown for today
        date_range = [i for i in range(9, 18)]  # 9 AM to 5 PM
        label_format = '%H:00'  # Hour format
    
    # Get current user's role
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if current_user.role in [Role.ADMIN, Role.HR]:
        # For admins and HR, get company-wide statistics
        if period == 'day':
            # Get hourly clock-ins for today
            clock_in_counts = db.session.query(
                extract('hour', Attendance.clock_in).label('hour'),
                func.count(Attendance.id)
            ).filter(
                func.date(Attendance.clock_in) == today
            ).group_by('hour').all()
            
            # Format data for chart
            labels = [f"{hour}:00" for hour in range(9, 18)]
            attendance_data = [0] * len(labels)
            
            for hour, count in clock_in_counts:
                if 9 <= hour < 18:
                    attendance_data[int(hour) - 9] = count
            
            # Calculate clock-in time statistics
            on_time = db.session.query(func.count(Attendance.id)).filter(
                func.date(Attendance.clock_in) == today,
                extract('hour', Attendance.clock_in) < 10  # Before 10 AM
            ).scalar() or 0
            
            late = db.session.query(func.count(Attendance.id)).filter(
                func.date(Attendance.clock_in) == today,
                extract('hour', Attendance.clock_in) >= 10  # 10 AM or later
            ).scalar() or 0
            
            return success_response({
                "period": "day",
                "labels": labels,
                "datasets": [{
                    "name": "Clock-ins",
                    "data": attendance_data
                }],
                "summary": {
                    "total_attendance": sum(attendance_data),
                    "on_time": on_time,
                    "late": late,
                    "absent": Employee.query.count() - (on_time + late)
                }
            })
        else:
            # For week/month, get daily attendance counts
            attendance_counts = db.session.query(
                Attendance.date,
                func.count(Attendance.id).filter(Attendance.status == 'present').label('present'),
                func.count(Attendance.id).filter(Attendance.status == 'absent').label('absent'),
                func.count(Attendance.id).filter(Attendance.status == 'half-day').label('half_day')
            ).filter(
                Attendance.date.in_([d for d in date_range if isinstance(d, date)])
            ).group_by(Attendance.date).all()
            
            # Format data for chart
            date_map = {d: i for i, d in enumerate(date_range) if isinstance(d, date)}
            labels = [d.strftime(label_format) for d in date_range if isinstance(d, date)]
            
            present_data = [0] * len(labels)
            absent_data = [0] * len(labels)
            half_day_data = [0] * len(labels)
            
            for att_date, present, absent, half_day in attendance_counts:
                if att_date in date_map:
                    idx = date_map[att_date]
                    present_data[idx] = present
                    absent_data[idx] = absent
                    half_day_data[idx] = half_day
            
            return success_response({
                "period": period,
                "labels": labels,
                "datasets": [
                    {
                        "name": "Present",
                        "data": present_data
                    },
                    {
                        "name": "Absent",
                        "data": absent_data
                    },
                    {
                        "name": "Half-day",
                        "data": half_day_data
                    }
                ],
                "summary": {
                    "total_working_days": len(labels),
                    "avg_attendance_rate": calculate_avg_attendance_rate(present_data, absent_data, half_day_data)
                }
            })
    else:
        # For regular employees, get their own attendance
        employee = Employee.query.filter_by(user_id=current_user_id).first()
        
        if not employee:
            return error_response("Employee profile not found", 404)
        
        if period == 'day':
            # Get employee's attendance for today
            today_attendance = Attendance.query.filter_by(
                employee_id=employee.id,
                date=today
            ).first()
            
            clock_in_time = today_attendance.clock_in.hour if today_attendance and today_attendance.clock_in else None
            clock_out_time = today_attendance.clock_out.hour if today_attendance and today_attendance.clock_out else None
            
            # Create hours worked chart data
            labels = [f"{hour}:00" for hour in range(9, 18)]
            hours_worked = [0] * len(labels)
            
            if clock_in_time is not None and clock_out_time is not None:
                start_idx = max(0, clock_in_time - 9)
                end_idx = min(len(labels), clock_out_time - 9)
                
                for i in range(start_idx, end_idx):
                    hours_worked[i] = 1  # Mark hour as worked
            
            return success_response({
                "period": "day",
                "labels": labels,
                "datasets": [{
                    "name": "Hours Worked",
                    "data": hours_worked
                }],
                "summary": {
                    "status": today_attendance.status if today_attendance else "not_recorded",
                    "clock_in": today_attendance.clock_in.isoformat() if today_attendance and today_attendance.clock_in else None,
                    "clock_out": today_attendance.clock_out.isoformat() if today_attendance and today_attendance.clock_out else None,
                    "hours_worked": today_attendance.hours_worked if today_attendance else 0,
                    "on_time": today_attendance and today_attendance.clock_in and today_attendance.clock_in.hour < 10
                }
            })
        else:
            # Get employee's attendance for date range
            attendance_records = Attendance.query.filter(
                Attendance.employee_id == employee.id,
                Attendance.date.in_([d for d in date_range if isinstance(d, date)])
            ).all()
            
            # Format data for chart
            date_map = {d: i for i, d in enumerate(date_range) if isinstance(d, date)}
            labels = [d.strftime(label_format) for d in date_range if isinstance(d, date)]
            
            status_data = [None] * len(labels)  # None for not recorded
            hours_data = [0] * len(labels)
            
            for record in attendance_records:
                if record.date in date_map:
                    idx = date_map[record.date]
                    status_data[idx] = record.status
                    hours_data[idx] = record.hours_worked
            
            return success_response({
                "period": period,
                "labels": labels,
                "datasets": [
                    {
                        "name": "Hours Worked",
                        "data": hours_data
                    }
                ],
                "status_data": status_data,
                "summary": {
                    "present_days": sum(1 for s in status_data if s == 'present'),
                    "absent_days": sum(1 for s in status_data if s == 'absent'),
                    "half_days": sum(1 for s in status_data if s == 'half-day'),
                    "not_recorded": sum(1 for s in status_data if s is None),
                    "total_hours": sum(hours_data)
                }
            })

def calculate_avg_attendance_rate(present_data, absent_data, half_day_data):
    """Calculate average attendance rate from present, absent and half-day counts"""
    days = []
    for p, a, h in zip(present_data, absent_data, half_day_data):
        total = p + a + h
        if total > 0:
            days.append((p + (h * 0.5)) / total * 100)
    
    return round(sum(days) / len(days), 2) if days else 0

# Get project statistics
@dashboard_bp.route('/projects', methods=['GET'])
@jwt_required()
def get_project_stats():
    """
    Get project statistics for dashboard
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    responses:
      200:
        description: Project statistics
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Get project statistics
    if current_user.role in [Role.ADMIN, Role.HR]:
        # For admins and HR, get all projects
        projects = Project.query.all()
    else:
        # For other roles, get projects they're part of
        projects = Project.query.join(
            Project.members
        ).filter(
            db.or_(
                Project.members.any(employee_id=employee.id),
                Project.created_by == employee.id
            )
        ).distinct().all()
    
    # Get project statistics by status
    status_counts = {status.value: 0 for status in Project.status.property.columns[0].type.enums}
    for project in projects:
        status_counts[project.status.value] += 1
    
    # Get task completion rate for each project
    project_data = []
    for project in projects:
        total_tasks = len(project.tasks)
        completed_tasks = sum(1 for task in project.tasks if task.status == TaskStatus.COMPLETED)
        
        # Calculate completion rate
        completion_rate = round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0
        
        project_data.append({
            "id": project.id,
            "name": project.name,
            "status": project.status.value,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "task_count": total_tasks,
            "completion_rate": completion_rate,
            "members_count": len(project.members)
        })
    
    # Sort by end date (closest deadline first)
    project_data.sort(key=lambda p: p.get("end_date") or "9999-12-31")
    
    return success_response({
        "by_status": status_counts,
        "total": len(projects),
        "projects": project_data[:10]  # Return top 10 projects
    })

# Get task statistics
@dashboard_bp.route('/tasks', methods=['GET'])
@jwt_required()
def get_task_stats():
    """
    Get task statistics for dashboard
    ---
    tags:
      - Dashboard
    security:
      - Bearer: []
    responses:
      200:
        description: Task statistics
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Get task statistics
    today = date.today()
    
    # Different queries based on role
    if current_user.role in [Role.ADMIN, Role.HR]:
        # For admins and HR, get all tasks
        tasks = Task.query.all()
        
        # Get tasks by priority
        priority_counts = db.session.query(
            Task.priority, 
            func.count(Task.id)
        ).group_by(Task.priority).all()
        
        priority_stats = {priority.value: 0 for priority in Task.priority.property.columns[0].type.enums}
        for priority, count in priority_counts:
            priority_stats[priority.value] = count
        
        # Get tasks by status
        status_counts = db.session.query(
            Task.status, 
            func.count(Task.id)
        ).group_by(Task.status).all()
        
        status_stats = {status.value: 0 for status in Task.status.property.columns[0].type.enums}
        for status, count in status_counts:
            status_stats[status.value] = count
        
        # Get overdue tasks
        overdue_tasks = Task.query.filter(
            Task.due_date < today,
            Task.status != TaskStatus.COMPLETED
        ).count()
        
        # Get recently completed tasks
        recently_completed = Task.query.filter(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at >= (today - timedelta(days=7))
        ).count()
        
        return success_response({
            "by_priority": priority_stats,
            "by_status": status_stats,
            "total": len(tasks),
            "overdue": overdue_tasks,
            "recently_completed": recently_completed,
            "completion_rate": round((status_stats.get('completed', 0) / len(tasks) * 100), 2) if tasks else 0
        })
    else:
        # For regular employees, get tasks they're assigned to
        assigned_tasks = Task.query.filter_by(assignee_id=employee.id).all()
        
        # Get status counts
        status_counts = {status.value: 0 for status in Task.status.property.columns[0].type.enums}
        for task in assigned_tasks:
            status_counts[task.status.value] += 1
        
        # Get priority counts
        priority_counts = {priority.value: 0 for priority in Task.priority.property.columns[0].type.enums}
        for task in assigned_tasks:
            priority_counts[task.priority.value] += 1
        
        # Get overdue tasks
        overdue_tasks = Task.query.filter(
            Task.assignee_id == employee.id,
            Task.due_date < today,
            Task.status != TaskStatus.COMPLETED
        ).count()
        
        # Get upcoming deadlines
        upcoming_deadlines = Task.query.filter(
            Task.assignee_id == employee.id,
            Task.status != TaskStatus.COMPLETED,
            Task.due_date.between(today, today + timedelta(days=7))
        ).order_by(Task.due_date).all()
        
        return success_response({
            "by_priority": priority_counts,
            "by_status": status_counts,
            "total": len(assigned_tasks),
            "overdue": overdue_tasks,
            "completion_rate": round((status_counts.get('completed', 0) / len(assigned_tasks) * 100), 2) if assigned_tasks else 0,
            "upcoming_deadlines": [{
                "id": task.id,
                "title": task.title,
                "project_name": task.project.name,
                "project_id": task.project_id,
                "priority": task.priority.value,
                "due_date": task.due_date.isoformat(),
                "progress": task.progress
            } for task in upcoming_deadlines]
        })
