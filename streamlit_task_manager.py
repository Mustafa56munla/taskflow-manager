import streamlit as st
from datetime import datetime, timedelta, date
import calendar
import firebase_admin
from firebase_admin import credentials, firestore
import json
import tempfile
import os

# --- CONFIGURATION & CREDENTIALS ---

# Simplified User Structure with Email and PIN
SIMPLIFIED_USER_CREDENTIALS = {
    'mustafa': {'email': 'mustafa.munla@azurreo.com', 'name': 'Mustafa (Admin)', 'role': 'admin', 'id': 'user_1', 'pin': '1234'},
    'bob': {'email': 'bob@team.com', 'name': 'Bob (Team Lead)', 'role': 'user', 'id': 'user_2', 'pin': '1234'},
    'charlie': {'email': 'charlie@team.com', 'name': 'Charlie (Member)', 'role': 'user', 'id': 'user_3', 'pin': '1234'},
}

# Task Types for the UI selection
TASK_TYPES = ['one-time', 'daily', 'weekly', 'bi-weekly', 'monthly']

# Define the initial mock tasks outside of functions
INITIAL_MOCK_TASKS = [
    { 'id': 'task_1', 'title': 'Review Authentication', 'description': 'Test the new login system.', 'due_date': datetime.now().date(), 'type': 'one-time', 'owner_id': 'mustafa', 'is_completed': False, },
    { 'id': 'task_2', 'title': 'Weekly Report Prep', 'description': 'Prepare slide deck for management.', 'due_date': datetime.now().date() - timedelta(days=2), 'type': 'weekly', 'owner_id': 'bob', 'is_completed': False, },
    { 'id': 'task_3', 'title': 'Clean Database', 'description': 'Routine maintenance.', 'due_date': datetime.now().date().replace(day=5), 'type': 'monthly', 'owner_id': 'charlie', 'is_completed': False, }
]

# --- HELPER FUNCTIONS ---

def get_user_name(username):
    """Retrieves the full name of a user based on their username (which is now the owner_id)."""
    user_data = st.session_state.users.get(username)
    return user_data.get('name') if user_data else f"Unknown User ({username})"

# --- AUTHENTICATION FUNCTIONS ---

def authenticate_user(email, pin):
    """Authenticates user based on email and PIN."""
    # Find user by email and check PIN
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
    # Check if app is already initialized to prevent errors on rerun
    if not firebase_admin._apps:
        temp_file_name = None
        try:
            # Load service account credentials dictionary from Streamlit secrets
            cred_dict = st.secrets["firebase_key"] 
            
            # --- FINAL ROBUST FIX (Temporary File Method) ---
            # 1. Convert the Streamlit AttrDict object to a standard Python dict
            service_account_info = dict(cred_dict)

            # 2. Write the standard dict to a temporary JSON file.
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                json.dump(service_account_info, temp_file)
                # Store the file name to delete it later
                temp_file_name = temp_file.name

            # 3. Use the path to the temporary file for credentials.Certificate
            cred = credentials.Certificate(temp_file_name)
            
            firebase_admin.initialize_app(cred)
            st.session_state.db = firestore.client()
            
            # Clean up the temporary file immediately after successful initialization
            if temp_file_name and os.path.exists(temp_file_name):
                os.remove(temp_file_name)

        except Exception as e:
            # Clean up on failure as well
            if temp_file_name and os.path.exists(temp_file_name):
                os.remove(temp_file_name)
            st.error(f"🛑 Error initializing Firebase. Have you set up the 'firebase_key' secret correctly? Details: {e}")
            st.stop()
    # Ensure client is available in session state after initialization
    if 'db' not in st.session_state:
         st.session_state.db = firestore.client()

# --- DATA STORAGE (PERSISTENT - FIRESTORE) ---

# Firestore Collection and Document references
TASK_DOC_REF = 'team_tasks/all_tasks' 

def load_tasks_from_db():
    """Loads tasks from Firestore. Returns (tasks_list, is_mock_data_flag)."""
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
            # Process tasks loaded from Firestore
            for task in tasks_from_db:
                # Convert Firestore Timestamp (datetime.datetime) to Python date object
                if task.get('due_date') and hasattr(task['due_date'], 'date'):
                    task['due_date'] = task['due_date'].date()
                
                # Find the highest existing task ID for the counter
                if task['id'].startswith('task_'):
                    try:
                        max_id = max(max_id, int(task['id'].split('_')[1]))
                    except ValueError:
                        pass
            st.session_state.next_task_id = max_id + 1
            return tasks_from_db, False # Data loaded successfully

        else:
            # Document is empty or new, return initial mock data for bootstrap
            st.session_state.next_task_id = 4
            return INITIAL_MOCK_TASKS, True # Returning mock data, need to save it

    except Exception as e:
        st.error(f"Failed to load tasks from Firestore. Check connection: {e}")
        st.session_state.next_task_id = 1
        return [], False # Return empty list on failure

def save_tasks_to_db(tasks):
    """Saves the entire task list back to Firestore as an array in a single document."""
    initialize_firebase()
    db = st.session_state.db
    
    # 1. Prepare data for Firestore (convert Python date objects to datetime/Timestamp)
    data_to_save = []
    for task in tasks:
        task_copy = task.copy()
        
        due_date_value = task_copy.get('due_date')

        # Robust Type Check for Saving to Firestore:
        
        # 1. Check for valid Python datetime object (from Firestore load, is fine as-is)
        if isinstance(due_date_value, datetime):
            task_copy['due_date'] = due_date_value
        
        # 2. Check for valid Python date object (from st.date_input, needs conversion to datetime)
        # We now use the imported 'date' class directly:
        elif isinstance(due_date_value, date):
            # Convert Python date (YYYY-MM-DD) to datetime (Timestamp)
            task_copy['due_date'] = datetime.combine(due_date_value, datetime.min.time())
        
        # 3. Handle missing/invalid values (set to None)
        elif due_date_value is None or (isinstance(due_date_value, str) and not due_date_value):
             task_copy['due_date'] = None
        
        # 4. Catch-all: If it's none of the above, it's corrupt data; set to None.
        else:
            task_copy['due_date'] = None
            st.warning(f"Date for task {task_copy.get('id')} was corrupt ({type(due_date_value)}). Resetting to None before save.")
        
        data_to_save.append(task_copy)

    # 2. Save the entire list as an array field in a single document
    try:
        db.document(TASK_DOC_REF).set({'tasks': data_to_save})
    except Exception as e:
        st.error(f"Failed to save tasks to Firestore: {e}")


# --- DATA SETUP (Using Session State for App Run) ---

def initialize_tasks():
    """Initializes the task list and user list in Streamlit session state."""
    
    if 'users' not in st.session_state:
        st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
        
    # Initialize Tasks using the *actual* DB loader
    if 'tasks' not in st.session_state:
        # Load tasks and check if we are bootstrapping mock data
        tasks, is_mock_data = load_tasks_from_db()
        st.session_state.tasks = tasks
        
        # FIX: Bootstrap the database by saving the mock data immediately on the very first load
        if is_mock_data:
            save_tasks_to_db(st.session_state.tasks)
            st.toast("Database initialized with mock tasks!")
    
    # Initialize edit state
    if 'editing_task_id' not in st.session_state:
        st.session_state.editing_task_id = None
        
    if 'edit_form_key' not in st.session_state:
        st.session_state.edit_form_key = 0


# --- RECURRENCE LOGIC (Python Implementation) ---
# ... (Recurrence logic remains unchanged)
def day_difference(date1, date2):
    """Calculates the difference in days between two date objects."""
    # FIX: Ensure both date objects are used correctly in the check
    if isinstance(date1, datetime): date1 = date1.date()
    if isinstance(date2, datetime): date2 = date2.date()
    return abs((date2 - date1).days)

