"""Streamlit Web UI for CCM1100S Diagnostic Tool"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import threading

from core.can_interface import CANInterface
from core.uds_client import UDSClient
from core.j1939_parser import J1939Parser
from models.sensor_data import SensorData, SolenoidStatus, ECUInfo
from models.dtc_codes import DTCHistory
from config.did_config import UDS_DIDS, J1939_MAPPING


class DiagnosticApp:
    """Main Streamlit Application"""

    def __init__(self):
        self.can = CANInterface()
        self.uds = UDSClient()
        self.j1939 = J1939Parser()
        self.dtc_history = DTCHistory()
        self.realtime_data = {}
        self.realtime_running = False

    def setup_page(self):
        """Configure Streamlit page"""
        st.set_page_config(
            page_title="CCM1100S Diagnostic Tool",
            page_icon="🚜",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        st.title("🚜 CCM1100S Diagnostic Tool")
        st.markdown("---")

    def sidebar(self):
        """Create sidebar with controls"""
        with st.sidebar:
            st.header("📡 Connection")

            if st.button("🔄 Test Connection", use_container_width=True):
                with st.spinner("Testing..."):
                    success, result, _ = self.uds.query_single_frame(0x220F)
                    if success:
                        st.success(f"✅ Connected - {result}")
                    else:
                        st.error(f"❌ {result}")

            st.header("📊 Options")
            auto_refresh = st.checkbox(
                "Auto Refresh Real-time Data", value=True)
            refresh_rate = st.slider("Refresh Rate (Hz)", 1, 10, 5)

            st.header("ℹ️ Info")
            st.info(
                "**Supported Features:**\n"
                "- Real-time sensor monitoring\n"
                "- ECU configuration read\n"
                "- Solenoid status\n"
                "- DTC error codes"
            )

            return auto_refresh, refresh_rate

    def realtime_tab(self):
        """Real-time monitoring tab"""
        st.header("📊 Real-time Sensor Data")

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            axle1 = self.realtime_data.get('Axle1 Angle', 0)
            st.metric("Axle 1 Angle", f"{axle1:.1f}°")

        with col2:
            axle5 = self.realtime_data.get('Axle5 Angle', 0)
            st.metric("Axle 5 Angle", f"{axle5:.1f}°")

        with col3:
            axle6 = self.realtime_data.get('Axle6 Angle', 0)
            st.metric("Axle 6 Angle", f"{axle6:.1f}°")

        with col4:
            voltage = self.realtime_data.get('System Voltage', 0)
            st.metric("System Voltage", f"{voltage:.1f}V")

        # Currents row
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Control Currents")
            a5_curr = self.realtime_data.get('A5 Control Current', 0)
            a6_curr = self.realtime_data.get('A6 Control Current', 0)
            st.metric("A5 Current", f"{a5_curr:.0f} mA")
            st.metric("A6 Current", f"{a6_curr:.0f} mA")

        with col2:
            st.subheader("Error Angles")
            a5_err = self.realtime_data.get('A5 Error Angle', 0)
            a6_err = self.realtime_data.get('A6 Error Angle', 0)
            st.metric("A5 Error", f"{a5_err:.2f}°")
            st.metric("A6 Error", f"{a6_err:.2f}°")

        # Solenoid status
        st.subheader("🔧 Solenoid Status")
        col1, col2, col3, col4, col5 = st.columns(5)

        sol_states = {
            'Load': self.realtime_data.get('Load Solenoid', 'OFF'),
            'A5 LK1': self.realtime_data.get('A5 Lock Valve 1', 'OFF'),
            'A5 LK2': self.realtime_data.get('A5 Lock Valve 2', 'OFF'),
            'A6 LK1': self.realtime_data.get('A6 Lock Valve 1', 'OFF'),
            'A6 LK2': self.realtime_data.get('A6 Lock Valve 2', 'OFF'),
        }

        for i, (name, state) in enumerate(sol_states.items()):
            cols = [col1, col2, col3, col4, col5]
            with cols[i]:
                color = "🟢" if state == "ON" else "🔴" if state == "ERROR" else "⚪"
                st.metric(name, f"{color} {state}")

    def ecu_info_tab(self):
        """ECU Information tab"""
        st.header("📋 ECU Configuration")

        if st.button("📖 Read ECU Information", use_container_width=True):
            with st.spinner("Reading ECU data..."):
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Version Information")

                    # Firmware
                    success, result, _ = self.uds.query_multi_frame(0x220D)
                    if success:
                        st.metric("Firmware Version", result)

                    # SW Version
                    success, result, _ = self.uds.query_single_frame(0x220E)
                    if success:
                        st.metric("SW Version", result)

                    # Serial Number
                    success, result, _ = self.uds.query_single_frame(0xF18C)
                    if success:
                        st.metric("Serial Number", result)

                    # Product Code
                    success, result, _ = self.uds.query_single_frame(0xF192)
                    if success:
                        st.metric("Product Code", result)

                with col2:
                    st.subheader("Identification Numbers")

                    # HW Number
                    success, result, _ = self.uds.query_multi_frame(0xF191)
                    if success:
                        st.metric("HW Number", result)

                    # PN Number
                    success, result, _ = self.uds.query_multi_frame(0xF187)
                    if success:
                        st.metric("PN Number", result)

                    # VIN
                    success, result, _ = self.uds.query_multi_frame(0xF190)
                    if success:
                        st.metric("VIN", result)

                    # VCN
                    success, result, _ = self.uds.query_multi_frame(0xF1A0)
                    if success:
                        st.metric("VCN", result)

    def parameters_tab(self):
        """UDS Parameters tab"""
        st.header("🔧 UDS Readable Parameters")

        # Create two columns for grid layout
        cols = st.columns(3)

        did_list = list(UDS_DIDS.keys())
        for idx, did in enumerate(did_list):
            info = UDS_DIDS[did]
            col = cols[idx % 3]

            with col:
                with st.expander(f"{info['name']} (0x{did:04X})"):
                    if st.button(f"Read", key=f"btn_{did}"):
                        with st.spinner(f"Reading {info['name']}..."):
                            if info.get('multiframe', False):
                                success, result, _ = self.uds.query_multi_frame(
                                    did)
                            else:
                                success, result, _ = self.uds.query_single_frame(
                                    did)

                            if success:
                                st.success(f"✅ {result}")
                            else:
                                st.error(f"❌ {result}")

    def dtc_tab(self):
        """DTC Error Codes tab"""
        st.header("⚠️ Diagnostic Trouble Codes")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Active DTCs")
            if self.dtc_history.get_active():
                for dtc in self.dtc_history.get_active():
                    st.warning(
                        f"**{dtc.description}**\n\nCode: {dtc.to_dict()['code']}")
            else:
                st.success("✅ No active DTCs")

        with col2:
            st.subheader("Actions")
            if st.button("📋 Read DTCs", use_container_width=True):
                st.info("DTC reading via UDS not implemented in this version")
            if st.button("🗑️ Clear DTCs", use_container_width=True):
                self.dtc_history.clear_all()
                st.success("DTCs cleared")

        # Show DTC history
        with st.expander("📜 DTC History"):
            if self.dtc_history.get_history():
                dtc_data = [dtc.to_dict()
                            for dtc in self.dtc_history.get_history()]
                st.dataframe(pd.DataFrame(dtc_data))
            else:
                st.info("No DTC history")

    def realtime_update_loop(self, stop_event):
        """Background thread for real-time updates"""
        while not stop_event.is_set():
            try:
                data = self.j1939.get_realtime_data(0.5)

                # Also read voltage periodically
                success, voltage, _ = self.uds.query_single_frame(0x220F)
                if success:
                    data['System Voltage'] = float(voltage.split()[0])

                self.realtime_data.update(data)
                time.sleep(0.2)
            except Exception:
                pass

    def run(self):
        """Main application entry point"""
        self.setup_page()
        auto_refresh, refresh_rate = self.sidebar()

        # Create tabs
        tabs = st.tabs([
            "📊 Real-time",
            "📋 ECU Info",
            "🔧 Parameters",
            "⚠️ DTC Codes"
        ])

        # Start real-time update thread
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self.realtime_update_loop, args=(stop_event,))

        if auto_refresh:
            thread.start()

        with tabs[0]:
            if auto_refresh:
                placeholder = st.empty()
                while auto_refresh and not stop_event.is_set():
                    with placeholder.container():
                        self.realtime_tab()
                    time.sleep(1 / refresh_rate)
            else:
                if st.button("🔄 Refresh Data"):
                    self.realtime_data = self.j1939.get_realtime_data(1.0)
                self.realtime_tab()

        with tabs[1]:
            self.ecu_info_tab()

        with tabs[2]:
            self.parameters_tab()

        with tabs[3]:
            self.dtc_tab()

        # Cleanup on exit
        if auto_refresh:
            stop_event.set()
            thread.join(timeout=1)


def main():
    app = DiagnosticApp()
    app.run()


if __name__ == "__main__":
    main()
