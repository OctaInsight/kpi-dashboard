# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from io import BytesIO
import base64

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    st.error("⚠️ Supabase library not installed. Run: pip install supabase")

# -------------------------------------------------------------
# Supabase connection (Postgres via Supabase REST client)
# -------------------------------------------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    """Initialize Supabase client with error handling"""
    try:
        # Check if secrets are configured
        if "supabase" not in st.secrets:
            st.error("❌ Supabase credentials not found in secrets.toml")
            st.info("""
            Please add the following to .streamlit/secrets.toml:
            
            [supabase]
            url = "your-project-url"
            key = "your-anon-key"
            """)
            st.stop()
        
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        
        if not url or not key:
            st.error("❌ Supabase URL or Key is empty")
            st.stop()
        
        client = create_client(url, key)
        
        # Test connection
        try:
            client.table("kpis").select("id", count="exact").limit(1).execute()
        except Exception as e:
            st.error(f"❌ Failed to connect to Supabase: {str(e)}")
            st.info("Please check your Supabase credentials and ensure the 'kpis' table exists.")
            st.stop()
        
        return client
    except Exception as e:
        st.error(f"❌ Error initializing Supabase: {str(e)}")
        st.stop()


# -------------------------------------------------------------
# Page configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="Project KPI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Session state
# -------------------------------------------------------------
if "authenticated_projects" not in st.session_state:
    st.session_state.authenticated_projects = set()
if "current_page" not in st.session_state:
    st.session_state.current_page = "main"
if "selected_kpi" not in st.session_state:
    st.session_state.selected_kpi = None
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None

# -------------------------------------------------------------
# Project passwords (read from secrets)
# -------------------------------------------------------------
try:
    PROJECT_PASSWORDS = dict(st.secrets.get("project_passwords", {}))
    if not PROJECT_PASSWORDS:
        st.warning("⚠️ No project passwords configured in secrets.toml")
        PROJECT_PASSWORDS = {"Demo Project": "demo123"}  # Fallback for testing
except Exception as e:
    st.error(f"Error loading project passwords: {e}")
    PROJECT_PASSWORDS = {"Demo Project": "demo123"}

# -------------------------------------------------------------
# Color schemes for charts
# -------------------------------------------------------------
COLOR_SCHEMES = {
    "Blue Tones": {
        'bar_colors': ['#1f77b4', '#aec7e8', '#3498db', '#5dade2', '#85c1e9'],
        'background': '#f8f9fa',
        'text_color': '#2c3e50',
        'grid_color': '#e0e0e0',
        'success': '#2ca02c',
        'warning': '#ff7f0e',
        'danger': '#d62728'
    },
    "Ocean": {
        'bar_colors': ['#006994', '#4FC3F7', '#0288D1', '#03A9F4', '#4DD0E1'],
        'background': '#E0F7FA',
        'text_color': '#004D40',
        'grid_color': '#B2EBF2',
        'success': '#00897B',
        'warning': '#FFA726',
        'danger': '#E53935'
    },
    "Sunset": {
        'bar_colors': ['#FF6B6B', '#FFB347', '#FF8C42', '#FFA07A', '#FF7F50'],
        'background': '#FFF5E6',
        'text_color': '#8B4513',
        'grid_color': '#FFE4B5',
        'success': '#4ECDC4',
        'warning': '#FFD93D',
        'danger': '#C0392B'
    },
    "Forest": {
        'bar_colors': ['#2E7D32', '#66BB6A', '#43A047', '#66BB6A', '#81C784'],
        'background': '#E8F5E9',
        'text_color': '#1B5E20',
        'grid_color': '#C8E6C9',
        'success': '#1B5E20',
        'warning': '#F57C00',
        'danger': '#C62828'
    },
    "Purple Dream": {
        'bar_colors': ['#7B1FA2', '#BA68C8', '#9C27B0', '#AB47BC', '#CE93D8'],
        'background': '#F3E5F5',
        'text_color': '#4A148C',
        'grid_color': '#E1BEE7',
        'success': '#00897B',
        'warning': '#FFA726',
        'danger': '#E53935'
    },
    "Monochrome": {
        'bar_colors': ['#424242', '#9E9E9E', '#616161', '#757575', '#BDBDBD'],
        'background': '#FAFAFA',
        'text_color': '#212121',
        'grid_color': '#E0E0E0',
        'success': '#616161',
        'warning': '#757575',
        'danger': '#212121'
    },
    "Dark Mode": {
        'bar_colors': ['#64B5F6', '#81C784', '#FFB74D', '#E57373', '#BA68C8'],
        'background': '#1e1e1e',
        'text_color': '#ffffff',
        'grid_color': '#404040',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'danger': '#F44336'
    },
    "Warm Autumn": {
        'bar_colors': ['#D84315', '#F4511E', '#FF6F00', '#FB8C00', '#FFA726'],
        'background': '#FFF3E0',
        'text_color': '#BF360C',
        'grid_color': '#FFE0B2',
        'success': '#7CB342',
        'warning': '#FFA000',
        'danger': '#D32F2F'
    }
}

