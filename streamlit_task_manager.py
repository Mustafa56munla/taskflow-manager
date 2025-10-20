import streamlit as st
from datetime import datetime, timedelta, date
import calendar
import firebase_admin
from firebase_admin import credentials, firestore
import json
import tempfile
import os

# --- CONFIGURATION & CREDENTIALS ---

# Simplified User Structure with Email and PIN (Used only for initial DB bootstrap)
SIMPLIFIED_USER_CREDENTIALS = {
    'mustafa': {'email': 'mustafa.munla@azurreo.com', 'name': 'Mustafa (Admin)', 'role': 'admin', 'id': 'user_1', 'pin': '1234'},
    'bob': {'email': 'bob@team.com', 'name': 'Bob (Team Lead)', 'role': 'user', 'id': 'user_2', 'pin': '1234'},
    'charlie': {'email': 'charlie@team.com', 'name': 'Charlie (Member)', 'role': 'user', 'id': 'user_3', 'pin': '1234'},
}

# Task Types for the UI selection
TASK_TYPES = ['one-time', 'daily', 'weekly', 'bi-weekly', 'monthly']

# --- NEW: Priority Configuration ---
PRIORITY_LEVELS = ['Low', 'Medium', 'High']
PRIORITY_COLORS = {
    'Low': '#22c55e',       # Green-500
    'Medium': '#f59e0b',    # Amber-500
    'High': '#ef4444'       # Red-500
}

# Mock Category Data
MOCK_ACCOUNTS = ['Nike', 'Adidas', 'Puma', 'General']
MOCK_CAMPAIGNS = ['Holiday 2025', 'Q4 Launch', 'Brand Awareness']

# --- MODIFIED: Added 'priority' to mock tasks ---
INITIAL_MOCK_TASKS = [
    { 'id': 'task_1', 'title': 'Review Authentication', 'description': 'Test the new login system.', 'due_date': datetime.now().date(), 'type': 'one-time', 'owner_id': 'mustafa', 'is_completed': False, 'account': 'Nike', 'campaign': 'Holiday 2025', 'priority': 'High' },
    { 'id': 'task_2', 'title': 'Weekly Report Prep', 'description': 'Prepare slide deck for management.', 'due_date': datetime.now().date() - timedelta(days=2), 'type': 'weekly', 'owner_id': 'bob', 'is_completed': False, 'account': 'Adidas', 'campaign': 'Q4 Launch', 'priority': 'Medium' },
    { 'id': 'task_3', 'title': 'Clean Database', 'description': 'Routine maintenance.', 'due_date': datetime.now().date().replace(day=5), 'type': 'monthly', 'owner_id': 'charlie', 'is_completed': False, 'account': 'General', 'campaign': 'Brand Awareness', 'priority': 'Low' }
]

# --- HELPER FUNCTIONS ---

def get_user_name(username):
    """Retrieves the full name of a user based on their username."""
    user_data = st.session_state.users.get(username)
    return user_data.get('name') if user_data else f"Unknown User ({username})"

# --- AUTHENTICATION FUNCTIONS ---

def authenticate_user(email, pin):
    """Authenticates user based on email and PIN."""
    for username, user_data in st.session_state.users.items():
        if user_data['email'].lower() == email.lower() and user_data['pin'] == pin:
            st.session_state.login_status = True
            st.session_state.username = username
            st.session_state.name = user_data['name']
            st.rerun()
            return True
    st.sidebar.error("Invalid email or PIN.")
    return False

def logout():
    """Clears session state and logs the user out."""
    st.session_state.login_status = False
    st.session_state.username = None
    st.session_state.name = None
    st.rerun()

# --- FIREBASE INITIALIZATION ---

