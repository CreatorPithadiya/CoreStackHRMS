from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from sqlalchemy import func
from datetime import datetime, date, timedelta
from app import db
from models import User, Employee, Attendance, Role
from schemas.attendance import (
    AttendanceSchema, AttendanceCreateSchema, 
    AttendanceUpdateSchema, AttendanceReportSchema
)
from utils.responses import success_response, error_response
from utils.decorators import admin_or_hr_required
from utils.pagination import paginate

attendance_bp = Blueprint('attendance', __name__)

# Clock in
@attendance_bp.route('/clock-in', methods=['POST'])
@jwt_required()
def clock_in():
    """
    Clock in attendance
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: ClockIn
          properties:
            work_from:
              type: string
              enum: [office, home, remote]
              default: office
            notes:
              type: string
    responses:
      200:
        description: Clock in successful
      400:
        description: Already clocked in today
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee not found", 404)
    
    today = date.today()
    
    # Check if already clocked in
    attendance = Attendance.query.filter_by(
        employee_id=employee.id,
        date=today
    ).first()
    
    if attendance and attendance.clock_in:
        return error_response("Already clocked in today", 400)
    
    # Get optional parameters
    data = request.json or {}
    work_from = data.get('work_from', 'office')
    notes = data.get('notes')
    
    # Create or update attendance record
    now = datetime.utcnow()
    if attendance:
        attendance.clock_in = now
        attendance.work_from = work_from
        attendance.notes = notes
    else:
        attendance = Attendance(
            employee_id=employee.id,
            date=today,
            clock_in=now,
            work_from=work_from,
            notes=notes
        )
        db.session.add(attendance)
    
    db.session.commit()
    
    return success_response({
        "message": "Clock in successful",
        "attendance": AttendanceSchema().dump(attendance)
    })

# Clock out
@attendance_bp.route('/clock-out', methods=['POST'])
@jwt_required()
def clock_out():
    """
    Clock out attendance
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: ClockOut
          properties:
            notes:
              type: string
    responses:
      200:
        description: Clock out successful
      400:
        description: Not yet clocked in today or already clocked out
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee not found", 404)
    
    today = date.today()
    
    # Check if already clocked in
    attendance = Attendance.query.filter_by(
        employee_id=employee.id,
        date=today
    ).first()
    
    if not attendance or not attendance.clock_in:
        return error_response("Not yet clocked in today", 400)
    
    if attendance.clock_out:
        return error_response("Already clocked out today", 400)
    
    # Update attendance record
    now = datetime.utcnow()
    attendance.clock_out = now
    
    # Update notes if provided
    data = request.json or {}
    if data.get('notes'):
        if attendance.notes:
            attendance.notes += f"\n{data['notes']}"
        else:
            attendance.notes = data['notes']
    
    db.session.commit()
    
    # Calculate hours worked
    hours_worked = attendance.hours_worked
    
    return success_response({
        "message": "Clock out successful",
        "attendance": AttendanceSchema().dump(attendance),
        "hours_worked": hours_worked
    })

