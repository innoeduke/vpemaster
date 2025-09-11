from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster import db
from vpemaster.models import Contact
from .main_routes import login_required
from datetime import date

contacts_bp = Blueprint('contacts_bp', __name__)

@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    return render_template('contacts.html', contacts=contacts)

@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    contact = None
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)

    if request.method == 'POST':
        if contact:
            contact.Name = request.form['name']
            contact.Club = request.form['club']
            contact.Current_Project = request.form['current_project']
            contact.Completed_Levels = request.form['completed_levels']
            db.session.commit()
        else:
            new_contact = Contact(
                Name=request.form['name'],
                Club=request.form['club'],
                Date_Created=date.today(),
                Current_Project=request.form['current_project'],
                Completed_Levels=request.form['completed_levels']
            )
            db.session.add(new_contact)
            db.session.commit()

        return redirect(url_for('contacts_bp.show_contacts'))

    return render_template('contact_form.html', contact=contact)

@contacts_bp.route('/contact/delete/<int:contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('contacts_bp.show_contacts'))