def is_task_due(task, target_date):
    """Checks if a task is due on a specific target date based on its recurrence type."""
    start_date = task['due_date']
    task_type = task['type']

    if target_date < start_date:
        return False
    
    if target_date == start_date:
        return True

    if task_type == 'one-time':
        return False

    if task_type == 'daily':
        return True
    
    if task_type == 'weekly':
        return target_date.weekday() == start_date.weekday()
    
    if task_type == 'bi-weekly':
        days_between = day_difference(target_date, start_date)
        return days_between % 14 == 0
    
    if task_type == 'monthly':
        return target_date.day == start_date.day
    
    return False

def get_next_occurrence(task, reference_date, days_limit=365):
    """Finds the next occurrence of a task within a days_limit."""
    
    next_date = reference_date
    end_date = reference_date + timedelta(days=days_limit)

    while next_date < end_date:
        if is_task_due(task, next_date):
            return next_date
        next_date += timedelta(days=1)
        
    return None

# --- UI COMPONENTS ---

def task_card(task, next_due_date, current_view, on_complete=None, index=None):
    """
    Displays a single task card with actions. 
    'index' is crucial for fixing the Duplicate Element Key error.
    """
    is_recurrent = task['type'] != 'one-time'
    recurrence_text = f"Repeats {task['type'].replace('-', ' ')}" if is_recurrent else 'One-time'
    
    # Determine card styling
    if task['is_completed']:
        card_style = "opacity: 0.6; background-color: #e5e7eb;"
        title_style = "text-decoration: line-through; color: #6b7280;"
    elif is_recurrent:
        card_style = "border-left: 4px solid #34d399; background-color: #ecfdf5;"
        title_style = "color: #1f2937;"
    else:
        card_style = "border-left: 4px solid #f87171; background-color: #fef2f2;"
        title_style = "color: #1f2937;"

    # Current user context for edit/delete permissions
    current_username = st.session_state.username
    is_admin = st.session_state.users[current_username]['role'] == 'admin'
    is_owner = task['owner_id'] == current_username
    can_edit_or_delete = is_admin or is_owner

    # Use index to make key absolutely unique in this specific view/loop
    unique_key_suffix = f"{task['id']}_{current_view}_{index if index is not None else ''}"

    col1, col2, col3, col4 = st.columns([0.5, 0.2, 0.15, 0.15])
    
    owner_name = get_user_name(task['owner_id'])

    with col1:
        st.markdown(f'<div style="{title_style} font-weight: bold; font-size: 16px;">{task["title"]}</div>', unsafe_allow_html=True)
        st.caption(f"Owned by: **{owner_name}** | {task['description'] if task['description'] else 'No description.'}")
        
    with col2:
        if next_due_date:
            st.markdown(f'<div style="font-weight: bold; font-size: 14px; text-align: right;">{next_due_date.strftime("%b %d")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size: 10px; text-align: right; color: #6b7280; text-transform: uppercase;">{recurrence_text}</div>', unsafe_allow_html=True)

    # Edit Button (Using the ultra-unique key suffix)
    with col3:
        if can_edit_or_delete:
            if st.button("Edit", key=f"edit_{unique_key_suffix}", help="Edit this task"):
                st.session_state.editing_task_id = task['id']
                st.session_state.edit_form_key += 1 
                st.rerun()

    # Done/Un-do or Delete Button (Using the ultra-unique key suffix)
    with col4:
        if current_view != 'All My Tasks' and is_owner:
            # Actionable view (Today/Upcoming) - show Done/Un-do
            if not task['is_completed']:
                st.button("Done", key=f"complete_{unique_key_suffix}", on_click=on_complete, args=(task['id'],), type="primary")
            else:
                st.button("Un-do", key=f"uncomplete_{unique_key_suffix}", on_click=on_complete, args=(task['id'],))
        elif can_edit_or_delete:
            # Non-actionable view (All Tasks) or not owner - show Delete
            if st.button("Delete", key=f"delete_{unique_key_suffix}", help="Delete this task forever"):
                delete_task(task['id'])

    st.markdown("---") # Simple separator

