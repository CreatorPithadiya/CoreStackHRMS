from functools import wraps
from flask_jwt_extended import get_jwt_identity
from flask import jsonify
from models import User, Role
from utils.responses import error_response

def admin_required(fn):
    """Decorator to require admin role for a route"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user or current_user.role != Role.ADMIN:
            return error_response("Admin role required", 403)
        
        return fn(*args, **kwargs)
    return wrapper

def admin_or_hr_required(fn):
    """Decorator to require admin or HR role for a route"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user or current_user.role not in [Role.ADMIN, Role.HR]:
            return error_response("Admin or HR role required", 403)
        
        return fn(*args, **kwargs)
    return wrapper

def manager_required(fn):
    """Decorator to require manager role for a route"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user or current_user.role not in [Role.ADMIN, Role.HR, Role.MANAGER]:
            return error_response("Manager role or higher required", 403)
        
        return fn(*args, **kwargs)
    return wrapper

def self_or_admin_required(employee_id_param='employee_id'):
    """Decorator to require the user to be the resource owner or admin/HR"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get the employee_id from route parameters
            employee_id = kwargs.get(employee_id_param)
            
            # If no employee_id in route, check query parameters
            if employee_id is None:
                from flask import request
                employee_id = request.args.get(employee_id_param)
            
            # Get current user
            current_user_id = get_jwt_identity()
            current_user = User.query.get(current_user_id)
            
            # Admin and HR can access any employee
            if current_user and current_user.role in [Role.ADMIN, Role.HR]:
                return fn(*args, **kwargs)
            
            # If we don't have an employee ID to check against, proceed (the route will check)
            if employee_id is None:
                return fn(*args, **kwargs)
            
            # Convert to integer if it's a string
            if isinstance(employee_id, str) and employee_id.isdigit():
                employee_id = int(employee_id)
            
            # Check if user is accessing their own record
            from models import Employee
            employee = Employee.query.filter_by(user_id=current_user_id).first()
            
            if not employee or employee.id != employee_id:
                return error_response("You don't have permission to access this resource", 403)
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def team_member_or_admin_required(employee_id_param='employee_id'):
    """Decorator to require the user to be the manager of the employee or admin/HR"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get the employee_id from route parameters
            employee_id = kwargs.get(employee_id_param)
            
            # If no employee_id in route, check query parameters
            if employee_id is None:
                from flask import request
                employee_id = request.args.get(employee_id_param)
            
            # Get current user
            current_user_id = get_jwt_identity()
            current_user = User.query.get(current_user_id)
            
            # Admin and HR can access any employee
            if current_user and current_user.role in [Role.ADMIN, Role.HR]:
                return fn(*args, **kwargs)
            
            # If we don't have an employee ID to check against, proceed (the route will check)
            if employee_id is None:
                return fn(*args, **kwargs)
            
            # Convert to integer if it's a string
            if isinstance(employee_id, str) and employee_id.isdigit():
                employee_id = int(employee_id)
            
            # Check if user is accessing their own record or a team member's record
            from models import Employee
            manager_employee = Employee.query.filter_by(user_id=current_user_id).first()
            
            if not manager_employee:
                return error_response("Manager profile not found", 404)
            
            # Self access or team member access
            if manager_employee.id == employee_id or Employee.query.filter_by(
                id=employee_id, manager_id=manager_employee.id
            ).first():
                return fn(*args, **kwargs)
            
            return error_response("You don't have permission to access this resource", 403)
        return wrapper
    return decorator

def role_required(roles):
    """Decorator to require specific roles for a route
    
    Args:
        roles: A list of roles from the Role enum that are allowed to access this route
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            current_user_id = get_jwt_identity()
            current_user = User.query.get(current_user_id)
            
            if not current_user or current_user.role not in roles:
                allowed_roles = ', '.join([role.value for role in roles])
                return error_response(f"Permission denied. Required roles: {allowed_roles}", 403)
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator
