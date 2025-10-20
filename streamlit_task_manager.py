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

# NEW: Priority Options and Sorting Order Mapping
PRIORITY_OPTIONS = ['High', 'Medium', 'Low']
PRIORITY_COLORS = {'High': '#ef4444', 'Medium': '#f59e0b', 'Low': '#3b82f6'} # Tailwind color mapping
# Dictionary to map priority strings to sortable numerical values (High=1, Low=3)
PRIORITY_SORT_MAP = {'High': 1, 'Medium': 2, 'Low': 3}

# Mock Category Data
MOCK_ACCOUNTS = ['Nike', 'Adidas', 'Puma', 'General']
MOCK_CAMPAIGNS = ['Holiday 2025', 'Q4 Launch', 'Brand Awareness']

# Define the initial mock tasks outside of functions
INITIAL_MOCK_TASKS = [
    # ADDED PRIORITY: 'High'
    { 'id': 'task_1', 'title': 'Review Authentication', 'description': 'Test the new login system.', 'due_date': datetime.now().date(), 'type': 'one-time', 'owner_id': 'mustafa', 'is_completed': False, 'account': 'Nike', 'campaign': 'Holiday 2025', 'priority': 'High' },
    # ADDED PRIORITY: 'Medium'
    { 'id': 'task_2', 'title': 'Weekly Report Prep', 'description': 'Prepare slide deck for management.', 'due_date': datetime.now().date() - timedelta(days=2), 'type': 'weekly', 'owner_id': 'bob', 'is_completed': False, 'account': 'Adidas', 'campaign': 'Q4 Launch', 'priority': 'Medium' },
    # ADDED PRIORITY: 'Low'
    { 'id': 'task_3', 'title': 'Clean Database', 'description': 'Routine maintenance.', 'due_date': datetime.now().date().replace(day=5), 'type': 'monthly', 'owner_id': 'charlie', 'is_completed': False, 'account': 'General', 'campaign': 'Brand Awareness', 'priority': 'Low' }
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
    # FIX: st.session_state.users is now guaranteed to be the latest from Firestore
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
    # Note: Streamlit session state (st.session_state) should persist across soft reruns.
    # Clearing it here and rerunning is the correct way to log out.
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
USER_DOC_REF = 'user_data/all_users' # New reference for user persistence
CATEGORY_DOC_REF = 'metadata/categories' # NEW reference for accounts/campaigns

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
                # Ensure priority is set, defaulting to 'Medium' if missing (for old tasks)
                if 'priority' not in task:
                    task['priority'] = 'Medium' 
                
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
        # Note: No specific success toast here as it fires frequently
    except Exception as e:
        st.error(f"Failed to save tasks to Firestore: {e}")

# --- USER DATA STORAGE (FIRESTORE) ---

def load_users_from_db():
    """Loads users from Firestore and stores them in session state. Returns is_mock_data_flag."""
    initialize_firebase()
    db = st.session_state.db
    
    is_mock_user_data = False
    
    try:
        doc = db.document(USER_DOC_REF).get()
        if doc.exists and doc.to_dict():
            users_from_db = doc.to_dict().get('users', SIMPLIFIED_USER_CREDENTIALS)
            st.session_state.users = users_from_db
        else:
            # Document is empty or new, use mock data
            st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
            is_mock_user_data = True

    except Exception as e:
        st.error(f"Failed to load users from Firestore. Defaulting to mock users. Details: {e}")
        st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
        is_mock_user_data = False # DB failed, using mock data, but don't force save/bootstrap
        
    return is_mock_user_data # Return the flag

def save_users_to_db(users_dict, context=""):
    """Saves the entire user dictionary back to Firestore in a single document."""
    initialize_firebase()
    db = st.session_state.db
    
    try:
        # Save the whole dictionary under the 'users' field
        db.document(USER_DOC_REF).set({'users': users_dict})
        # FIX: Adding success logging to confirm write operation
        if context:
            st.toast(f"User data saved successfully after {context}.")
    except Exception as e:
        # FIX: Provide context on failure
        st.error(f"Failed to save users to Firestore (Context: {context}): {e}")

# --- CATEGORY DATA STORAGE (FIRESTORE) ---

def load_categories_from_db():
    """Loads accounts and campaigns from Firestore. Returns (categories_dict, is_mock_data_flag)."""
    initialize_firebase()
    db = st.session_state.db
    
    try:
        doc = db.document(CATEGORY_DOC_REF).get()
        if doc.exists and doc.to_dict():
            return doc.to_dict(), False
        else:
            # Document is empty or new, return initial mock data for bootstrap
            mock_categories = {
                'accounts': MOCK_ACCOUNTS,
                'campaigns': MOCK_CAMPAIGNS
            }
            return mock_categories, True

    except Exception as e:
        st.error(f"Failed to load categories from Firestore. Defaulting to mock categories. Details: {e}")
        return {'accounts': MOCK_ACCOUNTS, 'campaigns': MOCK_CAMPAIGNS}, False

def save_categories_to_db(categories_dict, context=""):
    """Saves the entire categories dictionary back to Firestore."""
    initialize_firebase()
    db = st.session_state.db
    
    try:
        db.document(CATEGORY_DOC_REF).set(categories_dict)
        if context:
            st.toast(f"Category data saved successfully after {context}.")
    except Exception as e:
        st.error(f"Failed to save categories to Firestore (Context: {context}): {e}")


# --- DATA SETUP (Using Session State for App Run) ---

def initialize_tasks():
    """Initializes the task list and user list in Streamlit session state."""
    
    # 0. Initialize Categories first
    if 'categories' not in st.session_state:
        categories_dict, is_mock_category_data = load_categories_from_db()
        st.session_state.categories = categories_dict

        # Bootstrap: Save the initial mock categories to DB if they were just loaded
        if is_mock_category_data:
            save_categories_to_db(st.session_state.categories, context="initial category bootstrap")
            st.toast("Category database initialized with mock data!")
            
    # 1. Initialize Users (This is now done in main() during login. Only bootstrap/save here.)
    if 'users' not in st.session_state or len(st.session_state.users) == 0:
        is_mock_user_data = load_users_from_db() # Call to ensure st.session_state.users is populated
        
        # Bootstrap: Save the initial mock users to DB if they were just loaded
        if is_mock_user_data:
            # FIX: This ensures the initial mock users are written permanently to DB
            save_users_to_db(st.session_state.users, context="initial user bootstrap")
            
    # 2. Initialize Tasks from DB (KEEP CACHED for performance)
    if 'tasks' not in st.session_state:
        # Load tasks and check if we are bootstrapping mock data
        tasks, is_mock_data = load_tasks_from_db()
        st.session_state.tasks = tasks
        
        # FIX: Bootstrap the database by saving the mock data immediately on the very first load
        if is_mock_data:
            save_tasks_to_db(st.session_state.tasks)
            st.toast("Task database initialized with mock tasks!")
    
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
    
    # NEW: Get priority info for styling and display
    priority = task.get('priority', 'Medium')
    priority_color = PRIORITY_COLORS.get(priority, '#cccccc') # Default gray
    
    # Determine card styling
    if task['is_completed']:
        card_style = "opacity: 0.6; background-color: #e5e7eb;"
        title_style = "text-decoration: line-through; color: #6b7280;"
    elif is_recurrent:
        card_style = f"border-left: 4px solid {priority_color}; background-color: #ecfdf5;"
        title_style = "color: #1f2937;"
    else:
        # Use priority color for one-time tasks
        card_style = f"border-left: 4px solid {priority_color}; background-color: #fef2f2;"
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
        # NEW: Display Priority and Context
        priority_tag = f'<span style="color: {priority_color}; font-weight: bold;">{priority.upper()}</span>'
        context_text = f"**{task.get('account', 'No Account')}** / **{task.get('campaign', 'No Campaign')}** | Priority: {priority_tag} | "
        st.caption(f"{context_text}Owned by: **{owner_name}** | {task['description'] if task['description'] else 'No description.'}", unsafe_allow_html=True)
        
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
        cols = st.columns(3) # Increased columns to 3
        with cols[0]:
            # Ensure due_date is a date object for the date_input widget
            current_due_date = task['due_date'] if isinstance(task['due_date'], datetime) else datetime.combine(task['due_date'], datetime.min.time()).date()
            new_due_date = st.date_input("Due/Start Date", value=current_due_date)
        with cols[1]:
            type_index = TASK_TYPES.index(task['type']) if task['type'] in TASK_TYPES else 0
            new_task_type = st.selectbox("Recurrence", TASK_TYPES, index=type_index)
        with cols[2]:
            # NEW PRIORITY FIELD
            priority_index = PRIORITY_OPTIONS.index(task.get('priority', 'Medium')) if task.get('priority', 'Medium') in PRIORITY_OPTIONS else 1
            new_priority = st.selectbox("Priority", PRIORITY_OPTIONS, index=priority_index)
        
        # NEW: Account and Campaign Selection
        st.markdown("---")
        st.markdown("##### Project Context")
        cols_context = st.columns(2)
        
        with cols_context[0]:
            account_options = st.session_state.categories.get('accounts', [])
            account_index = account_options.index(task['account']) if task['account'] in account_options else 0
            new_account = st.selectbox("Account", account_options, index=account_index)

        with cols_context[1]:
            campaign_options = st.session_state.categories.get('campaigns', [])
            campaign_index = campaign_options.index(task['campaign']) if task['campaign'] in campaign_options else 0
            new_campaign = st.selectbox("Campaign", campaign_options, index=campaign_index)

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
                # NEW FIELDS
                'account': new_account,
                'campaign': new_campaign,
                'priority': new_priority, # SAVE NEW PRIORITY
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
                
                # Recurrence, Date, and Priority Column
                cols = st.columns(3) # Increased columns to 3
                with cols[0]:
                    due_date = st.date_input("Due/Start Date", value=datetime.now().date(), key="date_input")
                with cols[1]:
                    task_type = st.selectbox("Recurrence", TASK_TYPES, key="type_select")
                with cols[2]:
                    # NEW PRIORITY FIELD
                    new_priority = st.selectbox("Priority", PRIORITY_OPTIONS, key="priority_select")


                # NEW: Account and Campaign Selection
                st.markdown("---")
                st.markdown("##### Project Context")
                cols_context = st.columns(2)
                
                with cols_context[0]:
                    account_options = st.session_state.categories.get('accounts', [])
                    new_account = st.selectbox("Account", account_options, key="account_select")

                with cols_context[1]:
                    campaign_options = st.session_state.categories.get('campaigns', [])
                    new_campaign = st.selectbox("Campaign", campaign_options, key="campaign_select")
                
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
                        # NEW FIELDS
                        'account': new_account,
                        'campaign': new_campaign,
                        'priority': new_priority, # SAVE NEW PRIORITY
                    })
                    save_tasks_to_db(st.session_state.tasks) # Call save after modifying
                    st.success(f"Task '{title}' added and assigned to {get_user_name(assignee_id)}!")
                elif submitted and not title:
                    st.error("Task title cannot be empty.")

# --- ADMIN CATEGORY MANAGEMENT FORM ---

def category_management_form():
    """Admin interface for managing Account and Campaign categories."""
    current_username = st.session_state.username
    is_admin = st.session_state.users[current_username]['role'] == 'admin'

    if is_admin:
        with st.expander("📁 Manage Project Categories (Admin Only)", expanded=False):
            st.subheader("Edit Accounts and Campaigns")
            
            # Edit Accounts
            st.markdown("##### Accounts")
            current_accounts = ", ".join(st.session_state.categories['accounts'])
            # Add a unique key for the text_area to prevent Streamlit warnings/errors
            new_accounts_str = st.text_area("Edit Accounts (Comma Separated)", value=current_accounts, key="admin_edit_accounts_area")
            
            # Edit Campaigns
            st.markdown("##### Campaigns")
            current_campaigns = ", ".join(st.session_state.categories['campaigns'])
            new_campaigns_str = st.text_area("Edit Campaigns (Comma Separated)", value=current_campaigns, key="admin_edit_campaigns_area")
            
            if st.button("Save Categories", key="save_categories_button", type="primary"):
                # Process and clean input
                updated_accounts = [a.strip() for a in new_accounts_str.split(',') if a.strip()]
                updated_campaigns = [c.strip() for c in new_campaigns_str.split(',') if c.strip()]

                if updated_accounts and updated_campaigns:
                    st.session_state.categories['accounts'] = updated_accounts
                    st.session_state.categories['campaigns'] = updated_campaigns
                    save_categories_to_db(st.session_state.categories, context="categories updated")
                    st.success("Accounts and Campaigns updated and saved!")
                    st.rerun()
                else:
                    st.error("Please ensure both Accounts and Campaigns lists are not empty.")
            st.markdown("---")