def delete_task(task_id):
    """Deletes a task by its ID."""
    st.session_state.tasks = [t for t in st.session_state.tasks if t['id'] != task_id]
    save_tasks_to_db(st.session_state.tasks) # Call save after modifying
    st.toast("Task deleted successfully!")
    st.rerun()

def find_task_by_id(task_id):
    """Finds a task dictionary by its ID."""
    return next((t for t in st.session_state.tasks if t['id'] == task_id), None)

def update_task(task_id, new_data):
    """Updates an existing task."""
    for i, task in enumerate(st.session_state.tasks):
        if task['id'] == task_id:
            st.session_state.tasks[i] = {**task, **new_data}
            st.toast(f"Task '{new_data['title']}' updated!")
            break
    save_tasks_to_db(st.session_state.tasks) # Call save after modifying
    st.session_state.editing_task_id = None
    st.rerun()

def edit_task_modal():
    """Modal/form for editing the task selected by st.session_state.editing_task_id."""
    task_id = st.session_state.editing_task_id
    if not task_id:
        return

    task = find_task_by_id(task_id)
    if not task:
        st.session_state.editing_task_id = None
        return

    # 1. Get current user info and role for assignment control
    current_username = st.session_state.username
    current_user_info = st.session_state.users[current_username]
    is_admin = current_user_info['role'] == 'admin'
    
    st.subheader(f"Editing Task: {task['title']}")
    
    with st.form(f"edit_task_form_{st.session_state.edit_form_key}", clear_on_submit=False):
        new_title = st.text_input("Title", value=task['title'])
        new_description = st.text_area("Description (Optional)", value=task['description'])
        
        # Recurrence and Date Column
        cols = st.columns(2)
        with cols[0]:
            # Ensure due_date is a date object for the date_input widget
            current_due_date = task['due_date'] if isinstance(task['due_date'], datetime) else datetime.combine(task['due_date'], datetime.min.time()).date()
            new_due_date = st.date_input("Due/Start Date", value=current_due_date)
        with cols[1]:
            type_index = TASK_TYPES.index(task['type']) if task['type'] in TASK_TYPES else 0
            new_task_type = st.selectbox("Recurrence", TASK_TYPES, index=type_index)
        
        # Assignment Logic
        assignee_id = task['owner_id']
        if is_admin:
            # Admin can re-assign the task
            all_usernames = list(st.session_state.users.keys())
            all_user_names = [st.session_state.users[uname]['name'] for uname in all_usernames]
            
            current_assignee_name = get_user_name(assignee_id)
            default_index = all_user_names.index(current_assignee_name) if current_assignee_name in all_user_names else 0
            
            selected_assignee_name = st.selectbox("Assignee (Admin Only)", all_user_names, index=default_index)
            assignee_id = next(uname for uname, u_data in st.session_state.users.items() if u_data['name'] == selected_assignee_name)
        else:
            st.caption(f"Assigned to: **{get_user_name(assignee_id)}** (Only Admins can change assignment)")
        
        # Action Buttons
        col_update, col_cancel = st.columns(2)
        with col_update:
            update_submitted = st.form_submit_button("Update Task", type="primary")
        with col_cancel:
            cancel_submitted = st.form_submit_button("Cancel")

        if update_submitted and new_title:
            new_data = {
                'title': new_title,
                'description': new_description,
                'due_date': new_due_date,
                'type': new_task_type,
                'owner_id': assignee_id,
            }
            update_task(task_id, new_data)

        if cancel_submitted:
            st.session_state.editing_task_id = None
            st.rerun()

