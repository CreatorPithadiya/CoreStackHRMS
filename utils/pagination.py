from flask import request

def paginate(query, page=None, per_page=None, default_page=1, default_per_page=20, max_per_page=100):
    """
    Paginate a SQLAlchemy query
    
    Args:
        query: SQLAlchemy query to paginate
        page: Page number (1-indexed)
        per_page: Items per page
        default_page: Default page if none provided
        default_per_page: Default items per page if none provided
        max_per_page: Maximum items per page allowed
        
    Returns:
        Pagination object with the following properties:
        - items: List of items for the current page
        - page: Current page number
        - per_page: Items per page
        - total: Total number of items
        - pages: Total number of pages
    """
    # Get pagination parameters from request if not provided
    if page is None:
        page = request.args.get('page', default_page, type=int)
    if per_page is None:
        per_page = request.args.get('per_page', default_per_page, type=int)
    
    # Validate pagination parameters
    page = max(1, page)  # Ensure page is at least 1
    per_page = min(max(1, per_page), max_per_page)  # Ensure per_page is between 1 and max_per_page
    
    # Get total count (without pagination)
    total = query.count()
    
    # Calculate total pages
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    # Get items for current page
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    
    # Create simple pagination object
    class Pagination:
        def __init__(self, items, page, per_page, total, pages):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = pages
            self.has_next = page < pages
            self.has_prev = page > 1
    
    return Pagination(items, page, per_page, total, pages)
