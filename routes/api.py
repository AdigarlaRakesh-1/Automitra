from flask import Blueprint, request, jsonify
from models import Customer, Vehicle, SparePart

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/check_duplicate_customer')
def check_duplicate_customer():
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)

    if not phone and not email:
        return jsonify({'duplicate': False})

    duplicate = Customer.check_duplicate(phone=phone, email=email, exclude_id=exclude_id)
    if duplicate:
        return jsonify({
            'duplicate': True,
            'id': duplicate.id,
            'name': duplicate.name,
            'phone': duplicate.phone,
            'email': duplicate.email
        })
    return jsonify({'duplicate': False})

@api_bp.route('/customer_vehicles/<int:customer_id>')
def customer_vehicles(customer_id):
    vehicles = Vehicle.query.filter_by(customer_id=customer_id).all()
    data = [
        {
            'id': v.id,
            'license_plate': v.license_plate,
            'make': v.make,
            'model': v.model,
            'year': v.year,
            'display': f"{v.year} {v.make} {v.model} ({v.license_plate})"
        }
        for v in vehicles
    ]
    return jsonify(data)

@api_bp.route('/part_info/<int:part_id>')
def part_info(part_id):
    part = SparePart.query.get_or_404(part_id)
    return jsonify({
        'id': part.id,
        'part_number': part.part_number,
        'name': part.name,
        'selling_price': float(part.selling_price),
        'stock_quantity': part.stock_quantity,
        'is_low_stock': part.is_low_stock
    })
