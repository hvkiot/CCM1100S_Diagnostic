"""Reusable UI Components for Streamlit Dashboard"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, Optional, List


class DashboardComponents:
    """Reusable UI components"""
    
    @staticmethod
    def metric_card(title: str, value: str, unit: str = "", 
                    delta: Optional[float] = None, 
                    icon: str = "📊") -> None:
        """Display a metric card"""
        col1, col2 = st.columns([1, 5])
        with col1:
            st.markdown(f"<h1>{icon}</h1>", unsafe_allow_html=True)
        with col2:
            if delta:
                st.metric(title, f"{value} {unit}", delta=f"{delta:.1f} {unit}")
            else:
                st.metric(title, f"{value} {unit}")
    
    @staticmethod
    def gauge_chart(value: float, title: str, min_val: float = -180, 
                    max_val: float = 180, unit: str = "°") -> None:
        """Create a gauge chart for angle display"""
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title},
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [min_val, max_val]},
                "bar": {"color": "darkblue"},
                "steps": [
                    {"range": [min_val, -90], "color": "lightgray"},
                    {"range": [-90, 90], "color": "gray"},
                    {"range": [90, max_val], "color": "lightgray"}
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": value
                }
            }
        ))
        fig.update_layout(height=250)
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def solenoid_indicator(name: str, status: str, size: str = "medium") -> None:
        """Display a solenoid status indicator"""
        colors = {
            "ON": "🔵",
            "OFF": "⚪",
            "ERROR": "🔴",
            "NOT AVAILABLE": "⚫",
            "UNKNOWN": "❓"
        }
        
        size_styles = {
            "small": "20px",
            "medium": "30px",
            "large": "40px"
        }
        
        icon = colors.get(status, "⚪")
        font_size = size_styles.get(size, "30px")
        
        st.markdown(
            f"""
            <div style="text-align: center; padding: 10px; border: 1px solid #ddd; border-radius: 10px;">
                <div style="font-size: {font_size};">{icon}</div>
                <div style="font-size: 12px; margin-top: 5px;">{name}</div>
                <div style="font-size: 10px; color: {'green' if status == 'ON' else 'red' if status == 'ERROR' else 'gray'};">{status}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    @staticmethod
    def can_status_indicator(is_connected: bool, packets_received: int = 0) -> None:
        """Display CAN bus status indicator"""
        if is_connected:
            st.success(f"✅ CAN Bus Connected | Packets: {packets_received}")
        else:
            st.error("❌ CAN Bus Disconnected")
    
    @staticmethod
    def error_badge(error_count: int) -> None:
        """Display error count badge"""
        if error_count > 0:
            st.warning(f"⚠️ Active Errors: {error_count}")
        else:
            st.info("✅ No Active Errors")
    
    @staticmethod
    def progress_bar(value: float, min_val: float, max_val: float, 
                     title: str, unit: str = "") -> None:
        """Display a progress bar for values"""
        percentage = ((value - min_val) / (max_val - min_val)) * 100
        percentage = max(0, min(100, percentage))
        
        st.markdown(f"**{title}**")
        st.progress(percentage / 100)
        st.caption(f"{value:.1f} {unit} ({percentage:.0f}%)")
    
    @staticmethod
    def status_table(data: Dict[str, Any], title: str = "Status") -> None:
        """Display a status table"""
        df = pd.DataFrame([data]).T
        df.columns = ["Value"]
        st.subheader(title)
        st.dataframe(df, use_container_width=True)
    
    @staticmethod
    def alert_card(message: str, alert_type: str = "info") -> None:
        """Display an alert card"""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }
        
        colors = {
            "info": "#2196F3",
            "warning": "#FF9800",
            "error": "#F44336",
            "success": "#4CAF50"
        }
        
        st.markdown(
            f"""
            <div style="background-color: {colors.get(alert_type, '#2196F3')}20; 
                        padding: 15px; 
                        border-radius: 10px; 
                        border-left: 4px solid {colors.get(alert_type, '#2196F3')};
                        margin: 10px 0;">
                <span style="font-size: 20px;">{icons.get(alert_type, 'ℹ️')}</span>
                <span style="margin-left: 10px;">{message}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    @staticmethod
    def parameter_card(name: str, value: str, description: str = "") -> None:
        """Display a parameter card"""
        with st.expander(f"📌 {name}"):
            st.markdown(f"**Value:** `{value}`")
            if description:
                st.caption(description)
    
    @staticmethod
    def dtc_table(dtc_list: List[Dict]) -> None:
        """Display DTC codes in a table"""
        if dtc_list:
            df = pd.DataFrame(dtc_list)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No DTC codes found")


class ChartComponents:
    """Chart components for data visualization"""
    
    @staticmethod
    def line_chart(data: pd.DataFrame, x_col: str, y_col: str, 
                   title: str, y_label: str = "") -> None:
        """Create a line chart"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data[x_col],
            y=data[y_col],
            mode='lines+markers',
            name=title
        ))
        fig.update_layout(
            title=title,
            xaxis_title=x_col,
            yaxis_title=y_label or y_col,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def bar_chart(data: Dict[str, float], title: str) -> None:
        """Create a bar chart"""
        fig = go.Figure(data=[
            go.Bar(x=list(data.keys()), y=list(data.values()))
        ])
        fig.update_layout(title=title)
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def multi_gauge(values: Dict[str, float], title: str) -> None:
        """Create multiple gauge charts"""
        cols = st.columns(len(values))
        for idx, (name, value) in enumerate(values.items()):
            with cols[idx]:
                DashboardComponents.gauge_chart(value, name)