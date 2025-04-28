from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from datetime import datetime, date, timedelta
from app import db
from models import User, Employee, LeaveRequest, LeaveType, LeaveStatus, Role
from schemas.leave import (
    LeaveRequestSchema, LeaveRequestCreateSchema, 
    LeaveRequestUpdateSchema, LeaveRequestActionSchema,
    LeaveBalanceSchema
)
from utils.responses import success_response, error_response
from utils.decorators import admin_or_hr_required
from utils.pagination import paginate

leave_bp = Blueprint('leave', __name__)

# Get leave requests with filtering
@leave_bp.route('', methods=['GET'])
@jwt_required()
def get_leave_requests():
    """
    Get leave requests with filtering
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: query
        type: integer
        required: false
      - name: status
        in: query
        type: string
        enum: [pending, approved, rejected, cancelled]
        required: false
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
        description: List of leave requests
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Get filter parameters
    employee_id = request.args.get('employee_id', type=int)
    status = request.args.get('status')
    
    try:
        start_date = datetime.strptime(request.args.get('start_date', ''), '%Y-%m-%d').date() if request.args.get('start_date') else None
        end_date = datetime.strptime(request.args.get('end_date', ''), '%Y-%m-%d').date() if request.args.get('end_date') else None
    except ValueError:
        return error_response("Invalid date format. Use YYYY-MM-DD", 400)
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Base query
    query = LeaveRequest.query
    
    # Filter by user role
    if current_user.role in [Role.ADMIN, Role.HR]:
        # Admin and HR can view all leave requests
        pass
    elif current_user.role == Role.MANAGER:
        # Managers can view their team members' leave requests
        manager = Employee.query.filter_by(user_id=current_user_id).first()
        
        if not manager:
            return error_response("Manager profile not found", 404)
        
        if employee_id:
            # If specific employee is requested, check if they're in the manager's team
            employee = Employee.query.get(employee_id)
            if not employee or (employee.manager_id != manager.id and employee.id != manager.id):
                return error_response("You don't have permission to view this employee's leave requests", 403)
        else:
            # Get all team members
            team_members = Employee.query.filter_by(manager_id=manager.id).all()
            team_ids = [manager.id] + [e.id for e in team_members]
            query = query.filter(LeaveRequest.employee_id.in_(team_ids))
    else:
        # Regular employees can only view their own leave requests
        employee = Employee.query.filter_by(user_id=current_user_id).first()
        
        if not employee:
            return error_response("Employee profile not found", 404)
        
        if employee_id and employee_id != employee.id:
            return error_response("You don't have permission to view this employee's leave requests", 403)
        
        query = query.filter_by(employee_id=employee.id)
    
    # Apply filters
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    if status:
        try:
            status_enum = LeaveStatus[status.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            return error_response(f"Invalid status: {status}", 400)
    
    if start_date:
        query = query.filter(db.or_(
            LeaveRequest.start_date >= start_date,
            LeaveRequest.end_date >= start_date
        ))
    
    if end_date:
        query = query.filter(db.or_(
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date <= end_date
        ))
    
    # Order by creation date descending
    query = query.order_by(LeaveRequest.created_at.desc())
    
    # Execute paginated query
    paginated_leaves = paginate(query, page, per_page)
    
    # Serialize results
    result = {
        "items": LeaveRequestSchema(many=True).dump(paginated_leaves.items),
        "total": paginated_leaves.total,
        "pages": paginated_leaves.pages,
        "page": page,
        "per_page": per_page
    }
    
    return success_response(result)

# Get specific leave request
@leave_bp.route('/<int:leave_id>', methods=['GET'])
@jwt_required()
def get_leave_request(leave_id):
    """
    Get specific leave request
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - name: leave_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Leave request details
      401:
        description: Unauthorized
      403:
        description: Forbidden - cannot view this leave request
      404:
        description: Leave request not found
    """
    leave_request = LeaveRequest.query.get(leave_id)
    
    if not leave_request:
        return error_response("Leave request not found", 404)
    
    # Check permission
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if current_user.role in [Role.ADMIN, Role.HR]:
        # Admin and HR can view any leave request
        pass
    elif current_user.role == Role.MANAGER:
        # Managers can view their team members' leave requests
        manager = Employee.query.filter_by(user_id=current_user_id).first()
        employee = Employee.query.get(leave_request.employee_id)
        
        if not manager or not employee or (employee.manager_id != manager.id and employee.id != manager.id):
            return error_response("You don't have permission to view this leave request", 403)
    else:
        # Regular employees can only view their own leave requests
        employee = Employee.query.filter_by(user_id=current_user_id).first()
        
        if not employee or leave_request.employee_id != employee.id:
            return error_response("You don't have permission to view this leave request", 403)
    
    return success_response(LeaveRequestSchema().dump(leave_request))

# Create leave request
@leave_bp.route('', methods=['POST'])
@jwt_required()
def create_leave_request():
    """
    Create new leave request
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: LeaveRequestCreate
          required:
            - leave_type
            - start_date
            - end_date
            - days
          properties:
            leave_type:
              type: string
              enum: [annual, sick, personal, maternity, paternity, bereavement, unpaid, other]
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            days:
              type: number
              description: Number of days (can be fractional for half-days)
            reason:
              type: string
    responses:
      201:
        description: Leave request created successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    schema = LeaveRequestCreateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Validate dates
    start_date = data['start_date']
    end_date = data['end_date']
    days = data['days']
    
    if start_date > end_date:
        return error_response("Start date must be before end date", 400)
    
    if start_date < date.today():
        return error_response("Cannot request leave for past dates", 400)
    
    # Calculate default days if not provided
    if not days:
        delta = end_date - start_date
        days = delta.days + 1
        # Adjust for weekends
        days = sum(1 for i in range(delta.days + 1) if (start_date + timedelta(days=i)).weekday() < 5)
    
    # Check for overlapping leave requests
    overlapping = LeaveRequest.query.filter(
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status != LeaveStatus.REJECTED,
        LeaveRequest.status != LeaveStatus.CANCELLED,
        db.or_(
            db.and_(
                LeaveRequest.start_date <= start_date,
                LeaveRequest.end_date >= start_date
            ),
            db.and_(
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= end_date
            ),
            db.and_(
                LeaveRequest.start_date >= start_date,
                LeaveRequest.end_date <= end_date
            )
        )
    ).first()
    
    if overlapping:
        return error_response("You already have a leave request for this period", 400)
    
    # Create leave request
    leave_request = LeaveRequest(
        employee_id=employee.id,
        leave_type=LeaveType[data['leave_type'].upper()],
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=data.get('reason')
    )
    
    db.session.add(leave_request)
    db.session.commit()
    
    return success_response(
        LeaveRequestSchema().dump(leave_request),
        201
    )