# --- ADMIN USER CONTROL PAGE ---

def admin_user_control_page():
    """Admin interface for managing users: CRUD operations and role/pin changes."""
    st.title("👤 User Management (Admin Only)")
    
    # List all users
    user_list_data = []
    for uname, u_data in st.session_state.users.items():
        user_list_data.append({
            'Username': uname,
            'Name': u_data['name'],
            'Email': u_data['email'],
            'Role': u_data['role'],
            'PIN': u_data['pin'],
            'ID': u_data['id']
        })
    
    st.subheader("Current Team Members")
    st.dataframe(user_list_data, use_container_width=True)
    
    st.markdown("---")

    # The Category Management section was moved to category_management_form()
    
    # --- 1. ADD NEW USER FORM ---
    with st.expander("➕ Add New User", expanded=False):
        with st.form("add_user_form", clear_on_submit=True):
            st.subheader("Create New User")
            new_username = st.text_input("Username (must be unique)", key="new_username_input").lower()
            new_name = st.text_input("Display Name", key="new_name_input")
            new_email = st.text_input("Email", key="new_email_input").lower()
            
            col1, col2 = st.columns(2)
            with col1:
                new_pin = st.text_input("4-digit PIN (Default: 1234)", type="password", max_chars=4, key="new_pin_input", value="1234")
            with col2:
                new_role = st.selectbox("Role", ['user', 'admin'], key="new_role_select")

            add_submitted = st.form_submit_button("Add User", type="primary")

            if add_submitted:
                if new_username in st.session_state.users:
                    st.error("Error: Username already exists.")
                elif not new_username or not new_name or not new_email or len(new_pin) != 4:
                    st.error("Error: All fields are required, and PIN must be 4 digits.")
                else:
                    # Simple unique ID generation
                    new_user_id = f"user_{len(st.session_state.users) + 10}" 
                    
                    st.session_state.users[new_username] = {
                        'email': new_email,
                        'name': new_name,
                        'role': new_role,
                        'id': new_user_id,
                        'pin': new_pin
                    }
                    # FIX: Adding context to save call
                    save_users_to_db(st.session_state.users, context="new user added")
                    st.success(f"User '{new_name}' ({new_username}) added successfully!")
                    st.rerun()

    st.markdown("---")

    # --- 2. EDIT/DELETE EXISTING USER FORM ---
    if st.session_state.users:
        
        # Determine the list of users for the selector
        user_options = [u['name'] for u in st.session_state.users.values()]
        
        # Safely determine the selected user's name
        user_to_edit_name = st.selectbox("Select User to Edit or Delete", user_options, key="select_user_to_edit")
        
        # Safely find the corresponding username (key)
        user_to_edit_username = next(uname for uname, u_data in st.session_state.users.items() if u_data['name'] == user_to_edit_name)
        user_to_edit = st.session_state.users[user_to_edit_username].copy()
        
        st.subheader(f"Edit/Delete: {user_to_edit_name}")

        # FIX: Form key is now unique based on the selected user's username
        with st.form(f"edit_delete_user_form_{user_to_edit_username}", clear_on_submit=False):
            
            # Display current username/email (not editable)
            st.text_input("Username (Not Editable)", value=user_to_edit_username, disabled=True, key=f"username_display_{user_to_edit_username}")
            
            # Editable fields
            edited_name = st.text_input("Display Name", value=user_to_edit['name'], key=f"edit_name_{user_to_edit_username}")
            edited_email = st.text_input("Email", value=user_to_edit['email'], key=f"edit_email_{user_to_edit_username}").lower()
            
            col3, col4 = st.columns(2)
            with col3:
                role_index = ['user', 'admin'].index(user_to_edit['role']) if user_to_edit['role'] in ['user', 'admin'] else 0
                # FIX: Role is correctly loaded using the current user's role index
                edited_role = st.selectbox("Role", ['user', 'admin'], index=role_index, key=f"edit_role_{user_to_edit_username}")
            with col4:
                # PIN value is correctly loaded
                edited_pin = st.text_input("PIN (Change)", type="password", max_chars=4, value=user_to_edit['pin'], key=f"edit_pin_{user_to_edit_username}")

            # Action Buttons
            col_update, col_delete = st.columns(2)

            with col_update:
                edit_submitted = st.form_submit_button("Update User", type="primary")
            with col_delete:
                delete_submitted = st.form_submit_button("Delete User", type="secondary")


            if edit_submitted:
                if not edited_name or not edited_email or len(edited_pin) != 4:
                    st.error("Error: All fields are required, and PIN must be 4 digits.")
                else:
                    # Update the session state and save to DB
                    st.session_state.users[user_to_edit_username].update({
                        'name': edited_name,
                        'email': edited_email,
                        'role': edited_role,
                        'pin': edited_pin
                    })
                    # FIX: Adding context to save call
                    save_users_to_db(st.session_state.users, context="user details updated")
                    st.success(f"User '{edited_name}' updated successfully!")
                    st.rerun()
            
            if delete_submitted:
                if user_to_edit_username == st.session_state.username:
                    st.error("Cannot delete your own account while logged in!")
                else:
                    # Remove user from dict
                    del st.session_state.users[user_to_edit_username]
                    
                    # Also re-assign any tasks owned by the deleted user to the Admin
                    admin_username = st.session_state.username # Safer: Re-assign to currently logged-in Admin
                    tasks_reassigned = 0
                    for task in st.session_state.tasks:
                        if task['owner_id'] == user_to_edit_username:
                            task['owner_id'] = admin_username
                            tasks_reassigned += 1
                            
                    # Save both changes
                    save_users_to_db(st.session_state.users, context="user deleted") # FIX: Adding context
                    save_tasks_to_db(st.session_state.tasks)
                    st.success(f"User '{user_to_edit_name}' deleted. {tasks_reassigned} tasks reassigned to {get_user_name(admin_username)}.")
                    st.rerun()
    else:
        st.warning("No users found to edit or delete.")