# -------------------------------------------------------------
# KPI Status calculation
# -------------------------------------------------------------
def calculate_kpi_status(current_value, target_value, start_date, end_date):
    """Calculate if KPI is on-track, at-risk, or off-track"""
    try:
        current_value = float(current_value)
        target_value = float(target_value)
    except (TypeError, ValueError):
        return "Not Started"

    if target_value <= 0:
        return "Not Started"

    if current_value >= target_value:
        return "Achieved"
    
    today = datetime.now().date()
    total_days = (end_date - start_date).days
    elapsed_days = (today - start_date).days
    
    if elapsed_days <= 0 or total_days <= 0:
        return "Not Started"
    
    expected_progress = (elapsed_days / total_days) * target_value
    if expected_progress <= 0:
        return "Not Started"
    
    progress_ratio = current_value / expected_progress
    
    if progress_ratio >= 0.9:
        return "On Track"
    elif progress_ratio >= 0.7:
        return "At Risk"
    else:
        return "Delayed"

# -------------------------------------------------------------
# Data Management Functions (Supabase)
# -------------------------------------------------------------
def df_from_supabase_rows(rows):
    """Convert Supabase rows into DataFrame with old column names."""
    if not rows:
        return pd.DataFrame(columns=[
            'id',
            'Project', 'KPI', 'Work Package', 'Target', 'Current Value',
            'Achievement Date', 'Male Count', 'Female Count', 'Comments',
            'Start Date', 'End Date', 'Timestamp'
        ])
    df = pd.DataFrame(rows)
    # Ensure all expected columns exist
    for col in [
        'project', 'kpi', 'work_package', 'target', 'current_value',
        'achievement_date', 'male_count', 'female_count', 'comments',
        'start_date', 'end_date', 'created_at', 'id'
    ]:
        if col not in df.columns:
            df[col] = None
    df = df.rename(columns={
        'project': 'Project',
        'kpi': 'KPI',
        'work_package': 'Work Package',
        'target': 'Target',
        'current_value': 'Current Value',
        'achievement_date': 'Achievement Date',
        'male_count': 'Male Count',
        'female_count': 'Female Count',
        'comments': 'Comments',
        'start_date': 'Start Date',
        'end_date': 'End Date',
        'created_at': 'Timestamp'
    })
    return df


def save_kpi_data(project_name, data):
    """Insert new KPI row into Supabase kpis table."""
    try:
        supabase = get_supabase_client()
        payload = {
            "project": project_name,
            "kpi": data["KPI"],
            "work_package": data["Work Package"],
            "target": float(data["Target"]),
            "current_value": float(data["Current Value"]),
            "achievement_date": data["Achievement Date"],
            "male_count": int(data.get("Male Count")) if data.get("Male Count") not in ["", None] else None,
            "female_count": int(data.get("Female Count")) if data.get("Female Count") not in ["", None] else None,
            "comments": data.get("Comments", ""),
            "start_date": data["Start Date"],
            "end_date": data["End Date"],
        }
        res = supabase.table("kpis").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False


