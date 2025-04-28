from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc
from datetime import datetime, date
import io
import os

from app import db
from models import Payroll, Salary, User, Employee, PayrollStatus, Role
from schemas.payroll import (
    PayrollSchema, PayrollCreateSchema, PayrollUpdateSchema,
    SalarySchema, SalaryCreateSchema, PayslipGenerateSchema
)
from utils.responses import success_response, error_response
from utils.decorators import role_required

payroll_bp = Blueprint('payroll', __name__)

# Salary endpoints
@payroll_bp.route('/salaries', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def get_salaries():
    """Get all salary records"""
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    
    query = Salary.query
    
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    salaries = query.order_by(desc(Salary.effective_date)).paginate(page=page, per_page=per_page)
    
    schema = SalarySchema(many=True)
    return success_response(
        "Salaries retrieved successfully",
        schema.dump(salaries.items),
        meta={"total": salaries.total, "page": page, "per_page": per_page}
    )

@payroll_bp.route('/salaries/current', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def get_current_salaries():
    """Get current salary for all employees"""
    user_id = get_jwt_identity()
    
    # Subquery to get the latest salary record for each employee
    latest_salaries = db.session.query(
        Salary.employee_id,
        db.func.max(Salary.effective_date).label('max_date')
    ).filter(
        (Salary.end_date.is_(None)) | (Salary.end_date >= date.today())
    ).group_by(Salary.employee_id).subquery()
    
    # Query to join with the subquery
    current_salaries = Salary.query.join(
        latest_salaries,
        db.and_(
            Salary.employee_id == latest_salaries.c.employee_id,
            Salary.effective_date == latest_salaries.c.max_date
        )
    ).all()
    
    schema = SalarySchema(many=True)
    return success_response("Current salaries retrieved successfully", schema.dump(current_salaries))

@payroll_bp.route('/salaries/<int:employee_id>/history', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def get_employee_salary_history(employee_id):
    """Get salary history for a specific employee"""
    user_id = get_jwt_identity()
    
    employee = Employee.query.get_or_404(employee_id)
    salaries = Salary.query.filter_by(employee_id=employee_id).order_by(desc(Salary.effective_date)).all()
    
    schema = SalarySchema(many=True)
    return success_response(
        f"Salary history for {employee.full_name} retrieved successfully",
        schema.dump(salaries)
    )

@payroll_bp.route('/salaries', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def create_salary():
    """Create a new salary record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    schema = SalaryCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Get the HR/Admin's employee record to set as creator
    creator = Employee.query.filter_by(user_id=user_id).first()
    if not creator:
        return error_response("Creator employee record not found", "", 404)
    
    # Check if employee exists
    employee = Employee.query.get(data['employee_id'])
    if not employee:
        return error_response("Employee not found", "", 404)
    
    # If an existing current salary exists (with no end_date), set its end_date to one day before the new effective_date
    current_salary = Salary.query.filter_by(
        employee_id=data['employee_id'],
        end_date=None
    ).first()
    
    if current_salary and current_salary.effective_date < data['effective_date']:
        # Set end date to one day before new salary's effective date
        from datetime import timedelta
        current_salary.end_date = data['effective_date'] - timedelta(days=1)
        db.session.add(current_salary)
    
    # Create new salary record
    new_salary = Salary(
        employee_id=data['employee_id'],
        base_salary=data['base_salary'],
        salary_type=data['salary_type'] if 'salary_type' in data else 'fixed',
        frequency=data['frequency'] if 'frequency' in data else 'monthly',
        effective_date=data['effective_date'],
        end_date=data.get('end_date'),
        created_by=creator.id
    )
    
    db.session.add(new_salary)
    db.session.commit()
    
    result_schema = SalarySchema()
    return success_response("Salary created successfully", result_schema.dump(new_salary), 201)

# Payroll endpoints
@payroll_bp.route('/payrolls', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def get_payrolls():
    """Get all payroll records"""
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    status = request.args.get('status')
    
    query = Payroll.query
    
    if employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    if status:
        query = query.filter_by(status=status)
    
    payrolls = query.order_by(desc(Payroll.period_end)).paginate(page=page, per_page=per_page)
    
    schema = PayrollSchema(many=True)
    return success_response(
        "Payrolls retrieved successfully",
        schema.dump(payrolls.items),
        meta={"total": payrolls.total, "page": page, "per_page": per_page}
    )

@payroll_bp.route('/payrolls/<int:payroll_id>', methods=['GET'])
@jwt_required()
def get_payroll(payroll_id):
    """Get a specific payroll record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Check permission: admin/HR can see all, employee can only see their own
    if user.role not in [Role.ADMIN, Role.HR] and payroll.employee.user_id != user_id:
        return error_response("Access denied", "You don't have permission to view this payroll", 403)
    
    schema = PayrollSchema()
    return success_response("Payroll retrieved successfully", schema.dump(payroll))

@payroll_bp.route('/payrolls', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def create_payroll():
    """Create a new payroll record"""
    user_id = get_jwt_identity()
    
    schema = PayrollCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Get the HR/Admin's employee record to set as creator
    creator = Employee.query.filter_by(user_id=user_id).first()
    if not creator:
        return error_response("Creator employee record not found", "", 404)
    
    # Check if employee exists
    employee = Employee.query.get(data['employee_id'])
    if not employee:
        return error_response("Employee not found", "", 404)
    
    # Create new payroll record
    new_payroll = Payroll(
        employee_id=data['employee_id'],
        period_start=data['period_start'],
        period_end=data['period_end'],
        base_salary=data['base_salary'],
        overtime_hours=data.get('overtime_hours', 0),
        overtime_amount=data.get('overtime_amount', 0),
        bonus=data.get('bonus', 0),
        bonus_description=data.get('bonus_description', ''),
        deductions=data.get('deductions', 0),
        deduction_description=data.get('deduction_description', ''),
        tax=data.get('tax', 0),
        net_amount=data['net_amount'],
        status=data.get('status', PayrollStatus.DRAFT.value),
        payment_date=data.get('payment_date'),
        notes=data.get('notes', ''),
        created_by=creator.id
    )
    
    db.session.add(new_payroll)
    db.session.commit()
    
    result_schema = PayrollSchema()
    return success_response("Payroll created successfully", result_schema.dump(new_payroll), 201)

@payroll_bp.route('/payrolls/<int:payroll_id>', methods=['PUT'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def update_payroll(payroll_id):
    """Update a payroll record"""
    user_id = get_jwt_identity()
    
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Can't update if it's already paid
    if payroll.status == PayrollStatus.PAID:
        return error_response("Cannot update", "Cannot update a payroll that has been paid", 400)
    
    schema = PayrollUpdateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update fields
    for key, value in data.items():
        setattr(payroll, key, value)
    
    db.session.commit()
    
    result_schema = PayrollSchema()
    return success_response("Payroll updated successfully", result_schema.dump(payroll))

@payroll_bp.route('/payrolls/<int:payroll_id>/process', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def process_payroll(payroll_id):
    """Process a draft payroll to processed status"""
    user_id = get_jwt_identity()
    
    payroll = Payroll.query.get_or_404(payroll_id)
    
    if payroll.status != PayrollStatus.DRAFT:
        return error_response("Invalid status", "Only draft payrolls can be processed", 400)
    
    payroll.status = PayrollStatus.PROCESSED
    db.session.commit()
    
    result_schema = PayrollSchema()
    return success_response("Payroll processed successfully", result_schema.dump(payroll))

@payroll_bp.route('/payrolls/<int:payroll_id>/pay', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def pay_payroll(payroll_id):
    """Mark a processed payroll as paid"""
    user_id = get_jwt_identity()
    
    payroll = Payroll.query.get_or_404(payroll_id)
    
    if payroll.status != PayrollStatus.PROCESSED:
        return error_response("Invalid status", "Only processed payrolls can be marked as paid", 400)
    
    payroll.status = PayrollStatus.PAID
    payroll.payment_date = date.today()
    db.session.commit()
    
    result_schema = PayrollSchema()
    return success_response("Payroll marked as paid successfully", result_schema.dump(payroll))

@payroll_bp.route('/payrolls/<int:payroll_id>/cancel', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def cancel_payroll(payroll_id):
    """Cancel a payroll that is not yet paid"""
    user_id = get_jwt_identity()
    
    payroll = Payroll.query.get_or_404(payroll_id)
    
    if payroll.status == PayrollStatus.PAID:
        return error_response("Invalid status", "Cannot cancel a payroll that has been paid", 400)
    
    payroll.status = PayrollStatus.CANCELLED
    db.session.commit()
    
    result_schema = PayrollSchema()
    return success_response("Payroll cancelled successfully", result_schema.dump(payroll))

@payroll_bp.route('/payrolls/generate-payslip', methods=['POST'])
@jwt_required()
def generate_payslip():
    """Generate a payslip for a specific payroll record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    schema = PayslipGenerateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    payroll_id = data['payroll_id']
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Check permission: admin/HR can generate for all, employee can only generate for their own
    if user.role not in [Role.ADMIN, Role.HR] and payroll.employee.user_id != user_id:
        return error_response("Access denied", "You don't have permission to generate this payslip", 403)
    
    # Here you would typically create a PDF, but for this demo we'll just return a JSON
    # In a real system, you would use a library like ReportLab or WeasyPrint to generate the PDF
    # and save it to a file, then return the file URL
    
    # Simulate PDF creation
    payslip_data = {
        "employee": {
            "name": payroll.employee.full_name,
            "id": payroll.employee.employee_id,
            "position": payroll.employee.position,
            "department": payroll.employee.department.name if payroll.employee.department else "N/A"
        },
        "payroll": {
            "period": f"{payroll.period_start} to {payroll.period_end}",
            "base_salary": payroll.base_salary,
            "overtime_hours": payroll.overtime_hours,
            "overtime_amount": payroll.overtime_amount,
            "bonus": payroll.bonus,
            "bonus_description": payroll.bonus_description,
            "deductions": payroll.deductions,
            "deduction_description": payroll.deduction_description,
            "tax": payroll.tax,
            "net_amount": payroll.net_amount
        },
        "options": {
            "include_breakdown": data.get('include_breakdown', True),
            "include_company_logo": data.get('include_company_logo', True),
            "include_signature": data.get('include_signature', False)
        },
        "generation_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return success_response("Payslip generated successfully", payslip_data)

@payroll_bp.route('/my-payrolls', methods=['GET'])
@jwt_required()
def get_my_payrolls():
    """Get current user's payroll records"""
    user_id = get_jwt_identity()
    
    employee = Employee.query.filter_by(user_id=user_id).first()
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    payrolls = Payroll.query.filter_by(
        employee_id=employee.id
    ).order_by(desc(Payroll.period_end)).paginate(page=page, per_page=per_page)
    
    schema = PayrollSchema(many=True)
    return success_response(
        "Your payrolls retrieved successfully",
        schema.dump(payrolls.items),
        meta={"total": payrolls.total, "page": page, "per_page": per_page}
    )