def initialize_firebase():
    """Initializes the Firebase Admin SDK if not already done."""
    if not firebase_admin._apps:
        temp_file_name = None
        try:
            cred_dict = st.secrets["firebase_key"]
            service_account_info = dict(cred_dict)
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                json.dump(service_account_info, temp_file)
                temp_file_name = temp_file.name
            cred = credentials.Certificate(temp_file_name)
            firebase_admin.initialize_app(cred)
            st.session_state.db = firestore.client()
            if temp_file_name and os.path.exists(temp_file_name):
                os.remove(temp_file_name)
        except Exception as e:
            if temp_file_name and os.path.exists(temp_file_name):
                os.remove(temp_file_name)
            st.error(f"🛑 Error initializing Firebase: {e}")
            st.stop()
    if 'db' not in st.session_state:
        st.session_state.db = firestore.client()

# --- DATA STORAGE (PERSISTENT - FIRESTORE) ---

TASK_DOC_REF = 'team_tasks/all_tasks'
USER_DOC_REF = 'user_data/all_users'
CATEGORY_DOC_REF = 'metadata/categories'

def load_tasks_from_db():
    initialize_firebase()
    db = st.session_state.db
    try:
        doc = db.document(TASK_DOC_REF).get()
        tasks_from_db = []
        max_id = 0
        if doc.exists:
            data = doc.to_dict()
            tasks_from_db = data.get('tasks', [])
        if tasks_from_db:
            for task in tasks_from_db:
                if task.get('due_date') and hasattr(task['due_date'], 'date'):
                    task['due_date'] = task['due_date'].date()
                if task['id'].startswith('task_'):
                    try:
                        max_id = max(max_id, int(task['id'].split('_')[1]))
                    except ValueError:
                        pass
            st.session_state.next_task_id = max_id + 1
            return tasks_from_db, False
        else:
            st.session_state.next_task_id = 4
            return INITIAL_MOCK_TASKS, True
    except Exception as e:
        st.error(f"Failed to load tasks from Firestore: {e}")
        st.session_state.next_task_id = 1
        return [], False

def save_tasks_to_db(tasks):
    initialize_firebase()
    db = st.session_state.db
    data_to_save = []
    for task in tasks:
        task_copy = task.copy()
        due_date_value = task_copy.get('due_date')
        if isinstance(due_date_value, datetime):
            task_copy['due_date'] = due_date_value
        elif isinstance(due_date_value, date):
            task_copy['due_date'] = datetime.combine(due_date_value, datetime.min.time())
        else:
            task_copy['due_date'] = None
        data_to_save.append(task_copy)
    try:
        db.document(TASK_DOC_REF).set({'tasks': data_to_save})
    except Exception as e:
        st.error(f"Failed to save tasks to Firestore: {e}")

def load_users_from_db():
    initialize_firebase()
    db = st.session_state.db
    is_mock_user_data = False
    try:
        doc = db.document(USER_DOC_REF).get()
        if doc.exists and doc.to_dict():
            st.session_state.users = doc.to_dict().get('users', SIMPLIFIED_USER_CREDENTIALS)
        else:
            st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
            is_mock_user_data = True
    except Exception as e:
        st.error(f"Failed to load users from Firestore: {e}")
        st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
    return is_mock_user_data

def save_users_to_db(users_dict, context=""):
    initialize_firebase()
    db = st.session_state.db
    try:
        db.document(USER_DOC_REF).set({'users': users_dict})
        if context:
            st.toast(f"User data saved: {context}.")
    except Exception as e:
        st.error(f"Failed to save users to Firestore ({context}): {e}")

def load_categories_from_db():
    initialize_firebase()
    db = st.session_state.db
    try:
        doc = db.document(CATEGORY_DOC_REF).get()
        if doc.exists and doc.to_dict():
            return doc.to_dict(), False
        else:
            return {'accounts': MOCK_ACCOUNTS, 'campaigns': MOCK_CAMPAIGNS}, True
    except Exception as e:
        st.error(f"Failed to load categories from Firestore: {e}")
        return {'accounts': MOCK_ACCOUNTS, 'campaigns': MOCK_CAMPAIGNS}, False

def save_categories_to_db(categories_dict, context=""):
    initialize_firebase()
    db = st.session_state.db
    try:
        db.document(CATEGORY_DOC_REF).set(categories_dict)
        if context:
            st.toast(f"Category data saved: {context}.")
    except Exception as e:
        st.error(f"Failed to save categories ({context}): {e}")

