import streamlit as st
from datetime import datetime, timedelta
import calendar
import streamlit_authenticator as stauth # Library for login/auth
import yaml
from yaml.loader import SafeLoader

# --- CONFIGURATION & CREDENTIALS ---

# Hashed password for the default password 'Password123!'
# NOTE: Users should change this immediately after logging in.
# FIX: Changed the hashing method from generate_password_hash() to the current standard generate()
DEFAULT_HASH = stauth.Hasher(['Password123!']).generate()[0]

# User credentials structure for the authenticator
USER_CREDENTIALS = {
    'credentials': {
        'usernames': {
            'mustafa': {'email': 'mustafa@team.com', 'name': 'Mustafa (Admin)', 'password': DEFAULT_HASH, 'role': 'admin', 'id': 'user_1'},
            'bob': {'email': 'bob@team.com', 'name': 'Bob (Team Lead)', 'password': DEFAULT_HASH, 'role': 'user', 'id': 'user_2'},
            'charlie': {'email': 'charlie@team.com', 'name': 'Charlie (Member)', 'password': DEFAULT_HASH, 'role': 'user', 'id': 'user_3'},
        }
    },
    'cookie': {
        'expiry_days': 30,
        'key': 'task_manager_cookie_key',
        'name': 'task_manager_cookie'
    },
    'preauthorized': {
        'emails': []
    }
}

# Task Types for the UI selection
TASK_TYPES = ['one-time', 'daily', 'weekly', 'bi-weekly', 'monthly']

# --- HELPER FUNCTIONS ---

def get_user_name(username):
    """Retrieves the full name of a user based on their username (which is now the owner_id)."""
    user_data = st.session_state.users.get(username)
    return user_data.get('name') if user_data else f"Unknown User ({username})"

# --- FIREBASE / DATA SETUP (Currently using Session State) ---

def initialize_tasks():
    """Initializes the task list and user list in Streamlit session state."""
    
    # Initialize the current user data from the loaded USER_CREDENTIALS structure
    if 'users' not in st.session_state:
        # Flatten the credentials structure for easier lookup (username -> data)
        st.session_state.users = USER_CREDENTIALS['credentials']['usernames']
        
    # Initialize Tasks
    if 'tasks' not in st.session_state:
        st.session_state.tasks = [
            # Task 1 (Mustafa - username 'mustafa')
            {
                'id': 'mock1',
                'title': 'Review Authentication',
                'description': 'Test the new login system.',
                'due_date': datetime.now().date(),
                'type': 'one-time',
                'owner_id': 'mustafa', 
                'is_completed': False,
            },
            # Task 2 (Bob - username 'bob')
            {
                'id': 'mock2',
                'title': 'Weekly Report Prep',
                'description': 'Prepare slide deck for management.',
                'due_date': datetime.now().date() - timedelta(days=2),
                'type': 'weekly',
                'owner_id': 'bob',
                'is_completed': False,
            },
            # Task 3 (Charlie - username 'charlie')
            {
                'id': 'mock3',
                'title': 'Clean Database',
                'description': 'Routine maintenance.',
                'due_date': datetime.now().date().replace(day=5),
                'type': 'monthly',
                'owner_id': 'charlie',
                'is_completed': False,
            }
        ]

# --- RECURRENCE LOGIC (Python Implementation) ---

def day_difference(date1, date2):
    """Calculates the difference in days between two date objects."""
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

def task_card(task, next_due_date, current_view, on_complete=None):
    """Displays a single task card."""
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

    col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
    
    owner_name = get_user_name(task['owner_id'])

    with col1:
        st.markdown(f'<div style="{title_style} font-weight: bold; font-size: 16px;">{task["title"]}</div>', unsafe_allow_html=True)
        st.caption(f"Owned by: **{owner_name}** | {task['description'] if task['description'] else 'No description.'}")
        
    with col2:
        if next_due_date:
            st.markdown(f'<div style="font-weight: bold; font-size: 14px; text-align: right;">{next_due_date.strftime("%b %d")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size: 10px; text-align: right; color: #6b7280; text-transform: uppercase;">{recurrence_text}</div>', unsafe_allow_html=True)

    with col3:
        # Completion toggle logic: only owner can toggle, and only in Dashboard actionable views
        if current_view != 'All My Tasks' and task['owner_id'] == st.session_state.username:
            if not task['is_completed']:
                st.button("Done", key=f"complete_{task['id']}_{current_view}", on_click=on_complete, args=(task['id'],))
            else:
                st.button("Un-do", key=f"uncomplete_{task['id']}_{current_view}", on_click=on_complete, args=(task['id'],))


    st.markdown("---") # Simple separator