def add_task_form():
    """Form for adding new tasks with conditional assignment."""
    
    # 1. Get current user info and role
    current_username = st.session_state.username
    current_user_info = st.session_state.users[current_username]
    is_admin = current_user_info['role'] == 'admin'
    
    # Only show the Add New Task expander if we are not currently editing
    if st.session_state.editing_task_id is None:
        with st.expander("➕ Add New Task"):
            with st.form("new_task_form", clear_on_submit=True):
                title = st.text_input("Title", key="title_input")
                description = st.text_area("Description (Optional)", key="desc_input")
                
                # Recurrence and Date Column
                cols = st.columns(2)
                with cols[0]:
                    due_date = st.date_input("Due/Start Date", value=datetime.now().date(), key="date_input")
                with cols[1]:
                    task_type = st.selectbox("Recurrence", TASK_TYPES, key="type_select")
                
                # Assignment Logic
                if is_admin:
                    st.markdown("---")
                    # Admin can assign to any user
                    all_usernames = list(st.session_state.users.keys())
                    all_user_names = [st.session_state.users[uname]['name'] for uname in all_usernames]
                    
                    # Find the current admin's full name to set as default selection
                    default_index = all_user_names.index(current_user_info['name'])
                    
                    selected_assignee_name = st.selectbox("Assignee (Admin Only)", all_user_names, key="assignee_select", index=default_index)
                    
                    # Reverse lookup the username from the name
                    assignee_id = next(uname for uname, u_data in st.session_state.users.items() if u_data['name'] == selected_assignee_name)
                else:
                    # Normal user is assigned the task automatically
                    assignee_id = current_username
                    st.caption(f"Task will be assigned to: **{current_user_info['name']}**")
                
                submitted = st.form_submit_button("Save Task", type="primary")

                if submitted and title:
                    # Use the session state counter to get a unique ID
                    new_id = f"task_{st.session_state.next_task_id}"
                    st.session_state.next_task_id += 1
                    
                    st.session_state.tasks.append({
                        'id': new_id,
                        'title': title,
                        'description': description,
                        'due_date': due_date,
                        'type': task_type,
                        'owner_id': assignee_id, # Use the determined assignee username
                        'is_completed': False,
                    })
                    save_tasks_to_db(st.session_state.tasks) # Call save after modifying
                    st.success(f"Task '{title}' added and assigned to {get_user_name(assignee_id)}!")
                elif submitted and not title:
                     st.error("Task title cannot be empty.")

def admin_only_user_management():
    """Admin-only interface for viewing team users."""

    current_user_info = st.session_state.users[st.session_state.username]
    is_admin = current_user_info['role'] == 'admin'

    if is_admin:
        st.header("Admin Tools")
        with st.expander("👥 View Team"):
            st.markdown("##### Current Users")
            # Convert user dictionary to a list of dicts for DataFrame display
            user_list = [{'Username': uname, 'Name': u_data['name'], 'Role': u_data['role'], 'Email': u_data['email'], 'PIN': u_data['pin']} 
                         for uname, u_data in st.session_state.users.items()]
            st.dataframe(user_list, use_container_width=True)

