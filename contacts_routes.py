# vpemaster/contacts_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from vpemaster import db
from vpemaster.models import Contact, SessionLog
from .main_routes import login_required
from datetime import date

contacts_bp = Blueprint('contacts_bp', __name__)

@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    if session.get('user_role') not in ['Admin', 'Officer']:
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    return render_template('contacts.html', contacts=contacts)

@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    if session.get('user_role') not in ['Admin', 'Officer']:
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
            "Working_Path": contact.Working_Path,
            "Next_Project": contact.Next_Project,
            "DTM": contact.DTM
        }
        return jsonify(contact=contact_data)

    if request.method == 'POST':
        if contact:
            contact.Name = request.form['name']
            contact.Club = request.form.get('club')
            contact.Next_Project = request.form.get('next_project')
            contact.Type = request.form.get('type')
            contact.Working_Path = request.form.get('working_path')
            contact.DTM = 'dtm' in request.form
        else:
            new_contact = Contact(
                Name=request.form['name'],
                Club=request.form.get('club'),
                Date_Created=date.today(),
                Next_Project=request.form.get('next_project'),
                Type=request.form.get('type'),
                Working_Path=request.form.get('working_path'),
                DTM='dtm' in request.form
            )
            db.session.add(new_contact)
        db.session.commit()
        return redirect(url_for('contacts_bp.show_contacts'))

    return render_template('contact_form.html', contact=contact)

@contacts_bp.route('/contact/delete/<int:contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    if session.get('user_role') not in ['Admin', 'Officer']:
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    SessionLog.query.filter_by(Owner_ID=contact_id).update({"Owner_ID": None})
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('contacts_bp.show_contacts'))