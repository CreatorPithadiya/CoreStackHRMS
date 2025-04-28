from flask import Blueprint, request, jsonify, current_app, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc
import os
import stripe
import json
from datetime import datetime

from app import db
from models import User, Employee, Role
from utils.responses import success_response, error_response
from utils.decorators import role_required

payment_bp = Blueprint('payment', __name__)

# Webhook secret can be set in .env or config file
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')

# Initialize Stripe with the secret key
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    # In production, this should log a warning but continue running
    pass

# Get domain for redirects (in production this should be fetched dynamically)
YOUR_DOMAIN = os.environ.get('REPLIT_DEV_DOMAIN') if os.environ.get('REPLIT_DEPLOYMENT') else os.environ.get('REPLIT_DOMAINS', '').split(',')[0]

@payment_bp.route('/subscription-plans', methods=['GET'])
def get_subscription_plans():
    """Get available subscription plans"""
    if not STRIPE_SECRET_KEY:
        return error_response("Stripe not configured", "Stripe API key is not set", 500)
    
    try:
        plans = stripe.Product.list(active=True, limit=10)
        
        # Get prices for each product
        result = []
        for product in plans.data:
            prices = stripe.Price.list(product=product.id, active=True)
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'image': product.images[0] if product.images else None,
                'prices': []
            }
            
            for price in prices.data:
                price_data = {
                    'id': price.id,
                    'currency': price.currency,
                    'unit_amount': price.unit_amount,
                    'recurring': price.recurring.to_dict() if price.recurring else None
                }
                product_data['prices'].append(price_data)
            
            result.append(product_data)
        
        return success_response("Subscription plans retrieved successfully", result)
    except stripe.error.StripeError as e:
        return error_response("Stripe error", str(e), 500)

@payment_bp.route('/create-checkout-session', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN])
def create_checkout_session():
    """Create a Stripe checkout session"""
    if not STRIPE_SECRET_KEY:
        return error_response("Stripe not configured", "Stripe API key is not set", 500)
    
    try:
        data = request.json
        
        if 'price_id' not in data:
            return error_response("Missing price ID", "price_id is required", 400)
        
        success_url = data.get('success_url', f"https://{YOUR_DOMAIN}/payment/success")
        cancel_url = data.get('cancel_url', f"https://{YOUR_DOMAIN}/payment/cancel")
        
        # Create the checkout session
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': data['price_id'],
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            automatic_tax={'enabled': True},
        )
        
        return success_response(
            "Checkout session created",
            {'checkout_url': checkout_session.url, 'session_id': checkout_session.id}
        )
    
    except stripe.error.StripeError as e:
        return error_response("Stripe error", str(e), 500)

@payment_bp.route('/portal-session', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN])
def create_portal_session():
    """Create a Stripe customer portal session"""
    if not STRIPE_SECRET_KEY:
        return error_response("Stripe not configured", "Stripe API key is not set", 500)
    
    try:
        data = request.json
        
        if 'customer_id' not in data:
            return error_response("Missing customer ID", "customer_id is required", 400)
        
        return_url = data.get('return_url', f"https://{YOUR_DOMAIN}/account")
        
        # Create the portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=data['customer_id'],
            return_url=return_url,
        )
        
        return success_response(
            "Portal session created",
            {'portal_url': portal_session.url}
        )
    
    except stripe.error.StripeError as e:
        return error_response("Stripe error", str(e), 500)

@payment_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhooks"""
    if not STRIPE_SECRET_KEY:
        return error_response("Stripe not configured", "Stripe API key is not set", 500)
    
    payload = request.data.decode('utf-8')
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        if not STRIPE_WEBHOOK_SECRET:
            # If webhook secret is not configured, just log the event type
            data = json.loads(payload)
            event = stripe.Event.construct_from(data, stripe.api_key)
        else:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        
        # Handle specific events
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Process the successful checkout
            # In a real app, you'd update a subscription record, grant access, etc.
            print(f"Checkout completed: {session.id}")
            
        elif event['type'] == 'invoice.paid':
            invoice = event['data']['object']
            
            # Process the successful payment
            # Update subscription status, billing records, etc.
            print(f"Invoice paid: {invoice.id}")
            
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            
            # Handle failed payment
            # Notify user, update subscription status, etc.
            print(f"Payment failed: {invoice.id}")
        
        # Return a 200 success response to acknowledge receipt of the event
        return jsonify(success=True)
    
    except ValueError as e:
        # Invalid payload
        return error_response("Invalid payload", str(e), 400)
    
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return error_response("Invalid signature", str(e), 400)
    
    except Exception as e:
        return error_response("Webhook error", str(e), 500)

@payment_bp.route('/subscription', methods=['GET'])
@jwt_required()
@role_required([Role.ADMIN])
def get_subscription():
    """Get current subscription status"""
    if not STRIPE_SECRET_KEY:
        return error_response("Stripe not configured", "Stripe API key is not set", 500)
    
    try:
        # In a real app, you'd fetch customer_id from user record
        customer_id = request.args.get('customer_id')
        
        if not customer_id:
            return error_response("Customer ID required", "customer_id query parameter is required", 400)
        
        # Get subscriptions for the customer
        subscriptions = stripe.Subscription.list(customer=customer_id, limit=10)
        
        result = []
        for subscription in subscriptions.data:
            # Get product details for each subscription
            product_ids = [item.price.product for item in subscription.items.data]
            products = {p.id: p for p in stripe.Product.list(ids=product_ids).data}
            
            items = []
            for item in subscription.items.data:
                product = products.get(item.price.product)
                items.append({
                    'id': item.id,
                    'product_name': product.name if product else "Unknown product",
                    'product_description': product.description if product else "",
                    'price_id': item.price.id,
                    'unit_amount': item.price.unit_amount,
                    'currency': item.price.currency,
                    'quantity': item.quantity
                })
            
            subscription_data = {
                'id': subscription.id,
                'status': subscription.status,
                'current_period_start': datetime.fromtimestamp(subscription.current_period_start).isoformat(),
                'current_period_end': datetime.fromtimestamp(subscription.current_period_end).isoformat(),
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'items': items
            }
            
            result.append(subscription_data)
        
        return success_response("Subscription data retrieved successfully", result)
    
    except stripe.error.StripeError as e:
        return error_response("Stripe error", str(e), 500)

@payment_bp.route('/usage-tracking', methods=['POST'])
@jwt_required()
@role_required([Role.ADMIN])
def track_usage():
    """Track metered usage for usage-based billing"""
    if not STRIPE_SECRET_KEY:
        return error_response("Stripe not configured", "Stripe API key is not set", 500)
    
    try:
        data = request.json
        
        if not all(k in data for k in ['subscription_item_id', 'quantity']):
            return error_response("Missing required fields", "subscription_item_id and quantity are required", 400)
        
        # Report usage to Stripe
        usage_record = stripe.SubscriptionItem.create_usage_record(
            data['subscription_item_id'],
            quantity=data['quantity'],
            timestamp=data.get('timestamp', 'now'),
            action=data.get('action', 'increment')
        )
        
        return success_response("Usage tracked successfully", {'usage_record_id': usage_record.id})
    
    except stripe.error.StripeError as e:
        return error_response("Stripe error", str(e), 500)