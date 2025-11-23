# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from io import BytesIO
import base64
import os
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Project KPI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create data directory if it doesn't exist - using repository root
# Get the directory where this script is located (repository root)
SCRIPT_DIR = Path(__file__).parent if '__file__' in globals() else Path.cwd()
DATA_DIR = SCRIPT_DIR / "kpi_data"

# Create directory if it doesn't exist
try:
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    # Create a .gitkeep file to ensure the folder is tracked by git
    gitkeep_file = DATA_DIR / ".gitkeep"
    if not gitkeep_file.exists():
        gitkeep_file.touch()
except Exception as e:
    st.error(f"Cannot create data directory: {e}")
    # Fallback to current working directory
    DATA_DIR = Path.cwd() / "kpi_data"
    DATA_DIR.mkdir(exist_ok=True, parents=True)

# Initialize session state
if 'authenticated_projects' not in st.session_state:
    st.session_state.authenticated_projects = set()
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'main'
if 'selected_kpi' not in st.session_state:
    st.session_state.selected_kpi = None
if 'selected_project' not in st.session_state:
    st.session_state.selected_project = None

# Project passwords (in production, store these securely)
PROJECT_PASSWORDS = {
    "Project Alpha": "alpha123",
    "Project Beta": "beta456",
    "Project Gamma": "gamma789"
}

# Color schemes for charts
COLOR_SCHEMES = {
    "Blue Tones": {
        'primary': '#1f77b4',
        'secondary': '#aec7e8',
        'success': '#2ca02c',
        'warning': '#ff7f0e',
        'danger': '#d62728',
        'background': '#f8f9fa'
    },
    "Ocean": {
        'primary': '#006994',
        'secondary': '#4FC3F7',
        'success': '#00897B',
        'warning': '#FFA726',
        'danger': '#E53935',
        'background': '#E0F7FA'
    },
    "Sunset": {
        'primary': '#FF6B6B',
        'secondary': '#FFB347',
        'success': '#4ECDC4',
        'warning': '#FFD93D',
        'danger': '#C0392B',
        'background': '#FFF5E6'
    },
    "Forest": {
        'primary': '#2E7D32',
        'secondary': '#66BB6A',
        'success': '#1B5E20',
        'warning': '#F57C00',
        'danger': '#C62828',
        'background': '#E8F5E9'
    },
    "Purple Dream": {
        'primary': '#7B1FA2',
        'secondary': '#BA68C8',
        'success': '#00897B',
        'warning': '#FFA726',
        'danger': '#E53935',
        'background': '#F3E5F5'
    },
    "Monochrome": {
        'primary': '#424242',
        'secondary': '#9E9E9E',
        'success': '#616161',
        'warning': '#757575',
        'danger': '#212121',
        'background': '#FAFAFA'
    }
}

# Helper function to get CSV file path for a project
def get_project_csv_path(project_name):
    """Get the CSV file path for a specific project"""
    # Sanitize project name for filename
    safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '_', '-')).strip()
    safe_name = safe_name.replace(' ', '_')
    return DATA_DIR / f"{safe_name}_KPI_data.csv"

# KPI Status calculation
def calculate_kpi_status(current_value, target_value, start_date, end_date):
    """Calculate if KPI is on-track, at-risk, or off-track"""
    if current_value >= target_value:
        return "Achieved"
    
    today = datetime.now().date()
    total_days = (end_date - start_date).days
    elapsed_days = (today - start_date).days
    
    if elapsed_days <= 0:
        return "Not Started"
    
    expected_progress = (elapsed_days / total_days) * target_value if total_days > 0 else 0
    progress_ratio = current_value / expected_progress if expected_progress > 0 else 0
    
    if progress_ratio >= 0.9:
        return "On Track"
    elif progress_ratio >= 0.7:
        return "At Risk"
    else:
        return "Delayed"