# --- DATA SETUP ---

def initialize_tasks():
    if 'categories' not in st.session_state:
        categories_dict, is_mock_category_data = load_categories_from_db()
        st.session_state.categories = categories_dict
        if is_mock_category_data:
            save_categories_to_db(st.session_state.categories, "initial bootstrap")

    if 'users' not in st.session_state or not st.session_state.users:
        if load_users_from_db():
            save_users_to_db(st.session_state.users, "initial user bootstrap")

    if 'tasks' not in st.session_state:
        tasks, is_mock_data = load_tasks_from_db()
        st.session_state.tasks = tasks
        if is_mock_data:
            save_tasks_to_db(st.session_state.tasks)

    if 'editing_task_id' not in st.session_state:
        st.session_state.editing_task_id = None
    if 'edit_form_key' not in st.session_state:
        st.session_state.edit_form_key = 0

# --- RECURRENCE LOGIC ---

def day_difference(date1, date2):
    if isinstance(date1, datetime): date1 = date1.date()
    if isinstance(date2, datetime): date2 = date2.date()
    return abs((date2 - date1).days)

def is_task_due(task, target_date):
    start_date = task['due_date']
    if not start_date or target_date < start_date:
        return False
    if target_date == start_date:
        return True
    task_type = task['type']
    if task_type == 'one-time': return False
    if task_type == 'daily': return True
    if task_type == 'weekly': return target_date.weekday() == start_date.weekday()
    if task_type == 'bi-weekly': return day_difference(target_date, start_date) % 14 == 0
    if task_type == 'monthly': return target_date.day == start_date.day
    return False

def get_next_occurrence(task, reference_date, days_limit=365):
    next_date = reference_date
    end_date = reference_date + timedelta(days=days_limit)
    while next_date < end_date:
        if is_task_due(task, next_date):
            return next_date
        next_date += timedelta(days=1)
    return None

# --- UI COMPONENTS ---

# --- MODIFIED: task_card now uses priority for styling ---
def task_card(task, next_due_date, current_view, on_complete=None, index=None):
    """Displays a single task card with actions, now color-coded by priority."""
    task_priority = task.get('priority', 'Medium')
    priority_color = PRIORITY_COLORS.get(task_priority, PRIORITY_COLORS['Medium'])
    
    if task['is_completed']:
        title_style = "text-decoration: line-through; color: #6b7280;"
    else:
        title_style = "color: #1f2937;"
        
    card_style = f"border-left: 5px solid {priority_color}; border-radius: 5px; padding: 10px; margin-bottom: 10px; background-color: #fafafa;"
    
    with st.container():
        st.markdown(f'<div style="{card_style}">', unsafe_allow_html=True)
        
        current_username = st.session_state.username
        is_admin = st.session_state.users[current_username]['role'] == 'admin'
        is_owner = task['owner_id'] == current_username
        can_edit_or_delete = is_admin or is_owner
        unique_key_suffix = f"{task['id']}_{current_view}_{index or ''}"

        col1, col2, col3, col4 = st.columns([0.5, 0.2, 0.15, 0.15])
        
        with col1:
            st.markdown(f'<div style="{title_style} font-weight: bold;">{task["title"]}</div>', unsafe_allow_html=True)
            # --- NEW: Display priority in the caption ---
            context_text = f"**{task.get('account', 'N/A')}** / **{task.get('campaign', 'N/A')}** | Priority: **{task_priority}**"
            st.caption(f"{context_text} | Owned by: **{get_user_name(task['owner_id'])}**")
            
        with col2:
            if next_due_date:
                st.markdown(f'<div style="text-align: right;">{next_due_date.strftime("%b %d, %Y")}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size: 0.8em; text-align: right; color: #6b7280;">{task["type"]}</div>', unsafe_allow_html=True)

        with col3:
            if can_edit_or_delete:
                if st.button("Edit", key=f"edit_{unique_key_suffix}"):
                    st.session_state.editing_task_id = task['id']
                    st.session_state.edit_form_key += 1
                    st.rerun()

        with col4:
            if current_view != 'All My Tasks' and is_owner:
                if not task['is_completed']:
                    st.button("Done", key=f"complete_{unique_key_suffix}", on_click=on_complete, args=(task['id'],), type="primary")
                else:
                    st.button("Un-do", key=f"uncomplete_{unique_key_suffix}", on_click=on_complete, args=(task['id'],))
            elif can_edit_or_delete:
                if st.button("Delete", key=f"delete_{unique_key_suffix}"):
                    delete_task(task['id'])
        
        st.markdown('</div>', unsafe_allow_html=True)