def load_kpi_data(project_name):
    """Load KPI data for a specific project from Supabase."""
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("kpis")
            .select("*")
            .eq("project", project_name)
            .order("created_at", desc=False)
            .execute()
        )
        rows = res.data if hasattr(res, 'data') else []
        return df_from_supabase_rows(rows)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return df_from_supabase_rows([])


def load_all_projects_data():
    """Load KPI data from all projects."""
    try:
        supabase = get_supabase_client()
        res = supabase.table("kpis").select("*").order("created_at", desc=False).execute()
        rows = res.data if hasattr(res, 'data') else []
        return df_from_supabase_rows(rows)
    except Exception as e:
        st.error(f"Error loading all data: {e}")
        return df_from_supabase_rows([])


def update_kpi_data(project_name, row_id, updated_data):
    """Update an existing KPI row in Supabase using its id."""
    try:
        supabase = get_supabase_client()
        payload = {
            "work_package": updated_data["Work Package"],
            "target": float(updated_data["Target"]),
            "current_value": float(updated_data["Current Value"]),
            "achievement_date": updated_data["Achievement Date"],
            "male_count": int(updated_data.get("Male Count")) if updated_data.get("Male Count") not in ["", None] else None,
            "female_count": int(updated_data.get("Female Count")) if updated_data.get("Female Count") not in ["", None] else None,
            "comments": updated_data.get("Comments", ""),
            "start_date": updated_data["Start Date"],
            "end_date": updated_data["End Date"],
        }
        res = (
            supabase.table("kpis")
            .update(payload)
            .eq("id", row_id)
            .eq("project", project_name)
            .execute()
        )
        return True
    except Exception as e:
        st.error(f"Error updating data: {e}")
        return False


def get_available_projects():
    """Get distinct list of project names from Supabase."""
    try:
        supabase = get_supabase_client()
        res = supabase.table("kpis").select("project").execute()
        rows = res.data if hasattr(res, 'data') else []
        projects = sorted({row["project"] for row in rows if row.get("project")})
        return projects
    except Exception as e:
        st.error(f"Error loading projects: {e}")
        return []

# -------------------------------------------------------------
# Authentication
# -------------------------------------------------------------
def authenticate_project(project_name):
    """Check if user is authenticated for project"""
    return project_name in st.session_state.authenticated_projects

def login_project(project_name, password):
    """Authenticate user for a project"""
    if PROJECT_PASSWORDS.get(project_name) == password:
        st.session_state.authenticated_projects.add(project_name)
        return True
    return False

# -------------------------------------------------------------
# Visualization Functions
# -------------------------------------------------------------
def create_kpi_overview_chart(df, chart_type, color_scheme_name, project_name):
    """Create overview chart for all KPIs in a project"""
    project_data = df[df['Project'] == project_name].copy()
    
    if project_data.empty:
        return None
    
    # Get latest entry for each KPI
    if 'Timestamp' in project_data.columns:
        project_data = project_data.sort_values('Timestamp')
    project_data = project_data.groupby('KPI').last().reset_index()
    
    # Calculate progress percentage
    project_data['Progress %'] = (
        project_data['Current Value'] / project_data['Target'] * 100
    ).round(2)
    
    # Calculate status
    project_data['Status'] = project_data.apply(
        lambda row: calculate_kpi_status(
            row['Current Value'], 
            row['Target'],
            pd.to_datetime(row['Start Date']).date() if row['Start Date'] else date.today(),
            pd.to_datetime(row['End Date']).date() if row['End Date'] else date.today()
        ), axis=1
    )
    
    colors = COLOR_SCHEMES[color_scheme_name]
    
    status_colors = {
        'Achieved': '#00CC66',
        'On Track': colors['bar_colors'][0],
        'At Risk': colors['warning'],
        'Delayed': colors['danger'],
        'Not Started': '#CCCCCC'
    }
    
    if chart_type == "Bar Chart":
        fig = px.bar(
            project_data, x='KPI', y='Progress %', 
            color='Status',
            color_discrete_map=status_colors,
            title=f'KPI Progress Overview - {project_name}',
            labels={'Progress %': 'Progress (%)'},
            text='Progress %'
        )
        fig.add_hline(
            y=100, line_dash="dash", line_color=colors['success'], 
            annotation_text="Target"
        )
        
    elif chart_type == "Histogram":
        fig = px.histogram(
            project_data, x='KPI', y='Progress %',
            color='Status',
            color_discrete_map=status_colors,
            title=f'KPI Progress Overview - {project_name}',
            labels={'Progress %': 'Progress (%)'}
        )
        fig.add_hline(y=100, line_dash="dash", line_color=colors['success'])
        
    elif chart_type == "Scatter Plot":
        fig = px.scatter(
            project_data, x='KPI', y='Progress %',
            size='Current Value', color='Status',
            color_discrete_map=status_colors,
            title=f'KPI Progress Overview - {project_name}'
        )
        fig.add_hline(y=100, line_dash="dash", line_color=colors['success'])
    
    fig.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        height=500,
        xaxis_tickangle=-45,
        font=dict(color=colors['text_color'], size=12),
        title_font=dict(color=colors['text_color'], size=18),
        xaxis=dict(
            gridcolor=colors['grid_color'],
            color=colors['text_color']
        ),
        yaxis=dict(
            gridcolor=colors['grid_color'],
            color=colors['text_color']
        )
    )
    
    return fig


