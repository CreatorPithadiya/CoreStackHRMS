from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app import db
from models import (
    User, Employee, Project, ProjectMember, 
    Task, TaskComment, TaskPriority, TaskStatus, Role
)
from schemas.task import (
    TaskSchema, TaskCreateSchema, 
    TaskUpdateSchema, TaskCommentSchema
)
from utils.responses import success_response, error_response
from utils.pagination import paginate
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__)

# Get all tasks
@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    """
    Get all tasks with pagination and filtering
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: project_id
        in: query
        type: integer
        required: false
      - name: assignee_id
        in: query
        type: integer
        required: false
      - name: status
        in: query
        type: string
        enum: [backlog, todo, in_progress, review, completed]
        required: false
      - name: priority
        in: query
        type: string
        enum: [low, medium, high, urgent]
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
        description: List of tasks
      401:
        description: Unauthorized
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Get filter parameters
    project_id = request.args.get('project_id', type=int)
    assignee_id = request.args.get('assignee_id', type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')
    search = request.args.get('search', '')
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Base query
    query = Task.query
    
    # If not admin or HR, filter to tasks accessible to the user
    if current_user.role not in [Role.ADMIN, Role.HR]:
        # Get projects where the user is a member
        member_projects = db.session.query(ProjectMember.project_id).filter_by(employee_id=employee.id).all()
        member_project_ids = [p[0] for p in member_projects]
        
        # Get projects created by the user
        created_projects = db.session.query(Project.id).filter_by(created_by=employee.id).all()
        created_project_ids = [p[0] for p in created_projects]
        
        # Combine both sets of project IDs
        accessible_project_ids = list(set(member_project_ids + created_project_ids))
        
        # Filter tasks to those in accessible projects or assigned to the user
        query = query.filter(
            db.or_(
                Task.project_id.in_(accessible_project_ids),
                Task.assignee_id == employee.id,
                Task.created_by == employee.id
            )
        )
    
    # Apply filters
    if project_id:
        query = query.filter_by(project_id=project_id)
    
    if assignee_id:
        query = query.filter_by(assignee_id=assignee_id)
    
    if status:
        try:
            status_enum = TaskStatus[status.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            return error_response(f"Invalid status: {status}", 400)
    
    if priority:
        try:
            priority_enum = TaskPriority[priority.upper()]
            query = query.filter_by(priority=priority_enum)
        except KeyError:
            return error_response(f"Invalid priority: {priority}", 400)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Task.title.ilike(search_term),
                Task.description.ilike(search_term)
            )
        )
    
    # Order by due date (if exists) and creation date
    query = query.order_by(
        Task.due_date.asc().nullslast(),
        Task.created_at.desc()
    )
    
    # Execute paginated query
    paginated_tasks = paginate(query, page, per_page)
    
    # Serialize results
    result = {
        "items": TaskSchema(many=True).dump(paginated_tasks.items),
        "total": paginated_tasks.total,
        "pages": paginated_tasks.pages,
        "page": page,
        "per_page": per_page
    }
    
    return success_response(result)

# Get specific task
@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """
    Get specific task details
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Task details
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to access this task
      404:
        description: Task not found
    """
    task = Task.query.get(task_id)
    
    if not task:
        return error_response("Task not found", 404)
    
    # Check if user has access to this task
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can access any task
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Check if employee is a member of the project, task creator, or assignee
    elif not ProjectMember.query.filter_by(project_id=task.project_id, employee_id=employee.id).first() \
        and task.created_by != employee.id \
        and task.assignee_id != employee.id:
        # Also check if they're the project creator
        project = Project.query.get(task.project_id)
        if not project or project.created_by != employee.id:
            return error_response("You don't have access to this task", 403)
    
    # Get detailed task info with comments
    task_data = TaskSchema().dump(task)
    
    return success_response(task_data)

# Create new task
@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    """
    Create new task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: TaskCreate
          required:
            - title
            - project_id
          properties:
            title:
              type: string
            description:
              type: string
            project_id:
              type: integer
            assignee_id:
              type: integer
            status:
              type: string
              enum: [backlog, todo, in_progress, review, completed]
              default: todo
            priority:
              type: string
              enum: [low, medium, high, urgent]
              default: medium
            progress:
              type: integer
              minimum: 0
              maximum: 100
              default: 0
            estimated_hours:
              type: number
            due_date:
              type: string
              format: date
    responses:
      201:
        description: Task created successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to create tasks in this project
      404:
        description: Project or assignee not found
    """
    schema = TaskCreateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Check if project exists
    project_id = data['project_id']
    project = Project.query.get(project_id)
    
    if not project:
        return error_response("Project not found", 404)
    
    # Check if user has access to create tasks in this project
    current_user = User.query.get(current_user_id)
    
    # Admin and HR can create tasks in any project
    if current_user.role not in [Role.ADMIN, Role.HR]:
        # Check if employee is a member of the project or project creator
        is_member = ProjectMember.query.filter_by(project_id=project_id, employee_id=employee.id).first() is not None
        is_creator = project.created_by == employee.id
        
        if not is_member and not is_creator:
            return error_response("You don't have permission to create tasks in this project", 403)
    
    # Check if assignee exists and is a member of the project
    assignee_id = data.get('assignee_id')
    if assignee_id:
        assignee = Employee.query.get(assignee_id)
        
        if not assignee:
            return error_response("Assignee not found", 404)
        
        # Check if assignee is a member of the project
        is_member = ProjectMember.query.filter_by(project_id=project_id, employee_id=assignee_id).first() is not None
        is_creator = project.created_by == assignee_id
        
        if not is_member and not is_creator:
            return error_response("Assignee is not a member of this project", 400)
    
    # Process status if provided
    status = data.get('status', 'TODO')
    try:
        status_enum = TaskStatus[status.upper()]
    except KeyError:
        return error_response(f"Invalid status: {status}", 400)
    
    # Process priority if provided
    priority = data.get('priority', 'MEDIUM')
    try:
        priority_enum = TaskPriority[priority.upper()]
    except KeyError:
        return error_response(f"Invalid priority: {priority}", 400)
    
    # Create task
    task = Task(
        title=data['title'],
        description=data.get('description'),
        project_id=project_id,
        assignee_id=assignee_id,
        created_by=employee.id,
        status=status_enum,
        priority=priority_enum,
        progress=data.get('progress', 0),
        estimated_hours=data.get('estimated_hours'),
        due_date=data.get('due_date')
    )
    
    db.session.add(task)
    db.session.commit()
    
    return success_response(
        TaskSchema().dump(task),
        201
    )

# Update task
@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    """
    Update task details
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: TaskUpdate
          properties:
            title:
              type: string
            description:
              type: string
            assignee_id:
              type: integer
            status:
              type: string
              enum: [backlog, todo, in_progress, review, completed]
            priority:
              type: string
              enum: [low, medium, high, urgent]
            progress:
              type: integer
              minimum: 0
              maximum: 100
            estimated_hours:
              type: number
            due_date:
              type: string
              format: date
    responses:
      200:
        description: Task updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to update this task
      404:
        description: Task or assignee not found
    """
    task = Task.query.get(task_id)
    
    if not task:
        return error_response("Task not found", 404)
    
    schema = TaskUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return error_response(err.messages, 400)
    
    # Check if user has permission to update this task
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can update any task
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Project managers can update any task in their projects
    elif ProjectMember.query.filter_by(
            project_id=task.project_id, 
            employee_id=employee.id,
            role='project manager'
        ).first() is not None:
        pass
    # Project creator can update any task in their projects
    elif Project.query.get(task.project_id).created_by == employee.id:
        pass
    # Task creator can update their own tasks
    elif task.created_by == employee.id:
        pass
    # Assignee can update certain fields of their tasks
    elif task.assignee_id == employee.id:
        # Assignee can only update status, progress, and estimated_hours
        allowed_fields = ['status', 'progress', 'estimated_hours']
        for field in list(data.keys()):
            if field not in allowed_fields:
                data.pop(field)
    else:
        return error_response("You don't have permission to update this task", 403)
    
    # Check if assignee exists and is a member of the project
    assignee_id = data.get('assignee_id')
    if assignee_id and assignee_id != task.assignee_id:
        assignee = Employee.query.get(assignee_id)
        
        if not assignee:
            return error_response("Assignee not found", 404)
        
        # Check if assignee is a member of the project
        is_member = ProjectMember.query.filter_by(project_id=task.project_id, employee_id=assignee_id).first() is not None
        is_creator = Project.query.get(task.project_id).created_by == assignee_id
        
        if not is_member and not is_creator:
            return error_response("Assignee is not a member of this project", 400)
    
    # Process status if provided
    if 'status' in data:
        try:
            data['status'] = TaskStatus[data['status'].upper()]
            
            # If marking as completed, set completion date
            if data['status'] == TaskStatus.COMPLETED and task.status != TaskStatus.COMPLETED:
                data['completed_at'] = datetime.utcnow()
                data['progress'] = 100
            # If moving from completed to another status, clear completion date
            elif task.status == TaskStatus.COMPLETED and data['status'] != TaskStatus.COMPLETED:
                data['completed_at'] = None
        except KeyError:
            return error_response(f"Invalid status: {data['status']}", 400)
    
    # Process priority if provided
    if 'priority' in data:
        try:
            data['priority'] = TaskPriority[data['priority'].upper()]
        except KeyError:
            return error_response(f"Invalid priority: {data['priority']}", 400)
    
    # Update task fields
    for key, value in data.items():
        setattr(task, key, value)
    
    db.session.commit()
    
    return success_response(TaskSchema().dump(task))

# Delete task
@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """
    Delete task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Task deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to delete this task
      404:
        description: Task not found
    """
    task = Task.query.get(task_id)
    
    if not task:
        return error_response("Task not found", 404)
    
    # Check if user has permission to delete this task
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can delete any task
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Project managers can delete any task in their projects
    elif ProjectMember.query.filter_by(
            project_id=task.project_id, 
            employee_id=employee.id,
            role='project manager'
        ).first() is not None:
        pass
    # Project creator can delete any task in their projects
    elif Project.query.get(task.project_id).created_by == employee.id:
        pass
    # Task creator can delete their own tasks
    elif task.created_by == employee.id:
        pass
    else:
        return error_response("You don't have permission to delete this task", 403)
    
    db.session.delete(task)
    db.session.commit()
    
    return success_response({
        "message": "Task deleted successfully"
    })

# Get task comments
@tasks_bp.route('/<int:task_id>/comments', methods=['GET'])
@jwt_required()
def get_task_comments(task_id):
    """
    Get comments for a task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: List of comments
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to access this task
      404:
        description: Task not found
    """
    task = Task.query.get(task_id)
    
    if not task:
        return error_response("Task not found", 404)
    
    # Check if user has access to this task
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Admin and HR can access any task
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Check if employee is a member of the project, task creator, or assignee
    elif not ProjectMember.query.filter_by(project_id=task.project_id, employee_id=employee.id).first() \
        and task.created_by != employee.id \
        and task.assignee_id != employee.id:
        # Also check if they're the project creator
        project = Project.query.get(task.project_id)
        if not project or project.created_by != employee.id:
            return error_response("You don't have access to this task", 403)
    
    # Get comments ordered by creation date
    comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_at).all()
    
    return success_response(TaskCommentSchema(many=True).dump(comments))

# Add comment to task
@tasks_bp.route('/<int:task_id>/comments', methods=['POST'])
@jwt_required()
def add_task_comment(task_id):
    """
    Add comment to task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: TaskCommentCreate
          required:
            - comment
          properties:
            comment:
              type: string
    responses:
      201:
        description: Comment added successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to comment on this task
      404:
        description: Task not found
    """
    task = Task.query.get(task_id)
    
    if not task:
        return error_response("Task not found", 404)
    
    # Check if user has access to this task
    current_user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Check if user can comment on this task (same access rules as viewing)
    current_user = User.query.get(current_user_id)
    
    # Admin and HR can comment on any task
    if current_user.role in [Role.ADMIN, Role.HR]:
        pass
    # Check if employee is a member of the project, task creator, or assignee
    elif not ProjectMember.query.filter_by(project_id=task.project_id, employee_id=employee.id).first() \
        and task.created_by != employee.id \
        and task.assignee_id != employee.id:
        # Also check if they're the project creator
        project = Project.query.get(task.project_id)
        if not project or project.created_by != employee.id:
            return error_response("You don't have permission to comment on this task", 403)
    
    # Validate request data
    try:
        data = request.json
        if not data or 'comment' not in data or not data['comment'].strip():
            return error_response("Comment text is required", 400)
        
        comment_text = data['comment'].strip()
    except Exception:
        return error_response("Invalid request data", 400)
    
    # Create comment
    comment = TaskComment(
        task_id=task_id,
        employee_id=employee.id,
        comment=comment_text
    )
    
    db.session.add(comment)
    db.session.commit()
    
    return success_response(
        TaskCommentSchema().dump(comment),
        201
    )

# Update task comment
@tasks_bp.route('/<int:task_id>/comments/<int:comment_id>', methods=['PUT'])
@jwt_required()
def update_task_comment(task_id, comment_id):
    """
    Update task comment
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
      - name: comment_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          id: TaskCommentUpdate
          required:
            - comment
          properties:
            comment:
              type: string
    responses:
      200:
        description: Comment updated successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to update this comment
      404:
        description: Task or comment not found
    """
    comment = TaskComment.query.get(comment_id)
    
    if not comment or comment.task_id != task_id:
        return error_response("Comment not found", 404)
    
    # Check if user owns this comment
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Only comment owner, admin or HR can update the comment
    if comment.employee_id != employee.id and current_user.role not in [Role.ADMIN, Role.HR]:
        return error_response("You don't have permission to update this comment", 403)
    
    # Validate request data
    try:
        data = request.json
        if not data or 'comment' not in data or not data['comment'].strip():
            return error_response("Comment text is required", 400)
        
        comment_text = data['comment'].strip()
    except Exception:
        return error_response("Invalid request data", 400)
    
    # Update comment
    comment.comment = comment_text
    comment.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return success_response(TaskCommentSchema().dump(comment))

# Delete task comment
@tasks_bp.route('/<int:task_id>/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_task_comment(task_id, comment_id):
    """
    Delete task comment
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
      - name: comment_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Comment deleted successfully
      401:
        description: Unauthorized
      403:
        description: Forbidden - not authorized to delete this comment
      404:
        description: Task or comment not found
    """
    comment = TaskComment.query.get(comment_id)
    
    if not comment or comment.task_id != task_id:
        return error_response("Comment not found", 404)
    
    # Check if user owns this comment
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    employee = Employee.query.filter_by(user_id=current_user_id).first()
    
    if not employee:
        return error_response("Employee profile not found", 404)
    
    # Only comment owner, admin or HR can delete the comment
    if comment.employee_id != employee.id and current_user.role not in [Role.ADMIN, Role.HR]:
        return error_response("You don't have permission to delete this comment", 403)
    
    db.session.delete(comment)
    db.session.commit()
    
    return success_response({
        "message": "Comment deleted successfully"
    })
