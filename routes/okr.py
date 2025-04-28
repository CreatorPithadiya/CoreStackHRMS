from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc

from app import db
from models import OKR, KeyResult, User, Employee, Role, OKRStatus
from schemas.okr import OKRSchema, OKRCreateSchema, OKRUpdateSchema, KeyResultUpdateSchema
from utils.responses import success_response, error_response
from utils.decorators import role_required

okr_bp = Blueprint('okr', __name__)

@okr_bp.route('/okrs', methods=['GET'])
@jwt_required()
def get_okrs():
    """Get all OKRs based on role and filters"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    status = request.args.get('status')
    timeframe = request.args.get('timeframe')
    
    query = OKR.query
    
    # Filter based on role
    if user.role not in [Role.ADMIN, Role.HR]:
        # Managers can see their team members' OKRs
        if user.role == Role.MANAGER and employee:
            team_members = [member.id for member in employee.team_members]
            if employee_id and employee_id not in team_members and employee_id != employee.id:
                return error_response("Access denied", "You can only view your own or your team members' OKRs", 403)
            
            if employee_id:
                query = query.filter_by(employee_id=employee_id)
            else:
                query = query.filter(OKR.employee_id.in_([employee.id] + team_members))
        else:
            # Regular employees can only see their own OKRs
            if employee:
                query = query.filter_by(employee_id=employee.id)
            else:
                return error_response("Employee record not found", "", 404)
    elif employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    # Apply other filters
    if status:
        query = query.filter_by(status=status)
    
    if timeframe:
        query = query.filter_by(timeframe=timeframe)
    
    okrs = query.order_by(desc(OKR.created_at)).paginate(page=page, per_page=per_page)
    
    schema = OKRSchema(many=True)
    return success_response(
        "OKRs retrieved successfully",
        schema.dump(okrs.items),
        meta={"total": okrs.total, "page": page, "per_page": per_page}
    )

@okr_bp.route('/okrs/<int:okr_id>', methods=['GET'])
@jwt_required()
def get_okr(okr_id):
    """Get a specific OKR"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    okr = OKR.query.get_or_404(okr_id)
    
    # Check permission: admin/HR can see all, managers can see their team's, employees can see their own
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER and employee:
            team_member_ids = [member.id for member in employee.team_members]
            if okr.employee_id != employee.id and okr.employee_id not in team_member_ids:
                return error_response("Access denied", "You can only view your own or your team members' OKRs", 403)
        elif not employee or okr.employee_id != employee.id:
            return error_response("Access denied", "You can only view your own OKRs", 403)
    
    schema = OKRSchema()
    return success_response("OKR retrieved successfully", schema.dump(okr))

