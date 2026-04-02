"""Main Dashboard UI for CCM1100S Diagnostic Tool"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import deque
import time
from typing import Dict, Any, Optional

from ui.components import DashboardComponents, ChartComponents
from models.sensor_data import SensorData
from models.solenoid_status import SolenoidStatus


class Dashboard:
    """Main dashboard for real-time monitoring"""
    
    def __init__(self, data_callback=None):
        self.components = DashboardComponents()
        self.charts = ChartComponents()
        self.data_callback = data_callback
        self.history = deque(maxlen=100)  # Store last 100 data points
        self.solenoid_history = deque(maxlen=100)
    
    def render_header(self):
        """Render dashboard header"""
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.title("🚜 CCM1100S Real-time Dashboard")
            st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        
        with col2:
            if st.button("🔄 Refresh Now", use_container_width=True):
                st.rerun()
        
        with col3:
            auto_refresh = st.checkbox("Auto Refresh", value=True)
        
        st.markdown("---")
        return auto_refresh
    
    def render_angle_gauges(self, data: SensorData):
        """Render angle gauges for axles"""
        st.subheader("📐 Axle Angles")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self.components.gauge_chart(
                value=data.axle1,
                title="Axle 1",
                min_val=-180,
                max_val=180,
                unit="°"
            )
        
        with col2:
            self.components.gauge_chart(
                value=data.axle5,
                title="Axle 5",
                min_val=-180,
                max_val=180,
                unit="°"
            )
        
        with col3:
            self.components.gauge_chart(
                value=data.axle6,
                title="Axle 6",
                min_val=-180,
                max_val=180,
                unit="°"
            )
    
    def render_currents(self, data: SensorData):
        """Render current measurements"""
        st.subheader("⚡ Control Currents")
        
        col1, col2 = st.columns(2)
        
        with col1:
            self.components.progress_bar(
                value=data.a5Amp,
                min_val=-32000,
                max_val=32000,
                title="A5 Current",
                unit="mA"
            )
        
        with col2:
            self.components.progress_bar(
                value=data.a6Amp,
                min_val=-32000,
                max_val=32000,
                title="A6 Current",
                unit="mA"
            )
    
    def render_errors(self, data: SensorData):
        """Render error angles"""
        st.subheader("⚠️ Error Angles")
        
        col1, col2 = st.columns(2)
        
        with col1:
            self.components.metric_card(
                title="A5 Error",
                value=f"{data.a5Error:.2f}",
                unit="°",
                icon="📐"
            )
        
        with col2:
            self.components.metric_card(
                title="A6 Error",
                value=f"{data.a6Error:.2f}",
                unit="°",
                icon="📐"
            )
    
    def render_solenoids(self, sol_status: SolenoidStatus):
        """Render solenoid status grid"""
        st.subheader("🔧 Solenoid Status")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            self.components.solenoid_indicator(
                name="Load",
                status=sol_status.load_solenoid,
                size="medium"
            )
        
        with col2:
            self.components.solenoid_indicator(
                name="A5 LK1",
                status=sol_status.a5_lock1,
                size="medium"
            )
        
        with col3:
            self.components.solenoid_indicator(
                name="A5 LK2",
                status=sol_status.a5_lock2,
                size="medium"
            )
        
        with col4:
            self.components.solenoid_indicator(
                name="A6 LK1",
                status=sol_status.a6_lock1,
                size="medium"
            )
        
        with col5:
            self.components.solenoid_indicator(
                name="A6 LK2",
                status=sol_status.a6_lock2,
                size="medium"
            )
        
        # Show errors if any
        if sol_status.is_any_error():
            errors = sol_status.get_error_list()
            self.components.alert_card(
                message=f"Solenoid errors detected: {', '.join(errors)}",
                alert_type="warning"
            )
    
    def render_system_info(self, data: SensorData):
        """Render system information"""
        st.subheader("ℹ️ System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            self.components.metric_card(
                title="System Voltage",
                value=f"{data.system_voltage:.1f}",
                unit="V",
                icon="⚡"
            )
        
        with col2:
            self.components.metric_card(
                title="Last Update",
                value=data.time.strftime("%H:%M:%S"),
                unit="",
                icon="🕐"
            )
    
    def render_history_chart(self):
        """Render historical data chart"""
        if len(self.history) > 1:
            st.subheader("📈 Historical Data")
            
            # Prepare data
            df = pd.DataFrame(self.history)
            df['time'] = pd.to_datetime(df['time'])
            
            # Multi-line chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['axle1'],
                mode='lines',
                name='Axle 1',
                line=dict(color='blue')
            ))
            
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['axle5'],
                mode='lines',
                name='Axle 5',
                line=dict(color='green')
            ))
            
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['axle6'],
                mode='lines',
                name='Axle 6',
                line=dict(color='red')
            ))
            
            fig.update_layout(
                title="Axle Angles Over Time",
                xaxis_title="Time",
                yaxis_title="Angle (°)",
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def update_data(self, sensor_data: SensorData, sol_status: SolenoidStatus):
        """Update dashboard with new data"""
        # Store in history
        self.history.append({
            'time': sensor_data.time,
            'axle1': sensor_data.axle1,
            'axle5': sensor_data.axle5,
            'axle6': sensor_data.axle6,
            'a5_error': sensor_data.a5Error,
            'a6_error': sensor_data.a6Error,
            'a5_current': sensor_data.a5Amp,
            'a6_current': sensor_data.a6Amp,
        })
        
        # Render all components
        self.render_angle_gauges(sensor_data)
        self.render_currents(sensor_data)
        self.render_errors(sensor_data)
        self.render_solenoids(sol_status)
        self.render_system_info(sensor_data)
        self.render_history_chart()
    
    def run(self, get_data_func):
        """Run the dashboard"""
        auto_refresh = self.render_header()
        
        # Main dashboard area
        placeholder = st.empty()
        
        while True:
            try:
                # Get latest data
                sensor_data, sol_status = get_data_func()
                
                if sensor_data and sol_status:
                    with placeholder.container():
                        self.update_data(sensor_data, sol_status)
                
                if not auto_refresh:
                    break
                
                time.sleep(1)  # Update every second
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                st.error(f"Error: {e}")
                time.sleep(1)