from flask import Blueprint, render_template, request, jsonify
from .auth.utils import login_required
from .models import Roster, Meeting, Contact
from . import db
from sqlalchemy import distinct

roster_bp = Blueprint('roster_bp', __name__)

@roster_bp.route('/roster', methods=['GET'])
@login_required
def roster():
    # 获取当前会议逻辑，与议程页面相同
    today = db.func.current_date()
    
    # 子查询获取至少有一个花名册条目的会议编号
    subquery = db.session.query(distinct(Roster.meeting_number)).subquery()
    
    # 查询未来的会议
    future_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Number.in_(subquery),
        Meeting.Meeting_Date >= today
    )
    
    # 查询最近的过去会议
    past_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Number.in_(subquery),
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
    if selected_meeting_num:
        selected_meeting = Meeting.query.filter(
            Meeting.Meeting_Number == selected_meeting_num
        ).first()
        
        # 获取该会议的花名册条目
        roster_entries = Roster.query\
            .join(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_number == selected_meeting_num)\
            .order_by(Roster.order_number.asc())\
            .all()
            
    # 获取所有联系人用于表单下拉列表
    contacts = Contact.query.order_by(Contact.Name).all()
    
    return render_template(
        'roster.html',
        all_meetings=all_meetings,
        selected_meeting=selected_meeting,
        roster_entries=roster_entries,
        contacts=contacts
    )


@roster_bp.route('/api/roster', methods=['POST'])
@login_required
def create_roster_entry():
    """创建新的花名册条目"""
    data = request.get_json()
    
    # 验证必需字段
    required_fields = ['meeting_number', 'order_number', 'contact_id', 'ticket']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # 创建新条目
    new_entry = Roster(
        meeting_number=data['meeting_number'],
        order_number=data['order_number'],
        contact_id=data['contact_id'],
        ticket=data['ticket']
    )
    
    try:
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({'message': 'Entry created successfully', 'id': new_entry.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/roster/<int:entry_id>', methods=['PUT'])
@login_required
def update_roster_entry(entry_id):
    """更新花名册条目"""
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
        
    data = request.get_json()
    
    # 更新字段
    if 'order_number' in data:
        entry.order_number = data['order_number']
    if 'contact_id' in data:
        entry.contact_id = data['contact_id']
    if 'ticket' in data:
        entry.ticket = data['ticket']
    
    try:
        db.session.commit()
        return jsonify({'message': 'Entry updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/roster/<int:entry_id>', methods=['DELETE'])
@login_required
def delete_roster_entry(entry_id):
    """删除花名册条目"""
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
        
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Entry deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500