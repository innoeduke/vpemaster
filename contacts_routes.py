# vpemaster/contacts_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from vpemaster import db
from vpemaster.models import Contact, SessionLog
from .main_routes import login_required
from datetime import date

contacts_bp = Blueprint('contacts_bp', __name__)

@contacts_bp.route('/contacts/search')
@login_required
def search_contacts_by_name():
    search_term = request.args.get('q', '')
    if search_term:
        contacts = Contact.query.filter(Contact.Name.ilike(f'%{search_term}%')).all()
    else:
        contacts = Contact.query.all()

    contacts_data = [{"id": c.id, "Name": c.Name} for c in contacts]
    return jsonify(contacts_data)

@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    if session.get('user_role') not in ['Admin', 'VPE', 'Officer']:
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())
    return render_template('contacts.html', contacts=contacts, pathways=pathways)

@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    if session.get('user_role') not in ['Admin', 'VPE', 'Officer']:
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contact = None
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'GET' and contact:
        contact_data = {
            "Name": contact.Name,
            "Type": contact.Type,
            "Club": contact.Club,
            "Phone_Number": contact.Phone_Number,
            "Bio": contact.Bio,
            "Working_Path": contact.Working_Path,
            "Next_Project": contact.Next_Project,
            "Completed_Levels": contact.Completed_Levels,
            "DTM": contact.DTM
        }
        return jsonify(contact=contact_data)

    if request.method == 'POST':
        if contact:
            contact.Name = request.form['name']
            contact.Club = request.form.get('club')
            contact.Phone_Number = request.form.get('phone_number')
            contact.Bio = request.form.get('bio')
            contact.Next_Project = request.form.get('next_project')
            contact.Completed_Levels = request.form.get('completed_levels')
            contact.Type = request.form.get('type')
            contact.Working_Path = request.form.get('working_path')
            contact.DTM = 'dtm' in request.form
        else:
            new_contact = Contact(
                Name=request.form['name'],
                Club=request.form.get('club'),
                Phone_Number=request.form.get('phone_number'),
                Bio=request.form.get('bio'),
                Date_Created=date.today(),
                Next_Project=request.form.get('next_project'),
                Completed_Levels=request.form.get('completed_levels'),
                Type=request.form.get('type'),
                Working_Path=request.form.get('working_path'),
                DTM='dtm' in request.form,
            )
            db.session.add(new_contact)
            db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=True, contact={'id': new_contact.id, 'Name': new_contact.Name})
        db.session.commit()
        return redirect(url_for('contacts_bp.show_contacts'))

    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())
    return render_template('contact_form.html', contact=contact, pathways=pathways)

@contacts_bp.route('/contact/delete/<int:contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    if session.get('user_role') not in ['Admin', 'VPE', 'Officer']:
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    SessionLog.query.filter_by(Owner_ID=contact_id).update({"Owner_ID": None})
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('contacts_bp.show_contacts'))

