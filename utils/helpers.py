from datetime import datetime, date, timedelta
from flask import request
import re

def parse_date(date_string, default=None):
    """Parse a date string in YYYY-MM-DD format"""
    if not date_string:
        return default
    
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError:
        return default

def get_date_range(period, reference_date=None):
    """Get start and end dates for a given period"""
    if reference_date is None:
        reference_date = date.today()
    
    if period == 'day':
        return reference_date, reference_date
    elif period == 'week':
        # Start from Monday of current week
        start_date = reference_date - timedelta(days=reference_date.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date
    elif period == 'month':
        # Start from first day of current month
        start_date = date(reference_date.year, reference_date.month, 1)
        # Go to first day of next month and subtract 1 day
        if reference_date.month == 12:
            end_date = date(reference_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(reference_date.year, reference_date.month + 1, 1) - timedelta(days=1)
        return start_date, end_date
    elif period == 'year':
        # Start from first day of current year
        start_date = date(reference_date.year, 1, 1)
        end_date = date(reference_date.year, 12, 31)
        return start_date, end_date
    else:
        # Default to current date
        return reference_date, reference_date

def extract_search_params(request_args, default_fields=None):
    """Extract search parameters from request arguments"""
    search = request_args.get('search', '')
    search_fields = request_args.get('search_fields', None)
    
    if search_fields:
        search_fields = search_fields.split(',')
    elif default_fields:
        search_fields = default_fields
    else:
        search_fields = []
    
    return search, search_fields

def format_phone_number(phone_number):
    """Format a phone number for consistent storage"""
    if not phone_number:
        return None
    
    # Remove all non-numeric characters
    digits = re.sub(r'\D', '', phone_number)
    
    # Ensure it has at least 10 digits
    if len(digits) < 10:
        return None
    
    # Format as (XXX) XXX-XXXX for US numbers or keep as is for international
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
    return digits

def calculate_hours_difference(start_time, end_time):
    """Calculate hours between two datetime objects"""
    if not start_time or not end_time:
        return 0
    
    time_diff = end_time - start_time
    hours = time_diff.total_seconds() / 3600
    return round(hours, 2)

def calculate_business_days(start_date, end_date):
    """Calculate number of business days between two dates (inclusive)"""
    if not start_date or not end_date:
        return 0
    
    # Ensure start_date <= end_date
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    # Calculate all days between the dates
    days = (end_date - start_date).days + 1
    
    # Count business days (exclude weekends)
    business_days = sum(1 for i in range(days) 
                      if (start_date + timedelta(days=i)).weekday() < 5)
    
    return business_days
