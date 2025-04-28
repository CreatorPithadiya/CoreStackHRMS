from flask import jsonify

def success_response(data, status_code=200):
    """
    Format a success response
    
    Args:
        data: The data to return
        status_code: HTTP status code
        
    Returns:
        JSON response with data and success flag
    """
    response = {
        "success": True,
        "data": data
    }
    return jsonify(response), status_code

def error_response(message, status_code=400):
    """
    Format an error response
    
    Args:
        message: Error message or dict of field errors
        status_code: HTTP status code
        
    Returns:
        JSON response with error message and success flag
    """
    response = {
        "success": False,
        "error": message
    }
    return jsonify(response), status_code

def paginated_response(items, page, per_page, total, schema, status_code=200):
    """
    Format a paginated response
    
    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total: Total number of items
        schema: Marshmallow schema to serialize items
        status_code: HTTP status code
        
    Returns:
        JSON response with paginated data
    """
    # Calculate total pages
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    # Serialize items using the provided schema
    serialized_items = schema.dump(items, many=True)
    
    response = {
        "success": True,
        "data": {
            "items": serialized_items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
                "has_next": page < pages,
                "has_prev": page > 1
            }
        }
    }
    
    return jsonify(response), status_code

def validation_error_response(errors, status_code=400):
    """
    Format a validation error response
    
    Args:
        errors: Dict of field errors from Marshmallow
        status_code: HTTP status code
        
    Returns:
        JSON response with field errors
    """
    response = {
        "success": False,
        "error": "Validation error",
        "errors": errors
    }
    return jsonify(response), status_code
