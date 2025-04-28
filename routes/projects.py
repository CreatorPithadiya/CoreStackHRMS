from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app import db
from models import (
    User, Employee, Project, ProjectMember, 
    Task, ProjectStatus, Role
)
from schemas.project import (
    ProjectSchema, ProjectCreateSchema, 
    ProjectUpdateSchema, ProjectMemberSchema
)
from utils.responses import success_response, error_response
from utils.pagination import paginate
from datetime import datetime

projects_bp = Blueprint('projects', __name__)

# Get all projects
@projects_bp.route('', methods=['GET'])
@jwt_required()
def get_projects():
    """
    Get all projects with pagination and filtering
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: status
        in: query
        type: string
        enum: [planning, in_progress, on_hold, completed, cancelled]
        required: false
      - name: search
        in: query
        type: string
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
        description: List of projects
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Get filter parameters
    status = request.args.get('status')
    search = request.args.get('search', '')
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Base query
    if current_user.role in [Role.ADMIN, Role.HR]:
        # Admin and HR can view all projects
        query = Project.query
    else:
        # Other users can only view projects they're members of or created
        query = Project.query.join(
            ProjectMember, 
            Project.id == ProjectMember.project_id
        ).filter(
            db.or_(
                ProjectMember.employee_id == employee.id,
                Project.created_by == employee.id
            )
        ).distinct()
    
    # Apply filters
    if status:
        try:
            status_enum = ProjectStatus[status.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            return error_response(f"Invalid status: {status}", 400)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Project.name.ilike(search_term),
                Project.description.ilike(search_term)
            )
        )
    
    # Order by start date descending (newest first)
    query = query.order_by(Project.start_date.desc())
    
    # Execute paginated query
    paginated_projects = paginate(query, page, per_page)
    
    # Serialize results
    result = {
        "items": ProjectSchema(many=True).dump(paginated_projects.items),
        "total": paginated_projects.total,
        "pages": paginated_projects.pages,
        "page": page,
        "per_page": per_page
    }
    
    return success_response(result)

# Get specific project
@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    """
    Get specific project details
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Project details
      401:
        description: Unauthorized
      403:
        description: Forbidden - not a member of this project
      404:
        description: Project not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has access to this project
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can access any project
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Check if employee is a member of this project or created it
    elif not ProjectMember.query.filter_by(project_id=project_id, employee_id=employee.id).first() and project.created_by != employee.id:
        return error_response("You don't have access to this project", 403)
    
    # Get detailed project info with members and tasks
    project_data = ProjectSchema().dump(project)
    
    return success_response(project_data)

# Create new project
@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    """
    Create new project
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: ProjectCreate
          required:
            - name
          properties:
            name:
              type: string
            description:
              type: string
            status:
              type: string
              enum: [planning, in_progress, on_hold, completed, cancelled]
              default: planning
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            budget:
              type: number
            members:
              type: array
              items:
                type: object
                properties:
                  employee_id:
                    type: integer
                  role:
                    type: string
                    default: member
    responses:
      201:
        description: Project created successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    schema = ProjectCreateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Extract members if provided
    members_data = data.pop('members', [])
    
    # Create project
    project = Project(
        name=data['name'],
        description=data.get('description'),
        status=ProjectStatus[data.get('status', 'PLANNING').upper()],
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        budget=data.get('budget'),
        created_by=employee.id
    )
    
    db.session.add(project)
    db.session.flush()  # Get project ID
    
    # Add creator as a project manager by default
    creator_member = ProjectMember(
        project_id=project.id,
        employee_id=employee.id,
        role='project manager'
    )
    db.session.add(creator_member)
    
    # Add additional members if provided
    for member_data in members_data:
        member = ProjectMember(
            project_id=project.id,
            employee_id=member_data['employee_id'],
            role=member_data.get('role', 'member')
        )
        db.session.add(member)
    
    db.session.commit()
    
    return success_response(
        ProjectSchema().dump(project),
        201
    )

# Update project
@projects_bp.route('/<int:project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    """
    Update project details
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: ProjectUpdate
          properties:
            name:
              type: string
            description:
              type: string
            status:
              type: string
              enum: [planning, in_progress, on_hold, completed, cancelled]
            start_date:
              type: string
              format: date
            end_date:
              type: string
              format: date
            budget:
              type: number
    responses:
      200:
        description: Project updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to update this project
      404:
        description: Project not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has permission to update this project
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can update any project
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Only project creator or project manager can update project
    elif project.created_by != employee.id:
        project_member = ProjectMember.query.filter_by(
            project_id=project_id, 
            employee_id=employee.id,
            role='project manager'
        ).first()
        
        if not project_member:
            return error_response("You don't have permission to update this project", 403)
    
    schema = ProjectUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Convert status to enum if provided
    if 'status' in data:
        try:
            data['status'] = ProjectStatus[data['status'].upper()]
        except KeyError:
            return error_response(f"Invalid status: {data['status']}", 400)
    
    # Update project fields
    for key, value in data.items():
        setattr(project, key, value)
    
    db.session.commit()
    
    return success_response(ProjectSchema().dump(project))

