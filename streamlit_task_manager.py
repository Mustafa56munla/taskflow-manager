import streamlit_due_date': next_date})

    # Apply Sorting
    reverse_sort = False
    if sort_ as st
from datetime import datetime, timedelta, date
import calendar
import firebase_admin
from firebase_admin importby == 'Due Date':
        sort_key = lambda x: x['next_due_date']
 credentials, firestore
import json
import tempfile
import os

# --- CONFIGURATION & CREDENTIALS ---    # --- NEW: Logic to handle sorting by priority (High to Low) ---
    elif sort_by == 'Priority':
        sort_key = lambda x: PRIORITY_LEVELS.index(x.get('priority',

# Simplified User Structure with Email and PIN (Used only for initial DB bootstrap)
SIMPLIFIED_USER_CREDENTIALS 'Low'))
        reverse_sort = True # Sort from High (index 2) to Low (index  = {
    'mustafa': {'email': 'mustafa.munla@azurreo.com', '0)
    else: # Title
        sort_key = lambda x: x['title']
    sorted_tasks = sorted(tasks_with_next_date, key=sort_key, reverse=reverse_sort)

    name': 'Mustafa (Admin)', 'role': 'admin', 'id': 'user_1', 'pin': '1234'},
    'bob': {'email': 'bob@team.com', 'name': 'Bob (Teamtasks_due_today = [t for t in sorted_tasks if t['next_due_date'] == today]
 Lead)', 'role': 'user', 'id': 'user_2', 'pin': '1234'},
    'charlie': {'email': 'charlie@team.com', 'name': '    upcoming_tasks = [t for t in sorted_tasks if today < t['next_due_date'] <= today + timedelta(days=7)]
    all_user_tasks = sorted_tasks

    def toggle_task_completion(Charlie (Member)', 'role': 'user', 'id': 'user_3', 'pin': '1234'},task_id):
        for task in st.session_state.tasks:
            if task['id'] == task_id:
                task['is_completed'] = not task['is_completed']
                st.toast(f"Task '{task['title']}' updated!")
                break
        save_tasks_to_db(st.session_state.tasks)
        st.rerun() 

    st.markdown("###
}

# Task Types for the UI selection
TASK_TYPES = ['one-time', 'daily', 'weekly', 'bi-weekly', 'monthly']

# --- NEW: Priority Configuration ---
PRIORITY_LEVELS = ['Low', 'Medium', 'High']
PRIORITY_COLORS = {
    'Low': '#22c55e',       # Green-500
    'Medium': '#f59e0b',    # Amber- 🎯 Tasks Due Today")
    if tasks_due_today:
        for i, task in enumerate(tasks_500
    'High': '#ef4444'       # Red-500
}due_today):
            task_card(task, task['next_due_date'], "Today", toggle_task_completion, index=i)
    else:
        st.info("Nothing due today! 🎉")

    

# Mock Category Data
MOCK_ACCOUNTS = ['Nike', 'Adidas', 'Puma', 'General']
MOCK_CAMPAIGNS = ['Holiday 2025', 'Q4 Launch', 'Brand Awareness']

# --- MODIFIED: Added 'priority' to mock tasks ---
INITIAL_MOCK_TASKSst.markdown("---")
    st.markdown("### 🗓️ Upcoming Tasks (Next 7 Days)")
    if upcoming_tasks:
        for i, task in enumerate(upcoming_tasks):
            task_card(task, task['next_due_date'], "Upcoming", toggle_task_completion, index=i)
    else:
        st.info("No upcoming tasks this week.")

    st.markdown("---")
    st.markdown("### 📝 All My Tasks")
    if all_user_tasks:
        for i, task in enumerate(all_user_tasks):
            task_card(task, task['next_due_date'], "All My Tasks", toggle_task_completion, index=i) 
    else:
        st.warning("You have no tasks saved yet.")

def calendar_view():
    st.subheader("Monthly Calendar")
    is_admin = st.session_state.users[st.session_state.username]['role'] == 'admin'
    
    view_filter = 'My Tasks'
    if is_admin:
        view_filter = st.radio("Calendar View", ('All Team Tasks', 'My Tasks'), horizontal=True, key='cal_view_filter')
    
    base_tasks = st.session_state.tasks if view_filter == 'All Team Tasks' = [
    { 'id': 'task_1', 'title': 'Review Authentication', 'description': 'Test the new login system.', 'due_date': datetime.now().date(), 'type': 'one-time', 'owner_id': 'mustafa', 'is_completed': False, 'account': 'Nike', 'campaign': 'Holiday 2025', 'priority': 'High' },
    { 'id': 'task_2', 'title': 'Weekly Report Prep', 'description': 'Prepare slide deck for management.', 'due_date': datetime.now().date() - timedelta(days=2), 'type': 'weekly', 'owner_id': 'bob', 'is_completed': False, 'account': 'Adidas', 'campaign': 'Q4 Launch', 'priority': 'Medium' },
    { 'id': 'task_3', 'title': 'Clean Database', 'description': 'Routine maintenance.', 'due_date': datetime.now().date().replace(day=5), 'type': 'monthly', 'owner_id': 'charlie', 'is_completed': False, 'account': 'General', 'campaign': 'Brand Awareness', 'priority': 'Low' }
]

# --- HELPER FUNCTIONS ---

def get_user_name(username):
    """Retrieves the full name of a user based on their username (which is now the owner_id).""" else [t for t in st.session_state.tasks if t['owner_id'] == st.session_state.username]
    
    if 'calendar_date' not in st.session_state:
        st.session_
    user_data = st.session_state.users.get(username)
    return user_data.state.calendar_date = datetime.now().date()

    col1, col2, col3 = st.get('name') if user_data else f"Unknown User ({username})"

# --- AUTHENTICATION FUNCTIONS ---columns([1, 2, 1])
    with col1:
        if st.button("←

def authenticate_user(email, pin):
    """Authenticates user based on email and PIN."""
    for Previous"):
            st.session_state.calendar_date = (st.session_state.calendar_date.replace(day=1) - timedelta(days=1)).replace(day=1)
    with col2:
 username, user_data in st.session_state.users.items():
        if user_data['email'].lower        st.markdown(f"<h3 style='text-align: center;'>{st.session_state.calendar_date() == email.lower() and user_data['pin'] == pin:
            st.session_state.login_status = True
            st.session_state.username = username
            st.session_state.name =.strftime('%B %Y')}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("Next →"):
            st.session_state.calendar_date = (st.session_ user_data['name']
            st.rerun()
            return True
    st.sidebar.errorstate.calendar_date.replace(day=28) + timedelta(days=4)).replace(day=1)

("Invalid email or PIN.")
    return False

def logout():
    """Clears session state and logs the user out."""    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days = cal.monthdates
    st.session_state.login_status = False
    st.session_state.username = Nonecalendar(st.session_state.calendar_date.year, st.session_state.calendar_date.month
    st.session_state.name = None
    st.rerun()


# --- FIREBASE INITIALIZATION ---

def initialize_firebase():
    """Initializes the Firebase Admin SDK if not already done."""
    if)
    days_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    cols = st.columns(7)
    for i, day in enumerate(days not firebase_admin._apps:
        temp_file_name = None
        try:
            cred__names):
        cols[i].markdown(f"**{day}**")

    for week in month_days:
        cols = st.columns(7)
        for i, day_date in enumerate(week):