def dashboard_view():
    """Displays the Dashboard view with Today and Upcoming tasks (filtered by current user)."""
    st.subheader("Actionable Summary (My Tasks)")

    today = datetime.now().date()
    
    current_username = st.session_state.username
    current_user_info = st.session_state.users[current_username]
    is_admin = current_user_info['role'] == 'admin'
    
    # Base list: filter to only show tasks owned by the current user
    # Note: This is an unused variable if Admin filter is active. Logic is consolidated below.
    # user_tasks = [task for task in st.session_state.tasks if task['owner_id'] == current_username]
    
    # --- 1. Filter Widgets ---
    account_options = st.session_state.categories.get('accounts', [])
    campaign_options = st.session_state.categories.get('campaigns', [])
    status_options = ['Incomplete', 'Completed']
    priority_options_filter = PRIORITY_OPTIONS # Use the defined options

    # Get all potential owners for Admin (Owner filter is only visible if the user is Admin)
    all_owner_names = [st.session_state.users[uname]['name'] for uname in st.session_state.users.keys()]
    all_owner_usernames = list(st.session_state.users.keys())

    
    with st.expander("🔍 Filter & Sort Tasks", expanded=False):
        
        # Row 1: Context Filters (Account/Campaign)
        st.markdown("##### Project Context Filters")
        filter_cols_1 = st.columns(2)
        with filter_cols_1[0]:
            selected_accounts = st.multiselect(
                "Account(s)", 
                options=account_options, 
                default=account_options,
                key='dash_account_filter'
            )
        with filter_cols_1[1]:
            selected_campaigns = st.multiselect(
                "Campaign(s)", 
                options=campaign_options, 
                default=campaign_options,
                key='dash_campaign_filter'
            )
        
        st.markdown("##### Status, Priority, and Team Filters")
        # Row 2: Status, Priority, Owner, and Sort
        filter_cols_2 = st.columns(4) # Increased columns to 4
        
        # Status Filter
        with filter_cols_2[0]:
            selected_status_names = st.multiselect(
                "Status",
                options=status_options,
                default=['Incomplete'], # Default to showing only incomplete tasks
                key='dash_status_filter'
            )
            # Convert status names to boolean logic
            is_completed_filter = {
                'Incomplete': False,
                'Completed': True
            }
            selected_statuses = [is_completed_filter[s] for s in selected_status_names]

        # Priority Filter (NEW)
        with filter_cols_2[1]:
            selected_priorities = st.multiselect(
                "Priority",
                options=priority_options_filter,
                default=priority_options_filter,
                key='dash_priority_filter'
            )

        # Owner Filter (Admin Only Feature)
        with filter_cols_2[2]:
            if is_admin:
                # Admin can filter by any user
                selected_owner_names = st.multiselect(
                    "Owner(s)", 
                    options=all_owner_names, 
                    default=all_owner_names,
                    key='dash_owner_filter'
                )
                # Convert names back to usernames (owner_id) for filtering
                selected_owners = [
                    uname for uname, u_data in st.session_state.users.items() 
                    if u_data['name'] in selected_owner_names
                ]
            else:
                # Regular user is always restricted to themselves, but need a default value
                selected_owners = [current_username]
                st.info("Showing only your tasks.")
        
        # Sort Control
        with filter_cols_2[3]:
            sort_by = st.selectbox(
                "Sort By",
                options=['Priority & Due Date', 'Due Date', 'Title'],
                key='dash_sort_select'
            )
        
        else:
        # Default filters if the expander is closed or not available
        selected_accounts = st.session_state.categories.get('accounts', [])
        selected_campaigns = st.session_state.categories.get('campaigns', [])
        selected_statuses = [False]
        selected_priorities = PRIORITY_OPTIONS
        selected_owners = [current_username]
        sort_by = 'Priority & Due Date' # Default sort

    # --- End Filter Widgets ---
    
    # --- 2. Apply Filters ---
    
    # Determine the base list based on role (Admin sees ALL tasks if viewing All Team Tasks in Calendar view, otherwise, filter by current user)
    # The dashboard view *always* defaults to the user's tasks unless an admin manually selects other owners in the filter.
    base_tasks_to_filter = st.session_state.tasks


    filtered_tasks = [
        task for task in base_tasks_to_filter
        if task.get('account') in selected_accounts and 
           task.get('campaign') in selected_campaigns and
           task.get('is_completed') in selected_statuses and
           task.get('owner_id') in selected_owners and
           task.get('priority') in selected_priorities # NEW PRIORITY FILTER
    ]
    
    # 3. Calculate next due dates for all tasks
    tasks_with_next_date = []
    for task in filtered_tasks: # Use filtered_tasks here
        next_date = get_next_occurrence(task, today, 365) 
        if next_date:
            tasks_with_next_date.append({
                **task,
                'next_due_date': next_date,
            })

    # 4. Apply Sorting
    if sort_by == 'Priority & Due Date':
        # Sort first by priority number (1=High) and then by due date
        sort_key = lambda x: (PRIORITY_SORT_MAP.get(x.get('priority', 'Medium'), 2), x['next_due_date'])
    elif sort_by == 'Due Date':
        sort_key = lambda x: x['next_due_date']
    else: # Title
        sort_key = lambda x: x['title']

    sorted_tasks = sorted(tasks_with_next_date, key=sort_key)


    # 5. Filter into Dashboard Sections (using the sorted list)
    tasks_due_today = [t for t in sorted_tasks if t['next_due_date'] == today]
    upcoming_tasks = [t for t in sorted_tasks if today < t['next_due_date'] <= today + timedelta(days=7)]
    all_user_tasks = sorted_tasks # This is already sorted and filtered

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
    
    st.markdown("### 📝 All Filtered Tasks")
    if all_user_tasks:
        for index, task in enumerate(all_user_tasks):
            # We pass 'All My Tasks' as the current_view but still pass toggle_task_completion
            # to task_card. The card logic handles which buttons to show.
            task_card(task, task['next_due_date'], "All My Tasks", toggle_task_completion, index=index) 
    else:
        st.warning(f"No tasks match the current filter criteria.")


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
    
    # Set the base list of tasks to check based on the user filter
    if view_filter == 'All Team Tasks':
        base_tasks = st.session_state.tasks
    else: # 'My Tasks'
        base_tasks = [t for t in st.session_state.tasks if t['owner_id'] == current_username]
    
    
    # --- 1. Filter Widgets ---
    account_options = st.session_state.categories.get('accounts', [])
    campaign_options = st.session_state.categories.get('campaigns', [])
    status_options = ['Incomplete', 'Completed']
    priority_options_filter = PRIORITY_OPTIONS
    all_owner_names = [st.session_state.users[uname]['name'] for uname in st.session_state.users.keys()]


    with st.expander("🔍 Filter Calendar", expanded=True): # Calendar filter often expanded
        filter_cols_1 = st.columns(2)
        
        with filter_cols_1[0]:
            cal_selected_accounts = st.multiselect(
                "Account(s)", 
                options=account_options, 
                default=account_options,
                key='cal_account_filter'
            )
        with filter_cols_1[1]:
            cal_selected_campaigns = st.multiselect(
                "Campaign(s)", 
                options=campaign_options, 
                default=campaign_options,
                key='cal_campaign_filter'
            )
        
        st.markdown("---")
        filter_cols_2 = st.columns(3) # Increased columns to 3
        
        # Status Filter
        with filter_cols_2[0]:
            cal_selected_status_names = st.multiselect(
                "Status",
                options=status_options,
                default=status_options,
                key='cal_status_filter'
            )
            cal_is_completed_filter = {
                'Incomplete': False,
                'Completed': True
            }
            cal_selected_statuses = [cal_is_completed_filter[s] for s in cal_selected_status_names]

        # Priority Filter (NEW)
        with filter_cols_2[1]:
            cal_selected_priorities = st.multiselect(
                "Priority",
                options=priority_options_filter,
                default=priority_options_filter,
                key='cal_priority_filter'
            )

        # Owner Filter (Admin Only Feature)
        with filter_cols_2[2]:
            if is_admin:
                # Admin can filter by any user
                cal_selected_owner_names = st.multiselect(
                    "Owner(s)", 
                    options=all_owner_names, 
                    default=all_owner_names,
                    key='cal_owner_filter'
                )
                cal_selected_owners = [
                    uname for uname, u_data in st.session_state.users.items() 
                    if u_data['name'] in cal_selected_owner_names
                ]
            else:
                # Regular user is always restricted to themselves
                cal_selected_owners = [current_username]
                st.caption("Owner filter restricted to your tasks.")
    
    # Default filters if the expander is not used
    # This block is not necessary as filters have defaults set above if the expander is present.
    # We will trust the multiselect defaults for a simpler implementation.
    
    # --- 2. Apply Filters to Base Task List ---
    tasks_to_check = [
        task for task in base_tasks
        if task.get('account') in cal_selected_accounts and 
           task.get('campaign') in cal_selected_campaigns and
           task.get('is_completed') in cal_selected_statuses and
           task.get('owner_id') in cal_selected_owners and
           task.get('priority') in cal_selected_priorities # NEW PRIORITY FILTER
    ]
    # --- End Apply Filters ---

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
            # Use the filtered tasks_to_check list
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
                # NEW: Add Priority to summary help text
                priority_symbol = "🔥" if t.get('priority') == 'High' else "🟡" if t.get('priority') == 'Medium' else "🧊"
                task_summary.append(f"{priority_symbol} {status} ({owner}): {t['title']}")

            content = f'<div style="text-align: center; height: 100%; padding: 5px; {style}">'
            content += f'<span style="font-weight: bold; font-size: 16px;">{day_date.day}</span><br>'
            
            if tasks_due:
                # NEW: Color based on highest priority due that day
                highest_priority = min(PRIORITY_SORT_MAP.get(t.get('priority', 'Medium'), 2) for t in tasks_due)
                color_for_day = PRIORITY_COLORS.get(PRIORITY_OPTIONS[highest_priority - 1], '#10b981')
                content += f'<span style="font-size: 12px; font-weight: bold; color: {color_for_day};">{len(tasks_due)} tasks</span>'
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
        # Define view options in session state for cross-page navigation
        if 'view' not in st.session_state:
            st.session_state.view = 'Dashboard'
        
        admin_options = ['Dashboard', 'Calendar', 'User Management']
        user_options = ['Dashboard', 'Calendar']
            
        view_options = admin_options if current_user['role'] == 'admin' else user_options
        
        # Determine the default index for the radio button
        try:
            default_index = view_options.index(st.session_state.view)
        except ValueError:
            # Fallback if the view is not authorized (e.g., user logs in and view was 'User Management')
            st.session_state.view = 'Dashboard'
            default_index = 0

        view = st.radio("Select View", view_options, index=default_index)
        
        st.session_state.view = view # Update session state view
        
        st.markdown("---")
        
        # User Info (Add logout button)
        st.info(f"**Current User:** {name} ({current_user['role'].capitalize()})")
        st.caption("Tasks are now saved persistently in **Firestore**.")
        
        st.markdown("---")
        
        # Logout Button
        st.button("Logout", on_click=logout, type="secondary")
        
        st.markdown("---")
        
        # Admin Tools Header and Code Viewer
        if current_user['role'] == 'admin':
            st.subheader("Admin Tools")
            with st.expander("🛠️ Developer Tools"):
                st.code(
                    """
                    # Core Task Functions
                    def delete_task(task_id):
                        # ...
                    def update_task(task_id, new_data):
                        # ...
                    """, language="python"
                )

        
    # --- MAIN CONTENT ---
    
    view_selected = st.session_state.view
    
    # Map views to functions for dictionary lookup
    VIEWS = {
        'Dashboard': dashboard_view,
        'Calendar': calendar_view,
        'User Management': admin_user_control_page
    }
    
    # --- 1. AUTHORIZATION GATE ---
    is_admin = current_user['role'] == 'admin'
    
    if view_selected == 'User Management' and not is_admin:
        st.error("You are not authorized to view User Management. Resetting to Dashboard.")
        st.session_state.view = 'Dashboard'
        st.rerun() # Exit the script run

    # --- 2. RENDER FORMS (Conditional on Dashboard/Calendar views) ---
    if view_selected in ['Dashboard', 'Calendar']:
        if is_admin:
            category_management_form()
        
        if st.session_state.editing_task_id:
            edit_task_modal()
            st.markdown("---")
        
        add_task_form()
        st.markdown("---")

    # --- 3. RENDER MAIN VIEW (Safe Dictionary Lookup) ---
    # We are guaranteed to be authorized at this point (or redirected), so just execute the view.
    if view_selected in VIEWS:
        VIEWS[view_selected]()