# Data Management Functions
def save_kpi_data(project_name, data):
    """Save KPI data to project-specific CSV file"""
    try:
        csv_path = get_project_csv_path(project_name)
        
        # Ensure directory exists
        csv_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Add timestamp
        data['Timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convert data to DataFrame
        new_row = pd.DataFrame([data])
        
        # Check if file exists
        if csv_path.exists():
            # Read existing data
            existing_df = pd.read_csv(csv_path)
            # Append new row
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        else:
            # Create new DataFrame
            updated_df = new_row
        
        # Save to CSV
        updated_df.to_csv(csv_path, index=False)
        
        # Verify the file was saved
        if csv_path.exists():
            st.success(f"✅ File saved at: {csv_path.absolute()}")
            return True
        else:
            st.error("❌ File was not saved properly")
            return False
    except Exception as e:
        st.error(f"Error saving data: {e}")
        import traceback
        st.error(f"Full error: {traceback.format_exc()}")
        return False

def load_kpi_data(project_name):
    """Load KPI data from project-specific CSV file"""
    try:
        csv_path = get_project_csv_path(project_name)
        
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            st.info(f"📂 Loaded data from: {csv_path.absolute()}")
            return df
        else:
            st.warning(f"⚠️ No file found at: {csv_path.absolute()}")
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=[
                'Project', 'KPI', 'Work Package', 'Target', 'Current Value',
                'Achievement Date', 'Male Count', 'Female Count', 'Comments',
                'Start Date', 'End Date', 'Timestamp'
            ])
    except Exception as e:
        st.error(f"Error loading data: {e}")
        import traceback
        st.error(f"Full error: {traceback.format_exc()}")
        return pd.DataFrame()

def load_all_projects_data():
    """Load data from all project CSV files"""
    all_data = []
    
    for csv_file in DATA_DIR.glob("*_KPI_data.csv"):
        try:
            df = pd.read_csv(csv_file)
            all_data.append(df)
        except Exception as e:
            st.warning(f"Could not load {csv_file.name}: {e}")
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