def dashboard_view():
    """Displays the Dashboard view with Today and Upcoming tasks (filtered by current user)."""
    st.subheader("Actionable Summary (My Tasks)")

    today = datetime.now().date()
    
    current_username = st.session_state.username
    # Dashboard always filters to only show tasks owned by the current user
    user_tasks = [task for task in st.session_state.tasks if task['owner_id'] == current_username]
    
    # 1. Calculate next due dates for all tasks
    tasks_with_next_date = []
    for task in user_tasks:
        next_date = get_next_occurrence(task, today, 365) 
        if next_date:
            tasks_with_next_date.append({
                **task,
                'next_due_date': next_date,
            })

    # 2. Filter into sections
    tasks_due_today = sorted(
        [t for t in tasks_with_next_date if t['next_due_date'] == today], 
        key=lambda x: x['title']
    )
    
    upcoming_tasks = sorted(
        [t for t in tasks_with_next_date if today < t['next_due_date'] <= today + timedelta(days=7)], 
        key=lambda x: x['next_due_date']
    )
    
    all_user_tasks = sorted(
        tasks_with_next_date, 
        key=lambda x: x['next_due_date']
    )

    def toggle_task_completion(task_id):
        """Toggles the completion status of a task by its ID."""
        for task in st.session_state.tasks:
            if task['id'] == task_id:
                task['is_completed'] = not task['is_completed']
                st.toast(f"Task '{task['title']}' updated!")
                break
        save_tasks_to_db(st.session_state.tasks) # Call save after modifying
        st.rerun() 

    # --- RENDER DASHBOARD SECTIONS ---
    
    st.markdown("### 🎯 Tasks Due Today")
    if tasks_due_today:
        for index, task in enumerate(tasks_due_today):
            task_card(task, task['next_due_date'], "Today", toggle_task_completion, index=index)
    else:
        st.info(f"Nothing due today for {get_user_name(current_username)}! 🎉")

    st.markdown("---")

    st.markdown("### 🗓️ Upcoming Tasks (Next 7 Days)")
    if upcoming_tasks:
        for index, task in enumerate(upcoming_tasks):
            task_card(task, task['next_due_date'], "Upcoming", toggle_task_completion, index=index)
    else:
        st.info(f"No upcoming tasks this week for {get_user_name(current_username)}.")

    st.markdown("---")
    
    st.markdown("### 📝 All My Tasks")
    if all_user_tasks:
        for index, task in enumerate(all_user_tasks):
            # We pass 'All My Tasks' as the current_view but still pass toggle_task_completion
            # to task_card. The card logic handles which buttons to show.
            task_card(task, task['next_due_date'], "All My Tasks", toggle_task_completion, index=index) 
    else:
        st.warning(f"{get_user_name(current_username)} has no tasks saved yet. Add one above!")


def calendar_view():
    """Displays the Calendar view with role-based filtering."""
    
    current_username = st.session_state.username
    current_user_info = st.session_state.users[current_username]
    is_admin = current_user_info['role'] == 'admin'

    st.subheader("Monthly Calendar")

    # Conditional Task Filter Control for Admin
    if is_admin:
        # Use session state to persist the filter choice
        if 'calendar_filter_radio' not in st.session_state:
             st.session_state.calendar_filter_radio = 'My Tasks'

        view_filter = st.radio(
            "Calendar View Filter",
            ('All Team Tasks', 'My Tasks'),
            key='calendar_filter_radio',
            horizontal=True
        )
    else:
        view_filter = 'My Tasks'
        st.caption("Showing tasks assigned to you.")
    
    # Set the list of tasks to check based on the filter
    if view_filter == 'All Team Tasks':
        tasks_to_check = st.session_state.tasks
    else: # 'My Tasks'
        tasks_to_check = [t for t in st.session_state.tasks if t['owner_id'] == current_username]
    
    # Current month navigation
    if 'calendar_date' not in st.session_state:
        st.session_state.calendar_date = datetime.now().date()

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("← Previous Month"):
            new_date = st.session_state.calendar_date.replace(day=1) - timedelta(days=1)
            st.session_state.calendar_date = new_date.replace(day=1)
    
    with col2:
        st.markdown(f"<h3 style='text-align: center;'>{st.session_state.calendar_date.strftime('%B %Y')}</h3>", unsafe_allow_html=True)

    with col3:
        if st.button("Next Month →"):
            next_month = st.session_state.calendar_date.month % 12 + 1
            next_year = st.session_state.calendar_date.year + (1 if next_month == 1 else 0)
            st.session_state.calendar_date = st.session_state.calendar_date.replace(month=next_month, year=next_year, day=1)

    st.markdown("---")
    
    current_date = st.session_state.calendar_date
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days = cal.monthdatescalendar(current_date.year, current_date.month)
    
    # Generate the calendar display
    days_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    # Render day names
    cols = st.columns(7)
    for i, day in enumerate(days_names):
        cols[i].markdown(f"**{day}**", help="Day of the week")

    # Render days
    for week in month_days:
        cols = st.columns(7)
        for i, day_date in enumerate(week):
            tasks_due = [t for t in tasks_to_check if is_task_due(t, day_date)]
            
            is_current_month = day_date.month == current_date.month
            is_today = day_date == datetime.now().date()
            
            style = ""
            if is_today:
                style = "background-color: #bfdbfe; border-radius: 8px; border: 2px solid #3b82f6;" 
            elif not is_current_month:
                style = "color: #9ca3af;" 

            task_summary = []
            for t in tasks_due:
                owner = get_user_name(t['owner_id']).split(' ')[0] 
                status = "✅" if t['is_completed'] else "☐"
                task_summary.append(f"{status} ({owner}): {t['title']}")

            content = f'<div style="text-align: center; height: 100%; padding: 5px; {style}">'
            content += f'<span style="font-weight: bold; font-size: 16px;">{day_date.day}</span><br>'
            
            if tasks_due:
                content += f'<span style="font-size: 12px; font-weight: bold; color: #10b981;">{len(tasks_due)} tasks</span>'
            else:
                content += '<span style="font-size: 10px; color: #9ca3af;">-</span>'

            content += '</div>'
            cols[i].markdown(content, unsafe_allow_html=True, help='\n'.join(task_summary) or "No tasks due.")
            
