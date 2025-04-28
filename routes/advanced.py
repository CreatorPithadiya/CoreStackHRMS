from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc, func
from datetime import datetime, date, timedelta
import json

from app import db
from models import (
    User, Employee, Role, Department, Task, 
    MoodTracker, MoodType, 
    PerformanceFeedback, FeedbackType,
    TaskReward, EmployeeReward, RewardType,
    WorkloadEntry,
    LearningCategory, LearningCourse, EmployeeCourse, LearningCourseStatus,
    HRQuery,
    ShadowLogin,
    RAGUpdate, RAGStatus,
    BehavioralMetric,
    ComplianceReport, ComplianceReportType
)
from schemas.advanced import (
    MoodTrackerSchema, MoodTrackerCreateSchema, MoodTrackerUpdateSchema,
    PerformanceFeedbackSchema, PerformanceFeedbackCreateSchema, PerformanceFeedbackUpdateSchema, AIFeedbackGenerateSchema,
    TaskRewardSchema, TaskRewardCreateSchema, EmployeeRewardSchema, EmployeeRewardCreateSchema, EmployeeRewardUpdateSchema,
    WorkloadEntrySchema, WorkloadEntryCreateSchema, WorkloadEntryUpdateSchema,
    LearningCategorySchema, LearningCategoryCreateSchema, LearningCourseSchema, LearningCourseCreateSchema, LearningCourseUpdateSchema,
    EmployeeCourseSchema, EmployeeCourseCreateSchema, EmployeeCourseUpdateSchema,
    HRQuerySchema, HRQueryCreateSchema, HRQueryResponseSchema,
    ShadowLoginSchema, ShadowLoginCreateSchema, ShadowLoginUpdateSchema,
    RAGUpdateSchema, RAGUpdateCreateSchema,
    BehavioralMetricSchema, BehavioralMetricCreateSchema,
    ComplianceReportSchema, ComplianceReportCreateSchema
)
from utils.responses import success_response, error_response
from utils.decorators import role_required

advanced_bp = Blueprint('advanced', __name__)

# =========== MOOD TRACKER ENDPOINTS =============

@advanced_bp.route('/mood-tracker', methods=['GET'])
@jwt_required()
def get_mood_records():
    """Get mood records based on user role and filters"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    mood = request.args.get('mood')
    
    query = MoodTracker.query
    
    # Filter based on role
    if user.role not in [Role.ADMIN, Role.HR]:
        # Managers can see their team members' moods
        if user.role == Role.MANAGER:
            team_members = [member.id for member in employee.team_members]
            if employee_id and employee_id not in team_members and employee_id != employee.id:
                return error_response("Access denied", "You can only view your own or your team members' mood records", 403)
            
            if employee_id:
                query = query.filter_by(employee_id=employee_id)
            else:
                query = query.filter(MoodTracker.employee_id.in_([employee.id] + team_members))
        else:
            # Regular employees can only see their own moods
            query = query.filter_by(employee_id=employee.id)
    elif employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    # Apply date filters
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(MoodTracker.date >= start)
        except ValueError:
            return error_response("Invalid date format", "Use YYYY-MM-DD format for start_date", 400)
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(MoodTracker.date <= end)
        except ValueError:
            return error_response("Invalid date format", "Use YYYY-MM-DD format for end_date", 400)
    
    # Filter by mood
    if mood:
        try:
            mood_enum = MoodType(mood)
            query = query.filter_by(mood=mood_enum)
        except ValueError:
            valid_moods = [m.value for m in MoodType]
            return error_response("Invalid mood", f"Mood must be one of: {', '.join(valid_moods)}", 400)
    
    records = query.order_by(desc(MoodTracker.date)).paginate(page=page, per_page=per_page)
    
    schema = MoodTrackerSchema(many=True)
    return success_response(
        "Mood records retrieved successfully",
        schema.dump(records.items),
        meta={"total": records.total, "page": page, "per_page": per_page}
    )

@advanced_bp.route('/mood-tracker', methods=['POST'])
@jwt_required()
def create_mood_record():
    """Create a new mood record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    schema = MoodTrackerCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check if the employee_id is the current user or a team member (for managers)
    if data['employee_id'] != employee.id and user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER:
            team_members = [member.id for member in employee.team_members]
            if data['employee_id'] not in team_members:
                return error_response("Access denied", "You can only create mood records for yourself or your team members", 403)
        else:
            return error_response("Access denied", "You can only create mood records for yourself", 403)
    
    # Check if employee exists
    target_employee = Employee.query.get(data['employee_id'])
    if not target_employee:
        return error_response("Employee not found", "", 404)
    
    # Check if a record already exists for this employee on this date
    record_date = data.get('date', date.today())
    existing = MoodTracker.query.filter_by(
        employee_id=data['employee_id'],
        date=record_date
    ).first()
    
    if existing:
        return error_response(
            "Record already exists", 
            f"A mood record already exists for this employee on {record_date}", 
            400
        )
    
    # Create new mood record
    new_record = MoodTracker(
        employee_id=data['employee_id'],
        mood=data['mood'],
        note=data.get('note', ''),
        date=record_date
    )
    
    db.session.add(new_record)
    db.session.commit()
    
    result_schema = MoodTrackerSchema()
    return success_response("Mood record created successfully", result_schema.dump(new_record), 201)