# Update leave request (only pending ones)
@leave_bp.route('/<int:leave_id>', methods=['PUT'])
@jwt_required()
def update_leave_request(leave_id):
    """
    Update leave request (only pending ones)
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - name: leave_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: LeaveRequestUpdate
          properties:
            leave_type:
              type: string
              enum: [annual, sick, personal, maternity, paternity, bereavement, unpaid, other]
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            days:
              type: number
            reason:
              type: string
    responses:
      200:
        description: Leave request updated successfully
      400:
        description: Validation error or request already processed
      401:
        description: Unauthorized
      403:
        description: Forbidden - cannot update this leave request
      404:
        description: Leave request not found
    """
    leave_request = LeaveRequest.query.get(leave_id)
    
    if not leave_request:
        return error_response("Leave request not found", 404)
    
    # Only pending requests can be updated
    if leave_request.status != LeaveStatus.PENDING:
        return error_response("Only pending leave requests can be updated", 400)
    
    # Check permission
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee or leave_request.employee_id != employee.id:
        return error_response("You don't have permission to update this leave request", 403)
    
    schema = LeaveRequestUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Validate dates if being updated
    start_date = data.get('start_date') or leave_request.start_date
    end_date = data.get('end_date') or leave_request.end_date
    
    if start_date > end_date:
        return error_response("Start date must be before end date", 400)
    
    if start_date < date.today():
        return error_response("Cannot request leave for past dates", 400)
    
    # Calculate days if dates are updated
    if 'start_date' in data or 'end_date' in data:
        delta = end_date - start_date
        days = delta.days + 1
        # Adjust for weekends
        days = sum(1 for i in range(delta.days + 1) if (start_date + timedelta(days=i)).weekday() < 5)
        data['days'] = days
    
    # Check for overlapping leave requests if dates are updated
    if 'start_date' in data or 'end_date' in data:
        overlapping = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.id != leave_id,
            LeaveRequest.status != LeaveStatus.REJECTED,
            LeaveRequest.status != LeaveStatus.CANCELLED,
            db.or_(
                db.and_(
                    LeaveRequest.start_date <= start_date,
                    LeaveRequest.end_date >= start_date
                ),
                db.and_(
                    LeaveRequest.start_date <= end_date,
                    LeaveRequest.end_date >= end_date
                ),
                db.and_(
                    LeaveRequest.start_date >= start_date,
                    LeaveRequest.end_date <= end_date
                )
            )
        ).first()
        
        if overlapping:
            return error_response("You already have a leave request for this period", 400)
    
    # Update leave request fields
    for key, value in data.items():
        if key == 'leave_type':
            setattr(leave_request, key, LeaveType[value.upper()])
        else:
            setattr(leave_request, key, value)
    
    db.session.commit()
    
    return success_response(LeaveRequestSchema().dump(leave_request))