# Get attendance status for today
@attendance_bp.route('/status', methods=['GET'])
@jwt_required()
def get_attendance_status():
    """
    Get attendance status for today
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    responses:
      200:
        description: Attendance status
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee not found", 404)
    
    today = date.today()
    
    # Get today's attendance
    attendance = Attendance.query.filter_by(
        employee_id=employee.id,
        date=today
    ).first()
    
    if not attendance:
        return success_response({
            "status": "not_started",
            "clock_in": None,
            "clock_out": None,
            "hours_worked": 0
        })
    
    status = "in_progress" if attendance.clock_in and not attendance.clock_out else "completed"
    
    return success_response({
        "status": status,
        "attendance": AttendanceSchema().dump(attendance),
        "hours_worked": attendance.hours_worked if attendance.clock_out else 0
    })

# Get employee attendance history
@attendance_bp.route('/history', methods=['GET'])
@jwt_required()
def get_attendance_history():
    """
    Get employee attendance history
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: query
        type: integer
        required: false
        description: If not provided, gets current user's attendance
      - name: start_date
        in: query
        type: string
        format: date
        required: false
      - name: end_date
        in: query
        type: string
        format: date
        required: false
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
    responses:
      200:
        description: Attendance history
      401:
        description: Unauthorized
      403:
        description: Forbidden - cannot access other employee's attendance
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Get employee_id parameter or use current user's employee
    employee_id = request.args.get('employee_id', type=int)
    
    if not employee_id:
        employee = Employee.query.filter_by(user_id=current_user_id).first()
        if not employee:
            return error_response("Employee not found", 404)
        employee_id = employee.id
    else:
        # Check if current user has permission to view this employee's attendance
        if current_user.role not in [Role.ADMIN, Role.HR]:
            employee = Employee.query.filter_by(user_id=current_user_id).first()
            
            # If user is a manager, check if the employee is in their team
            if current_user.role == Role.MANAGER:
                team_member = Employee.query.filter_by(id=employee_id, manager_id=employee.id).first()
                if not team_member and employee_id != employee.id:
                    return error_response("You don't have permission to view this employee's attendance", 403)
            # Regular employees can only view their own attendance
            elif employee.id != employee_id:
                return error_response("You don't have permission to view this employee's attendance", 403)
    
    # Parse date filters
    try:
        start_date = datetime.strptime(request.args.get('start_date', ''), '%Y-%m-%d').date() if request.args.get('start_date') else None
        end_date = datetime.strptime(request.args.get('end_date', ''), '%Y-%m-%d').date() if request.args.get('end_date') else None
    except ValueError:
        return error_response("Invalid date format. Use YYYY-MM-DD", 400)
    
    # Set default date range if not provided
    if not start_date:
        start_date = date.today().replace(day=1)  # First day of current month
    if not end_date:
        end_date = date.today()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Query attendance records
    query = Attendance.query.filter_by(employee_id=employee_id)
    
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    
    # Order by date descending
    query = query.order_by(Attendance.date.desc())
    
    # Execute paginated query
    paginated_attendance = paginate(query, page, per_page)
    
    # Serialize results
    result = {
        "items": AttendanceSchema(many=True).dump(paginated_attendance.items),
        "total": paginated_attendance.total,
        "pages": paginated_attendance.pages,
        "page": page,
        "per_page": per_page
    }
    
    return success_response(result)

# Admin/HR manual attendance record
@attendance_bp.route('/record', methods=['POST'])
@jwt_required()
@admin_or_hr_required
def record_attendance():
    """
    Manually record attendance (Admin/HR only)
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: RecordAttendance
          required:
            - employee_id
            - date
            - status
          properties:
            employee_id:
              type: integer
            date:
              type: string
              format: date
            status:
              type: string
              enum: [present, absent, half-day]
            clock_in:
              type: string
              format: date-time
            clock_out:
              type: string
              format: date-time
            work_from:
              type: string
              enum: [office, home, remote]
            notes:
              type: string
    responses:
      201:
        description: Attendance recorded successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
      404:
        description: Employee not found
    """
    schema = AttendanceCreateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    employee_id = data['employee_id']
    attendance_date = data['date']
    
    # Check if employee exists
    employee = Employee.query.get(employee_id)
    if not employee:
        return error_response("Employee not found", 404)
    
    # Check if attendance record already exists for this date
    existing = Attendance.query.filter_by(
        employee_id=employee_id,
        date=attendance_date
    ).first()
    
    if existing:
        return error_response(f"Attendance record already exists for {attendance_date}", 400)
    
    # Create attendance record
    attendance = Attendance(
        employee_id=employee_id,
        date=attendance_date,
        status=data['status'],
        clock_in=data.get('clock_in'),
        clock_out=data.get('clock_out'),
        work_from=data.get('work_from', 'office'),
        notes=data.get('notes')
    )
    
    db.session.add(attendance)
    db.session.commit()
    
    return success_response(
        AttendanceSchema().dump(attendance),
        201
    )

# Update attendance record
@attendance_bp.route('/record/<int:attendance_id>', methods=['PUT'])
@jwt_required()
@admin_or_hr_required
def update_attendance(attendance_id):
    """
    Update attendance record (Admin/HR only)
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - name: attendance_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: UpdateAttendance
          properties:
            status:
              type: string
              enum: [present, absent, half-day]
            clock_in:
              type: string
              format: date-time
            clock_out:
              type: string
              format: date-time
            work_from:
              type: string
              enum: [office, home, remote]
            notes:
              type: string
    responses:
      200:
        description: Attendance updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
      404:
        description: Attendance record not found
    """
    attendance = Attendance.query.get(attendance_id)
    
    if not attendance:
        return error_response("Attendance record not found", 404)
    
    schema = AttendanceUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Update attendance fields
    for key, value in data.items():
        setattr(attendance, key, value)
    
    db.session.commit()
    
    return success_response(AttendanceSchema().dump(attendance))

# Delete attendance record
@attendance_bp.route('/record/<int:attendance_id>', methods=['DELETE'])
@jwt_required()
@admin_or_hr_required
def delete_attendance(attendance_id):
    """
    Delete attendance record (Admin/HR only)
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - name: attendance_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Attendance deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
      404:
        description: Attendance record not found
    """
    attendance = Attendance.query.get(attendance_id)
    
    if not attendance:
        return error_response("Attendance record not found", 404)
    
    db.session.delete(attendance)
    db.session.commit()
    
    return success_response({
        "message": "Attendance record deleted successfully"
    })

