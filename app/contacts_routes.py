# vpemaster/contacts_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from . import db
from .models import Contact, SessionLog
from .auth.utils import login_required, is_authorized
from datetime import date

contacts_bp = Blueprint('contacts_bp', __name__)


@contacts_bp.route('/contacts/search')
@login_required
def search_contacts_by_name():
    search_term = request.args.get('q', '')
    if search_term:
        contacts = Contact.query.filter(
            Contact.Name.ilike(f'%{search_term}%')).all()
    else:
        contacts = Contact.query.all()

    contacts_data = [{"id": c.id, "Name": c.Name} for c in contacts]
    return jsonify(contacts_data)


@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    if not is_authorized(session.get('user_role'), 'CONTACT_BOOK_EDIT'):
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())
    return render_template('contacts.html', contacts=contacts, pathways=pathways)


@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    if not is_authorized(session.get('user_role'), 'CONTACT_BOOK_EDIT'):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contact = None
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'GET' and contact:
        contact_data = {
            "Name": contact.Name,
            "Email": contact.Email or None,
            "Type": contact.Type,
            "Club": contact.Club,
            "Completed_Levels": contact.Completed_Levels,
            "DTM": contact.DTM,
            "Phone_Number": contact.Phone_Number,
            "Bio": contact.Bio
        }
        return jsonify(contact=contact_data)

    if request.method == 'POST':
        contact_name = request.form.get('name')
        email = request.form.get('email') or None

        if contact:
            # Logic for updating an existing contact
            contact.Name = contact_name
            contact.Email = email
            contact.Club = request.form.get('club')
            contact.Completed_Levels = request.form.get('completed_levels')
            contact.Type = request.form.get('type')
            contact.DTM = 'dtm' in request.form
            contact.Phone_Number = request.form.get('phone_number')
            contact.Bio = request.form.get('bio')
            db.session.commit()
        else:
            # Logic for creating a new contact
            existing_contact = Contact.query.filter_by(
                Name=contact_name).first()
            if existing_contact:
                message = f"A contact with the name '{contact_name}' already exists."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(success=False, message=message)
                else:
                    flash(message, 'error')
                    return redirect(url_for('contacts_bp.show_contacts'))

            if email:
                existing_email = Contact.query.filter_by(Email=email).first()
                if existing_email:
                    message = f"A contact with the email '{email}' already exists."
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify(success=False, message=message)
                    else:
                        flash(message, 'error')
                        return redirect(url_for('contacts_bp.show_contacts'))

            new_contact = Contact(
                Name=contact_name,
                Email=email,
                Club=request.form.get('club'),
                Date_Created=date.today(),
                Completed_Levels=request.form.get('completed_levels'),
                Type=request.form.get('type'),
                DTM='dtm' in request.form,
                Phone_Number=request.form.get('phone_number'),
                Bio=request.form.get('bio')
            )
            db.session.add(new_contact)
            db.session.commit()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=True, contact={'id': new_contact.id, 'Name': new_contact.Name, 'Phone_Number': new_contact.Phone_Number, 'Bio': new_contact.Bio})

        # 检查是否有来源页面参数，如果有则重定向回来源页面
        referer = request.args.get('referer')
        if referer and 'roster' in referer:
            # 添加新联系人的信息到URL参数中
            separator = '&' if '?' in referer else '?'
            redirect_url = f"{referer}{separator}new_contact_id={new_contact.id}&new_contact_name={new_contact.Name}&new_contact_type={new_contact.Type}"
            return redirect(redirect_url)
        return redirect(url_for('contacts_bp.show_contacts'))

    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())
    return render_template('contact_form.html', contact=contact, pathways=pathways)


@contacts_bp.route('/contact/delete/<int:contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    if not is_authorized(session.get('user_role'), 'CONTACT_BOOK_EDIT'):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    SessionLog.query.filter_by(Owner_ID=contact_id).update({"Owner_ID": None})
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('contacts_bp.show_contacts'))


@contacts_bp.route('/api/contact', methods=['POST'])
@login_required
def create_contact_api():
    """通过 API 创建新联系人"""
    if not is_authorized(session.get('user_role'), 'CONTACT_BOOK_EDIT'):
        return jsonify({'error': 'Permission denied'}), 403

    try:
        data = request.get_json()
        
        # 验证必需字段
        if not data.get('name') or not data.get('type'):
            return jsonify({'error': 'Name and Type are required'}), 400
            
        # 检查是否已存在同名联系人
        existing_contact = Contact.query.filter_by(Name=data['name']).first()
        if existing_contact:
            return jsonify({'error': f"A contact with the name '{data['name']}' already exists."}), 400
            
        # 如果提供了邮箱，检查是否已存在
        if data.get('email'):
            existing_email = Contact.query.filter_by(Email=data['email']).first()
            if existing_email:
                return jsonify({'error': f"A contact with the email '{data['email']}' already exists."}), 400

        # 创建新联系人
        new_contact = Contact(
            Name=data['name'],
            Email=data.get('email') or None,
            Type=data['type'],
            Club=data.get('club') or 'Victoria Park Toastmasters',  # 默认俱乐部
            Date_Created=date.today(),
            Phone_Number=data.get('phone') or None
        )
        
        db.session.add(new_contact)
        db.session.commit()
        
        # 返回新创建的联系人信息
        return jsonify({
            'id': new_contact.id,
            'name': new_contact.Name,
            'type': new_contact.Type,
            'email': new_contact.Email,
            'phone': new_contact.Phone_Number
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