# Cancel leave request
@leave_bp.route('/<int:leave_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_leave_request(leave_id):
    """
    Cancel leave request
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - name: leave_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Leave request cancelled successfully
      400:
        description: Cannot cancel (already approved/rejected/cancelled)
      401:
        description: Unauthorized
      403:
        description: Forbidden - cannot cancel this leave request
      404:
        description: Leave request not found
    """
    leave_request = LeaveRequest.query.get(leave_id)
    
    if not leave_request:
        return error_response("Leave request not found", 404)
    
    # Check permission
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee or leave_request.employee_id != employee.id:
        return error_response("You don't have permission to cancel this leave request", 403)
    
    # Cannot cancel already processed requests
    if leave_request.status in [LeaveStatus.REJECTED, LeaveStatus.CANCELLED]:
        return error_response(f"Leave request is already {leave_request.status.value}", 400)
    
    # Cannot cancel past leaves
    if leave_request.status == LeaveStatus.APPROVED and leave_request.start_date < date.today():
        return error_response("Cannot cancel past approved leaves", 400)
    
    # Update status
    leave_request.status = LeaveStatus.CANCELLED
    db.session.commit()
    
    return success_response({
        "message": "Leave request cancelled successfully",
        "leave_request": LeaveRequestSchema().dump(leave_request)
    })

# Approve or reject leave request (HR/Admin/Manager)
@leave_bp.route('/<int:leave_id>/action', methods=['POST'])
@jwt_required()
def leave_action(leave_id):
    """
    Approve or reject leave request
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - name: leave_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: LeaveAction
          required:
            - action
          properties:
            action:
              type: string
              enum: [approve, reject]
            note:
              type: string
    responses:
      200:
        description: Leave request processed successfully
      400:
        description: Validation error or request already processed
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to approve/reject
      404:
        description: Leave request not found
    """
    leave_request = LeaveRequest.query.get(leave_id)
    
    if not leave_request:
        return error_response("Leave request not found", 404)
    
    # Only pending requests can be approved/rejected
    if leave_request.status != LeaveStatus.PENDING:
        return error_response(f"Leave request is already {leave_request.status.value}", 400)
    
    schema = LeaveRequestActionSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check permission
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    reviewer = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not reviewer:
        return error_response("Reviewer profile not found", 404)
    
    can_approve = False
    
    # Admin and HR can approve/reject any leave request
    if current_user.role in [Role.ADMIN, Role.HR]:
        can_approve = True
    # Managers can only approve/reject their team members' requests
    elif current_user.role == Role.MANAGER:
        employee = Employee.query.get(leave_request.employee_id)
        if employee and employee.manager_id == reviewer.id:
            can_approve = True
    
    if not can_approve:
        return error_response("You don't have permission to approve/reject this leave request", 403)
    
    # Process leave request
    if data['action'] == 'approve':
        leave_request.status = LeaveStatus.APPROVED
    else:
        leave_request.status = LeaveStatus.REJECTED
    
    leave_request.reviewed_by = reviewer.id
    leave_request.reviewed_at = datetime.utcnow()
    leave_request.review_note = data.get('note')
    
    db.session.commit()
    
    return success_response({
        "message": f"Leave request {data['action']}d successfully",
        "leave_request": LeaveRequestSchema().dump(leave_request)
    })

# Get leave balances (for future implementation)
@leave_bp.route('/balance', methods=['GET'])
@jwt_required()
def get_leave_balance():
    """
    Get leave balances for employee
    ---
    tags:
      - Leave
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: query
        type: integer
        required: false
        description: If not provided, gets current user's balance
    responses:
      200:
        description: Leave balances
      401:
        description: Unauthorized
      403:
        description: Forbidden - cannot view this employee's balance
      404:
        description: Employee not found
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Get employee_id parameter or use current user's employee
    employee_id = request.args.get('employee_id', type=int)
    
    if not employee_id:
        employee = Employee.query.filter_by(user_id=current_user_id).first()
        if not employee:
            return error_response("Employee profile not found", 404)
        employee_id = employee.id
    else:
        # Check if current user has permission to view this employee's balance
        if current_user.role not in [Role.ADMIN, Role.HR]:
            employee = Employee.query.filter_by(user_id=current_user_id).first()
            
            # If user is a manager, check if the employee is in their team
            if current_user.role == Role.MANAGER:
                team_member = Employee.query.filter_by(id=employee_id, manager_id=employee.id).first()
                if not team_member and employee_id != employee.id:
                    return error_response("You don't have permission to view this employee's leave balance", 403)
            # Regular employees can only view their own balance
            elif employee.id != employee_id:
                return error_response("You don't have permission to view this employee's leave balance", 403)
    
    employee = Employee.query.get(employee_id)
    if not employee:
        return error_response("Employee not found", 404)
    
    # Mock data for leave balances (would be implemented in Phase 2)
    # In a real system, this would come from a leave balance table
    current_year = date.today().year
    join_date = employee.date_of_joining
    
    # Calculate years of service
    years_of_service = current_year - join_date.year
    if (date.today().month, date.today().day) < (join_date.month, join_date.day):
        years_of_service -= 1
    
    # Example: Base annual leave is 20 days + 1 day for each year of service (max 30)
    annual_leave_entitled = min(20 + years_of_service, 30)
    
    # Count days taken this year
    days_taken = db.session.query(db.func.sum(LeaveRequest.days)).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.leave_type == LeaveType.ANNUAL,
        db.extract('year', LeaveRequest.start_date) == current_year
    ).scalar() or 0
    
    # Count days pending
    days_pending = db.session.query(db.func.sum(LeaveRequest.days)).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.PENDING,
        LeaveRequest.leave_type == LeaveType.ANNUAL,
        db.extract('year', LeaveRequest.start_date) == current_year
    ).scalar() or 0
    
    # Sick leave allotment
    sick_leave_entitled = 15
    sick_days_taken = db.session.query(db.func.sum(LeaveRequest.days)).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.leave_type == LeaveType.SICK,
        db.extract('year', LeaveRequest.start_date) == current_year
    ).scalar() or 0
    
    # Personal leave allotment
    personal_leave_entitled = 3
    personal_days_taken = db.session.query(db.func.sum(LeaveRequest.days)).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.leave_type == LeaveType.PERSONAL,
        db.extract('year', LeaveRequest.start_date) == current_year
    ).scalar() or 0
    
    result = {
        "employee": {
            "id": employee.id,
            "name": employee.full_name,
            "years_of_service": years_of_service
        },
        "leave_balances": [
            {
                "leave_type": "annual",
                "entitled": annual_leave_entitled,
                "taken": days_taken,
                "pending": days_pending,
                "balance": annual_leave_entitled - days_taken,
                "unit": "days"
            },
            {
                "leave_type": "sick",
                "entitled": sick_leave_entitled,
                "taken": sick_days_taken,
                "pending": 0,  # Not tracking pending for sick leave
                "balance": sick_leave_entitled - sick_days_taken,
                "unit": "days"
            },
            {
                "leave_type": "personal",
                "entitled": personal_leave_entitled,
                "taken": personal_days_taken,
                "pending": 0,  # Not tracking pending for personal leave
                "balance": personal_leave_entitled - personal_days_taken,
                "unit": "days"
            }
        ]
    }
    
    return success_response(result)