@okr_bp.route('/okrs', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def create_okr():
    """Create a new OKR"""
    user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    schema = OKRCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check if target employee exists
    target_employee = Employee.query.get(data['employee_id'])
    if not target_employee:
        return error_response("Target employee not found", "", 404)
    
    # For managers, check if the target employee is in their team
    user = User.query.get(user_id)
    if user.role == Role.MANAGER:
        team_member_ids = [member.id for member in employee.team_members]
        if data['employee_id'] != employee.id and data['employee_id'] not in team_member_ids:
            return error_response("Access denied", "You can only create OKRs for yourself or your team members", 403)
    
    # Create new OKR
    new_okr = OKR(
        employee_id=data['employee_id'],
        title=data['title'],
        description=data.get('description', ''),
        timeframe=data.get('timeframe', 'quarterly'),
        start_date=data['start_date'],
        end_date=data['end_date'],
        status=data.get('status', OKRStatus.DRAFT.value),
        progress=0,
        created_by=employee.id
    )
    
    db.session.add(new_okr)
    db.session.commit()
    
    # Add key results if provided
    if 'key_results' in data and data['key_results']:
        for kr_data in data['key_results']:
            key_result = KeyResult(
                okr_id=new_okr.id,
                title=kr_data['title'],
                description=kr_data.get('description', ''),
                target_value=kr_data['target_value'],
                current_value=0,
                unit=kr_data.get('unit', ''),
                progress=0
            )
            db.session.add(key_result)
        
        db.session.commit()
    
    result_schema = OKRSchema()
    return success_response("OKR created successfully", result_schema.dump(new_okr), 201)

@okr_bp.route('/okrs/<int:okr_id>', methods=['PUT'])
@jwt_required()
def update_okr(okr_id):
    """Update an OKR"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    okr = OKR.query.get_or_404(okr_id)
    
    # Check permission: admin/HR can update all, managers can update their team's, employees can only update their own
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER:
            team_member_ids = [member.id for member in employee.team_members]
            if okr.employee_id != employee.id and okr.employee_id not in team_member_ids:
                return error_response("Access denied", "You can only update your own or your team members' OKRs", 403)
        elif okr.employee_id != employee.id:
            return error_response("Access denied", "You can only update your own OKRs", 403)
    
    # Cannot update completed OKRs
    if okr.status == OKRStatus.COMPLETED:
        return error_response("Cannot update", "Cannot update a completed OKR", 400)
    
    schema = OKRUpdateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update fields
    for key, value in data.items():
        setattr(okr, key, value)
    
    db.session.commit()
    
    result_schema = OKRSchema()
    return success_response("OKR updated successfully", result_schema.dump(okr))

@okr_bp.route('/okrs/<int:okr_id>/activate', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def activate_okr(okr_id):
    """Activate a draft OKR"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    okr = OKR.query.get_or_404(okr_id)
    
    # Check permission for managers
    if user.role == Role.MANAGER:
        team_member_ids = [member.id for member in employee.team_members]
        if okr.employee_id != employee.id and okr.employee_id not in team_member_ids:
            return error_response("Access denied", "You can only activate your own or your team members' OKRs", 403)
    
    if okr.status != OKRStatus.DRAFT:
        return error_response("Invalid status", "Only draft OKRs can be activated", 400)
    
    okr.status = OKRStatus.ACTIVE
    db.session.commit()
    
    result_schema = OKRSchema()
    return success_response("OKR activated successfully", result_schema.dump(okr))

@okr_bp.route('/okrs/<int:okr_id>/complete', methods=['POST'])
@jwt_required()
def complete_okr(okr_id):
    """Mark an OKR as completed"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    okr = OKR.query.get_or_404(okr_id)
    
    # Check permission: admin/HR can complete all, managers can complete their team's, employees can complete their own
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER:
            team_member_ids = [member.id for member in employee.team_members]
            if okr.employee_id != employee.id and okr.employee_id not in team_member_ids:
                return error_response("Access denied", "You can only complete your own or your team members' OKRs", 403)
        elif okr.employee_id != employee.id:
            return error_response("Access denied", "You can only complete your own OKRs", 403)
    
    if okr.status != OKRStatus.ACTIVE:
        return error_response("Invalid status", "Only active OKRs can be completed", 400)
    
    okr.status = OKRStatus.COMPLETED
    db.session.commit()
    
    result_schema = OKRSchema()
    return success_response("OKR completed successfully", result_schema.dump(okr))

@okr_bp.route('/okrs/<int:okr_id>/cancel', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def cancel_okr(okr_id):
    """Cancel an OKR"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    okr = OKR.query.get_or_404(okr_id)
    
    # Check permission for managers
    if user.role == Role.MANAGER:
        team_member_ids = [member.id for member in employee.team_members]
        if okr.employee_id != employee.id and okr.employee_id not in team_member_ids:
            return error_response("Access denied", "You can only cancel your own or your team members' OKRs", 403)
    
    if okr.status == OKRStatus.COMPLETED:
        return error_response("Invalid status", "Cannot cancel a completed OKR", 400)
    
    okr.status = OKRStatus.CANCELLED
    db.session.commit()
    
    result_schema = OKRSchema()
    return success_response("OKR cancelled successfully", result_schema.dump(okr))

@okr_bp.route('/key-results/<int:key_result_id>', methods=['PUT'])
@jwt_required()
def update_key_result(key_result_id):
    """Update a key result"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    key_result = KeyResult.query.get_or_404(key_result_id)
    okr = OKR.query.get(key_result.okr_id)
    
    # Check permission: admin/HR can update all, managers can update their team's, employees can update their own
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER:
            team_member_ids = [member.id for member in employee.team_members]
            if okr.employee_id != employee.id and okr.employee_id not in team_member_ids:
                return error_response("Access denied", "You can only update your own or your team members' key results", 403)
        elif okr.employee_id != employee.id:
            return error_response("Access denied", "You can only update your own key results", 403)
    
    # Cannot update key results in completed OKRs
    if okr.status == OKRStatus.COMPLETED:
        return error_response("Cannot update", "Cannot update key results in a completed OKR", 400)
    
    schema = KeyResultUpdateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update fields
    for key, value in data.items():
        setattr(key_result, key, value)
    
    # Calculate progress if current_value is updated
    if 'current_value' in data:
        if key_result.target_value > 0:
            key_result.progress = min(100, int((key_result.current_value / key_result.target_value) * 100))
        
        # Update OKR progress based on average of key results
        all_key_results = KeyResult.query.filter_by(okr_id=okr.id).all()
        if all_key_results:
            total_progress = sum(kr.progress for kr in all_key_results)
            okr.progress = total_progress // len(all_key_results)
            db.session.add(okr)
    
    db.session.commit()
    
    # Return the updated OKR with all key results
    result_schema = OKRSchema()
    return success_response("Key result updated successfully", result_schema.dump(okr))

@okr_bp.route('/my-okrs', methods=['GET'])
@jwt_required()
def get_my_okrs():
    """Get current user's OKRs"""
    user_id = get_jwt_identity()
    
    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    
    query = OKR.query.filter_by(employee_id=employee.id)
    
    if status:
        query = query.filter_by(status=status)
    
    okrs = query.order_by(desc(OKR.created_at)).paginate(page=page, per_page=per_page)
    
    schema = OKRSchema(many=True)
    return success_response(
        "Your OKRs retrieved successfully",
        schema.dump(okrs.items),
        meta={"total": okrs.total, "page": page, "per_page": per_page}
    )