def update_kpi_data(project_name, row_index, updated_data):
    """Update existing KPI data in project-specific CSV"""
    try:
        csv_path = get_project_csv_path(project_name)
        
        if not csv_path.exists():
            st.error("Project data file not found")
            return False
        
        # Read existing data
        df = pd.read_csv(csv_path)
        
        # Update timestamp
        updated_data['Timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update the specific row
        for key, value in updated_data.items():
            if key in df.columns:
                df.at[row_index, key] = value
        
        # Save back to CSV
        df.to_csv(csv_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error updating data: {e}")
        return False

def get_available_projects():
    """Get list of projects that have CSV files"""
    projects = []
    
    # Check if directory exists
    if not DATA_DIR.exists():
        st.warning(f"⚠️ Data directory does not exist: {DATA_DIR.absolute()}")
        return projects
    
    # List all CSV files
    csv_files = list(DATA_DIR.glob("*_KPI_data.csv"))
    
    if not csv_files:
        st.info(f"📂 No CSV files found in: {DATA_DIR.absolute()}")
    
    for csv_file in csv_files:
        try:
            # Extract project name from filename
            project_name = csv_file.stem.replace('_KPI_data', '').replace('_', ' ')
            projects.append(project_name)
        except Exception as e:
            st.warning(f"Could not read project name from {csv_file.name}: {e}")
    
    return projects

# Authentication
def authenticate_project(project_name):
    """Check if user is authenticated for project"""
    return project_name in st.session_state.authenticated_projects

def login_project(project_name, password):
    """Authenticate user for a project"""
    if PROJECT_PASSWORDS.get(project_name) == password:
        st.session_state.authenticated_projects.add(project_name)
        return True
    return False

# Visualization Functions
def create_kpi_overview_chart(df, chart_type, color_scheme_name, project_name):
    """Create overview chart for all KPIs in a project"""
    project_data = df[df['Project'] == project_name].copy()
    
    if project_data.empty:
        return None
    
    # Get latest entry for each KPI
    project_data = project_data.groupby('KPI').last().reset_index()
    
    # Calculate progress percentage
    project_data['Progress %'] = (project_data['Current Value'] / project_data['Target'] * 100).round(2)
    
    # Calculate status
    project_data['Status'] = project_data.apply(
        lambda row: calculate_kpi_status(
            row['Current Value'], 
            row['Target'],
            pd.to_datetime(row['Start Date']).date() if row['Start Date'] else date.today(),
            pd.to_datetime(row['End Date']).date() if row['End Date'] else date.today()
        ), axis=1
    )
    
    # Get color scheme
    colors = COLOR_SCHEMES[color_scheme_name]
    
    if chart_type == "Bar Chart":
        fig = px.bar(project_data, x='KPI', y='Progress %', 
                    color='Status',
                    color_discrete_map={
                        'Achieved': '#00CC66',
                        'On Track': colors['primary'],
                        'At Risk': colors['warning'],
                        'Delayed': colors['danger'],
                        'Not Started': '#CCCCCC'
                    },
                    title=f'KPI Progress Overview - {project_name}',
                    labels={'Progress %': 'Progress (%)'},
                    text='Progress %')
        fig.add_hline(y=100, line_dash="dash", line_color=colors['success'], 
                     annotation_text="Target")
        
    elif chart_type == "Histogram":
        fig = px.histogram(project_data, x='KPI', y='Progress %',
                          color='Status',
                          color_discrete_map={
                              'Achieved': '#00CC66',
                              'On Track': colors['primary'],
                              'At Risk': colors['warning'],
                              'Delayed': colors['danger'],
                              'Not Started': '#CCCCCC'
                          },
                          title=f'KPI Progress Overview - {project_name}',
                          labels={'Progress %': 'Progress (%)'})
        fig.add_hline(y=100, line_dash="dash", line_color=colors['success'])
        
    elif chart_type == "Scatter Plot":
        fig = px.scatter(project_data, x='KPI', y='Progress %',
                        size='Current Value', color='Status',
                        color_discrete_map={
                            'Achieved': '#00CC66',
                            'On Track': colors['primary'],
                            'At Risk': colors['warning'],
                            'Delayed': colors['danger'],
                            'Not Started': '#CCCCCC'
                        },
                        title=f'KPI Progress Overview - {project_name}')
        fig.add_hline(y=100, line_dash="dash", line_color=colors['success'])
    
    fig.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor='white',
        height=500,
        xaxis_tickangle=-45,
        font=dict(color='#2c3e50')
    )
    
    return fig

def create_status_pie_chart(df, project_name, color_scheme_name):
    """Create pie chart showing KPI status distribution"""
    project_data = df[df['Project'] == project_name].copy()
    
    if project_data.empty:
        return None
    
    # Get latest entry for each KPI
    project_data = project_data.groupby('KPI').last().reset_index()
    
    # Calculate status for each KPI
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
    
    fig = px.pie(values=status_counts.values, names=status_counts.index,
                title=f'KPI Status Distribution - {project_name}',
                color=status_counts.index,
                color_discrete_map={
                    'Achieved': '#00CC66',
                    'On Track': colors['primary'],
                    'At Risk': colors['warning'],
                    'Delayed': colors['danger'],
                    'Not Started': '#CCCCCC'
                })
    
    fig.update_layout(
        paper_bgcolor='white',
        height=400,
        font=dict(color='#2c3e50')
    )
    return fig

def create_detailed_kpi_charts(df, project_name, kpi_name, color_scheme_name):
    """Create detailed charts for a specific KPI"""
    kpi_data = df[(df['Project'] == project_name) & (df['KPI'] == kpi_name)].copy()
    
    if kpi_data.empty:
        return None, None, None, None
    
    # Sort by timestamp to show progression
    kpi_data = kpi_data.sort_values('Timestamp')
    colors = COLOR_SCHEMES[color_scheme_name]
    
    # Chart 1: Current vs Target
    latest_data = kpi_data.iloc[-1]
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        name='Current Value',
        x=[kpi_name],
        y=[latest_data['Current Value']],
        marker_color=colors['primary']
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
        paper_bgcolor='white',
        font=dict(color='#2c3e50')
    )
    
    # Chart 2: Progress over time
    if len(kpi_data) > 1:
        kpi_data['Achievement Date'] = pd.to_datetime(kpi_data['Achievement Date'], errors='coerce')
        
        fig2 = px.line(kpi_data, x='Achievement Date', y='Current Value',
                      title='Progress Over Time',
                      markers=True)
        fig2.update_traces(line_color=colors['primary'], marker_color=colors['secondary'])
        fig2.add_hline(y=latest_data['Target'], line_dash="dash", 
                      line_color=colors['success'], annotation_text="Target")
        fig2.update_layout(
            height=300,
            plot_bgcolor=colors['background'],
            paper_bgcolor='white',
            font=dict(color='#2c3e50')
        )
    else:
        fig2 = None
    
    # Chart 3: Gender breakdown (if applicable)
    male = latest_data.get('Male Count', 0)
    female = latest_data.get('Female Count', 0)
    
    if pd.notna(male) and pd.notna(female) and (male > 0 or female > 0):
        fig3 = px.pie(values=[male, female], names=['Male', 'Female'],
                     title='Gender Distribution',
                     color_discrete_sequence=[colors['primary'], colors['warning']])
        fig3.update_layout(
            height=300,
            paper_bgcolor='white',
            font=dict(color='#2c3e50')
        )
    else:
        fig3 = None
    
    # Chart 4: Status indicator
    status = calculate_kpi_status(
        latest_data['Current Value'],
        latest_data['Target'],
        pd.to_datetime(latest_data['Start Date']).date(),
        pd.to_datetime(latest_data['End Date']).date()
    )
    
    progress = (latest_data['Current Value'] / latest_data['Target'] * 100)
    
    fig4 = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=progress,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"Progress: {status}"},
        delta={'reference': 100},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': colors['primary']},
            'steps': [
                {'range': [0, 70], 'color': '#f0f0f0'},
                {'range': [70, 90], 'color': colors['warning'], 'opacity': 0.3},
                {'range': [90, 100], 'color': colors['success'], 'opacity': 0.3}
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
        paper_bgcolor='white',
        font=dict(color='#2c3e50')
    )
    
    return fig1, fig2, fig3, fig4

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