def create_status_pie_chart(df, project_name, color_scheme_name):
    """Create pie chart showing KPI status distribution"""
    project_data = df[df['Project'] == project_name].copy()
    
    if project_data.empty:
        return None
    
    if 'Timestamp' in project_data.columns:
        project_data = project_data.sort_values('Timestamp')
    project_data = project_data.groupby('KPI').last().reset_index()
    
    project_data['Status'] = project_data.apply(
        lambda row: calculate_kpi_status(
            row['Current Value'], 
            row['Target'],
            pd.to_datetime(row['Start Date']).date() if row['Start Date'] else date.today(),
            pd.to_datetime(row['End Date']).date() if row['End Date'] else date.today()
        ), axis=1
    )
    
    status_counts = project_data['Status'].value_counts()
    colors = COLOR_SCHEMES[color_scheme_name]
    
    status_colors = {
        'Achieved': '#00CC66',
        'On Track': colors['bar_colors'][0],
        'At Risk': colors['warning'],
        'Delayed': colors['danger'],
        'Not Started': '#CCCCCC'
    }
    
    fig = px.pie(
        values=status_counts.values, names=status_counts.index,
        title=f'KPI Status Distribution - {project_name}',
        color=status_counts.index,
        color_discrete_map=status_colors
    )
    
    fig.update_layout(
        paper_bgcolor=colors['background'],
        height=400,
        font=dict(color=colors['text_color'], size=12),
        title_font=dict(color=colors['text_color'], size=16)
    )
    return fig