@advanced_bp.route('/mood-tracker/<int:record_id>', methods=['PUT'])
@jwt_required()
def update_mood_record(record_id):
    """Update a mood record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    record = MoodTracker.query.get_or_404(record_id)
    
    # Check permissions
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER:
            team_members = [member.id for member in employee.team_members]
            if record.employee_id != employee.id and record.employee_id not in team_members:
                return error_response("Access denied", "You can only update your own or your team members' mood records", 403)
        elif record.employee_id != employee.id:
            return error_response("Access denied", "You can only update your own mood records", 403)
    
    schema = MoodTrackerUpdateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update fields
    for key, value in data.items():
        setattr(record, key, value)
    
    db.session.commit()
    
    result_schema = MoodTrackerSchema()
    return success_response("Mood record updated successfully", result_schema.dump(record))

@advanced_bp.route('/mood-tracker/sentiment-dashboard', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def get_mood_dashboard():
    """Get aggregated mood data for dashboard visualization"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    days = request.args.get('days', 30, type=int)
    department_id = request.args.get('department_id', type=int)
    
    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Base query
    query = db.session.query(
        MoodTracker.date,
        MoodTracker.mood,
        func.count(MoodTracker.id).label('count')
    ).filter(MoodTracker.date.between(start_date, end_date))
    
    # Filter based on role and department
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER and employee:
            team_members = [member.id for member in employee.team_members]
            query = query.filter(MoodTracker.employee_id.in_([employee.id] + team_members))
    elif department_id:
        # Get all employees in the department
        dept_employees = Employee.query.filter_by(department_id=department_id).all()
        dept_employee_ids = [e.id for e in dept_employees]
        query = query.filter(MoodTracker.employee_id.in_(dept_employee_ids))
    
    # Group by date and mood
    mood_data = query.group_by(MoodTracker.date, MoodTracker.mood).all()
    
    # Format results for dashboard
    result = {
        'date_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
        },
        'mood_counts': {},
        'trend_data': [],
        'summary': {}
    }
    
    # Initialize counts for all mood types
    for mood_type in MoodType:
        result['mood_counts'][mood_type.value] = 0
    
    # Process mood data
    date_mood_counts = {}
    for record in mood_data:
        # Add to total counts
        mood_value = record.mood.value
        result['mood_counts'][mood_value] = result['mood_counts'].get(mood_value, 0) + record.count
        
        # Add to trend data by date
        date_str = record.date.isoformat()
        if date_str not in date_mood_counts:
            date_mood_counts[date_str] = {mood_type.value: 0 for mood_type in MoodType}
        
        date_mood_counts[date_str][mood_value] = record.count
    
    # Convert date_mood_counts to a list for trend visualization
    for date_str, counts in sorted(date_mood_counts.items()):
        result['trend_data'].append({
            'date': date_str,
            **counts
        })
    
    # Calculate summary statistics
    total_records = sum(result['mood_counts'].values())
    if total_records > 0:
        positive_count = result['mood_counts'].get('very_happy', 0) + result['mood_counts'].get('happy', 0)
        negative_count = result['mood_counts'].get('unhappy', 0) + result['mood_counts'].get('very_unhappy', 0)
        neutral_count = result['mood_counts'].get('neutral', 0)
        
        result['summary'] = {
            'total_records': total_records,
            'positive_percentage': round((positive_count / total_records) * 100, 2),
            'neutral_percentage': round((neutral_count / total_records) * 100, 2),
            'negative_percentage': round((negative_count / total_records) * 100, 2),
            'most_common_mood': max(result['mood_counts'], key=result['mood_counts'].get)
        }
    
    return success_response("Mood dashboard data retrieved successfully", result)