# Get attendance statistics
@attendance_bp.route('/report', methods=['GET'])
@jwt_required()
def get_attendance_report():
    """
    Get attendance statistics
    ---
    tags:
      - Attendance
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: query
        type: integer
        required: false
        description: If not provided, gets current user's attendance
      - name: start_date
        in: query
        type: string
        format: date
        required: false
      - name: end_date
        in: query
        type: string
        format: date
        required: false
    responses:
      200:
        description: Attendance statistics
      401:
        description: Unauthorized
      403:
        description: Forbidden - cannot access other employee's attendance
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Get employee_id parameter or use current user's employee
    employee_id = request.args.get('employee_id', type=int)
    
    if not employee_id:
        employee = Employee.query.filter_by(user_id=current_user_id).first()
        if not employee:
            return error_response("Employee not found", 404)
        employee_id = employee.id
    else:
        # Check if current user has permission to view this employee's attendance
        if current_user.role not in [Role.ADMIN, Role.HR]:
            employee = Employee.query.filter_by(user_id=current_user_id).first()
            
            # If user is a manager, check if the employee is in their team
            if current_user.role == Role.MANAGER:
                team_member = Employee.query.filter_by(id=employee_id, manager_id=employee.id).first()
                if not team_member and employee_id != employee.id:
                    return error_response("You don't have permission to view this employee's attendance", 403)
            # Regular employees can only view their own attendance
            elif employee.id != employee_id:
                return error_response("You don't have permission to view this employee's attendance", 403)
    
    # Parse date filters
    try:
        start_date = datetime.strptime(request.args.get('start_date', ''), '%Y-%m-%d').date() if request.args.get('start_date') else None
        end_date = datetime.strptime(request.args.get('end_date', ''), '%Y-%m-%d').date() if request.args.get('end_date') else None
    except ValueError:
        return error_response("Invalid date format. Use YYYY-MM-DD", 400)
    
    # Set default date range if not provided (last 30 days)
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Query attendance records
    query = Attendance.query.filter_by(employee_id=employee_id)
    
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    
    attendance_records = query.all()
    
    # Calculate statistics
    total_days = (end_date - start_date).days + 1
    working_days = len([d for d in (start_date + timedelta(days=x) for x in range(total_days)) 
                        if d.weekday() < 5])  # Exclude weekends
    
    present_days = sum(1 for a in attendance_records if a.status == 'present')
    absent_days = sum(1 for a in attendance_records if a.status == 'absent')
    half_days = sum(1 for a in attendance_records if a.status == 'half-day')
    
    # Calculate unrecorded working days
    recorded_dates = set(a.date for a in attendance_records)
    all_working_dates = set(start_date + timedelta(days=x) for x in range(total_days) 
                          if (start_date + timedelta(days=x)).weekday() < 5)
    unrecorded_days = len(all_working_dates - recorded_dates)
    
    # Calculate total hours worked
    total_hours = sum(a.hours_worked for a in attendance_records)
    
    # Calculate work location stats
    office_days = sum(1 for a in attendance_records if a.work_from == 'office')
    home_days = sum(1 for a in attendance_records if a.work_from == 'home')
    remote_days = sum(1 for a in attendance_records if a.work_from == 'remote')
    
    # Calculate attendance rate
    attendance_rate = (present_days + (half_days * 0.5)) / working_days * 100 if working_days > 0 else 0
    
    # Calculate punctuality (on time vs late)
    on_time_count = sum(1 for a in attendance_records 
                      if a.clock_in and a.clock_in.time() < datetime.strptime('09:30', '%H:%M').time())
    
    punctuality_rate = (on_time_count / present_days * 100) if present_days > 0 else 0
    
    result = {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_days": total_days,
            "working_days": working_days
        },
        "attendance": {
            "present_days": present_days,
            "absent_days": absent_days,
            "half_days": half_days,
            "unrecorded_days": unrecorded_days,
            "attendance_rate": round(attendance_rate, 2)
        },
        "work_hours": {
            "total_hours": round(total_hours, 2),
            "average_hours": round(total_hours / present_days, 2) if present_days > 0 else 0
        },
        "location": {
            "office_days": office_days,
            "home_days": home_days,
            "remote_days": remote_days
        },
        "punctuality": {
            "on_time_count": on_time_count,
            "punctuality_rate": round(punctuality_rate, 2)
        }
    }
    
    return success_response(result)
