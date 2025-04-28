from flask import Blueprint, request, jsonify, current_app, Response, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc, func, and_, or_
import csv
import io
import json
from datetime import datetime, date, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import base64
from io import BytesIO

from app import db
from models import (
    User, Employee, Role, Department, 
    Attendance, LeaveRequest, 
    Project, Task, ProjectMember, TaskStatus,
    Payroll, Salary,
    OKR, KeyResult
)
from utils.responses import success_response, error_response
from utils.decorators import role_required

reports_bp = Blueprint('reports', __name__)

# Helper function to convert data to CSV
def generate_csv(headers, data, filename):
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(headers)
    for row in data:
        writer.writerow(row)
    
    output = si.getvalue()
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

# Helper function to generate a chart
def generate_chart(title, x_values, y_values, kind='bar', x_label='', y_label='', color='skyblue'):
    plt.figure(figsize=(10, 6))
    
    if kind == 'bar':
        plt.bar(x_values, y_values, color=color)
    elif kind == 'line':
        plt.plot(x_values, y_values, marker='o', linestyle='-', color=color)
    elif kind == 'pie':
        plt.pie(y_values, labels=x_values, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
    
    plt.title(title)
    
    if kind != 'pie':
        plt.xlabel(x_label)
        plt.ylabel(y_label)
        plt.xticks(rotation=45)
        plt.tight_layout()
    
    # Save the figure to a BytesIO object
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    # Encode as base64 for inline display in HTML
    data = base64.b64encode(buf.getbuffer()).decode('ascii')
    
    plt.close()
    
    return data

# ======== ATTENDANCE REPORTS ========

@reports_bp.route('/reports/attendance', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def attendance_report():
    """Generate attendance report"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    department_id = request.args.get('department_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    format_type = request.args.get('format', 'json')  # json, csv, chart
    report_type = request.args.get('report_type', 'daily')  # daily, summary
    
    # Parse dates
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = date.today().replace(day=1)
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today()
    except ValueError:
        return error_response("Invalid date format", "Use YYYY-MM-DD format", 400)
    
    # Build query
    query = db.session.query(
        Employee.id, 
        Employee.first_name, 
        Employee.last_name, 
        Employee.employee_id,
        Department.name.label('department'),
        Attendance.date,
        Attendance.status,
        Attendance.clock_in,
        Attendance.clock_out,
        Attendance.work_from
    ).join(
        Attendance, Employee.id == Attendance.employee_id
    ).outerjoin(
        Department, Employee.department_id == Department.id
    ).filter(
        Attendance.date.between(start_date, end_date)
    )
    
    # Filter by department
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    
    # Filter by employee
    if employee_id:
        query = query.filter(Employee.id == employee_id)
    
    # For managers, restrict to their team
    if user.role == Role.MANAGER and employee:
        team_members = [member.id for member in employee.team_members]
        query = query.filter(Employee.id.in_([employee.id] + team_members))
    
    # Get the data
    attendance_data = query.order_by(Employee.last_name, Employee.first_name, Attendance.date).all()
    
    # Process the data according to report type
    if report_type == 'daily':
        # Detailed daily attendance
        result = []
        for record in attendance_data:
            hours_worked = 0
            if record.clock_in and record.clock_out:
                delta = record.clock_out - record.clock_in
                hours_worked = round(delta.total_seconds() / 3600, 2)
            
            result.append({
                'employee_id': record.employee_id,
                'name': f"{record.first_name} {record.last_name}",
                'department': record.department or 'N/A',
                'date': record.date.isoformat(),
                'status': record.status,
                'clock_in': record.clock_in.isoformat() if record.clock_in else None,
                'clock_out': record.clock_out.isoformat() if record.clock_out else None,
                'hours_worked': hours_worked,
                'work_from': record.work_from
            })
    
    else:  # summary report
        # Group by employee and summarize
        summary = {}
        
        for record in attendance_data:
            emp_key = record.id
            
            if emp_key not in summary:
                summary[emp_key] = {
                    'employee_id': record.employee_id,
                    'name': f"{record.first_name} {record.last_name}",
                    'department': record.department or 'N/A',
                    'days_present': 0,
                    'days_absent': 0,
                    'days_half': 0,
                    'total_hours': 0,
                    'work_from_office': 0,
                    'work_from_home': 0,
                    'work_remote': 0
                }
            
            # Count status
            if record.status == 'present':
                summary[emp_key]['days_present'] += 1
            elif record.status == 'absent':
                summary[emp_key]['days_absent'] += 1
            elif record.status == 'half-day':
                summary[emp_key]['days_half'] += 1
            
            # Count work location
            if record.work_from == 'office':
                summary[emp_key]['work_from_office'] += 1
            elif record.work_from == 'home':
                summary[emp_key]['work_from_home'] += 1
            elif record.work_from == 'remote':
                summary[emp_key]['work_remote'] += 1
            
            # Calculate hours
            if record.clock_in and record.clock_out:
                delta = record.clock_out - record.clock_in
                summary[emp_key]['total_hours'] += round(delta.total_seconds() / 3600, 2)
        
        # Calculate attendance rate
        for emp_id, data in summary.items():
            total_days = data['days_present'] + data['days_absent'] + data['days_half']
            data['attendance_rate'] = round((data['days_present'] + (data['days_half'] * 0.5)) / total_days * 100, 2) if total_days > 0 else 0
        
        result = list(summary.values())
    
    # Generate response based on format
    if format_type == 'csv':
        if report_type == 'daily':
            headers = ['Employee ID', 'Name', 'Department', 'Date', 'Status', 'Clock In', 'Clock Out', 'Hours Worked', 'Work From']
            data = [[
                r['employee_id'], r['name'], r['department'], r['date'], r['status'], 
                r['clock_in'], r['clock_out'], r['hours_worked'], r['work_from']
            ] for r in result]
        else:
            headers = [
                'Employee ID', 'Name', 'Department', 'Days Present', 'Days Absent', 'Half Days', 
                'Total Hours', 'Work From Office', 'Work From Home', 'Work Remote', 'Attendance Rate (%)'
            ]
            data = [[
                r['employee_id'], r['name'], r['department'], r['days_present'], r['days_absent'], 
                r['days_half'], r['total_hours'], r['work_from_office'], r['work_from_home'], 
                r['work_remote'], r['attendance_rate']
            ] for r in result]
        
        filename = f"attendance_report_{report_type}_{start_date.isoformat()}_{end_date.isoformat()}.csv"
        return generate_csv(headers, data, filename)
    
    elif format_type == 'chart':
        if report_type == 'daily':
            # Group by date and count
            date_counts = {}
            for record in attendance_data:
                date_str = record.date.isoformat()
                if date_str not in date_counts:
                    date_counts[date_str] = {'present': 0, 'absent': 0, 'half-day': 0}
                
                date_counts[date_str][record.status] += 1
            
            dates = sorted(date_counts.keys())
            present_counts = [date_counts[d]['present'] for d in dates]
            absent_counts = [date_counts[d]['absent'] for d in dates]
            half_day_counts = [date_counts[d]['half-day'] for d in dates]
            
            # Generate charts
            chart_data = {
                'attendance_by_date': {
                    'title': 'Daily Attendance',
                    'type': 'bar',
                    'labels': dates,
                    'datasets': [
                        {'label': 'Present', 'data': present_counts, 'color': 'green'},
                        {'label': 'Absent', 'data': absent_counts, 'color': 'red'},
                        {'label': 'Half Day', 'data': half_day_counts, 'color': 'yellow'}
                    ]
                }
            }
            
            title = f"Daily Attendance ({start_date.isoformat()} to {end_date.isoformat()})"
            chart_image = generate_chart(
                title, 
                dates,
                present_counts,
                kind='line', 
                x_label='Date', 
                y_label='Count', 
                color='green'
            )
            
            return success_response(
                "Attendance chart generated successfully", 
                {'chart_image': chart_image, 'chart_data': chart_data}
            )
        
        else:  # summary chart
            if not result:
                return error_response("No data", "No attendance data found for the specified criteria", 404)
            
            # Summary by employee
            employees = [r['name'] for r in result]
            present_counts = [r['days_present'] for r in result]
            attendance_rates = [r['attendance_rate'] for r in result]
            
            # Get top 10 if more than 10 employees
            if len(employees) > 10:
                # Sort by attendance rate
                sorted_data = sorted(zip(employees, attendance_rates), key=lambda x: x[1], reverse=True)
                top_employees = [e for e, _ in sorted_data[:10]]
                top_rates = [r for _, r in sorted_data[:10]]
                
                employees = top_employees
                attendance_rates = top_rates
            
            title = f"Attendance Rate by Employee ({start_date.isoformat()} to {end_date.isoformat()})"
            chart_image = generate_chart(
                title, 
                employees,
                attendance_rates,
                kind='bar', 
                x_label='Employee', 
                y_label='Attendance Rate (%)', 
                color='skyblue'
            )
            
            return success_response(
                "Attendance chart generated successfully", 
                {'chart_image': chart_image}
            )
    
    else:  # json format
        return success_response(
            f"Attendance {report_type} report generated successfully",
            result,
            meta={
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_records': len(result)
            }
        )

# ======== LEAVE REPORTS ========

@reports_bp.route('/reports/leave', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def leave_report():
    """Generate leave report"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    department_id = request.args.get('department_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    leave_type = request.args.get('leave_type')
    status = request.args.get('status')
    format_type = request.args.get('format', 'json')  # json, csv, chart
    
    # Parse dates
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = date(date.today().year, 1, 1)  # Start of current year
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today()
    except ValueError:
        return error_response("Invalid date format", "Use YYYY-MM-DD format", 400)
    
    # Build query
    query = db.session.query(
        Employee.id, 
        Employee.first_name, 
        Employee.last_name, 
        Employee.employee_id,
        Department.name.label('department'),
        LeaveRequest.id.label('leave_id'),
        LeaveRequest.leave_type,
        LeaveRequest.start_date,
        LeaveRequest.end_date,
        LeaveRequest.days,
        LeaveRequest.status,
        LeaveRequest.reason,
        LeaveRequest.created_at
    ).join(
        LeaveRequest, Employee.id == LeaveRequest.employee_id
    ).outerjoin(
        Department, Employee.department_id == Department.id
    ).filter(
        or_(
            LeaveRequest.start_date.between(start_date, end_date),
            LeaveRequest.end_date.between(start_date, end_date),
            and_(
                LeaveRequest.start_date <= start_date,
                LeaveRequest.end_date >= end_date
            )
        )
    )
    
    # Filter by department
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    
    # Filter by employee
    if employee_id:
        query = query.filter(Employee.id == employee_id)
    
    # Filter by leave type
    if leave_type:
        query = query.filter(LeaveRequest.leave_type == leave_type)
    
    # Filter by status
    if status:
        query = query.filter(LeaveRequest.status == status)
    
    # For managers, restrict to their team
    if user.role == Role.MANAGER and employee:
        team_members = [member.id for member in employee.team_members]
        query = query.filter(Employee.id.in_([employee.id] + team_members))
    
    # Get the data
    leave_data = query.order_by(Employee.last_name, Employee.first_name, LeaveRequest.start_date).all()
    
    # Process the data
    result = []
    for record in leave_data:
        result.append({
            'employee_id': record.employee_id,
            'name': f"{record.first_name} {record.last_name}",
            'department': record.department or 'N/A',
            'leave_id': record.leave_id,
            'leave_type': record.leave_type.value if hasattr(record.leave_type, 'value') else record.leave_type,
            'start_date': record.start_date.isoformat(),
            'end_date': record.end_date.isoformat(),
            'days': record.days,
            'status': record.status.value if hasattr(record.status, 'value') else record.status,
            'reason': record.reason,
            'created_at': record.created_at.isoformat()
        })
    
    # Generate response based on format
    if format_type == 'csv':
        headers = [
            'Employee ID', 'Name', 'Department', 'Leave ID', 'Leave Type', 
            'Start Date', 'End Date', 'Days', 'Status', 'Reason', 'Created At'
        ]
        data = [[
            r['employee_id'], r['name'], r['department'], r['leave_id'], r['leave_type'], 
            r['start_date'], r['end_date'], r['days'], r['status'], r['reason'], r['created_at']
        ] for r in result]
        
        filename = f"leave_report_{start_date.isoformat()}_{end_date.isoformat()}.csv"
        return generate_csv(headers, data, filename)
    
    elif format_type == 'chart':
        if not result:
            return error_response("No data", "No leave data found for the specified criteria", 404)
        
        # Group by leave type
        leave_type_counts = {}
        for record in result:
            leave_type = record['leave_type']
            if leave_type not in leave_type_counts:
                leave_type_counts[leave_type] = 0
            leave_type_counts[leave_type] += record['days']
        
        leave_types = list(leave_type_counts.keys())
        leave_days = [leave_type_counts[lt] for lt in leave_types]
        
        title = f"Leave Days by Type ({start_date.isoformat()} to {end_date.isoformat()})"
        chart_image = generate_chart(
            title, 
            leave_types,
            leave_days,
            kind='pie'
        )
        
        return success_response(
            "Leave chart generated successfully", 
            {'chart_image': chart_image}
        )
    
    else:  # json format
        # Calculate summary statistics
        summary = {
            'total_leave_requests': len(result),
            'total_leave_days': sum(r['days'] for r in result),
            'by_type': {},
            'by_status': {}
        }
        
        for record in result:
            # Summarize by leave type
            leave_type = record['leave_type']
            if leave_type not in summary['by_type']:
                summary['by_type'][leave_type] = {'count': 0, 'days': 0}
            
            summary['by_type'][leave_type]['count'] += 1
            summary['by_type'][leave_type]['days'] += record['days']
            
            # Summarize by status
            status = record['status']
            if status not in summary['by_status']:
                summary['by_status'][status] = {'count': 0, 'days': 0}
            
            summary['by_status'][status]['count'] += 1
            summary['by_status'][status]['days'] += record['days']
        
        return success_response(
            "Leave report generated successfully",
            {'detailed': result, 'summary': summary},
            meta={
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_records': len(result)
            }
        )

# ======== PAYROLL REPORTS ========

@reports_bp.route('/reports/payroll', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def payroll_report():
    """Generate payroll report"""
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    department_id = request.args.get('department_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    status = request.args.get('status')
    format_type = request.args.get('format', 'json')  # json, csv, chart
    
    # Parse dates
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = date(date.today().year, date.today().month, 1)  # Start of current month
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today()
    except ValueError:
        return error_response("Invalid date format", "Use YYYY-MM-DD format", 400)
    
    # Build query
    query = db.session.query(
        Employee.id, 
        Employee.first_name, 
        Employee.last_name, 
        Employee.employee_id,
        Department.name.label('department'),
        Payroll.id.label('payroll_id'),
        Payroll.period_start,
        Payroll.period_end,
        Payroll.base_salary,
        Payroll.overtime_hours,
        Payroll.overtime_amount,
        Payroll.bonus,
        Payroll.deductions,
        Payroll.tax,
        Payroll.net_amount,
        Payroll.status,
        Payroll.payment_date,
        Payroll.created_at
    ).join(
        Payroll, Employee.id == Payroll.employee_id
    ).outerjoin(
        Department, Employee.department_id == Department.id
    ).filter(
        or_(
            Payroll.period_start.between(start_date, end_date),
            Payroll.period_end.between(start_date, end_date),
            and_(
                Payroll.period_start <= start_date,
                Payroll.period_end >= end_date
            )
        )
    )
    
    # Filter by department
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    
    # Filter by employee
    if employee_id:
        query = query.filter(Employee.id == employee_id)
    
    # Filter by status
    if status:
        query = query.filter(Payroll.status == status)
    
    # Get the data
    payroll_data = query.order_by(Employee.last_name, Employee.first_name, Payroll.period_end).all()
    
    # Process the data
    result = []
    for record in payroll_data:
        result.append({
            'employee_id': record.employee_id,
            'name': f"{record.first_name} {record.last_name}",
            'department': record.department or 'N/A',
            'payroll_id': record.payroll_id,
            'period_start': record.period_start.isoformat(),
            'period_end': record.period_end.isoformat(),
            'base_salary': record.base_salary,
            'overtime_hours': record.overtime_hours,
            'overtime_amount': record.overtime_amount,
            'bonus': record.bonus,
            'deductions': record.deductions,
            'tax': record.tax,
            'net_amount': record.net_amount,
            'status': record.status.value if hasattr(record.status, 'value') else record.status,
            'payment_date': record.payment_date.isoformat() if record.payment_date else None,
            'created_at': record.created_at.isoformat()
        })
    
    # Generate response based on format
    if format_type == 'csv':
        headers = [
            'Employee ID', 'Name', 'Department', 'Payroll ID', 'Period Start', 'Period End', 
            'Base Salary', 'Overtime Hours', 'Overtime Amount', 'Bonus', 'Deductions', 
            'Tax', 'Net Amount', 'Status', 'Payment Date'
        ]
        data = [[
            r['employee_id'], r['name'], r['department'], r['payroll_id'], r['period_start'], 
            r['period_end'], r['base_salary'], r['overtime_hours'], r['overtime_amount'], 
            r['bonus'], r['deductions'], r['tax'], r['net_amount'], r['status'], r['payment_date']
        ] for r in result]
        
        filename = f"payroll_report_{start_date.isoformat()}_{end_date.isoformat()}.csv"
        return generate_csv(headers, data, filename)
    
    elif format_type == 'chart':
        if not result:
            return error_response("No data", "No payroll data found for the specified criteria", 404)
        
        # Group by department
        department_totals = {}
        for record in result:
            dept = record['department']
            if dept not in department_totals:
                department_totals[dept] = 0
            department_totals[dept] += record['net_amount']
        
        departments = list(department_totals.keys())
        amounts = [department_totals[d] for d in departments]
        
        title = f"Payroll by Department ({start_date.isoformat()} to {end_date.isoformat()})"
        chart_image = generate_chart(
            title, 
            departments,
            amounts,
            kind='bar', 
            x_label='Department', 
            y_label='Total Amount'
        )
        
        return success_response(
            "Payroll chart generated successfully", 
            {'chart_image': chart_image}
        )
    
    else:  # json format
        # Calculate summary statistics
        summary = {
            'total_payrolls': len(result),
            'total_base_salary': sum(r['base_salary'] for r in result),
            'total_overtime': sum(r['overtime_amount'] for r in result),
            'total_bonus': sum(r['bonus'] for r in result),
            'total_deductions': sum(r['deductions'] for r in result),
            'total_tax': sum(r['tax'] for r in result),
            'total_net_amount': sum(r['net_amount'] for r in result),
            'by_department': {},
            'by_status': {}
        }
        
        for record in result:
            # Summarize by department
            dept = record['department']
            if dept not in summary['by_department']:
                summary['by_department'][dept] = {'count': 0, 'amount': 0}
            
            summary['by_department'][dept]['count'] += 1
            summary['by_department'][dept]['amount'] += record['net_amount']
            
            # Summarize by status
            status = record['status']
            if status not in summary['by_status']:
                summary['by_status'][status] = {'count': 0, 'amount': 0}
            
            summary['by_status'][status]['count'] += 1
            summary['by_status'][status]['amount'] += record['net_amount']
        
        return success_response(
            "Payroll report generated successfully",
            {'detailed': result, 'summary': summary},
            meta={
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_records': len(result)
            }
        )

# ======== PROJECT AND TASK REPORTS ========

@reports_bp.route('/reports/projects', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def project_report():
    """Generate project and task report"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    department_id = request.args.get('department_id', type=int)
    project_id = request.args.get('project_id', type=int)
    employee_id = request.args.get('employee_id', type=int)
    status = request.args.get('status')
    report_type = request.args.get('report_type', 'projects')  # projects, tasks, team_performance
    format_type = request.args.get('format', 'json')  # json, csv, chart
    
    # Parse dates
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = date.today() - timedelta(days=90)  # Last 90 days
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today()
    except ValueError:
        return error_response("Invalid date format", "Use YYYY-MM-DD format", 400)
    
    # For managers, restrict to their projects
    managed_project_ids = []
    if user.role == Role.MANAGER and employee:
        # Get projects managed by this manager
        managed_projects = Project.query.filter_by(created_by=employee.id).all()
        managed_project_ids = [p.id for p in managed_projects]
        
        # Also get projects the manager is a member of
        member_projects = db.session.query(Project.id).join(
            ProjectMember, Project.id == ProjectMember.project_id
        ).filter(ProjectMember.employee_id == employee.id).all()
        
        member_project_ids = [p.id for p in member_projects]
        managed_project_ids = list(set(managed_project_ids + member_project_ids))
    
    # PROJECTS REPORT
    if report_type == 'projects':
        # Build projects query
        query = db.session.query(
            Project.id,
            Project.name,
            Project.description,
            Project.status,
            Project.start_date,
            Project.end_date,
            Project.budget,
            Project.created_at,
            Employee.first_name,
            Employee.last_name,
            func.count(Task.id).label('task_count'),
            func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label('completed_tasks')
        ).join(
            Employee, Project.created_by == Employee.id
        ).outerjoin(
            Task, Project.id == Task.project_id
        ).filter(
            or_(
                Project.start_date.between(start_date, end_date),
                Project.end_date.between(start_date, end_date),
                and_(
                    Project.start_date <= start_date,
                    or_(
                        Project.end_date >= end_date,
                        Project.end_date == None
                    )
                )
            )
        )
        
        # Filter by project
        if project_id:
            query = query.filter(Project.id == project_id)
        
        # Filter by manager's projects
        if user.role == Role.MANAGER and managed_project_ids:
            query = query.filter(Project.id.in_(managed_project_ids))
        
        # Filter by status
        if status:
            query = query.filter(Project.status == status)
        
        query = query.group_by(Project.id, Employee.id)
        
        # Get the data
        project_data = query.order_by(Project.end_date.desc()).all()
        
        # Process the data
        result = []
        for record in project_data:
            completion_rate = (record.completed_tasks / record.task_count * 100) if record.task_count > 0 else 0
            
            result.append({
                'project_id': record.id,
                'name': record.name,
                'description': record.description,
                'status': record.status.value if hasattr(record.status, 'value') else record.status,
                'start_date': record.start_date.isoformat() if record.start_date else None,
                'end_date': record.end_date.isoformat() if record.end_date else None,
                'budget': record.budget,
                'manager': f"{record.first_name} {record.last_name}",
                'task_count': record.task_count,
                'completed_tasks': record.completed_tasks,
                'completion_rate': round(completion_rate, 2),
                'created_at': record.created_at.isoformat()
            })
        
        # Generate response based on format
        if format_type == 'csv':
            headers = [
                'Project ID', 'Name', 'Description', 'Status', 'Start Date', 'End Date', 
                'Budget', 'Manager', 'Task Count', 'Completed Tasks', 'Completion Rate (%)'
            ]
            data = [[
                r['project_id'], r['name'], r['description'], r['status'], r['start_date'], 
                r['end_date'], r['budget'], r['manager'], r['task_count'], 
                r['completed_tasks'], r['completion_rate']
            ] for r in result]
            
            filename = f"project_report_{start_date.isoformat()}_{end_date.isoformat()}.csv"
            return generate_csv(headers, data, filename)
        
        elif format_type == 'chart':
            if not result:
                return error_response("No data", "No project data found for the specified criteria", 404)
            
            # Project completion rates
            projects = [r['name'] for r in result]
            completion_rates = [r['completion_rate'] for r in result]
            
            # Get top 10 if more than 10 projects
            if len(projects) > 10:
                # Sort by completion rate
                sorted_data = sorted(zip(projects, completion_rates), key=lambda x: x[1], reverse=True)
                top_projects = [p for p, _ in sorted_data[:10]]
                top_rates = [r for _, r in sorted_data[:10]]
                
                projects = top_projects
                completion_rates = top_rates
            
            title = f"Project Completion Rates ({start_date.isoformat()} to {end_date.isoformat()})"
            chart_image = generate_chart(
                title, 
                projects,
                completion_rates,
                kind='bar', 
                x_label='Project', 
                y_label='Completion Rate (%)'
            )
            
            return success_response(
                "Project chart generated successfully", 
                {'chart_image': chart_image}
            )
        
        else:  # json format
            # Calculate summary statistics
            summary = {
                'total_projects': len(result),
                'avg_completion_rate': round(sum(r['completion_rate'] for r in result) / len(result), 2) if result else 0,
                'by_status': {}
            }
            
            for record in result:
                # Summarize by status
                status = record['status']
                if status not in summary['by_status']:
                    summary['by_status'][status] = {'count': 0, 'avg_completion': 0}
                
                summary['by_status'][status]['count'] += 1
                summary['by_status'][status]['avg_completion'] += record['completion_rate']
            
            # Calculate averages
            for status in summary['by_status']:
                if summary['by_status'][status]['count'] > 0:
                    summary['by_status'][status]['avg_completion'] = round(
                        summary['by_status'][status]['avg_completion'] / summary['by_status'][status]['count'], 
                        2
                    )
            
            return success_response(
                "Project report generated successfully",
                {'detailed': result, 'summary': summary},
                meta={
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_records': len(result)
                }
            )
    
    # TASKS REPORT
    elif report_type == 'tasks':
        # Build tasks query
        query = db.session.query(
            Task.id,
            Task.title,
            Task.status,
            Task.priority,
            Task.progress,
            Task.due_date,
            Task.created_at,
            Task.completed_at,
            Project.id.label('project_id'),
            Project.name.label('project_name'),
            Employee.first_name.label('assignee_first_name'),
            Employee.last_name.label('assignee_last_name'),
            Employee.employee_id.label('assignee_employee_id')
        ).join(
            Project, Task.project_id == Project.id
        ).outerjoin(
            Employee, Task.assignee_id == Employee.id
        ).filter(
            or_(
                Task.created_at.between(datetime.combine(start_date, datetime.min.time()), 
                                      datetime.combine(end_date, datetime.max.time())),
                Task.completed_at.between(datetime.combine(start_date, datetime.min.time()), 
                                        datetime.combine(end_date, datetime.max.time())),
                Task.due_date.between(start_date, end_date) if Task.due_date is not None else False
            )
        )
        
        # Filter by project
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        # Filter by manager's projects
        if user.role == Role.MANAGER and managed_project_ids:
            query = query.filter(Task.project_id.in_(managed_project_ids))
        
        # Filter by employee
        if employee_id:
            query = query.filter(Task.assignee_id == employee_id)
        
        # Filter by status
        if status:
            query = query.filter(Task.status == status)
        
        # Get the data
        task_data = query.order_by(Task.due_date).all()
        
        # Process the data
        result = []
        for record in task_data:
            result.append({
                'task_id': record.id,
                'title': record.title,
                'status': record.status.value if hasattr(record.status, 'value') else record.status,
                'priority': record.priority.value if hasattr(record.priority, 'value') else record.priority,
                'progress': record.progress,
                'due_date': record.due_date.isoformat() if record.due_date else None,
                'created_at': record.created_at.isoformat(),
                'completed_at': record.completed_at.isoformat() if record.completed_at else None,
                'project_id': record.project_id,
                'project_name': record.project_name,
                'assignee': f"{record.assignee_first_name} {record.assignee_last_name}" if record.assignee_first_name else "Unassigned",
                'assignee_id': record.assignee_employee_id
            })
        
        # Generate response based on format
        if format_type == 'csv':
            headers = [
                'Task ID', 'Title', 'Status', 'Priority', 'Progress', 'Due Date', 
                'Created At', 'Completed At', 'Project ID', 'Project Name', 'Assignee'
            ]
            data = [[
                r['task_id'], r['title'], r['status'], r['priority'], r['progress'], r['due_date'], 
                r['created_at'], r['completed_at'], r['project_id'], r['project_name'], r['assignee']
            ] for r in result]
            
            filename = f"task_report_{start_date.isoformat()}_{end_date.isoformat()}.csv"
            return generate_csv(headers, data, filename)
        
        elif format_type == 'chart':
            if not result:
                return error_response("No data", "No task data found for the specified criteria", 404)
            
            # Group by status
            status_counts = {}
            for record in result:
                status = record['status']
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
            
            statuses = list(status_counts.keys())
            counts = [status_counts[s] for s in statuses]
            
            title = f"Tasks by Status ({start_date.isoformat()} to {end_date.isoformat()})"
            chart_image = generate_chart(
                title, 
                statuses,
                counts,
                kind='pie'
            )
            
            return success_response(
                "Task chart generated successfully", 
                {'chart_image': chart_image}
            )
        
        else:  # json format
            # Calculate summary statistics
            summary = {
                'total_tasks': len(result),
                'completed_tasks': sum(1 for r in result if r['status'] == 'completed'),
                'overdue_tasks': sum(1 for r in result if r['due_date'] and r['due_date'] < date.today().isoformat() and r['status'] != 'completed'),
                'by_status': {},
                'by_priority': {},
                'by_assignee': {}
            }
            
            for record in result:
                # Summarize by status
                status = record['status']
                if status not in summary['by_status']:
                    summary['by_status'][status] = 0
                summary['by_status'][status] += 1
                
                # Summarize by priority
                priority = record['priority']
                if priority not in summary['by_priority']:
                    summary['by_priority'][priority] = 0
                summary['by_priority'][priority] += 1
                
                # Summarize by assignee
                assignee = record['assignee']
                if assignee not in summary['by_assignee']:
                    summary['by_assignee'][assignee] = {'total': 0, 'completed': 0}
                
                summary['by_assignee'][assignee]['total'] += 1
                if record['status'] == 'completed':
                    summary['by_assignee'][assignee]['completed'] += 1
            
            # Calculate completion rates for assignees
            for assignee in summary['by_assignee']:
                if summary['by_assignee'][assignee]['total'] > 0:
                    summary['by_assignee'][assignee]['completion_rate'] = round(
                        (summary['by_assignee'][assignee]['completed'] / summary['by_assignee'][assignee]['total']) * 100,
                        2
                    )
            
            return success_response(
                "Task report generated successfully",
                {'detailed': result, 'summary': summary},
                meta={
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_records': len(result)
                }
            )
    
    # TEAM PERFORMANCE REPORT
    elif report_type == 'team_performance':
        # Only managers and above can access this report
        if user.role not in [Role.ADMIN, Role.HR, Role.MANAGER]:
            return error_response("Access denied", "Only managers and administrators can access team performance reports", 403)
        
        # Get employees to analyze
        if employee_id:
            employees = [Employee.query.get(employee_id)]
            if not employees[0]:
                return error_response("Employee not found", "", 404)
        elif department_id:
            employees = Employee.query.filter_by(department_id=department_id).all()
        elif user.role == Role.MANAGER and employee:
            # Get manager's team
            employees = list(employee.team_members)
            employees.append(employee)  # Include the manager
        else:
            # For admins/HR without filters, limit to a reasonable number
            employees = Employee.query.limit(50).all()
        
        # Get tasks for these employees
        employee_ids = [e.id for e in employees]
        tasks = Task.query.filter(
            Task.assignee_id.in_(employee_ids),
            or_(
                Task.created_at.between(datetime.combine(start_date, datetime.min.time()), 
                                      datetime.combine(end_date, datetime.max.time())),
                Task.completed_at.between(datetime.combine(start_date, datetime.min.time()), 
                                        datetime.combine(end_date, datetime.max.time())),
                Task.due_date.between(start_date, end_date) if Task.due_date is not None else False
            )
        ).all()
        
        # Compile performance metrics
        result = []
        for emp in employees:
            # Get tasks for this employee
            emp_tasks = [t for t in tasks if t.assignee_id == emp.id]
            
            if not emp_tasks:
                continue  # Skip employees with no tasks
            
            total_tasks = len(emp_tasks)
            completed_tasks = sum(1 for t in emp_tasks if t.status == TaskStatus.COMPLETED)
            
            # Calculate on-time completion rate
            on_time_tasks = 0
            late_tasks = 0
            for task in emp_tasks:
                if task.status == TaskStatus.COMPLETED and task.completed_at and task.due_date:
                    if task.completed_at.date() <= task.due_date:
                        on_time_tasks += 1
                    else:
                        late_tasks += 1
            
            on_time_rate = (on_time_tasks / completed_tasks * 100) if completed_tasks > 0 else 0
            
            # Calculate average task completion time (in days)
            completion_times = []
            for task in emp_tasks:
                if task.status == TaskStatus.COMPLETED and task.completed_at and task.created_at:
                    delta = task.completed_at - task.created_at
                    completion_times.append(delta.total_seconds() / 86400)  # Convert to days
            
            avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
            
            # Get priorities
            high_priority_tasks = sum(1 for t in emp_tasks if t.priority in ['high', 'urgent'])
            high_priority_completed = sum(1 for t in emp_tasks if t.priority in ['high', 'urgent'] and t.status == TaskStatus.COMPLETED)
            
            # Create employee performance record
            performance = {
                'employee_id': emp.employee_id,
                'name': emp.full_name,
                'department': emp.department.name if emp.department else 'N/A',
                'position': emp.position or 'N/A',
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round((completed_tasks / total_tasks) * 100, 2) if total_tasks > 0 else 0,
                'on_time_tasks': on_time_tasks,
                'late_tasks': late_tasks,
                'on_time_rate': round(on_time_rate, 2),
                'avg_completion_time': round(avg_completion_time, 2),
                'high_priority_tasks': high_priority_tasks,
                'high_priority_completed': high_priority_completed,
                'high_priority_rate': round((high_priority_completed / high_priority_tasks) * 100, 2) if high_priority_tasks > 0 else 0
            }
            
            result.append(performance)
        
        # Sort by completion rate (descending)
        result.sort(key=lambda x: x['completion_rate'], reverse=True)
        
        # Generate response based on format
        if format_type == 'csv':
            headers = [
                'Employee ID', 'Name', 'Department', 'Position', 'Total Tasks', 'Completed Tasks', 
                'Completion Rate (%)', 'On-Time Tasks', 'Late Tasks', 'On-Time Rate (%)', 
                'Avg Completion Time (days)', 'High Priority Tasks', 'High Priority Completed', 
                'High Priority Rate (%)'
            ]
            data = [[
                r['employee_id'], r['name'], r['department'], r['position'], r['total_tasks'], 
                r['completed_tasks'], r['completion_rate'], r['on_time_tasks'], r['late_tasks'], 
                r['on_time_rate'], r['avg_completion_time'], r['high_priority_tasks'], 
                r['high_priority_completed'], r['high_priority_rate']
            ] for r in result]
            
            filename = f"team_performance_report_{start_date.isoformat()}_{end_date.isoformat()}.csv"
            return generate_csv(headers, data, filename)
        
        elif format_type == 'chart':
            if not result:
                return error_response("No data", "No performance data found for the specified criteria", 404)
            
            # Employee completion rates
            employees = [r['name'] for r in result]
            completion_rates = [r['completion_rate'] for r in result]
            
            # Get top 10 if more than 10 employees
            if len(employees) > 10:
                employees = employees[:10]
                completion_rates = completion_rates[:10]
            
            title = f"Team Completion Rates ({start_date.isoformat()} to {end_date.isoformat()})"
            chart_image = generate_chart(
                title, 
                employees,
                completion_rates,
                kind='bar', 
                x_label='Employee', 
                y_label='Completion Rate (%)'
            )
            
            return success_response(
                "Team performance chart generated successfully", 
                {'chart_image': chart_image}
            )
        
        else:  # json format
            # Calculate summary statistics
            if not result:
                return success_response(
                    "Team performance report generated successfully",
                    {'detailed': [], 'summary': {}},
                    meta={
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'total_records': 0
                    }
                )
            
            summary = {
                'total_employees': len(result),
                'total_tasks': sum(r['total_tasks'] for r in result),
                'completed_tasks': sum(r['completed_tasks'] for r in result),
                'avg_completion_rate': round(sum(r['completion_rate'] for r in result) / len(result), 2),
                'avg_on_time_rate': round(sum(r['on_time_rate'] for r in result) / len(result), 2),
                'avg_completion_time': round(sum(r['avg_completion_time'] for r in result) / len(result), 2),
                'top_performers': [{'name': r['name'], 'completion_rate': r['completion_rate']} for r in result[:3]],
                'by_department': {}
            }
            
            # Group by department
            for record in result:
                dept = record['department']
                if dept not in summary['by_department']:
                    summary['by_department'][dept] = {
                        'employees': 0,
                        'total_tasks': 0,
                        'completed_tasks': 0,
                        'completion_rate': 0
                    }
                
                summary['by_department'][dept]['employees'] += 1
                summary['by_department'][dept]['total_tasks'] += record['total_tasks']
                summary['by_department'][dept]['completed_tasks'] += record['completed_tasks']
            
            # Calculate department completion rates
            for dept in summary['by_department']:
                if summary['by_department'][dept]['total_tasks'] > 0:
                    summary['by_department'][dept]['completion_rate'] = round(
                        (summary['by_department'][dept]['completed_tasks'] / summary['by_department'][dept]['total_tasks']) * 100,
                        2
                    )
            
            return success_response(
                "Team performance report generated successfully",
                {'detailed': result, 'summary': summary},
                meta={
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_records': len(result)
                }
            )
    
    else:
        return error_response("Invalid report type", f"Report type '{report_type}' is not supported", 400)