# Main App
def main():
    st.title("📊 OCTA KPI Tracking System")
    
    # Sidebar - Data Storage Info
    st.sidebar.title("💾 Data Storage")
    st.sidebar.info(f"**Data directory:**\n`{DATA_DIR.absolute()}`")
    
    # Check if directory exists and is writable
    if DATA_DIR.exists():
        st.sidebar.success("✅ Directory exists")
        
        # Count files but don't show names (privacy)
        csv_files = list(DATA_DIR.glob("*_KPI_data.csv"))
        if csv_files:
            st.sidebar.success(f"📁 {len(csv_files)} CSV file(s) found")
        else:
            st.sidebar.warning("⚠️ No CSV files found")
    else:
        st.sidebar.error("❌ Directory does not exist")
    
    # Show available projects count only
    available_projects = get_available_projects()
    if available_projects:
        st.sidebar.info(f"📊 {len(available_projects)} project(s) with data")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", 
                           ["Add New KPI Data", "Edit Existing Data", "KPI Dashboard"])
    
    # PAGE 1: Add New KPI Data
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
                    'Project': project,
                    'KPI': kpi,
                    'Work Package': work_package,
                    'Target': target,
                    'Current Value': current_value,
                    'Achievement Date': achievement_date.strftime("%Y-%m-%d"),
                    'Male Count': male_count if include_gender else '',
                    'Female Count': female_count if include_gender else '',
                    'Comments': comments,
                    'Start Date': start_date.strftime("%Y-%m-%d"),
                    'End Date': end_date.strftime("%Y-%m-%d")
                }
                
                if save_kpi_data(project, data):
                    st.success(f"✅ KPI data saved successfully to {get_project_csv_path(project).name}")
                    st.balloons()
                else:
                    st.error("❌ Failed to save data")
            else:
                st.warning("⚠️ Please fill in all required fields")
    
    # PAGE 2: Edit Existing Data
    elif page == "Edit Existing Data":
        st.header("✏️ Edit Existing KPI Data")
        
        # Get projects with data
        available_projects = get_available_projects()
        
        if not available_projects:
            st.info("No data available. Please add KPI data first.")
            return
        
        project = st.selectbox("Select Project", available_projects)
        
        # Authentication
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
        
        # Load project data
        df = load_kpi_data(project)
        
        if df.empty:
            st.info(f"No KPI data available for {project}")
            return
        
        # Show summary table
        st.subheader("📋 Current KPI Data")
        st.dataframe(df, use_container_width=True)
        
        # Select KPI to edit
        kpi_to_edit = st.selectbox("Select KPI to Edit", df['KPI'].unique())
        
        kpi_records = df[df['KPI'] == kpi_to_edit].copy()
        
        if len(kpi_records) > 0:
            record_index = st.selectbox("Select Record", range(len(kpi_records)), 
                                       format_func=lambda x: f"Record {x+1} - {kpi_records.iloc[x]['Timestamp']}")
            
            selected_record = kpi_records.iloc[record_index]
            actual_row_index = kpi_records.index[record_index]
            
            st.subheader("✏️ Edit Record")
            
            col1, col2 = st.columns(2)
            
            with col1:
                new_wp = st.text_input("Work Package", value=str(selected_record['Work Package']))
                new_target = st.number_input("Target", value=float(selected_record['Target']))
                new_current = st.number_input("Current Value", value=float(selected_record['Current Value']))
                new_achievement_date = st.date_input("Achievement Date", 
                    value=pd.to_datetime(selected_record['Achievement Date']).date() if pd.notna(selected_record['Achievement Date']) else date.today())
            
            with col2:
                male_val = selected_record['Male Count']
                female_val = selected_record['Female Count']
                new_male = st.number_input("Male Count", value=int(male_val) if pd.notna(male_val) and male_val != '' else 0)
                new_female = st.number_input("Female Count", value=int(female_val) if pd.notna(female_val) and female_val != '' else 0)
                new_comments = st.text_area("Comments", value=str(selected_record['Comments']) if pd.notna(selected_record['Comments']) else "")
                new_start = st.date_input("Start Date", 
                    value=pd.to_datetime(selected_record['Start Date']).date() if pd.notna(selected_record['Start Date']) else date.today())
                new_end = st.date_input("End Date", 
                    value=pd.to_datetime(selected_record['End Date']).date() if pd.notna(selected_record['End Date']) else date.today())
            
            if st.button("💾 Update KPI Data", type="primary"):
                updated_data = {
                    'Project': project,
                    'KPI': kpi_to_edit,
                    'Work Package': new_wp,
                    'Target': new_target,
                    'Current Value': new_current,
                    'Achievement Date': new_achievement_date.strftime("%Y-%m-%d"),
                    'Male Count': new_male,
                    'Female Count': new_female,
                    'Comments': new_comments,
                    'Start Date': new_start.strftime("%Y-%m-%d"),
                    'End Date': new_end.strftime("%Y-%m-%d")
                }
                
                if update_kpi_data(project, actual_row_index, updated_data):
                    st.success("✅ KPI data updated successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to update data")
    
    # PAGE 3: KPI Dashboard
    elif page == "KPI Dashboard":
        st.header("📈 KPI Dashboard")
        
        # Get projects with data
        available_projects = get_available_projects()
        
        if not available_projects:
            st.info("No data available. Please add KPI data first.")
            return
        
        # Project selection
        project = st.selectbox("Select Project for Dashboard", available_projects)
        
        # Load project data
        df = load_kpi_data(project)
        
        if df.empty:
            st.info(f"No data available for {project}")
            return
        
        # Check if we're viewing a specific KPI detail
        if st.session_state.current_page == 'kpi_detail' and st.session_state.selected_kpi:
            # KPI Detail View
            st.subheader(f"📊 Detailed View: {st.session_state.selected_kpi}")
            
            if st.button("⬅️ Back to Overview"):
                st.session_state.current_page = 'main'
                st.session_state.selected_kpi = None
                st.rerun()
            
            # Color scheme selection
            col1, col2 = st.columns([3, 1])
            with col2:
                color_scheme = st.selectbox("Color Scheme", 
                    list(COLOR_SCHEMES.keys()),
                    key="detail_color")
            
            # Create detailed charts
            fig1, fig2, fig3, fig4 = create_detailed_kpi_charts(
                df, project, st.session_state.selected_kpi, color_scheme
            )
            
            # Display charts
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
            
            # Download buttons
            st.subheader("📥 Download Charts")
            download_cols = st.columns(4)
            
            if fig1:
                with download_cols[0]:
                    if st.button("Download Chart 1"):
                        pdf_bytes = fig_to_pdf(fig1)
                        st.download_button("📄 Download PDF", pdf_bytes, 
                                         f"{st.session_state.selected_kpi}_chart1.pdf",
                                         mime="application/pdf")
            
            if fig2:
                with download_cols[1]:
                    if st.button("Download Chart 2"):
                        pdf_bytes = fig_to_pdf(fig2)
                        st.download_button("📄 Download PDF", pdf_bytes,
                                         f"{st.session_state.selected_kpi}_chart2.pdf",
                                         mime="application/pdf")
            
            # Show KPI details table
            st.subheader("📋 KPI Details")
            kpi_detail_data = df[df['KPI'] == st.session_state.selected_kpi]
            st.dataframe(kpi_detail_data, use_container_width=True)
            
        else:
            # Overview Dashboard
            st.session_state.current_page = 'main'
            
            # Chart customization options
            col1, col2, col3 = st.columns(3)
            
            with col1:
                chart_type = st.selectbox("Chart Type", 
                    ["Bar Chart", "Histogram", "Scatter Plot"])
            
            with col2:
                color_scheme = st.selectbox("Color Scheme", 
                    list(COLOR_SCHEMES.keys()))
            
            # Main overview chart
            overview_fig = create_kpi_overview_chart(df, chart_type, color_scheme, project)
            
            if overview_fig:
                st.plotly_chart(overview_fig, use_container_width=True)
                
                # Download button for overview
                if st.button("📥 Download Overview Chart as PDF"):
                    pdf_bytes = fig_to_pdf(overview_fig)
                    st.download_button("📄 Download PDF", pdf_bytes,
                                     f"{project}_overview.pdf",
                                     mime="application/pdf")
            
            # Status distribution pie chart
            col1, col2 = st.columns(2)
            
            with col1:
                status_fig = create_status_pie_chart(df, project, color_scheme)
                if status_fig:
                    st.plotly_chart(status_fig, use_container_width=True)
            
            with col2:
                # KPI Summary Table
                st.subheader("📊 KPI Summary")
                
                # Get latest entry for each KPI
                summary_data = df.groupby('KPI').last().reset_index()
                summary_data['Progress %'] = (summary_data['Current Value'] / summary_data['Target'] * 100).round(2)
                summary = summary_data[['KPI', 'Target', 'Current Value', 'Progress %']]
                
                st.dataframe(summary, use_container_width=True)
            
            # Clickable KPI cards
            st.subheader("🎯 Click on a KPI for Detailed View")
            
            project_kpis = df['KPI'].unique()
            
            cols = st.columns(min(3, len(project_kpis)))
            
            for idx, kpi in enumerate(project_kpis):
                with cols[idx % 3]:
                    kpi_data = df[df['KPI'] == kpi].iloc[-1]
                    progress = (kpi_data['Current Value'] / kpi_data['Target'] * 100)
                    
                    status = calculate_kpi_status(
                        kpi_data['Current Value'],
                        kpi_data['Target'],
                        pd.to_datetime(kpi_data['Start Date']).date(),
                        pd.to_datetime(kpi_data['End Date']).date()
                    )
                    
                    status_color = {
                        'Achieved': '🟢',
                        'On Track': '🔵',
                        'At Risk': '🟡',
                        'Delayed': '🔴',
                        'Not Started': '⚪'
                    }.get(status, '⚪')
                    
                    if st.button(f"{status_color} {kpi}\n{progress:.1f}% Complete", 
                               key=f"kpi_{idx}", use_container_width=True):
                        st.session_state.current_page = 'kpi_detail'
                        st.session_state.selected_kpi = kpi
                        st.session_state.selected_project = project
                        st.rerun()

if __name__ == "__main__":
    main()