def add_task_form():
    """Form for adding new tasks with conditional assignment."""
    
    # 1. Get current user info and role
    current_username = st.session_state.username
    current_user_info = st.session_state.users[current_username]
    is_admin = current_user_info['role'] == 'admin'
    
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
                # Add task to session state
                new_id = f"task_{len(st.session_state.tasks) + 1}"
                st.session_state.tasks.append({
                    'id': new_id,
                    'title': title,
                    'description': description,
                    'due_date': due_date,
                    'type': task_type,
                    'owner_id': assignee_id, # Use the determined assignee username
                    'is_completed': False,
                })
                st.success(f"Task '{title}' added and assigned to {get_user_name(assignee_id)}!")
            elif submitted and not title:
                 st.error("Task title cannot be empty.")

def admin_only_user_management():
    """Admin-only interface for creating users (currently disabled in auth context)."""
    # NOTE: In an authenticated app, user creation would typically use a registration form
    # and save to the database. We will keep this simple for now but limit it to viewing.

    current_user_info = st.session_state.users[st.session_state.username]
    is_admin = current_user_info['role'] == 'admin'

    if is_admin:
        st.header("Admin Tools")
        with st.expander("👥 View Team"):
            st.markdown("##### Current Users")
            # Convert user dictionary to a list of dicts for DataFrame display
            user_list = [{'Username': uname, 'Name': u_data['name'], 'Role': u_data['role']} 
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
        st.experimental_rerun() 

    # --- RENDER DASHBOARD SECTIONS ---
    
    st.markdown("### 🎯 Tasks Due Today")
    if tasks_due_today:
        for task in tasks_due_today:
            task_card(task, task['next_due_date'], "Today", toggle_task_completion)
    else:
        st.info(f"Nothing due today for {get_user_name(current_username)}! 🎉")

    st.markdown("---")

    st.markdown("### 🗓️ Upcoming Tasks (Next 7 Days)")
    if upcoming_tasks:
        for task in upcoming_tasks:
            task_card(task, task['next_due_date'], "Upcoming", toggle_task_completion)
    else:
        st.info(f"No upcoming tasks this week for {get_user_name(current_username)}.")

    st.markdown("---")
    
    st.markdown("### 📝 All My Tasks")
    if all_user_tasks:
        for task in all_user_tasks:
            task_card(task, task['next_due_date'], "All My Tasks", None) 
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

def main_app_content(name, username, authenticator):
    """The core logic of the task manager, displayed only after successful login."""
    
    st.title("TaskFlow Manager")
    
    # Initialize data store and user state (must run after successful login)
    initialize_tasks()

    current_user = st.session_state.users[username]

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Navigation")
        view = st.radio("Select View", ['Dashboard', 'Calendar'])
        st.markdown("---")
        
        # User Info and Logout
        st.info(f"**Logged in as:** {name} ({current_user['role'].capitalize()})")
        authenticator.logout('Logout', 'main')
        st.caption("Tasks are currently saved in browser session state.")
        
        st.markdown("---")
        
        # Admin User View
        admin_only_user_management()
        
        # Password Change
        with st.expander("🔑 Change Password"):
            # We must pass the credentials dictionary to update_user_details for it to work
            if authenticator.update_user_details(username, 'Update password'):
                # After successful change, update the session state for immediate use 
                # (in a real app, this would update the database/config file)
                st.session_state.users[username]['password'] = st.session_state['new_pass_hash']
                st.success('Password updated successfully! This change is temporary in this demo, please restart the app to revert.')
            
    # --- MAIN CONTENT ---
    add_task_form()
    st.markdown("---")

    if view == 'Dashboard':
        dashboard_view()
    elif view == 'Calendar':
        calendar_view()

# --- MAIN ENTRY POINT ---

def main():
    """Handles authentication and then renders the main application."""
    st.set_page_config(layout="wide", page_title="TaskFlow Manager")

    # Load and initialize the authenticator
    config = USER_CREDENTIALS
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

    # Attempt to authenticate the user
    name, authentication_status, username = authenticator.login('Login', 'main')

    if authentication_status:
        # Successful Login
        st.session_state.username = username
        main_app_content(name, username, authenticator)
    elif authentication_status == False:
        # Failed Login
        st.error('Username/password is incorrect')
    elif authentication_status == None:
        # Initial State: Waiting for login
        st.title("TaskFlow Manager - Login")
        st.warning('Please enter your username and password.')
        st.markdown("""
        ---
        **Demo Credentials:**
        * **Usernames:** `mustafa` (Admin), `bob` (User), `charlie` (User)
        * **Default Password (All):** `Password123!`
        """)

if __name__ == "__main__":
    main()