# --- MAIN APPLICATION CONTENT ---

def main_app_content(name, username):
    """The core logic of the task manager, displayed only after successful login."""
    
    st.title("TaskFlow Manager")
    
    # Initialize data store and user state (must run after successful selection)
    initialize_tasks()

    current_user = st.session_state.users[username]

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Navigation")
        view = st.radio("Select View", ['Dashboard', 'Calendar'])
        st.markdown("---")
        
        # User Info (Add logout button)
        st.info(f"**Current User:** {name} ({current_user['role'].capitalize()})")
        st.caption("Tasks are now saved persistently in **Firestore**.")
        
        st.markdown("---")
        
        # Logout Button
        st.button("Logout", on_click=logout, type="secondary")
        
        st.markdown("---")
        
        # Admin User View
        admin_only_user_management()
        
    # --- MAIN CONTENT ---
    # Show edit modal if a task is selected for editing
    if st.session_state.editing_task_id:
        edit_task_modal()
        st.markdown("---")

    add_task_form()
    st.markdown("---")

    if view == 'Dashboard':
        dashboard_view()
    elif view == 'Calendar':
        calendar_view()

# --- MAIN ENTRY POINT ---

def main():
    """Handles user login and then renders the main application."""
    st.set_page_config(layout="wide", page_title="TaskFlow Manager")

    # Initialize user structure and login state
    if 'users' not in st.session_state:
        st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
    if 'login_status' not in st.session_state:
        st.session_state.login_status = False
        st.session_state.username = None
        st.session_state.name = None

    st.sidebar.title("TaskFlow Manager")
    
    if st.session_state.login_status:
        # If logged in, proceed to main content
        name = st.session_state.name
        username = st.session_state.username
        main_app_content(name, username)
    else:
        # If logged out, show the custom login form
        st.title("Welcome to TaskFlow Manager")
        
        st.markdown("Please log in to continue.")
        
        with st.form("login_form"):
            st.sidebar.subheader("Login with Email & PIN")
            login_email = st.sidebar.text_input("Email", key="login_email")
            login_pin = st.sidebar.text_input("4-digit PIN", type="password", key="login_pin", max_chars=4)
            
            # Use columns to position the login button
            col1, col2 = st.sidebar.columns([1, 1])
            with col1:
                login_submitted = st.form_submit_button("Login", type="primary")

            if login_submitted:
                # Retrieve the values from the form inputs
                if login_email and login_pin:
                    authenticate_user(login_email, login_pin)
                else:
                    st.sidebar.error("Please enter both email and PIN.")

if __name__ == "__main__":
    main()