# Delete project
@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@jwt_required()
def delete_project(project_id):
    """
    Delete project (only for admin, HR, or project creator)
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Project deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to delete this project
      404:
        description: Project not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has permission to delete this project
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Only admin, HR, or project creator can delete project
    if current_user.role not in [Role.ADMIN, Role.HR] and project.created_by != employee.id:
        return error_response("You don't have permission to delete this project", 403)
    
    # Check if project has tasks
    if Task.query.filter_by(project_id=project_id).count() > 0:
        # Instead of hard delete, mark as cancelled
        project.status = ProjectStatus.CANCELLED
        db.session.commit()
        return success_response({
            "message": "Project marked as cancelled because it has associated tasks"
        })
    
    # No tasks, proceed with deletion
    db.session.delete(project)
    db.session.commit()
    
    return success_response({
        "message": "Project deleted successfully"
    })

# Add member to project
@projects_bp.route('/<int:project_id>/members', methods=['POST'])
@jwt_required()
def add_project_member(project_id):
    """
    Add member to project
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: AddProjectMember
          required:
            - employee_id
          properties:
            employee_id:
              type: integer
            role:
              type: string
              default: member
    responses:
      201:
        description: Member added successfully
      400:
        description: Validation error or already a member
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to add members
      404:
        description: Project or employee not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has permission to add members
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin, HR, project creator or project manager can add members
    can_add_members = (
        current_user.role in [Role.ADMIN, Role.HR] or 
        project.created_by == employee.id or
        ProjectMember.query.filter_by(
            project_id=project_id, 
            employee_id=employee.id,
            role='project manager'
        ).first() is not None
    )
    
    if not can_add_members:
        return error_response("You don't have permission to add members to this project", 403)
    
    # Validate request data
    try:
        data = request.json
        if not data or 'employee_id' not in data:
            return error_response("Employee ID is required", 400)
        
        employee_id = data['employee_id']
        role = data.get('role', 'member')
    except Exception:
        return error_response("Invalid request data", 400)
    
    # Check if employee exists
    target_employee = Employee.query.get(employee_id)
    if not target_employee:
        return error_response("Employee not found", 404)
    
    # Check if already a member
    existing_member = ProjectMember.query.filter_by(
        project_id=project_id,
        employee_id=employee_id
    ).first()
    
    if existing_member:
        return error_response("Employee is already a member of this project", 400)
    
    # Add new member
    new_member = ProjectMember(
        project_id=project_id,
        employee_id=employee_id,
        role=role
    )
    
    db.session.add(new_member)
    db.session.commit()
    
    return success_response(
        ProjectMemberSchema().dump(new_member),
        201
    )

# Remove member from project
@projects_bp.route('/<int:project_id>/members/<int:employee_id>', methods=['DELETE'])
@jwt_required()
def remove_project_member(project_id, employee_id):
    """
    Remove member from project
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
      - name: employee_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Member removed successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to remove members
      404:
        description: Project, member or membership not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has permission to remove members
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin, HR, project creator or project manager can remove members
    can_remove_members = (
        current_user.role in [Role.ADMIN, Role.HR] or 
        project.created_by == employee.id or
        ProjectMember.query.filter_by(
            project_id=project_id, 
            employee_id=employee.id,
            role='project manager'
        ).first() is not None
    )
    
    if not can_remove_members:
        return error_response("You don't have permission to remove members from this project", 403)
    
    # Check if membership exists
    membership = ProjectMember.query.filter_by(
        project_id=project_id,
        employee_id=employee_id
    ).first()
    
    if not membership:
        return error_response("Employee is not a member of this project", 404)
    
    # Cannot remove project creator if they're a project manager
    if project.created_by == employee_id and membership.role == 'project manager':
        return error_response("Cannot remove the project creator", 400)
    
    # Remove member
    db.session.delete(membership)
    db.session.commit()
    
    return success_response({
        "message": "Member removed successfully"
    })

# Update member role in project
@projects_bp.route('/<int:project_id>/members/<int:employee_id>', methods=['PUT'])
@jwt_required()
def update_project_member_role(project_id, employee_id):
    """
    Update member role in project
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
      - name: employee_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: UpdateMemberRole
          required:
            - role
          properties:
            role:
              type: string
              enum: [project manager, team lead, member]
    responses:
      200:
        description: Member role updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to update member roles
      404:
        description: Project, member or membership not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has permission to update member roles
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Only Admin, HR, project creator or project manager can update roles
    can_update_roles = (
        current_user.role in [Role.ADMIN, Role.HR] or 
        project.created_by == employee.id or
        ProjectMember.query.filter_by(
            project_id=project_id, 
            employee_id=employee.id,
            role='project manager'
        ).first() is not None
    )
    
    if not can_update_roles:
        return error_response("You don't have permission to update member roles in this project", 403)
    
    # Check if membership exists
    membership = ProjectMember.query.filter_by(
        project_id=project_id,
        employee_id=employee_id
    ).first()
    
    if not membership:
        return error_response("Employee is not a member of this project", 404)
    
    # Validate request data
    try:
        data = request.json
        if not data or 'role' not in data:
            return error_response("Role is required", 400)
        
        role = data['role']
        if role not in ['project manager', 'team lead', 'member']:
            return error_response("Invalid role", 400)
    except Exception:
        return error_response("Invalid request data", 400)
    
    # Update role
    membership.role = role
    db.session.commit()
    
    return success_response(ProjectMemberSchema().dump(membership))

# Get project members
@projects_bp.route('/<int:project_id>/members', methods=['GET'])
@jwt_required()
def get_project_members(project_id):
    """
    Get project members
    ---
    tags:
      - Projects
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: List of project members
      401:
        description: Unauthorized
      403:
        description: Forbidden - not a member of this project
      404:
        description: Project not found
    """
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has access to this project
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can access any project
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Check if employee is a member of this project or created it
    elif not ProjectMember.query.filter_by(project_id=project_id, employee_id=employee.id).first() and project.created_by != employee.id:
        return error_response("You don't have access to this project", 403)
    
    # Get members with role information
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    
    return success_response(ProjectMemberSchema(many=True).dump(members))