# --- MAIN ENTRY POINT ---

def main():
    """Handles user login and then renders the main application."""
    st.set_page_config(layout="wide", page_title="TaskFlow Manager")

    # Initialize user structure and login state
    if 'users' not in st.session_state:
        st.session_state.users = SIMPLIFIED_USER_CREDENTIALS
    if 'login_status' not in st.session_state:
        st.session_state.login_status = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'name' not in st.session_state:
        st.session_state.name = None
    
    st.sidebar.title("TaskFlow Manager")
    
    if st.session_state.login_status and st.session_state.username and st.session_state.username in st.session_state.users:
        # If logged in and user exists (session state is intact), proceed to main content
        name = st.session_state.name
        username = st.session_state.username
        main_app_content(name, username)
    else:
        # If logged out or session state lost, show the custom login form
        st.title("Welcome to TaskFlow Manager")
        st.markdown("Please log in to continue using the form in the sidebar.")
        
        with st.sidebar: # FIX: Form context is now correctly inside the sidebar
            with st.form("login_form"):
                st.subheader("Login with Email & PIN")
                login_email = st.text_input("Email", key="login_email")
                login_pin = st.text_input("4-digit PIN", type="password", key="login_pin", max_chars=4)
                
                # Use columns to position the login button
                col1, col2 = st.columns([1, 1])
                with col1:
                    login_submitted = st.form_submit_button("Sign In", type="primary") 

                if login_submitted:
                    # Retrieve the values from the form inputs
                    if login_email and login_pin:
                        # FIX: This now ensures st.session_state.users is populated
                        # with the latest user data from Firestore BEFORE authentication.
                        load_users_from_db() 
                        authenticate_user(login_email, login_pin)
                    else:
                        st.error("Please enter both email and PIN.")

if __name__ == "__main__":
    main()