# =========== AI PERFORMANCE FEEDBACK ENDPOINTS =============

@advanced_bp.route('/performance-feedback', methods=['GET'])
@jwt_required()
def get_performance_feedback():
    """Get performance feedback records based on user role and filters"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    feedback_type = request.args.get('feedback_type')
    is_draft = request.args.get('is_draft', type=bool)
    
    query = PerformanceFeedback.query
    
    # Filter based on role
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER and employee:
            team_members = [member.id for member in employee.team_members]
            if employee_id and employee_id not in team_members and employee_id != employee.id:
                return error_response("Access denied", "You can only view your own or your team members' feedback", 403)
            
            if employee_id:
                query = query.filter_by(employee_id=employee_id)
            else:
                # Managers can see feedback for themselves and their team members
                query = query.filter(
                    (PerformanceFeedback.employee_id.in_([employee.id] + team_members)) |
                    (PerformanceFeedback.reviewer_id == employee.id)
                )
        else:
            # Regular employees can only see their own feedback and feedback they've given
            query = query.filter(
                (PerformanceFeedback.employee_id == employee.id) |
                (PerformanceFeedback.reviewer_id == employee.id)
            )
            
            # Regular employees cannot see draft feedback meant for them
            if employee_id != employee.id:
                query = query.filter(PerformanceFeedback.is_draft == False)
    elif employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    # Apply other filters
    if feedback_type:
        try:
            feedback_type_enum = FeedbackType(feedback_type)
            query = query.filter_by(feedback_type=feedback_type_enum)
        except ValueError:
            valid_types = [ft.value for ft in FeedbackType]
            return error_response("Invalid feedback type", f"Type must be one of: {', '.join(valid_types)}", 400)
    
    if is_draft is not None:
        query = query.filter_by(is_draft=is_draft)
    
    feedback_records = query.order_by(desc(PerformanceFeedback.created_at)).paginate(page=page, per_page=per_page)
    
    schema = PerformanceFeedbackSchema(many=True)
    return success_response(
        "Performance feedback records retrieved successfully",
        schema.dump(feedback_records.items),
        meta={"total": feedback_records.total, "page": page, "per_page": per_page}
    )

@advanced_bp.route('/performance-feedback', methods=['POST'])
@jwt_required()
def create_performance_feedback():
    """Create a new performance feedback record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee and user.role != Role.ADMIN:
        return error_response("Employee record not found", "", 404)
    
    schema = PerformanceFeedbackCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check permissions for providing feedback
    if user.role not in [Role.ADMIN, Role.HR]:
        feedback_type = data['feedback_type']
        target_employee_id = data['employee_id']
        
        if feedback_type == FeedbackType.MANAGER.value:
            if user.role != Role.MANAGER:
                return error_response("Access denied", "Only managers can provide manager feedback", 403)
            
            # Check if target is a team member
            team_members = [member.id for member in employee.team_members]
            if target_employee_id not in team_members:
                return error_response("Access denied", "You can only provide manager feedback to your team members", 403)
        
        elif feedback_type == FeedbackType.PEER.value:
            # Anyone can provide peer feedback, but it should not be for themselves
            if target_employee_id == employee.id:
                return error_response("Invalid request", "You cannot provide peer feedback for yourself", 400)
        
        elif feedback_type == FeedbackType.SELF.value:
            # Self feedback must be for the current user
            if target_employee_id != employee.id:
                return error_response("Access denied", "You can only provide self feedback for yourself", 403)
        
        elif feedback_type == FeedbackType.AI_GENERATED.value and user.role not in [Role.ADMIN, Role.HR, Role.MANAGER]:
            return error_response("Access denied", "You don't have permission to create AI-generated feedback", 403)
    
    # Check if target employee exists
    target_employee = Employee.query.get(data['employee_id'])
    if not target_employee:
        return error_response("Target employee not found", "", 404)
    
    # For non-AI feedback, set the reviewer_id to the current employee
    reviewer_id = data.get('reviewer_id')
    if data['feedback_type'] != FeedbackType.AI_GENERATED.value and not reviewer_id:
        reviewer_id = employee.id
    
    # Create new feedback record
    new_feedback = PerformanceFeedback(
        employee_id=data['employee_id'],
        reviewer_id=reviewer_id,
        feedback_type=data['feedback_type'],
        content=data['content'],
        strengths=data.get('strengths', ''),
        areas_of_improvement=data.get('areas_of_improvement', ''),
        rating=data.get('rating'),
        is_draft=data.get('is_draft', True)
    )
    
    db.session.add(new_feedback)
    db.session.commit()
    
    result_schema = PerformanceFeedbackSchema()
    return success_response("Performance feedback created successfully", result_schema.dump(new_feedback), 201)