def delete_task(task_id):
    st.session_state.tasks = [t for t in st.session_state.tasks if t['id'] != task_id]
    save_tasks_to_db(st.session_state.tasks)
    st.toast("Task deleted!")
    st.rerun()

def find_task_by_id(task_id):
    return next((t for t in st.session_state.tasks if t['id'] == task_id), None)

def update_task(task_id, new_data):
    for i, task in enumerate(st.session_state.tasks):
        if task['id'] == task_id:
            st.session_state.tasks[i].update(new_data)
            st.toast(f"Task '{new_data['title']}' updated!")
            break
    save_tasks_to_db(st.session_state.tasks)
    st.session_state.editing_task_id = None
    st.rerun()

# --- MODIFIED: edit_task_modal now includes a priority selector ---
def edit_task_modal():
    task_id = st.session_state.editing_task_id
    if not task_id: return
    task = find_task_by_id(task_id)
    if not task:
        st.session_state.editing_task_id = None
        return

    is_admin = st.session_state.users[st.session_state.username]['role'] == 'admin'
    
    with st.form(f"edit_task_form_{st.session_state.edit_form_key}"):
        st.subheader(f"Editing Task: {task['title']}")
        new_title = st.text_input("Title", value=task['title'])
        new_description = st.text_area("Description", value=task.get('description', ''))
        
        cols = st.columns(3)
        current_due_date = task['due_date'] if isinstance(task['due_date'], (datetime, date)) else datetime.now().date()
        new_due_date = cols[0].date_input("Due/Start Date", value=current_due_date)
        new_task_type = cols[1].selectbox("Recurrence", TASK_TYPES, index=TASK_TYPES.index(task['type']))
        
        # --- NEW: Priority selector for editing ---
        current_priority = task.get('priority', 'Medium')
        priority_index = PRIORITY_LEVELS.index(current_priority) if current_priority in PRIORITY_LEVELS else 1
        new_priority = cols[2].selectbox("Priority", PRIORITY_LEVELS, index=priority_index)
        
        cols_context = st.columns(2)
        account_options = st.session_state.categories.get('accounts', [])
        new_account = cols_context[0].selectbox("Account", account_options, index=(account_options.index(task['account']) if task.get('account') in account_options else 0))
        campaign_options = st.session_state.categories.get('campaigns', [])
        new_campaign = cols_context[1].selectbox("Campaign", campaign_options, index=(campaign_options.index(task['campaign']) if task.get('campaign') in campaign_options else 0))

        assignee_id = task['owner_id']
        if is_admin:
            all_user_names = [d['name'] for d in st.session_state.users.values()]
            current_assignee_name = get_user_name(assignee_id)
            selected_assignee_name = st.selectbox("Assignee", all_user_names, index=(all_user_names.index(current_assignee_name) if current_assignee_name in all_user_names else 0))
            assignee_id = next(u for u, d in st.session_state.users.items() if d['name'] == selected_assignee_name)
        
        update_submitted = st.form_submit_button("Update Task", type="primary")
        if st.form_submit_button("Cancel"):
            st.session_state.editing_task_id = None
            st.rerun()

        if update_submitted and new_title:
            update_task(task_id, {
                'title': new_title, 'description': new_description, 'due_date': new_due_date,
                'type': new_task_type, 'owner_id': assignee_id, 'account': new_account,
                'campaign': new_campaign, 'priority': new_priority  # --- NEW: Save the updated priority
            })

