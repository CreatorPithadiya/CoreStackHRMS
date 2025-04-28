import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from flasgger import Swagger
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create base model class
class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
ma = Marshmallow()
jwt = JWTManager()
migrate = Migrate()

def create_app():
    # Create and configure the app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object('config.Config')
    
    # Initialize extensions with app
    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    
    # Enable CORS
    CORS(app)
    
    # Configure Swagger
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs/"
    }
    
    swagger = Swagger(app, config=swagger_config, template={
        "swagger": "2.0",
        "info": {
            "title": "CoreStack API",
            "description": "CoreStack HRMS + PMS Unified Platform API",
            "version": "1.0.0",
            "contact": {
                "email": "admin@corestack.com"
            }
        },
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
            }
        },
        "security": [
            {
                "Bearer": []
            }
        ]
    })
    
    # Import models to ensure they're registered with SQLAlchemy
    from models import (
        User, Employee, Department, Attendance, LeaveRequest, Project, Task, TaskComment,
        Payroll, Salary, OKR, KeyResult, ClientAccess,
        MoodTracker, PerformanceFeedback, TaskReward, EmployeeReward, WorkloadEntry,
        LearningCategory, LearningCourse, EmployeeCourse, HRQuery, ShadowLogin,
        RAGUpdate, BehavioralMetric, ComplianceReport
    )
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.employees import employees_bp
    from routes.attendance import attendance_bp
    from routes.leave import leave_bp
    from routes.projects import projects_bp
    from routes.tasks import tasks_bp
    from routes.dashboard import dashboard_bp
    
    # Phase 2 feature routes
    from routes.payroll import payroll_bp
    from routes.okr import okr_bp
    from routes.client import client_bp
    from routes.reports import reports_bp
    from routes.payment import payment_bp
    
    # Advanced feature routes
    from routes.advanced import advanced_bp
    
    # Register core blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(employees_bp, url_prefix='/api/employees')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(leave_bp, url_prefix='/api/leave')
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    
    # Register Phase 2 feature blueprints
    app.register_blueprint(payroll_bp, url_prefix='/api/payroll')
    app.register_blueprint(okr_bp, url_prefix='/api/okr')
    app.register_blueprint(client_bp, url_prefix='/api/client')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(payment_bp, url_prefix='/api/payment')
    
    # Register Advanced feature blueprints
    app.register_blueprint(advanced_bp, url_prefix='/api/advanced')
    
    # Create error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return {"error": "Bad request", "message": str(e)}, 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        return {"error": "Unauthorized", "message": str(e)}, 401
    
    @app.errorhandler(403)
    def forbidden(e):
        return {"error": "Forbidden", "message": str(e)}, 403
        
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found", "message": str(e)}, 404
    
    @app.errorhandler(500)
    def server_error(e):
        return {"error": "Internal server error", "message": str(e)}, 500
    
    # Create database tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")
    
    return app

app = create_app()