def create_detailed_kpi_charts(df, project_name, kpi_name, color_scheme_name):
    """Create detailed charts for a specific KPI"""
    kpi_data = df[(df['Project'] == project_name) & (df['KPI'] == kpi_name)].copy()
    
    if kpi_data.empty:
        return None, None, None, None
    
    if 'Timestamp' in kpi_data.columns:
        kpi_data = kpi_data.sort_values('Timestamp')
    colors = COLOR_SCHEMES[color_scheme_name]
    
    latest_data = kpi_data.iloc[-1].to_dict()
    
    # Chart 1: Current vs Target
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        name='Current Value',
        x=[kpi_name],
        y=[latest_data['Current Value']],
        marker_color=colors['bar_colors'][0]
    ))
    fig1.add_trace(go.Bar(
        name='Target',
        x=[kpi_name],
        y=[latest_data['Target']],
        marker_color=colors['success']
    ))
    fig1.update_layout(
        title='Current Value vs Target',
        barmode='group',
        height=300,
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font=dict(color=colors['text_color'], size=12),
        title_font=dict(color=colors['text_color'], size=14),
        xaxis=dict(gridcolor=colors['grid_color'], color=colors['text_color']),
        yaxis=dict(gridcolor=colors['grid_color'], color=colors['text_color'])
    )
    
    # Chart 2: Progress over time
    if len(kpi_data) > 1:
        kpi_data['Achievement Date'] = pd.to_datetime(
            kpi_data['Achievement Date'], errors='coerce'
        )
        
        fig2 = px.line(
            kpi_data, x='Achievement Date', y='Current Value',
            title='Progress Over Time',
            markers=True
        )
        fig2.update_traces(
            line_color=colors['bar_colors'][0],
            marker_color=colors['bar_colors'][1]
        )
        fig2.add_hline(
            y=latest_data['Target'], line_dash="dash", 
            line_color=colors['success'], annotation_text="Target"
        )
        fig2.update_layout(
            height=300,
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            font=dict(color=colors['text_color'], size=12),
            title_font=dict(color=colors['text_color'], size=14),
            xaxis=dict(gridcolor=colors['grid_color'], color=colors['text_color']),
            yaxis=dict(gridcolor=colors['grid_color'], color=colors['text_color'])
        )
    else:
        fig2 = None
    
    # Chart 3: Gender breakdown
    male = latest_data.get('Male Count', 0)
    female = latest_data.get('Female Count', 0)
    
    try:
        male = float(male) if male not in ['', None] and pd.notna(male) else 0
        female = float(female) if female not in ['', None] and pd.notna(female) else 0
    except (ValueError, TypeError):
        male = 0
        female = 0
    
    if (male > 0 or female > 0):
        fig3 = px.pie(
            values=[male, female], names=['Male', 'Female'],
            title='Gender Distribution',
            color_discrete_sequence=[colors['bar_colors'][0], colors['bar_colors'][2]]
        )
        fig3.update_layout(
            height=300,
            paper_bgcolor=colors['background'],
            font=dict(color=colors['text_color'], size=12),
            title_font=dict(color=colors['text_color'], size=14)
        )
    else:
        fig3 = None
    
    # Chart 4: Status indicator
    try:
        start_date_str = latest_data.get('Start Date', '')
        end_date_str = latest_data.get('End Date', '')
        
        if start_date_str and pd.notna(start_date_str):
            start_date = pd.to_datetime(start_date_str).date()
        else:
            start_date = date.today()
            
        if end_date_str and pd.notna(end_date_str):
            end_date = pd.to_datetime(end_date_str).date()
        else:
            end_date = date.today()
        
        status = calculate_kpi_status(
            latest_data['Current Value'],
            latest_data['Target'],
            start_date,
            end_date
        )
        
        target_val = float(latest_data['Target']) if latest_data['Target'] else 0
        current_val = float(latest_data['Current Value']) if latest_data['Current Value'] else 0
        progress = (current_val / target_val * 100) if target_val > 0 else 0
        
        fig4 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=progress,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"Progress: {status}", 'font': {'color': colors['text_color']}},
            delta={'reference': 100},
            number={'font': {'color': colors['text_color'], 'size': 30}},
            gauge={
                'axis': {
                    'range': [None, 100],
                    'tickcolor': colors['text_color'],
                    'tickfont': {'color': colors['text_color']}
                },
                'bar': {'color': colors['bar_colors'][0]},
                'steps': [
                    {'range': [0, 70], 'color': colors['grid_color']},
                    {'range': [70, 90], 'color': colors['warning']},
                    {'range': [90, 100], 'color': colors['success']}
                ],
                'threshold': {
                    'line': {'color': colors['danger'], 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ))
        fig4.update_layout(
            height=300,
            paper_bgcolor=colors['background'],
            font=dict(color=colors['text_color'], size=12)
        )
    except Exception as e:
        st.warning(f"Could not create gauge chart: {e}")
        fig4 = None
    
    return fig1, fig2, fig3, fig4

# -------------------------------------------------------------
# Export to PDF
# -------------------------------------------------------------
def fig_to_pdf(fig):
    """Convert plotly figure to PDF bytes"""
    img_bytes = fig.to_image(format="pdf")
    return img_bytes

def create_download_link(fig, filename):
    """Create download link for figure as PDF"""
    pdf_bytes = fig_to_pdf(fig)
    b64 = base64.b64encode(pdf_bytes).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download PDF</a>'
    return href

# -------------------------------------------------------------
# Main App
# -------------------------------------------------------------
def main():
    # Check if Supabase is available
    if not SUPABASE_AVAILABLE:
        st.stop()
    
    st.title("📊 OCTA KPI Tracking System")
    
    st.sidebar.title("💾 Data Storage")
    st.sidebar.info("Data is stored in Supabase Postgres table: `kpis`")
    
    # Show connection status
    try:
        get_supabase_client()
        st.sidebar.success("✅ Connected to Supabase")
    except:
        st.sidebar.error("❌ Not connected to Supabase")
        st.stop()
    
    available_projects = get_available_projects()
    if available_projects:
        st.sidebar.metric("Projects", len(available_projects))
    else:
        st.sidebar.warning("No projects found yet.")
    
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to", 
        ["Add New KPI Data", "Edit Existing Data", "KPI Dashboard"]
    )
    
    # -------------- PAGE 1: Add New KPI Data ------------------
    if page == "Add New KPI Data":
        st.header("➕ Add New KPI Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            project = st.selectbox("Select Project", list(PROJECT_PASSWORDS.keys()))
            
            # Authentication
            if not authenticate_project(project):
                password = st.text_input("Enter Project Password", type="password", key="add_pwd")
                if st.button("Login", key="add_login"):
                    if login_project(project, password):
                        st.success("✅ Authenticated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid password")
                st.stop()
            
            st.success(f"✅ Authenticated for {project}")
            
            kpi = st.text_input("KPI Name")
            work_package = st.text_input("Work Package (WP)")
            target = st.number_input("Target Value", min_value=0.0, step=1.0)
            current_value = st.number_input("Current Achieved Value", min_value=0.0, step=1.0)
        
        with col2:
            achievement_date = st.date_input("Achievement Date", value=date.today())
            
            include_gender = st.checkbox("Include Gender Breakdown")
            male_count = 0
            female_count = 0
            
            if include_gender:
                male_count = st.number_input("Male Count", min_value=0, step=1)
                female_count = st.number_input("Female Count", min_value=0, step=1)
            
            comments = st.text_area("Comments")
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
        
        if st.button("💾 Save KPI Data", type="primary"):
            if kpi and work_package:
                data = {
                    "Project": project,
                    "KPI": kpi,
                    "Work Package": work_package,
                    "Target": target,
                    "Current Value": current_value,
                    "Achievement Date": achievement_date.strftime("%Y-%m-%d"),
                    "Male Count": male_count if include_gender else "",
                    "Female Count": female_count if include_gender else "",
                    "Comments": comments,
                    "Start Date": start_date.strftime("%Y-%m-%d"),
                    "End Date": end_date.strftime("%Y-%m-%d"),
                }
                
                with st.spinner("Saving data..."):
                    if save_kpi_data(project, data):
                        st.success("✅ KPI data saved successfully to database")
                        st.balloons()
                    else:
                        st.error("❌ Failed to save data")
            else:
                st.warning("⚠️ Please fill in all required fields")
    
    # -------------- PAGE 2: Edit Existing Data ----------------
    elif page == "Edit Existing Data":
        st.header("✏️ Edit Existing KPI Data")
        
        available_projects = get_available_projects()
        if not available_projects:
            st.info("No data available. Please add KPI data first.")
            return
        
        project = st.selectbox("Select Project", available_projects)
        
        if not authenticate_project(project):
            password = st.text_input("Enter Project Password", type="password", key="edit_pwd")
            if st.button("Login", key="edit_login"):
                if login_project(project, password):
                    st.success("✅ Authenticated successfully!")
                    st.rerun()
                else:
                    st.error("❌ Invalid password")
            st.stop()
        
        st.success(f"✅ Authenticated for {project}")
        
        df = load_kpi_data(project)
        if df.empty:
            st.info(f"No KPI data available for {project}")
            return
        
        st.subheader("📋 Current KPI Data")
        st.dataframe(df, use_container_width=True)
        
        kpi_to_edit = st.selectbox("Select KPI to Edit", df["KPI"].unique())
        
        kpi_records = df[df["KPI"] == kpi_to_edit].copy()
        
        if len(kpi_records) > 0:
            record_index = st.selectbox(
                "Select Record",
                range(len(kpi_records)),
                format_func=lambda x: f"Record {x+1} - {kpi_records.iloc[x]['Timestamp']}"
            )
            
            selected_record = kpi_records.iloc[record_index]
            row_id = int(selected_record["id"])  # use DB primary key
            
            st.subheader("✏️ Edit Record")
            col1, col2 = st.columns(2)
            
            with col1:
                new_wp = st.text_input("Work Package", value=str(selected_record["Work Package"]))
                new_target = st.number_input(
                    "Target", value=float(selected_record["Target"])
                )
                new_current = st.number_input(
                    "Current Value", value=float(selected_record["Current Value"])
                )
                new_achievement_date = st.date_input(
                    "Achievement Date",
                    value=pd.to_datetime(selected_record["Achievement Date"]).date()
                    if pd.notna(selected_record["Achievement Date"])
                    else date.today(),
                )
            
            with col2:
                male_val = selected_record["Male Count"]
                female_val = selected_record["Female Count"]
                new_male = st.number_input(
                    "Male Count",
                    value=int(male_val) if pd.notna(male_val) and male_val != "" else 0,
                )
                new_female = st.number_input(
                    "Female Count",
                    value=int(female_val)
                    if pd.notna(female_val) and female_val != ""
                    else 0,
                )
                new_comments = st.text_area(
                    "Comments",
                    value=str(selected_record["Comments"])
                    if pd.notna(selected_record["Comments"])
                    else "",
                )
                new_start = st.date_input(
                    "Start Date",
                    value=pd.to_datetime(selected_record["Start Date"]).date()
                    if pd.notna(selected_record["Start Date"])
                    else date.today(),
                )
                new_end = st.date_input(
                    "End Date",
                    value=pd.to_datetime(selected_record["End Date"]).date()
                    if pd.notna(selected_record["End Date"])
                    else date.today(),
                )
            
            if st.button("💾 Update KPI Data", type="primary"):
                updated_data = {
                    "Project": project,
                    "KPI": kpi_to_edit,
                    "Work Package": new_wp,
                    "Target": new_target,
                    "Current Value": new_current,
                    "Achievement Date": new_achievement_date.strftime("%Y-%m-%d"),
                    "Male Count": new_male,
                    "Female Count": new_female,
                    "Comments": new_comments,
                    "Start Date": new_start.strftime("%Y-%m-%d"),
                    "End Date": new_end.strftime("%Y-%m-%d"),
                }
                
                with st.spinner("Updating data..."):
                    if update_kpi_data(project, row_id, updated_data):
                        st.success("✅ KPI data updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update data")
    
    # -------------- PAGE 3: KPI Dashboard ---------------------
    elif page == "KPI Dashboard":
        st.header("📈 KPI Dashboard")
        
        available_projects = get_available_projects()
        if not available_projects:
            st.info("No data available. Please add KPI data first.")
            return
        
        project = st.selectbox("Select Project for Dashboard", available_projects)
        
        df = load_kpi_data(project)
        if df.empty:
            st.info(f"No data available for {project}")
            return
        
        if st.session_state.current_page == "kpi_detail" and st.session_state.selected_kpi:
            st.subheader(f"📊 Detailed View: {st.session_state.selected_kpi}")
            
            if st.button("⬅️ Back to Overview"):
                st.session_state.current_page = "main"
                st.session_state.selected_kpi = None
                st.rerun()
            
            col1, col2 = st.columns([3, 1])
            with col2:
                color_scheme = st.selectbox(
                    "Color Scheme",
                    list(COLOR_SCHEMES.keys()),
                    key="detail_color"
                )
            
            fig1, fig2, fig3, fig4 = create_detailed_kpi_charts(
                df, project, st.session_state.selected_kpi, color_scheme
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if fig1:
                    st.plotly_chart(fig1, use_container_width=True)
                if fig2:
                    st.plotly_chart(fig2, use_container_width=True)
            with col2:
                if fig4:
                    st.plotly_chart(fig4, use_container_width=True)
                if fig3:
                    st.plotly_chart(fig3, use_container_width=True)
            
            st.subheader("📥 Download Charts")
            download_cols = st.columns(4)
            
            if fig1:
                with download_cols[0]:
                    if st.button("Download Chart 1"):
                        pdf_bytes = fig_to_pdf(fig1)
                        st.download_button(
                            "📄 Download PDF",
                            pdf_bytes,
                            f"{st.session_state.selected_kpi}_chart1.pdf",
                            mime="application/pdf",
                        )
            
            if fig2:
                with download_cols[1]:
                    if st.button("Download Chart 2"):
                        pdf_bytes = fig_to_pdf(fig2)
                        st.download_button(
                            "📄 Download PDF",
                            pdf_bytes,
                            f"{st.session_state.selected_kpi}_chart2.pdf",
                            mime="application/pdf",
                        )
            
            st.subheader("📋 KPI Details")
            kpi_detail_data = df[df["KPI"] == st.session_state.selected_kpi]
            st.dataframe(kpi_detail_data, use_container_width=True)
        
        else:
            st.session_state.current_page = "main"
            
            col1, col2, col3 = st.columns(3)
            with col1:
                chart_type = st.selectbox(
                    "Chart Type",
                    ["Bar Chart", "Histogram", "Scatter Plot"]
                )
            with col2:
                color_scheme = st.selectbox(
                    "Color Scheme",
                    list(COLOR_SCHEMES.keys())
                )
            
            overview_fig = create_kpi_overview_chart(df, chart_type, color_scheme, project)
            if overview_fig:
                st.plotly_chart(overview_fig, use_container_width=True)
                
                if st.button("📥 Download Overview Chart as PDF"):
                    pdf_bytes = fig_to_pdf(overview_fig)
                    st.download_button(
                        "📄 Download PDF",
                        pdf_bytes,
                        f"{project}_overview.pdf",
                        mime="application/pdf",
                    )
            
            col1, col2 = st.columns(2)
            with col1:
                status_fig = create_status_pie_chart(df, project, color_scheme)
                if status_fig:
                    st.plotly_chart(status_fig, use_container_width=True)
            with col2:
                st.subheader("📊 KPI Summary")
                if 'Timestamp' in df.columns:
                    df_sorted = df.sort_values('Timestamp')
                else:
                    df_sorted = df.copy()
                summary_data = df_sorted.groupby("KPI").last().reset_index()
                summary_data["Progress %"] = (
                    summary_data["Current Value"] / summary_data["Target"] * 100
                ).round(2)
                summary = summary_data[["KPI", "Target", "Current Value", "Progress %"]]
                st.dataframe(summary, use_container_width=True)
            
            st.subheader("🎯 Click on a KPI for Detailed View")
            project_kpis = df["KPI"].unique()
            cols = st.columns(min(3, len(project_kpis)))
            
            for idx, kpi_name in enumerate(project_kpis):
                with cols[idx % 3]:
                    kpi_data = df[df["KPI"] == kpi_name].iloc[-1]
                    progress = (
                        kpi_data["Current Value"] / kpi_data["Target"] * 100
                        if kpi_data["Target"]
                        else 0
                    )
                    status = calculate_kpi_status(
                        kpi_data["Current Value"],
                        kpi_data["Target"],
                        pd.to_datetime(kpi_data["Start Date"]).date(),
                        pd.to_datetime(kpi_data["End Date"]).date(),
                    )
                    status_color = {
                        "Achieved": "🟢",
                        "On Track": "🔵",
                        "At Risk": "🟡",
                        "Delayed": "🔴",
                        "Not Started": "⚪",
                    }.get(status, "⚪")
                    
                    if st.button(
                        f"{status_color} {kpi_name}\n{progress:.1f}% Complete",
                        key=f"kpi_{idx}",
                        use_container_width=True,
                    ):
                        st.session_state.current_page = "kpi_detail"
                        st.session_state.selected_kpi = kpi_name
                        st.session_state.selected_project = project
                        st.rerun()


if __name__ == "__main__":
    main()
