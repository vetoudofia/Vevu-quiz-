@admin_bp.route('/alerts/low-balance', methods=['GET'])
@admin_required
def get_low_balance_alerts():
    """Get low balance alerts (withdrawals needing attention)"""
    
    # Get pending withdrawals that have processing_days = 3 (indicates low balance)
    pending_withdrawals = Transaction.query.filter_by(
        type='withdraw',
        status='pending'
    ).all()
    
    alerts = []
    for tx in pending_withdrawals:
        # Check if this was flagged as low balance (processing_days == 3)
        if tx.transaction_metadata and tx.transaction_metadata.get('processing_days') == 3:
            user = User.query.get(tx.user_id)
            alerts.append({
                'id': tx.id,
                'reference': tx.reference,
                'user_id': tx.user_id,
                'user_name': f"{user.first_name} {user.last_name}".strip() if user else 'Unknown',
                'user_email': user.email if user else 'Unknown',
                'amount': tx.amount,
                'bank_details': {
                    'bank_code': tx.transaction_metadata.get('bank_code'),
                    'account_number': tx.transaction_metadata.get('account_number'),
                    'account_name': tx.transaction_metadata.get('account_name')
                },
                'requested_at': tx.created_at.isoformat(),
                'estimated_completion': tx.transaction_metadata.get('estimated_completion'),
                'processing_days': 3,
                'paystack_balance_at_request': tx.transaction_metadata.get('paystack_balance_at_request')
            })
    
    return jsonify({
        'success': True,
        'alerts': alerts,
        'count': len(alerts)
    }), 200


@admin_bp.route('/alerts/mark-read/<alert_id>', methods=['POST'])
@admin_required
def mark_alert_read(alert_id):
    """Mark an alert as read (if you store them)"""
    # Implement based on your notification system
    return jsonify({'success': True, 'message': 'Alert marked as read'}), 200