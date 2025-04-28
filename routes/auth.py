from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity
)
from marshmallow import ValidationError
from app import db
from models import User, Employee
from schemas.auth import (
    LoginSchema, RegisterSchema, 
    ChangePasswordSchema, UserSchema
)
from utils.responses import success_response, error_response

auth_bp = Blueprint('auth', __name__)

# Login endpoint
@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User Login
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        schema:
          id: Login
          required:
            - email
            - password
          properties:
            email:
              type: string
              description: User email
              example: "john.doe@example.com"
            password:
              type: string
              description: User password
              example: "securepassword"
    responses:
      200:
        description: Login successful
      401:
        description: Invalid credentials
    """
    schema = LoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.check_password(data['password']):
        return error_response("Invalid email or password", 401)
    
    if not user.is_active:
        return error_response("Your account is disabled", 401)
    
    # Update last login timestamp
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    # Get employee data
    employee = None
    employee_data = None
    if user.employee:
        employee = Employee.query.get(user.employee.id)
        employee_data = {
            "id": employee.id,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "position": employee.position,
            "profile_image": employee.profile_image
        }
    
    return success_response({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "employee": employee_data
        }
    })

# Register endpoint (admin only)
@auth_bp.route('/register', methods=['POST'])
@jwt_required()
def register():
    """
    Register new user
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: Register
          required:
            - email
            - password
            - role
          properties:
            email:
              type: string
              description: User email
              example: "jane.smith@example.com"
            password:
              type: string
              description: User password
              example: "securepassword"
            role:
              type: string
              description: User role
              enum: ["admin", "hr", "manager", "employee"]
              example: "employee"
    responses:
      201:
        description: User registered successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - requires admin role
    """
    # Only admin can register new users
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if not current_user or current_user.role.value != 'admin':
        return error_response("Only administrators can register new users", 403)
    
    schema = RegisterSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return error_response("Email already registered", 400)
    
    # Create new user
    new_user = User(
        email=data['email'],
        role=data['role']
    )
    new_user.set_password(data['password'])
    
    db.session.add(new_user)
    db.session.commit()
    
    return success_response(
        UserSchema().dump(new_user),
        201
    )

# Get current user
@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current user information
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: User information
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return error_response("User not found", 404)
    
    # Get employee data if it exists
    employee_data = None
    if user.employee:
        employee = Employee.query.get(user.employee.id)
        employee_data = {
            "id": employee.id,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "employee_id": employee.employee_id,
            "position": employee.position,
            "profile_image": employee.profile_image,
            "department": employee.department.name if employee.department else None
        }
    
    return success_response({
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "last_login": user.last_login,
            "employee": employee_data
        }
    })

# Refresh token
@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: New access token
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    
    return success_response({
        "access_token": new_access_token
    })

# Change password
@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change user password
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: ChangePassword
          required:
            - current_password
            - new_password
          properties:
            current_password:
              type: string
              description: Current password
              example: "oldpassword"
            new_password:
              type: string
              description: New password
              example: "newpassword"
    responses:
      200:
        description: Password changed successfully
      400:
        description: Validation error
      401:
        description: Unauthorized or incorrect current password
    """
    schema = ChangePasswordSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.check_password(data['current_password']):
        return error_response("Current password is incorrect", 401)
    
    user.set_password(data['new_password'])
    db.session.commit()
    
    return success_response({
        "message": "Password changed successfully"
    })

# Logout endpoint (frontend will handle token removal)
@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout user
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Logout successful
      401:
        description: Unauthorized
    """
    # JWT tokens are stateless, so we don't need to do anything on the backend
    # The frontend will remove the tokens from storage
    
    return success_response({
        "message": "Logout successful"
    })