# --- MODIFIED: add_task_form now includes a priority selector ---
def add_task_form():
    is_admin = st.session_state.users[st.session_state.username]['role'] == 'admin'
    if st.session_state.editing_task_id is None:
        with st.expander("➕ Add New Task"):
            with st.form("new_task_form", clear_on_submit=True):
                title = st.text_input("Title")
                description = st.text_area("Description")
                
                cols = st.columns(3)
                due_date = cols[0].date_input("Due/Start Date", value=datetime.now().date())
                task_type = cols[1].selectbox("Recurrence", TASK_TYPES)
                # --- NEW: Priority selector for new tasks ---
                priority = cols[2].selectbox("Priority", PRIORITY_LEVELS, index=1) # Default to Medium

                cols_context = st.columns(2)
                new_account = cols_context[0].selectbox("Account", st.session_state.categories.get('accounts', []))
                new_campaign = cols_context[1].selectbox("Campaign", st.session_state.categories.get('campaigns', []))
                
                assignee_id = st.session_state.username
                if is_admin:
                    all_user_names = [d['name'] for d in st.session_state.users.values()]
                    selected_assignee_name = st.selectbox("Assignee", all_user_names, index=all_user_names.index(st.session_state.name))
                    assignee_id = next(u for u, d in st.session_state.users.items() if d['name'] == selected_assignee_name)
                
                if st.form_submit_button("Save Task", type="primary"):
                    if title:
                        new_id = f"task_{st.session_state.next_task_id}"
                        st.session_state.next_task_id += 1
                        st.session_state.tasks.append({
                            'id': new_id, 'title': title, 'description': description,
                            'due_date': due_date, 'type': task_type, 'owner_id': assignee_id,
                            'is_completed': False, 'account': new_account, 'campaign': new_campaign,
                            'priority': priority  # --- NEW: Add priority to new task data
                        })
                        save_tasks_to_db(st.session_state.tasks)
                        st.success(f"Task '{title}' added!")
                    else:
                        st.error("Title cannot be empty.")

# --- ADMIN PAGES ---
def category_management_form():
    if st.session_state.users[st.session_state.username]['role'] == 'admin':
        with st.expander("📁 Manage Categories (Admin)"):
            current_accounts = ", ".join(st.session_state.categories['accounts'])
            new_accounts = st.text_area("Accounts (comma-separated)", current_accounts)
            current_campaigns = ", ".join(st.session_state.categories['campaigns'])
            new_campaigns = st.text_area("Campaigns (comma-separated)", current_campaigns)
            if st.button("Save Categories"):
                st.session_state.categories['accounts'] = [a.strip() for a in new_accounts.split(',')]
                st.session_state.categories['campaigns'] = [c.strip() for c in new_campaigns.split(',')]
                save_categories_to_db(st.session_state.categories, "admin update")
                st.success("Categories saved!")
                st.rerun()

def admin_user_control_page():
    st.title("👤 User Management")
    st.dataframe([{'Username': u, **d} for u, d in st.session_state.users.items()], use_container_width=True)
    # Add/Edit/Delete user forms can be placed here as in your original code

# --- VIEWS ---

