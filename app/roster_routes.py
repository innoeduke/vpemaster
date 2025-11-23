from flask import Blueprint, render_template, request, jsonify
from .auth.utils import login_required
from .models import Roster, Meeting, Contact
from . import db
from sqlalchemy import distinct

roster_bp = Blueprint('roster_bp', __name__)


@roster_bp.route('/', methods=['GET'])
@login_required
def roster():
    # 获取当前会议逻辑，与议程页面相同
    today = db.func.current_date()

    # 查询未来的会议
    future_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Date >= today
    )

    # 查询最近的过去会议
    past_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Date < today
    ).order_by(Meeting.Meeting_Date.desc()).limit(8)

    # 执行查询
    future_meetings = future_meetings_q.all()
    past_meetings = past_meetings_q.all()

    # 合并、排序并获取会议编号
    all_meetings = sorted(
        future_meetings + past_meetings, key=lambda m: m.Meeting_Date, reverse=True)
    meeting_numbers = [m.Meeting_Number for m in all_meetings]

    selected_meeting_str = request.args.get('meeting_number')
    selected_meeting_num = None

    if selected_meeting_str:
        try:
            selected_meeting_num = int(selected_meeting_str)
        except ValueError:
            selected_meeting_num = None
    else:
        # 查找最近的即将到来的会议
        upcoming_meeting = Meeting.query\
            .filter(Meeting.Meeting_Date >= today)\
            .order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc())\
            .first()

        if upcoming_meeting:
            selected_meeting_num = upcoming_meeting.Meeting_Number
        elif meeting_numbers:
            # 回退到最近的现有会议
            selected_meeting_num = meeting_numbers[0]

    # 获取选定的会议
    selected_meeting = None
    roster_entries = []
    first_unallocated_entry = None
    if selected_meeting_num:
        selected_meeting = Meeting.query.filter(
            Meeting.Meeting_Number == selected_meeting_num
        ).first()

        # 获取该会议的花名册条目（包括未分配联系人的条目）
        roster_entries = Roster.query\
            .outerjoin(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_number == selected_meeting_num)\
            .order_by(Roster.order_number.asc())\
            .all()
                
        # 查找下一个可用序号（最后一个序号+1）
        next_unallocated_entry = None
        if roster_entries:
            max_order = max(entry.order_number for entry in roster_entries)
            next_unallocated_entry = type('obj', (object,), {'order_number': max_order + 1})()
        else:
            next_unallocated_entry = type('obj', (object,), {'order_number': 1})()

        # 查找第一个未分配的条目（联系人名称为空）
        for entry in roster_entries:
            if not entry.contact_id:
                first_unallocated_entry = entry
                break

    # 获取所有联系人用于表单下拉列表
    contacts = Contact.query.order_by(Contact.Name).all()

    return render_template(
        'roster.html',
        all_meetings=all_meetings,
        selected_meeting=selected_meeting,
        selected_meeting_num=selected_meeting_num,
        roster_entries=roster_entries,
        contacts=contacts,
        meeting_numbers=meeting_numbers,
        next_unallocated_entry=next_unallocated_entry
    )


@roster_bp.route('/api/roster', methods=['POST'])
@login_required
def create_roster_entry():
    """创建新的花名册条目"""
    data = request.get_json()

    required_fields = ['meeting_number', 'order_number', 'ticket']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    new_entry = Roster(
        meeting_number=data['meeting_number'],
        order_number=data['order_number'],
        ticket=data['ticket']
    )

    if 'contact_id' in data and data['contact_id']:
        new_entry.contact_id = data['contact_id']

    try:
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({'message': 'Entry created successfully', 'id': new_entry.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/roster/<int:entry_id>', methods=['GET'])
@login_required
def get_roster_entry(entry_id):
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    
    contact_name = None
    contact_type = None
    if entry.contact:
        contact_name = entry.contact.Name
        contact_type = entry.contact.Type

    return jsonify({
        'id': entry.id,
        'meeting_number': entry.meeting_number,
        'order_number': entry.order_number,
        'ticket': entry.ticket,
        'contact_id': entry.contact_id,
        'contact_name': contact_name,
        'contact_type': contact_type
    })


@roster_bp.route('/api/roster/<int:entry_id>', methods=['PUT'])
@login_required
def update_roster_entry(entry_id):
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    data = request.get_json()

    if 'order_number' in data:
        entry.order_number = data['order_number']
    if 'ticket' in data:
        entry.ticket = data['ticket']

    if 'contact_id' in data:
        if data['contact_id']:  # 如果contact_id不为空
            entry.contact_id = data['contact_id']
        else:  # 如果contact_id为空，设置为None
            entry.contact_id = None

    try:
        db.session.commit()
        return jsonify({'message': 'Entry updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/roster/<int:entry_id>', methods=['DELETE'])
@login_required
def cancel_roster_entry(entry_id):
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    try:
        entry.ticket = 'Cancelled'
        db.session.commit()
        return jsonify({'message': 'Entry cancelled successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