@advanced_bp.route('/performance-feedback/<int:feedback_id>', methods=['PUT'])
@jwt_required()
def update_performance_feedback(feedback_id):
    """Update a performance feedback record"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    feedback = PerformanceFeedback.query.get_or_404(feedback_id)
    
    # Check permissions
    if user.role not in [Role.ADMIN, Role.HR]:
        # For managers and regular employees, they can only update feedback they've created
        if not employee or (feedback.reviewer_id != employee.id):
            return error_response("Access denied", "You can only update feedback you've created", 403)
    
    schema = PerformanceFeedbackUpdateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update fields
    for key, value in data.items():
        setattr(feedback, key, value)
    
    db.session.commit()
    
    result_schema = PerformanceFeedbackSchema()
    return success_response("Performance feedback updated successfully", result_schema.dump(feedback))

@advanced_bp.route('/performance-feedback/ai-generate', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def generate_ai_feedback():
    """Generate AI-powered performance feedback"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    schema = AIFeedbackGenerateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    target_employee_id = data['employee_id']
    
    # Check permissions for managers
    if user.role == Role.MANAGER:
        team_members = [member.id for member in employee.team_members]
        if target_employee_id != employee.id and target_employee_id not in team_members:
            return error_response("Access denied", "You can only generate feedback for yourself or your team members", 403)
    
    # Check if target employee exists
    target_employee = Employee.query.get(target_employee_id)
    if not target_employee:
        return error_response("Target employee not found", "", 404)
    
    # In a real system, this would integrate with an AI/ML service
    # For demonstration, we'll generate placeholder content based on available data
    
    timeframe = data['timeframe']
    metrics_to_include = data.get('metrics_to_include', [])
    
    # Here, you would:
    # 1. Collect relevant data about the employee (tasks, attendance, etc.)
    # 2. Pass this data to an AI service (like OpenAI API) to generate personalized feedback
    # 3. Create a structured feedback record from the AI response
    
    # For demonstration, create simulated AI feedback
    strengths = []
    improvements = []
    content_paragraphs = []
    rating = 0
    
    # Analyze tasks
    if 'tasks' in metrics_to_include or not metrics_to_include:
        tasks = Task.query.filter_by(assignee_id=target_employee_id).all()
        completed_tasks = [t for t in tasks if t.status == 'completed']
        completion_rate = len(completed_tasks) / len(tasks) if tasks else 0
        
        if completion_rate > 0.8:
            strengths.append("Excellent task completion rate")
            content_paragraphs.append(f"Has completed {completion_rate*100:.1f}% of assigned tasks, demonstrating strong reliability and productivity.")
            rating += 5
        elif completion_rate > 0.6:
            strengths.append("Good task management")
            content_paragraphs.append(f"Maintains a solid task completion rate of {completion_rate*100:.1f}%, showing consistent productivity.")
            rating += 4
        else:
            improvements.append("Task completion needs improvement")
            content_paragraphs.append(f"Current task completion rate is {completion_rate*100:.1f}%. Consider implementing a more structured approach to task management.")
            rating += 2
    
    # Analyze collaboration
    if 'collaboration' in metrics_to_include or not metrics_to_include:
        # For demo, random collaboration assessment
        import random
        collaboration_score = random.randint(1, 10)
        
        if collaboration_score > 7:
            strengths.append("Strong team collaboration")
            content_paragraphs.append("Consistently demonstrates excellent collaboration with team members, contributes positively to group discussions, and helps others when needed.")
            rating += 5
        elif collaboration_score > 4:
            strengths.append("Effective collaboration skills")
            content_paragraphs.append("Works well with others and contributes to team objectives. Could occasionally take more initiative in group settings.")
            rating += 3
        else:
            improvements.append("Collaboration and teamwork")
            content_paragraphs.append("Would benefit from more active participation in team activities and improving communication with colleagues.")
            rating += 1
    
    # Normalize the rating to 1-5 scale
    metrics_count = len(metrics_to_include) if metrics_to_include else 2
    normalized_rating = min(5, max(1, round(rating / metrics_count)))
    
    # Create the AI-generated feedback
    ai_feedback = PerformanceFeedback(
        employee_id=target_employee_id,
        reviewer_id=None,  # No reviewer for AI-generated feedback
        feedback_type=FeedbackType.AI_GENERATED,
        content="\n\n".join(content_paragraphs),
        strengths="\n- ".join([""] + strengths) if strengths else "",
        areas_of_improvement="\n- ".join([""] + improvements) if improvements else "",
        rating=normalized_rating,
        is_draft=True  # AI-generated feedback starts as a draft
    )
    
    db.session.add(ai_feedback)
    db.session.commit()
    
    result_schema = PerformanceFeedbackSchema()
    return success_response("AI feedback generated successfully", result_schema.dump(ai_feedback), 201)

