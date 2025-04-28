from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app import db
from models import User, Employee, Department, Role
from schemas.employee import (
    EmployeeSchema, EmployeeCreateSchema, 
    EmployeeUpdateSchema, DepartmentSchema
)
from utils.responses import success_response, error_response
from utils.decorators import admin_or_hr_required
from utils.pagination import paginate

employees_bp = Blueprint('employees', __name__)

# Get all employees
@employees_bp.route('', methods=['GET'])
@jwt_required()
def get_employees():
    """
    Get all employees with pagination
    ---
    tags:
      - Employees
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
      - name: department_id
        in: query
        type: integer
        required: false
      - name: search
        in: query
        type: string
        required: false
        description: Search by name, employee ID or position
    responses:
      200:
        description: List of employees
      401:
        description: Unauthorized
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    department_id = request.args.get('department_id', type=int)
    search = request.args.get('search', '')
    
    query = Employee.query
    
    # Filter by department if specified
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    # Search functionality
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.employee_id.ilike(search_term),
                Employee.position.ilike(search_term)
            )
        )
    
    # Execute paginated query
    paginated_employees = paginate(query, page, per_page)
    
    # Serialize results
    result = {
        "items": EmployeeSchema(many=True).dump(paginated_employees.items),
        "total": paginated_employees.total,
        "pages": paginated_employees.pages,
        "page": page,
        "per_page": per_page
    }
    
    return success_response(result)

# Get specific employee
@employees_bp.route('/<int:employee_id>', methods=['GET'])
@jwt_required()
def get_employee(employee_id):
    """
    Get specific employee details
    ---
    tags:
      - Employees
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Employee details
      404:
        description: Employee not found
      401:
        description: Unauthorized
    """
    employee = Employee.query.get(employee_id)
    
    if not employee:
        return error_response("Employee not found", 404)
    
    # Check if current user is authorized to view this employee
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Admin and HR can access any employee profile
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Managers can access their team members
    elif current_user.role == Role.MANAGER:
        manager_employee = Employee.query.filter_by(user_id=current_user_id).first()
        if employee.manager_id != manager_employee.id and employee.id != manager_employee.id:
            return error_response("You don't have permission to view this employee", 403)
    # Employees can only access their own profile
    else:
        employee_user = Employee.query.filter_by(user_id=current_user_id).first()
        if employee.id != employee_user.id:
            return error_response("You don't have permission to view this employee", 403)
    
    # Get employee data
    employee_data = EmployeeSchema().dump(employee)
    
    return success_response(employee_data)

# Create new employee
@employees_bp.route('', methods=['POST'])
@jwt_required()
@admin_or_hr_required
def create_employee():
    """
    Create new employee
    ---
    tags:
      - Employees
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: EmployeeCreate
          required:
            - first_name
            - last_name
            - employee_id
            - email
            - date_of_joining
          properties:
            first_name:
              type: string
            last_name:
              type: string
            employee_id:
              type: string
            email:
              type: string
            password:
              type: string
            date_of_joining:
              type: string
              format: date
            department_id:
              type: integer
            position:
              type: string
            date_of_birth:
              type: string
              format: date
            phone_number:
              type: string
            address:
              type: string
            gender:
              type: string
            manager_id:
              type: integer
    responses:
      201:
        description: Employee created successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
    """
    schema = EmployeeCreateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return error_response("Email already exists", 400)
    
    # Check if employee ID already exists
    if Employee.query.filter_by(employee_id=data['employee_id']).first():
        return error_response("Employee ID already exists", 400)
    
    # Create user
    user = User(
        email=data['email'],
        role=Role.EMPLOYEE  # Default role is employee
    )
    user.set_password(data.get('password', 'changeme'))  # Default password if not provided
    
    db.session.add(user)
    db.session.flush()  # Flush to get the user ID
    
    # Create employee
    employee = Employee(
        user_id=user.id,
        first_name=data['first_name'],
        last_name=data['last_name'],
        employee_id=data['employee_id'],
        department_id=data.get('department_id'),
        position=data.get('position'),
        date_of_birth=data.get('date_of_birth'),
        date_of_joining=data['date_of_joining'],
        phone_number=data.get('phone_number'),
        address=data.get('address'),
        gender=data.get('gender'),
        manager_id=data.get('manager_id')
    )
    
    db.session.add(employee)
    db.session.commit()
    
    return success_response(
        EmployeeSchema().dump(employee), 
        201
    )

# Update employee
@employees_bp.route('/<int:employee_id>', methods=['PUT'])
@jwt_required()
def update_employee(employee_id):
    """
    Update employee details
    ---
    tags:
      - Employees
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: EmployeeUpdate
          properties:
            first_name:
              type: string
            last_name:
              type: string
            department_id:
              type: integer
            position:
              type: string
            date_of_birth:
              type: string
              format: date
            phone_number:
              type: string
            address:
              type: string
            gender:
              type: string
            manager_id:
              type: integer
    responses:
      200:
        description: Employee updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - Insufficient permissions
      404:
        description: Employee not found
    """
    employee = Employee.query.get(employee_id)
    
    if not employee:
        return error_response("Employee not found", 404)
    
    schema = EmployeeUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check permissions
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Admin and HR can update any employee
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Managers can update their team members
    elif current_user.role == Role.MANAGER:
        manager_employee = Employee.query.filter_by(user_id=current_user_id).first()
        if employee.manager_id != manager_employee.id and employee.id != manager_employee.id:
            return error_response("You don't have permission to update this employee", 403)
        
        # Managers can only update limited fields
        allowed_fields = ['first_name', 'last_name', 'phone_number', 'address']
        for field in list(data.keys()):
            if field not in allowed_fields:
                data.pop(field)
    # Employee can update only own profile and only limited fields
    else:
        employee_user = Employee.query.filter_by(user_id=current_user_id).first()
        if employee.id != employee_user.id:
            return error_response("You don't have permission to update this employee", 403)
        
        # Employees can only update limited fields
        allowed_fields = ['phone_number', 'address']
        for field in list(data.keys()):
            if field not in allowed_fields:
                data.pop(field)
    
    # Update employee fields
    for key, value in data.items():
        setattr(employee, key, value)
    
    db.session.commit()
    
    return success_response(EmployeeSchema().dump(employee))

# Delete employee (soft delete)
@employees_bp.route('/<int:employee_id>', methods=['DELETE'])
@jwt_required()
@admin_or_hr_required
def delete_employee(employee_id):
    """
    Delete employee (soft delete)
    ---
    tags:
      - Employees
    security:
      - Bearer: []
    parameters:
      - name: employee_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Employee deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
      404:
        description: Employee not found
    """
    employee = Employee.query.get(employee_id)
    
    if not employee:
        return error_response("Employee not found", 404)
    
    # Get user associated with employee
    user = User.query.get(employee.user_id)
    
    if user:
        # Deactivate user (soft delete)
        user.is_active = False
        db.session.commit()
    
    return success_response({
        "message": "Employee deactivated successfully"
    })

# Get all departments
@employees_bp.route('/departments', methods=['GET'])
@jwt_required()
def get_departments():
    """
    Get all departments
    ---
    tags:
      - Departments
    security:
      - Bearer: []
    responses:
      200:
        description: List of departments
      401:
        description: Unauthorized
    """
    departments = Department.query.all()
    result = DepartmentSchema(many=True).dump(departments)
    
    return success_response(result)

# Create department
@employees_bp.route('/departments', methods=['POST'])
@jwt_required()
@admin_or_hr_required
def create_department():
    """
    Create new department
    ---
    tags:
      - Departments
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: DepartmentCreate
          required:
            - name
          properties:
            name:
              type: string
            description:
              type: string
    responses:
      201:
        description: Department created successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
    """
    schema = DepartmentSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check if department already exists
    if Department.query.filter_by(name=data['name']).first():
        return error_response("Department already exists", 400)
    
    department = Department(
        name=data['name'],
        description=data.get('description')
    )
    
    db.session.add(department)
    db.session.commit()
    
    return success_response(
        DepartmentSchema().dump(department),
        201
    )

# Update department
@employees_bp.route('/departments/<int:department_id>', methods=['PUT'])
@jwt_required()
@admin_or_hr_required
def update_department(department_id):
    """
    Update department
    ---
    tags:
      - Departments
    security:
      - Bearer: []
    parameters:
      - name: department_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: DepartmentUpdate
          properties:
            name:
              type: string
            description:
              type: string
    responses:
      200:
        description: Department updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
      404:
        description: Department not found
    """
    department = Department.query.get(department_id)
    
    if not department:
        return error_response("Department not found", 404)
    
    schema = DepartmentSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check if name already exists (if being changed)
    if data.get('name') and data['name'] != department.name:
        if Department.query.filter_by(name=data['name']).first():
            return error_response("Department name already exists", 400)
    
    # Update department fields
    for key, value in data.items():
        setattr(department, key, value)
    
    db.session.commit()
    
    return success_response(DepartmentSchema().dump(department))

# Delete department
@employees_bp.route('/departments/<int:department_id>', methods=['DELETE'])
@jwt_required()
@admin_or_hr_required
def delete_department(department_id):
    """
    Delete department
    ---
    tags:
      - Departments
    security:
      - Bearer: []
    parameters:
      - name: department_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Department deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - Admin or HR role required
      404:
        description: Department not found
      400:
        description: Cannot delete department with employees
    """
    department = Department.query.get(department_id)
    
    if not department:
        return error_response("Department not found", 404)
    
    # Check if department has employees
    if Employee.query.filter_by(department_id=department_id).first():
        return error_response("Cannot delete department with assigned employees", 400)
    
    db.session.delete(department)
    db.session.commit()
    
    return success_response({
        "message": "Department deleted successfully"
    })
