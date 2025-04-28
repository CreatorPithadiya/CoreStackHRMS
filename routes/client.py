from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc

from app import db
from models import ClientAccess, User, Employee, Project, Task, TaskComment, ProjectMember, Role
from schemas.client import ClientAccessSchema, ClientAccessCreateSchema, ClientAccessUpdateSchema, ClientProjectViewSchema
from utils.responses import success_response, error_response
from utils.decorators import role_required

client_bp = Blueprint('client', __name__)

@client_bp.route('/client-access', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.MANAGER])
def get_client_access():
    """Get all client access records"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    client_id = request.args.get('client_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    query = ClientAccess.query
    
    if client_id:
        query = query.filter_by(client_id=client_id)
    
    if project_id:
        query = query.filter_by(project_id=project_id)
    
    # Filter by projects that the manager owns if not admin
    if user.role == Role.MANAGER and employee:
        managed_projects = Project.query.filter_by(created_by=employee.id).all()
        project_ids = [p.id for p in managed_projects]
        query = query.filter(ClientAccess.project_id.in_(project_ids))
    
    access_records = query.order_by(desc(ClientAccess.created_at)).paginate(page=page, per_page=per_page)
    
    schema = ClientAccessSchema(many=True)
    return success_response(
        "Client access records retrieved successfully",
        schema.dump(access_records.items),
        meta={"total": access_records.total, "page": page, "per_page": per_page}
    )

@client_bp.route('/client-access/<int:access_id>', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.MANAGER, Role.CLIENT])
def get_client_access_by_id(access_id):
    """Get a specific client access record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    access = ClientAccess.query.get_or_404(access_id)
    
    # Check permissions
    if user.role == Role.CLIENT:
        if access.client_id != user.id:
            return error_response("Access denied", "You don't have permission to view this access record", 403)
    elif user.role == Role.MANAGER:
        employee = Employee.query.filter_by(user_id=user_id).first()
        project = Project.query.get(access.project_id)
        if not project or project.created_by != employee.id:
            return error_response("Access denied", "You don't have permission to view this access record", 403)
    
    schema = ClientAccessSchema()
    return success_response("Client access record retrieved successfully", schema.dump(access))

@client_bp.route('/client-access', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.MANAGER])
def create_client_access():
    """Create a new client access record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    schema = ClientAccessCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check if client user exists and has CLIENT role
    client = User.query.get(data['client_id'])
    if not client or client.role != Role.CLIENT:
        return error_response("Invalid client", "User must exist and have CLIENT role", 400)
    
    # Check if project exists
    project = Project.query.get(data['project_id'])
    if not project:
        return error_response("Project not found", "", 404)
    
    # Check if manager owns the project
    if user.role == Role.MANAGER and project.created_by != employee.id:
        return error_response("Access denied", "You can only grant access to projects you manage", 403)
    
    # Check if access record already exists
    existing = ClientAccess.query.filter_by(
        client_id=data['client_id'],
        project_id=data['project_id']
    ).first()
    
    if existing:
        return error_response("Access already exists", "This client already has access to this project", 400)
    
    # Create new access record
    new_access = ClientAccess(
        client_id=data['client_id'],
        project_id=data['project_id'],
        can_view_files=data.get('can_view_files', False),
        can_view_tasks=data.get('can_view_tasks', True),
        can_view_comments=data.get('can_view_comments', False),
        can_view_team=data.get('can_view_team', True),
        created_by=employee.id
    )
    
    db.session.add(new_access)
    db.session.commit()
    
    result_schema = ClientAccessSchema()
    return success_response("Client access created successfully", result_schema.dump(new_access), 201)

@client_bp.route('/client-access/<int:access_id>', methods=['PUT'])
@jwt_required()
@role_required([Role.ADMIN, Role.MANAGER])
def update_client_access(access_id):
    """Update a client access record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    access = ClientAccess.query.get_or_404(access_id)
    
    # Check if manager owns the project
    if user.role == Role.MANAGER:
        project = Project.query.get(access.project_id)
        if not project or project.created_by != employee.id:
            return error_response("Access denied", "You can only update access for projects you manage", 403)
    
    schema = ClientAccessUpdateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update fields
    for key, value in data.items():
        setattr(access, key, value)
    
    db.session.commit()
    
    result_schema = ClientAccessSchema()
    return success_response("Client access updated successfully", result_schema.dump(access))

@client_bp.route('/client-access/<int:access_id>', methods=['DELETE'])
@jwt_required()
@role_required([Role.ADMIN, Role.MANAGER])
def delete_client_access(access_id):
    """Delete a client access record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    access = ClientAccess.query.get_or_404(access_id)
    
    # Check if manager owns the project
    if user.role == Role.MANAGER:
        project = Project.query.get(access.project_id)
        if not project or project.created_by != employee.id:
            return error_response("Access denied", "You can only delete access for projects you manage", 403)
    
    db.session.delete(access)
    db.session.commit()
    
    return success_response("Client access deleted successfully", {})

# Client project view endpoints
@client_bp.route('/client/projects', methods=['GET'])
@jwt_required()
@role_required([Role.CLIENT])
def get_client_projects():
    """Get projects that the client has access to"""
    user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    access_records = ClientAccess.query.filter_by(client_id=user_id).all()
    project_ids = [record.project_id for record in access_records]
    
    projects = Project.query.filter(Project.id.in_(project_ids)).paginate(page=page, per_page=per_page)
    
    schema = ClientProjectViewSchema(many=True)
    result = []
    
    # For each project, compile the view based on access permissions
    for project in projects.items:
        access = next((a for a in access_records if a.project_id == project.id), None)
        if not access:
            continue
        
        project_view = {'project': project}
        
        # Add tasks if allowed
        if access.can_view_tasks:
            project_view['tasks'] = project.tasks
        
        # Add team members if allowed
        if access.can_view_team:
            members = [pm.employee for pm in project.members]
            project_view['members'] = members
        
        # Add comments if allowed
        if access.can_view_comments:
            comments = []
            for task in project.tasks:
                comments.extend(task.comments)
            project_view['comments'] = comments
        
        result.append(project_view)
    
    return success_response(
        "Client projects retrieved successfully",
        schema.dump(result),
        meta={"total": projects.total, "page": page, "per_page": per_page}
    )

@client_bp.route('/client/projects/<int:project_id>', methods=['GET'])
@jwt_required()
@role_required([Role.CLIENT])
def get_client_project(project_id):
    """Get a specific project that the client has access to"""
    user_id = get_jwt_identity()
    
    # Check if client has access to this project
    access = ClientAccess.query.filter_by(client_id=user_id, project_id=project_id).first()
    if not access:
        return error_response("Access denied", "You don't have access to this project", 403)
    
    project = Project.query.get_or_404(project_id)
    
    project_view = {'project': project}
    
    # Add tasks if allowed
    if access.can_view_tasks:
        project_view['tasks'] = project.tasks
    
    # Add team members if allowed
    if access.can_view_team:
        members = [pm.employee for pm in project.members]
        project_view['members'] = members
    
    # Add comments if allowed
    if access.can_view_comments:
        comments = []
        for task in project.tasks:
            comments.extend(task.comments)
        project_view['comments'] = comments
    
    schema = ClientProjectViewSchema()
    return success_response("Client project retrieved successfully", schema.dump(project_view))