# =========== GAMIFIED TASK SYSTEM ENDPOINTS =============

@advanced_bp.route('/task-rewards', methods=['GET'])
@jwt_required()
def get_task_rewards():
    """Get task rewards based on filters"""
    user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    task_id = request.args.get('task_id', type=int)
    reward_type = request.args.get('reward_type')
    
    query = TaskReward.query
    
    if task_id:
        query = query.filter_by(task_id=task_id)
    
    if reward_type:
        try:
            reward_type_enum = RewardType(reward_type)
            query = query.filter_by(reward_type=reward_type_enum)
        except ValueError:
            valid_types = [rt.value for rt in RewardType]
            return error_response("Invalid reward type", f"Type must be one of: {', '.join(valid_types)}", 400)
    
    rewards = query.order_by(desc(TaskReward.created_at)).paginate(page=page, per_page=per_page)
    
    schema = TaskRewardSchema(many=True)
    return success_response(
        "Task rewards retrieved successfully",
        schema.dump(rewards.items),
        meta={"total": rewards.total, "page": page, "per_page": per_page}
    )

@advanced_bp.route('/task-rewards', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def create_task_reward():
    """Create a new task reward"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    schema = TaskRewardCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check if task exists
    task = Task.query.get(data['task_id'])
    if not task:
        return error_response("Task not found", "", 404)
    
    # For managers, ensure they have permission for this task's project
    if user.role == Role.MANAGER and employee:
        project = task.project
        if project.created_by != employee.id:
            # Check if manager is a member of the project
            is_project_member = any(pm.employee_id == employee.id for pm in project.members)
            if not is_project_member:
                return error_response("Access denied", "You don't have permission to add rewards to this task", 403)
    
    # Create new task reward
    new_reward = TaskReward(
        task_id=data['task_id'],
        reward_type=data['reward_type'],
        points=data.get('points', 0),
        name=data.get('name', ''),
        description=data.get('description', '')
    )
    
    db.session.add(new_reward)
    db.session.commit()
    
    result_schema = TaskRewardSchema()
    return success_response("Task reward created successfully", result_schema.dump(new_reward), 201)

@advanced_bp.route('/employee-rewards', methods=['GET'])
@jwt_required()
def get_employee_rewards():
    """Get employee rewards based on filters"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    claimed = request.args.get('claimed', type=bool)
    
    query = EmployeeReward.query
    
    # Filter based on role
    if user.role not in [Role.ADMIN, Role.HR]:
        if user.role == Role.MANAGER and employee:
            team_members = [member.id for member in employee.team_members]
            if employee_id and employee_id not in team_members and employee_id != employee.id:
                return error_response("Access denied", "You can only view your own or your team members' rewards", 403)
            
            if employee_id:
                query = query.filter_by(employee_id=employee_id)
            else:
                query = query.filter(EmployeeReward.employee_id.in_([employee.id] + team_members))
        elif employee:
            # Regular employees can only see their own rewards
            query = query.filter_by(employee_id=employee.id)
        else:
            return error_response("Employee record not found", "", 404)
    elif employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    if claimed is not None:
        query = query.filter_by(claimed=claimed)
    
    rewards = query.order_by(desc(EmployeeReward.earned_at)).paginate(page=page, per_page=per_page)
    
    schema = EmployeeRewardSchema(many=True)
    return success_response(
        "Employee rewards retrieved successfully",
        schema.dump(rewards.items),
        meta={"total": rewards.total, "page": page, "per_page": per_page}
    )

@advanced_bp.route('/employee-rewards', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def award_employee_reward():
    """Award a task reward to an employee"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    schema = EmployeeRewardCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check if employee exists
    target_employee = Employee.query.get(data['employee_id'])
    if not target_employee:
        return error_response("Employee not found", "", 404)
    
    # Check if reward exists
    reward = TaskReward.query.get(data['task_reward_id'])
    if not reward:
        return error_response("Task reward not found", "", 404)
    
    # For managers, check if they have permission
    if user.role == Role.MANAGER:
        team_members = [member.id for member in employee.team_members]
        if data['employee_id'] not in team_members:
            return error_response("Access denied", "You can only award rewards to your team members", 403)
    
    # Create new employee reward
    new_employee_reward = EmployeeReward(
        employee_id=data['employee_id'],
        task_reward_id=data['task_reward_id'],
        claimed=data.get('claimed', False)
    )
    
    db.session.add(new_employee_reward)
    db.session.commit()
    
    result_schema = EmployeeRewardSchema()
    return success_response("Reward awarded successfully", result_schema.dump(new_employee_reward), 201)

@advanced_bp.route('/employee-rewards/<int:reward_id>/claim', methods=['POST'])
@jwt_required()
def claim_reward(reward_id):
    """Claim an awarded reward"""
    user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    employee_reward = EmployeeReward.query.get_or_404(reward_id)
    
    # Check if this reward belongs to the current employee
    if employee_reward.employee_id != employee.id:
        return error_response("Access denied", "You can only claim your own rewards", 403)
    
    # Check if already claimed
    if employee_reward.claimed:
        return error_response("Already claimed", "This reward has already been claimed", 400)
    
    # Update the reward
    employee_reward.claimed = True
    employee_reward.claimed_at = datetime.utcnow()
    db.session.commit()
    
    result_schema = EmployeeRewardSchema()
    return success_response("Reward claimed successfully", result_schema.dump(employee_reward))

# =========== HR CHATBOT ENDPOINTS =============

@advanced_bp.route('/hr-queries', methods=['GET'])
@jwt_required()
def get_hr_queries():
    """Get HR queries based on user role"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    employee_id = request.args.get('employee_id', type=int)
    
    query = HRQuery.query
    
    # Filter based on role
    if user.role not in [Role.ADMIN, Role.HR]:
        if not employee:
            return error_response("Employee record not found", "", 404)
        
        # Regular employees can only see their own non-private queries or private queries
        query = query.filter_by(employee_id=employee.id)
    elif employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    queries = query.order_by(desc(HRQuery.created_at)).paginate(page=page, per_page=per_page)
    
    schema = HRQuerySchema(many=True)
    return success_response(
        "HR queries retrieved successfully",
        schema.dump(queries.items),
        meta={"total": queries.total, "page": page, "per_page": per_page}
    )

@advanced_bp.route('/hr-queries', methods=['POST'])
@jwt_required()
def create_hr_query():
    """Create a new HR query"""
    user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    schema = HRQueryCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check permissions
    if data['employee_id'] != employee.id:
        return error_response("Access denied", "You can only create queries for yourself", 403)
    
    # Create new HR query
    new_query = HRQuery(
        employee_id=data['employee_id'],
        query=data['query'],
        is_private=data.get('is_private', True)
    )
    
    db.session.add(new_query)
    db.session.commit()
    
    # In a real system, here you would:
    # 1. Pass the query to an AI/NLP service like OpenAI API
    # 2. Get a response and save it to the query object
    # 3. For this demo, we'll simulate a simple response
    
    # Simulate AI response based on keywords in the query
    query_text = data['query'].lower()
    response = None
    
    if 'leave' in query_text or 'vacation' in query_text or 'time off' in query_text:
        response = "According to our policy, regular employees are entitled to 15 days of annual leave, 10 days of sick leave, and 5 personal days per year. Please submit leave requests through the leave management system at least 2 days in advance for approval."
    
    elif 'salary' in query_text or 'pay' in query_text or 'compensation' in query_text:
        response = "Salary reviews are conducted annually in June. Your compensation is determined based on performance reviews, market standards, and company budget. For specific queries about your salary, please schedule a private meeting with HR."
    
    elif 'benefits' in query_text or 'insurance' in query_text or 'healthcare' in query_text:
        response = "Our benefits package includes health insurance, dental coverage, vision care, 401(k) matching up to 5%, and wellness programs. Detailed information can be found in the benefits handbook in the company portal."
    
    elif 'work hours' in query_text or 'schedule' in query_text or 'flexible' in query_text:
        response = "Standard work hours are 9:00 AM to 5:00 PM with a 1-hour lunch break. We offer flexible scheduling with core hours from 10:00 AM to 3:00 PM. Remote work options are available based on department policies and manager approval."
    
    else:
        response = "Thank you for your query. I've recorded it and will have someone from HR follow up with you directly."
    
    # Update the query with the response
    new_query.response = response
    db.session.commit()
    
    result_schema = HRQuerySchema()
    return success_response("HR query created successfully", result_schema.dump(new_query), 201)

@advanced_bp.route('/hr-queries/<int:query_id>/respond', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR])
def respond_to_hr_query(query_id):
    """Respond to an HR query"""
    hr_query = HRQuery.query.get_or_404(query_id)
    
    schema = HRQueryResponseSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Update the response
    hr_query.response = data['response']
    db.session.commit()
    
    result_schema = HRQuerySchema()
    return success_response("Response added successfully", result_schema.dump(hr_query))

# =========== RAG PROJECT PROGRESS ENDPOINTS =============

@advanced_bp.route('/rag-updates', methods=['GET'])
@jwt_required()
def get_rag_updates():
    """Get RAG (Red-Amber-Green) project updates"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    project_id = request.args.get('project_id', type=int)
    status = request.args.get('status')
    
    query = RAGUpdate.query
    
    # Apply project filter
    if project_id:
        query = query.filter_by(project_id=project_id)
    
    # Apply status filter
    if status:
        try:
            status_enum = RAGStatus(status)
            query = query.filter_by(status=status_enum)
        except ValueError:
            valid_statuses = [s.value for s in RAGStatus]
            return error_response("Invalid status", f"Status must be one of: {', '.join(valid_statuses)}", 400)
    
    # Filter projects based on role
    if user.role not in [Role.ADMIN, Role.HR]:
        if not employee:
            return error_response("Employee record not found", "", 404)
        
        if user.role == Role.MANAGER:
            # Managers can see updates for projects they manage or are members of
            managed_projects = Project.query.filter_by(created_by=employee.id).all()
            managed_project_ids = [p.id for p in managed_projects]
            
            # Also get projects the manager is a member of
            member_projects = ProjectMember.query.filter_by(employee_id=employee.id).all()
            member_project_ids = [pm.project_id for pm in member_projects]
            
            all_project_ids = list(set(managed_project_ids + member_project_ids))
            
            if project_id and project_id not in all_project_ids:
                return error_response("Access denied", "You can only view RAG updates for projects you manage or are a member of", 403)
            
            if not project_id:
                query = query.filter(RAGUpdate.project_id.in_(all_project_ids))
        else:
            # Regular employees can only see updates for projects they're members of
            member_projects = ProjectMember.query.filter_by(employee_id=employee.id).all()
            member_project_ids = [pm.project_id for pm in member_projects]
            
            if project_id and project_id not in member_project_ids:
                return error_response("Access denied", "You can only view RAG updates for projects you're a member of", 403)
            
            if not project_id:
                query = query.filter(RAGUpdate.project_id.in_(member_project_ids))
    
    updates = query.order_by(desc(RAGUpdate.update_date), desc(RAGUpdate.created_at)).paginate(page=page, per_page=per_page)
    
    schema = RAGUpdateSchema(many=True)
    return success_response(
        "RAG updates retrieved successfully",
        schema.dump(updates.items),
        meta={"total": updates.total, "page": page, "per_page": per_page}
    )

@advanced_bp.route('/rag-updates', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN, Role.MANAGER])
def create_rag_update():
    """Create a new RAG project update"""
    user_id = get_jwt_identity()
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    if not employee:
        return error_response("Employee record not found", "", 404)
    
    schema = RAGUpdateCreateSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return error_response("Validation error", str(e), 400)
    
    # Check if project exists
    project = Project.query.get(data['project_id'])
    if not project:
        return error_response("Project not found", "", 404)
    
    # Check if user has permission for this project
    user = User.query.get(user_id)
    if user.role == Role.MANAGER:
        # Manager must be the project creator or a member
        if project.created_by != employee.id:
            is_member = ProjectMember.query.filter_by(
                project_id=project.id,
                employee_id=employee.id
            ).first() is not None
            
            if not is_member:
                return error_response("Access denied", "You don't have permission to create updates for this project", 403)
    
    # Create new RAG update
    new_update = RAGUpdate(
        project_id=data['project_id'],
        status=data['status'],
        update_date=data.get('update_date', date.today()),
        description=data['description'],
        action_items=data.get('action_items', ''),
        updated_by=employee.id
    )
    
    db.session.add(new_update)
    db.session.commit()
    
    result_schema = RAGUpdateSchema()
    return success_response("RAG update created successfully", result_schema.dump(new_update), 201)

@advanced_bp.route('/rag-updates/dashboard', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN, Role.HR, Role.MANAGER])
def get_rag_dashboard():
    """Get dashboard data for RAG updates"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    employee = Employee.query.filter_by(user_id=user_id).first()
    
    # Get all projects based on role
    if user.role in [Role.ADMIN, Role.HR]:
        projects = Project.query.all()
    elif user.role == Role.MANAGER and employee:
        # Managers see projects they manage or are members of
        managed_projects = Project.query.filter_by(created_by=employee.id).all()
        
        member_projects_query = Project.query.join(
            ProjectMember, Project.id == ProjectMember.project_id
        ).filter(ProjectMember.employee_id == employee.id)
        
        member_projects = member_projects_query.all()
        
        # Combine lists and remove duplicates
        project_ids = set([p.id for p in managed_projects] + [p.id for p in member_projects])
        projects = Project.query.filter(Project.id.in_(project_ids)).all()
    else:
        return error_response("Access denied", "You don't have permission to view the RAG dashboard", 403)
    
    # Get latest RAG update for each project
    result = {
        'summary': {
            'red': 0,
            'amber': 0,
            'green': 0,
            'total_projects': len(projects),
            'projects_with_updates': 0
        },
        'projects': []
    }
    
    for project in projects:
        latest_update = RAGUpdate.query.filter_by(project_id=project.id).order_by(desc(RAGUpdate.update_date)).first()
        
        if latest_update:
            result['summary']['projects_with_updates'] += 1
            result['summary'][latest_update.status.value] += 1
            
            result['projects'].append({
                'id': project.id,
                'name': project.name,
                'status': project.status.value,
                'rag_status': latest_update.status.value,
                'last_update': latest_update.update_date.isoformat(),
                'description': latest_update.description,
                'action_items': latest_update.action_items,
                'updater': {
                    'id': latest_update.updater.id,
                    'name': latest_update.updater.full_name
                } if latest_update.updater else None
            })
        else:
            # Projects with no RAG updates
            result['projects'].append({
                'id': project.id,
                'name': project.name,
                'status': project.status.value,
                'rag_status': None,
                'last_update': None,
                'description': None,
                'action_items': None,
                'updater': None
            })
    
    # Calculate percentages
    total_with_updates = result['summary']['projects_with_updates']
    if total_with_updates > 0:
        result['summary']['red_percentage'] = round((result['summary']['red'] / total_with_updates) * 100, 2)
        result['summary']['amber_percentage'] = round((result['summary']['amber'] / total_with_updates) * 100, 2)
        result['summary']['green_percentage'] = round((result['summary']['green'] / total_with_updates) * 100, 2)
    
    return success_response("RAG dashboard data retrieved successfully", result)