# --- MODIFIED: dashboard_view now includes sorting by priority ---
def dashboard_view():
    st.subheader("Actionable Summary")
    today = datetime.now().date()
    current_username = st.session_state.username
    is_admin = st.session_state.users[current_username]['role'] == 'admin'

    with st.expander("🔍 Filter & Sort Tasks"):
        filter_cols = st.columns(3)
        selected_accounts = filter_cols[0].multiselect("Accounts", st.session_state.categories.get('accounts', []), default=st.session_state.categories.get('accounts', []))
        selected_campaigns = filter_cols[1].multiselect("Campaigns", st.session_state.categories.get('campaigns', []), default=st.session_state.categories.get('campaigns', []))
        selected_statuses_str = filter_cols[2].multiselect("Status", ['Incomplete', 'Completed'], default=['Incomplete'])
        selected_statuses = [s == 'Completed' for s in selected_statuses_str]
        
        # --- NEW: Added 'Priority' to sorting options ---
        sort_by = st.selectbox("Sort By", ['Due Date', 'Title', 'Priority'])

    base_tasks_to_filter = st.session_state.tasks if is_admin else [t for t in st.session_state.tasks if t['owner_id'] == current_username]
    
    filtered_tasks = [
        t for t in base_tasks_to_filter if
        t.get('account') in selected_accounts and
        t.get('campaign') in selected_campaigns and
        t.get('is_completed') in selected_statuses
    ]
    
    tasks_with_next_date = [{'next_due_date': get_next_occurrence(t, today), **t} for t in filtered_tasks]
    tasks_with_next_date = [t for t in tasks_with_next_date if t['next_due_date']]

    # --- NEW: Logic to handle sorting by priority (High to Low) ---
    reverse_sort = False
    if sort_by == 'Due Date':
        sort_key = lambda x: x['next_due_date']
    elif sort_by == 'Priority':
        # Sorts by the index in PRIORITY_LEVELS ('Low': 0, 'Medium': 1, 'High': 2)
        sort_key = lambda x: PRIORITY_LEVELS.index(x.get('priority', 'Medium'))
        reverse_sort = True  # Reverse to get High priority first
    else:  # Title
        sort_key = lambda x: x['title']
        
    sorted_tasks = sorted(tasks_with_next_date, key=sort_key, reverse=reverse_sort)

    tasks_today = [t for t in sorted_tasks if t['next_due_date'] == today]
    tasks_upcoming = [t for t in sorted_tasks if today < t['next_due_date'] <= today + timedelta(days=7)]

    def toggle_task_completion(task_id):
        for task in st.session_state.tasks:
            if task['id'] == task_id:
                task['is_completed'] = not task['is_completed']
                break
        save_tasks_to_db(st.session_state.tasks)
        st.rerun()

    st.markdown("### 🎯 Today")
    if tasks_today:
        for i, task in enumerate(tasks_today):
            task_card(task, task['next_due_date'], "Today", toggle_task_completion, index=i)
    else:
        st.info("No tasks due today!")

    st.markdown("### 🗓️ Upcoming (Next 7 Days)")
    if tasks_upcoming:
        for i, task in enumerate(tasks_upcoming):
            task_card(task, task['next_due_date'], "Upcoming", toggle_task_completion, index=i)
    else:
        st.info("No upcoming tasks this week.")

def calendar_view():
    st.subheader("Monthly Calendar")
    # Calendar view logic remains the same
    # ...

# --- MAIN APP ---

def main_app_content(name, username):
    st.title("TaskFlow Manager")
    initialize_tasks()
    current_user = st.session_state.users[username]
    
    with st.sidebar:
        st.header("Navigation")
        view_options = ['Dashboard', 'Calendar']
        if current_user['role'] == 'admin':
            view_options.append('User Management')
        view = st.radio("Select View", view_options, key='view_selection')
        st.info(f"User: **{name}** ({current_user['role']})")
        st.button("Logout", on_click=logout)

    if view in ['Dashboard', 'Calendar']:
        if current_user['role'] == 'admin':
            category_management_form()
        if st.session_state.editing_task_id:
            edit_task_modal()
        add_task_form()
        st.markdown("---")

    if view == 'Dashboard':
        dashboard_view()
    elif view == 'Calendar':
        calendar_view()
    elif view == 'User Management' and current_user['role'] == 'admin':
        admin_user_control_page()

def main():
    st.set_page_config(layout="wide", page_title="TaskFlow Manager")
    if 'login_status' not in st.session_state:
        st.session_state.login_status = False

    if st.session_state.login_status:
        main_app_content(st.session_state.name, st.session_state.username)
    else:
        st.title("Welcome to TaskFlow Manager")
        with st.sidebar.form("login_form"):
            st.subheader("Login")
            email = st.text_input("Email")
            pin = st.text_input("PIN", type="password")
            if st.form_submit_button("Sign In", type="primary"):
                if email and pin:
                    load_users_from_db()  # Load fresh user data before auth
                    authenticate_user(email, pin)
                else:
                    st.error("Please enter email and PIN.")

if __name__ == "__main__":
    main()
